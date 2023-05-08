# Copyright (c) farm-ng, inc. Amiga Development Kit License, Version 0.1
import argparse
import asyncio
import os
from typing import List
from typing import Optional
# import farm_ng libs
import grpc
from farm_ng.canbus import canbus_pb2
from farm_ng.canbus.canbus_client import CanbusClient
from farm_ng.canbus.packet import AmigaControlState
from farm_ng.canbus.packet import AmigaTpdo1
from farm_ng.canbus.packet import make_amiga_rpdo1_proto
from farm_ng.canbus.packet import parse_amiga_tpdo1_proto
from farm_ng.oak import oak_pb2
from farm_ng.oak.camera_client import OakCameraClient
from farm_ng.service import service_pb2
from farm_ng.service.service_client import ClientConfig

# import internal libs
from robo_spray import ops
from robo_spray.gps import GPS
from robo_spray.map import create_marker
from robo_spray.can import make_amiga_spray1_proto



# Must come before kivy imports
os.environ["KIVY_NO_ARGS"] = "1"

# gui configs must go before any other kivy import
from kivy.config import Config  # noreorder # noqa: E402

Config.set("graphics", "resizable", False)
Config.set("graphics", "width", "1280")
Config.set("graphics", "height", "800")
Config.set("graphics", "fullscreen", "false")
Config.set("input", "mouse", "mouse,disable_on_activity")
Config.set("kivy", "keyboard_mode", "systemanddock")

# kivy imports
from kivy.app import App  # noqa: E402
from kivy.lang.builder import Builder  # noqa: E402
from kivy_garden.mapview.geojson import GeoJsonMapLayer
from kivy_garden.mapview import MapMarker, MapView

