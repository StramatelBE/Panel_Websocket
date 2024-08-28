from websocket_client import WebSocketClient
from gpio_handler import GPIOHandler
from utils import get_cpu_temperature, write_log
import asyncio
import subprocess

class PanelController:
    def __init__(self, loop):
        self.uri = "ws://example.com:port"
        self.client_name = "panel"
        self.client_type = "display_panel"
        self.heartbeat_interval = 5

        # Pass the loop to GPIOHandler
        self.gpio_handler = GPIOHandler(loop)
        self.websocket_client = WebSocketClient(self.uri, self.client_name, self.client_type, self)

    async def connect(self):
        await self.websocket_client.connect()

    async def process_instruction(self, instruction):
        if instruction == "on":
            await self.turn_on_screen()
            self.gpio_handler.set_leds(True, True)
            write_log("Screen turned ON")
        elif instruction == "off":
            await self.turn_off_screen()
            self.gpio_handler.set_leds(False, False)
            write_log("Screen turned OFF")

    async def turn_on_screen(self):
        subprocess.run(["xrandr", "--output", "HDMI-1", "--auto"])
        write_log("HDMI-1 screen turned ON")

    async def turn_off_screen(self):
        subprocess.run(["xrandr", "--output", "HDMI-1", "--off"])
        write_log("HDMI-1 screen turned OFF")

    def cleanup(self):
        self.gpio_handler.cleanup()
        write_log("GPIO cleanup complete")
