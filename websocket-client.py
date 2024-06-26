import asyncio
import websockets
import json
import subprocess
import math

import os
import RPi.GPIO as GPIO
from dotenv import load_dotenv

class PanelController:
    def __init__(self):
        load_dotenv()
        self.uri = f"{os.getenv('URI')}:{os.getenv('PORT')}"
        self.client_name = os.getenv('CLIENT_NAME')
        self.client_type = os.getenv('CLIENT_TYPE')
        self.display_output = "HDMI-1"
        self.heartbeat_interval = 30  # Default heartbeat interval in seconds

        # GPIO setup
        self.door_sensor_pin = 17
        self.sector_status_pin = 27
        self.button_pin = 4
        self.led1_pin = 22
        self.led2_pin = 10

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.door_sensor_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.sector_status_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.button_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.led1_pin, GPIO.OUT)
        GPIO.setup(self.led2_pin, GPIO.OUT)

        self.current_state = "off"

    async def connect(self):
        while True:
            try:
                async with websockets.connect(self.uri) as websocket:
                    print("Connected to the server")
                    await self.register(websocket)
                    await self.main_loop(websocket)
            except websockets.ConnectionClosedError as e:
                print(f"Connection closed: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Unexpected error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def register(self, websocket):
        registration_message = {
            "type": "register",
            "clientType": self.client_type,
            "name": self.client_name
        }
        await websocket.send(json.dumps(registration_message))
        await self.disable_screen_sleep()
        print(f"Registered with server as {self.client_type}, name: {self.client_name}")

    async def main_loop(self, websocket):
    # Create the heartbeat task
        heartbeat_task = asyncio.create_task(self.send_heartbeat(websocket))
        try:
            while True:
                message = await websocket.recv()
                await self.handle_message(message, websocket)
        finally:
            heartbeat_task.cancel()  # Ensure the task is cancelled when the loop exits
            await heartbeat_task  # Wait for the task to be cancelled properly


    async def handle_message(self, message, websocket):
        try:
            data = json.loads(message)
            if data.get("type") == "instruction" and data.get("to") == "panel":
                await self.process_instruction(data)
                if "heartbeatTimer" in data:
                    new_interval = int(data["heartbeatTimer"])
                    if new_interval > 0:
                        self.heartbeat_interval = new_interval
                    else:
                        print("Invalid heartbeat interval received; ignoring update.")
                await self.send_heartbeat_to_server(websocket)
        except json.JSONDecodeError:
            print("Failed to decode message:", message)

    async def process_instruction(self, data):
        instruction = data.get("instruction")
        env = os.environ.copy()
        env["DISPLAY"] = ":0"
        if instruction == "on":
            subprocess.run(["xrandr", "--output", self.display_output, "--auto"], env=env)
            self.current_state = "on"
            GPIO.output(self.led1_pin, GPIO.HIGH)
            GPIO.output(self.led2_pin, GPIO.HIGH)
        elif instruction == "off":
            await self.turn_off_screen()

    async def send_heartbeat(self, websocket):
        while True:
            try:
                await self.send_heartbeat_to_server(websocket)
                await asyncio.sleep(self.heartbeat_interval)  # Ensure the interval is valid and being used
            except asyncio.CancelledError:
                print("Heartbeat task cancelled, exiting...")
                break
            except Exception as e:
                print(f"Error during heartbeat: {e}")  # Log any errors that occur


    async def send_heartbeat_to_server(self, websocket):
        try:
            data = {
                "type": "heartbeat",
                "state": await self.get_display_state(),
                "cpuTemp": await self.get_cpu_temperature(),
                "sectorStatus": GPIO.input(self.sector_status_pin) == GPIO.LOW,
                "isDoorOpen": GPIO.input(self.door_sensor_pin) == GPIO.HIGH,
                "maintenanceMode": GPIO.input(self.button_pin) == GPIO.HIGH,
                "name": self.client_name
            }
            await websocket.send(json.dumps(data))
            print(f"Heartbeat sent at interval {self.heartbeat_interval}s")  # Log when a heartbeat is sent
        except Exception as e:
            print(f"Failed to send heartbeat: {e}")  # Log the error
     

    async def get_cpu_temperature(self):
        try:
            # Command to get CPU temperature
            temp_files = subprocess.check_output("cat /sys/class/thermal/thermal_zone*/temp", shell=True)
            temp_lines = temp_files.splitlines()
            temp_milli_celsius = int(temp_lines[0])
            
            # Convert milli Celsius to Celsius and use math.floor to round down
            temp_celsius = temp_milli_celsius / 1000.0
            return math.floor(temp_celsius)
        except Exception as e:
            print(f"Error reading CPU temperature: {e}")
            return None


    async def get_display_state(self):
        try:
            result = subprocess.check_output("xrandr --listmonitors", shell=True).decode()
            return "on" if "Monitors: 1" in result else "off"
        except Exception as e:
            print(f"Error getting display state: {e}")
            return "unknown"

    async def disable_screen_sleep(self):
        env = os.environ.copy()
        env["DISPLAY"] = ":0"
        subprocess.run(["xset", "s", "off"], env=env)
        subprocess.run(["xset", "s", "noblank"], env=env)
        # subprocess.run(["xset", "-dpms"], env=env)

    async def turn_off_screen(self):
        env = os.environ.copy()
        env["DISPLAY"] = ":0"
        subprocess.run(["xrandr", "--output", self.display_output, "--off"], env=env)
        # subprocess.run(["xset", "dpms", "force", "off"], env=env)
        self.current_state = "off"
        GPIO.output(self.led1_pin, GPIO.LOW)
        GPIO.output(self.led2_pin, GPIO.LOW)

    def cleanup(self):
        GPIO.cleanup()

if __name__ == "__main__":
    controller = PanelController()
    try:
        asyncio.run(controller.connect())
    finally:
        controller.cleanup()