class SprayApp(App):
    """Base class for the main Kivy app."""

    def __init__(self,address:str, canbus_port: int) -> None:
        super().__init__()

        self.address = address
        self.canbus_port: int = canbus_port

        self.async_tasks: List[asyncio.Task] = []

        self.gps = GPS()

        self.geojson_layer = GeoJsonMapLayer(source="/data/home/amiga/apps/robo-spray/src/assets/campus_food.json")        
        
        self.activate = 0

    def build(self):
        return Builder.load_file("res/main.kv")

    def on_spray_btn(self) -> None:
        """Activates the spray by manually."""
        # Send Can signal
        self.activate = 1
        print("on")

    def off_spray_btn(self) -> None:
        """Deactivates the spray by manually."""
        # Send Can signal
        self.activate = 0
        print("off")


    def on_exit_btn(self) -> None:
        """Kills the running kivy application."""
        self.gps.stop()
        App.get_running_app().stop()

    async def app_func(self):
        async def run_wrapper() -> None:
            # we don't actually need to set asyncio as the lib because it is
            # the default, but it doesn't hurt to be explicit
            await self.async_run(async_lib="asyncio")
            for task in self.async_tasks:
                task.cancel()


        # Placeholder task
        self.async_tasks.append(asyncio.ensure_future(self.template_function()))
        
        # configure the canbus client
        canbus_config: ClientConfig = ClientConfig(
            address=self.address, port=self.canbus_port
        )
        canbus_client: CanbusClient = CanbusClient(canbus_config)


        # Canbus task(s)
        self.async_tasks.append(
            asyncio.ensure_future(self.stream_canbus(canbus_client))
        )
        self.async_tasks.append(
            asyncio.ensure_future(self.send_can_msgs(canbus_client))
        )

        self.gps.start()

        return await asyncio.gather(run_wrapper(), *self.async_tasks)

    async def template_function(self) -> None:
        """Placeholder forever loop."""
        while self.root is None:
            await asyncio.sleep(0.01)

        self.mapview:MapMarker = self.root.ids["mapview"]
        self.mapview.add_layer(self.geojson_layer)
        
        # self.geojson_layer.traverse_feature(create_marker)
        
        while True:
            await asyncio.sleep(1.0)
            if 0:
                # increment the counter using internal libs and update the gui
                self.counter = ops.add(self.counter, 1)
                self.root.ids.counter_label.text = (
                    f"{'Tic' if self.counter % 2 == 0 else 'Tac'}: {self.counter}"
                )

            # Get GPS data
            geo = self.gps.get_gps_data()
            if geo:
                # Update Map
                self.mapview.center_on(geo.lat, geo.lon)
                mapview_marker = self.root.ids["mapview_marker"]

                # Moving test
                mapview_marker.lat = geo.lat
                mapview_marker.lon = geo.lon


    async def stream_canbus(self, client: CanbusClient) -> None:
        """This task:

        - listens to the canbus client's stream
        - filters for AmigaTpdo1 messages
        - extracts useful values from AmigaTpdo1 messages
        """
        while self.root is None:
            await asyncio.sleep(0.01)

        response_stream = None

        while True:
            # check the state of the service
            state = await client.get_state()

            if state.value not in [
                service_pb2.ServiceState.IDLE,
                service_pb2.ServiceState.RUNNING,
            ]:
                if response_stream is not None:
                    response_stream.cancel()
                    response_stream = None

                print("Canbus service is not streaming or ready to stream")
                await asyncio.sleep(0.1)
                continue

            if (
                response_stream is None
                and state.value != service_pb2.ServiceState.UNAVAILABLE
            ):
                # get the streaming object
                response_stream = client.stream()

            try:
                # try/except so app doesn't crash on killed service
                response: canbus_pb2.StreamCanbusReply = await response_stream.read()
                assert response and response != grpc.aio.EOF, "End of stream"
            except Exception as e:
                print(e)
                response_stream.cancel()
                response_stream = None
                continue

            for proto in response.messages.messages:
                amiga_tpdo1: Optional[AmigaTpdo1] = parse_amiga_tpdo1_proto(proto)
                if amiga_tpdo1:
                    # Store the value for possible other uses
                    self.amiga_tpdo1 = amiga_tpdo1

                    # Update the Label values as they are received
                    self.amiga_state = AmigaControlState(amiga_tpdo1.state).name[6:]
                    self.amiga_speed = str(amiga_tpdo1.meas_speed)
                    self.amiga_rate = str(amiga_tpdo1.meas_ang_rate)


    async def send_can_msgs(self, client: CanbusClient) -> None:
        """This task ensures the canbus client sendCanbusMessage method has the pose_generator it will use to send
        messages on the CAN bus to control the Amiga robot."""
        while self.root is None:
            await asyncio.sleep(0.01)

        response_stream = None
        while True:
            # check the state of the service
            state = await client.get_state()

            # Wait for a running CAN bus service
            if state.value != service_pb2.ServiceState.RUNNING:
                # Cancel existing stream, if it exists
                if response_stream is not None:
                    response_stream.cancel()
                    response_stream = None
                print("Waiting for running canbus service...")
                await asyncio.sleep(0.1)
                continue

            if response_stream is None:
                print("Start sending CAN messages")
                response_stream = client.stub.sendCanbusMessage(self.spray_generator())

            try:
                async for response in response_stream:
                    # Sit in this loop and wait until canbus service reports back it is not sending
                    assert response.success
            except Exception as e:
                print(e)
                response_stream.cancel()
                response_stream = None
                continue

            await asyncio.sleep(0.1)

    async def spray_generator(self, period: float = 0.02):
        """The spray generator yields an AmigaSpray1 (spray control command) for the canbus client to send on the bus
        at the specified period (recommended 50hz) based on the onscreen spray button."""
        while self.root is None:
            await asyncio.sleep(0.01)

        #joystick: VirtualJoystickWidget = self.root.ids["joystick"]
        while True:
            # print(f"self.activate:{self.activate}")
            msg: canbus_pb2.RawCanbusMessage = make_amiga_spray1_proto(
                state_req=AmigaControlState.STATE_AUTO_ACTIVE,
                activate=self.activate,
            )
            yield canbus_pb2.SendCanbusMessageRequest(message=msg)
            await asyncio.sleep(period)

            
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="template-app")

    # Add additional command line arguments here
    parser.add_argument(
        "--address", 
        type=str,
        default="localhost",
        help="The server address"
    )

    parser.add_argument(
        "--canbus-port",
        type=int,
        required=False,
        default=50060,
        help="The grpc port where the canbus service is running.",
    )

    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(SprayApp(
                address=args.address, canbus_port=args.canbus_port
            ).app_func()
        )
    except asyncio.CancelledError:
        pass
    loop.close()
