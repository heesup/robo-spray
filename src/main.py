# Copyright (c) farm-ng, inc. Amiga Development Kit License, Version 0.1
import argparse
import asyncio
import os
from typing import List
from typing import Optional
import json

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

# Must come before kivy imports
os.environ["KIVY_NO_ARGS"] = "1"

# gui configs "must" go before any other kivy import. It includes other import from libs
from kivy.config import Config  # noreorder # noqa: E402

Config.set("graphics", "resizable", False)
Config.set("graphics", "width", "1280")
Config.set("graphics", "height", "800")
Config.set("graphics", "fullscreen", "false")
Config.set("input", "mouse", "mouse,disable_on_activity, disable_multitouch")
Config.set("kivy", "keyboard_mode", "systemanddock")

# kivy imports
from kivy.app import App  # noqa: E402
from kivy.lang.builder import Builder  # noqa: E402
from kivy_garden.mapview.geojson import GeoJsonMapLayer
from kivy_garden.mapview import MapMarker, MapView
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.graphics import Color, Ellipse


# import internal libs
from robo_spray.gps import GPS
from robo_spray.can import make_amiga_spray1_proto
from robo_spray.map import draw_markers,draw_tracks
from robo_spray.auto_spray import build_kd_tree, match_gps_position, calculate_utm_distance


import os
this_path = os.path.dirname(__file__)

class SprayApp(App):
    """Base class for the main Kivy app."""

    def __init__(self,address:str, canbus_port: int) -> None:
        super().__init__()

        self.address = address
        self.canbus_port: int = canbus_port

        self.async_tasks: List[asyncio.Task] = []

        self.gps = GPS()
        self.geo:any = None

        self.spray_activate = 0
        self.auto_spray_activate:bool = False

        self.auto_spray_radious:float = 1.0

        with open(os.path.join(this_path,"assets/spray_position_points.json")) as file:
            self.spary_pos = json.load(file)

        with open(os.path.join(this_path,"assets/spray_position_all.json")) as file:
            self.spary_track = json.load(file)
                

        
    def build(self):
        return Builder.load_file("res/main.kv")

    def on_spray_btn(self) -> None:
        """Activates the spray by manually."""
        # Send Can signal
        self.spray_activate = 1
        print("on")

    def off_spray_btn(self) -> None:
        """Deactivates the spray by manually."""
        # Send Can signal
        self.spray_activate = 0
        print("off")

    def drwaw_circle(self) -> None:
        # with self.mapview.canvas:
        #     # Set the fill color
        #     Color(1, 0, 0, 0.5)
        #     # Draw a circle using Ellipse
        #     radius = 100
        #     self.ellipse = Ellipse(pos=(self.mapview.center_x-radius/2, self.mapview.center_y-radius/2),
        #             size=(radius, radius))
        pass
            
    def clear_circle(self) -> None:
        with self.mapview.canvas:
            self.mapview.canvas.remove(self.ellipse)
            self.ellipse = None

    def auto_spray_btn(self) -> None:
        """Activates the auto spray """
        btn:Button = self.root.ids["auto_spary_btn_layout"]
        print(btn.state)
        if self.auto_spray_activate == False:
            print("Auto spray On")
            self.auto_spray_activate = True
            # self.drwaw_circle()
        else:
            print("Auto spray Off")
            self.auto_spray_activate = False

            spary_btn:Button = self.root.ids["spary_btn_layout"]
            spary_btn.state = "normal"
            self.spray_activate = 0
            # self.clear_circle()
            
        

        


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
        self.async_tasks.append(asyncio.ensure_future(self.update_gps_function()))
        self.async_tasks.append(asyncio.ensure_future(self.display_map_function()))
        self.async_tasks.append(asyncio.ensure_future(self.auto_spray()))

        
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

    async def update_gps_function(self) -> None:
        """Placeholder forever loop."""
        while self.root is None:
            await asyncio.sleep(0.01)

        while True:
            # Get GPS data
            self.geo = self.gps.get_gps_data()
            await asyncio.sleep(0.1)

    async def display_map_function(self) -> None:
        """Placeholder forever loop."""
        while self.root is None:
            await asyncio.sleep(0.01)

        self.mapview:MapView = self.root.ids["mapview"]

        # draw_tracks(mapview=self.mapview,data=self.spary_track)
        draw_markers(mapview=self.mapview,data=self.spary_pos)


        while True:
            
            if self.geo:
                # Update Map
                self.mapview.center_on(self.geo.lat, self.geo.lon)
                mapview_marker = self.root.ids["mapview_marker"]

                # Moving test
                mapview_marker.lat = self.geo.lat
                mapview_marker.lon = self.geo.lon




            await asyncio.sleep(0.5)

    async def auto_spray(self) -> None:
        """Placeholder forever loop."""
        while self.root is None:
            await asyncio.sleep(0.01)

        while True:
            
            while self.auto_spray_activate:
                gps_position = (self.geo.lon,self.geo.lat)

                # Build KD-Tree
                kdtree = build_kd_tree(self.spary_pos)

                # Match GPS position to GeoJSON feature
                matched_feature = match_gps_position(gps_position, kdtree, self.spary_pos)

                # Access matched feature properties
                name = matched_feature['properties']['name']
                # You can access other properties based on your GeoJSON structure

                print(f'Matched feature name: {name}')

                # Calc dist
                dist = calculate_utm_distance(self.geo.lat,self.geo.lon,
                                       matched_feature['geometry']['coordinates'][1],matched_feature['geometry']['coordinates'][0])
                
                btn:Button = self.root.ids["spary_btn_layout"]
                if dist < self.auto_spray_radious:
                    print("Spray!!")
                    btn.state = "down"
                    self.spray_activate = 1
                else:
                    btn.state = "normal"
                    self.spray_activate = 0
                    pass
                
                await asyncio.sleep(0.1)

            await asyncio.sleep(0.1)


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

                # print("Canbus service is not streaming or ready to stream")
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
                # print("Waiting for running canbus service...")
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
            print(f"self.activate:{self.spray_activate}")
            msg: canbus_pb2.RawCanbusMessage = make_amiga_spray1_proto(
                state_req=AmigaControlState.STATE_AUTO_ACTIVE,
                activate=self.spray_activate,
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
