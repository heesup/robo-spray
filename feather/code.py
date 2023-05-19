from farm_ng.utils.general import TickRepeater
from farm_ng.utils.main_loop import MainLoop
from struct import pack,unpack

from digitalio import DigitalInOut, Direction, Pull
import board
import time

switch = DigitalInOut(board.D11)
switch.direction = Direction.OUTPUT

class CansnifferApp:
    def __init__(self, main_loop: MainLoop, can, node_id) -> None:
        self.can = can
        self.node_id = node_id
        self.main_loop = main_loop
        self.main_loop.show_debug = True
        self.main_loop.show_time = True
        self.main_loop.show_can_dts = True
        self.debug_repeater = TickRepeater(ticks_period_ms=1000)

        self.format = "<Bhx" # little-endian [unsigned char, short]

        self._register_message_handlers()

    def _register_message_handlers(self):
        can_id = 0x777
        self.main_loop.command_handlers[can_id] = self._handle_amiga_spary1

    def _handle_amiga_spary1(self, message):
        #print(message.data)
        decoded_msg = self.decode(message.data)
        print(decoded_msg)
        if int(decoded_msg) > 0:

            # turn switch on
            switch.value = True

        else:

            # turn switch off
            switch.value = False

    def decode(self, data):
        """Decodes CAN message data and populates the values of the class."""

        (self.state_req, activate) = unpack(self.format, data)
        self.activate = activate
        return self.activate

    def iter(self):
        if self.debug_repeater.check():
            print("\033[2J", end="")
            print(self.main_loop.io_debug_str())


def main():
    MainLoop(AppClass=CansnifferApp, has_display=False).loop()


main()
