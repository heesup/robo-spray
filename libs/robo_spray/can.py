
import time
from struct import pack,unpack

from farm_ng.canbus.packet import AmigaControlState, Packet, DASHBOARD_NODE_ID
from farm_ng.canbus import canbus_pb2

from farm_ng.canbus.packet import AmigaRpdo1 # reference

#@TODO: Fix and add more decsription

class AmigaSpray1(Packet):
    """State, speed, and angular rate command (request) sent to the Amiga vehicle control unit (VCU).

    New in fw v0.1.9 / farm-ng-amiga v0.0.7: Add pto & hbridge control. Message data is now 8 bytes (was 5).
    """

    cob_id = 0x300

    def __init__(
        self,
        state_req: AmigaControlState = AmigaControlState.STATE_ESTOPPED,
        activate: int = 0,
    ):
        self.format = "<Bh" # little-endian [unsigned char, short]
        self.legacy_format = "<Bhh"

        self.state_req = state_req
        self.activate = activate
        self.stamp_packet(time.monotonic())

    def encode(self):
        """Returns the data contained by the class encoded as CAN message data."""
        return pack(
            self.format,
            self.state_req,
            self.activate,
        )

    def decode(self, data):
        """Decodes CAN message data and populates the values of the class."""
        if len(data) == 5:
            # TODO: Instate warning when dashboard fw v0.1.9 is released
            # warnings.warn(
            #     "Please update dashboard firmware to >= v0.1.9."
            #     " New AmigaTpdo1 packets include more data. Support will be removed in farm_ng_amiga v0.0.9",
            #     stacklevel=2,
            # )
            (self.state_req, cmd_speed, cmd_ang_rate) = unpack(self.legacy_format, data)
            self.cmd_speed = cmd_speed / 1000.0
            self.cmd_ang_rate = cmd_ang_rate / 1000.0
        else:
            (self.state_req, cmd_speed, cmd_ang_rate, self.pto_bits, self.hbridge_bits) = unpack(self.format, data)
            self.cmd_speed = cmd_speed / 1000.0
            self.cmd_ang_rate = cmd_ang_rate / 1000.0

    def __str__(self):
        return "AMIGA Spray Request state {} activate {}".format(
            self.state_req, self.activate
        )



def make_amiga_spray1_proto(
    state_req: AmigaControlState, activate: bool
) -> canbus_pb2.RawCanbusMessage:
    """Creates a canbus_pb2.RawCanbusMessage.

    Uses the AmigaRpdo1 structure and formatting, that can be sent
    directly to the canbus service to be formatted and send on the CAN bus.

    Args:
        state_req: State of the Amiga vehicle control unit (VCU).
        cmd_speed: Command speed in meters per second.
        cmd_ang_rate: Command angular rate in radians per second.

    Returns:
        An instance of a canbus_pb2.RawCanbusMessage.
    """
    # TODO: add some checkers, or make python CHECK_API
    return canbus_pb2.RawCanbusMessage(
        id=AmigaSpray1.cob_id + DASHBOARD_NODE_ID,
        data=AmigaSpray1(
            state_req=state_req,
            activate=activate,
        ).encode(),
    )


if __name__=="__main__":

    # Test the can message
    msg: canbus_pb2.RawCanbusMessage = make_amiga_spray1_proto(
        state_req=AmigaControlState.STATE_AUTO_ACTIVE,
        activate=1
    )
