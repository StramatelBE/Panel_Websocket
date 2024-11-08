import asyncio
import time
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
        self.heartbeat_interval = 5  # Default heartbeat interval in seconds

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
        await self.turn_off_screen()
        while True:
            try:
                async with websockets.connect(self.uri) as websocket:
                    print("Connected to the server")
                    await self.turn_off_screen()
                    await self.register(websocket)
                    await self.main_loop(websocket)
            except websockets.ConnectionClosedError as e:
                print(f"Connection closed: {e}. Reconnecting in 5 seconds...")
                await self.turn_off_screen()
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Unexpected error: {e}. Reconnecting in 5 seconds...")
                await self.turn_off_screen()
                await asyncio.sleep(5)


# Initialize state
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
        heartbeat_task = asyncio.create_task(self.send_heartbeat(websocket))
        try:
            while True:
                message = await websocket.recv()
                await self.handle_message(message, websocket)
        finally:
            heartbeat_task.cancel()
            await heartbeat_task

    async def handle_message(self, message, websocket):
        print(message)
        try:
            data = json.loads(message)
            if data.get("type") == "instruction" and data.get("to") == "panel":
                instruction = data.get("instruction")
                instruction_id = data.get("instructionId")
                print(f"Received instruction: {instruction} with ID: {instruction_id}")
                if instruction:
                    await self.process_instruction(instruction, instruction_id, websocket)
                    # Send an immediate heartbeat after processing the instruction
                    if instruction != "reboot":
                        await self.send_heartbeat_to_server(websocket)
            else:
                pass
        except json.JSONDecodeError:
            print("Failed to decode message:", message)

    async def process_instruction(self, instruction, instruction_id, websocket):
        env = os.environ.copy()
        env["DISPLAY"] = ":0"
        if instruction == "on":
            await self.turn_on_screen()
        elif instruction == "off":
            await self.turn_off_screen()
        elif instruction == "refresh":
            print("Refreshing panel state...")
        elif instruction == "reboot":
            await self.set_rebooting_state(websocket)
            await asyncio.sleep(1)  # Ensure the message is sent before rebooting
            await self.reboot()
        else:
            print(f"Unknown instruction received: {instruction}")

        # Send acknowledgement after processing
        await self.send_acknowledgement(instruction_id, 'completed', websocket)

    async def send_acknowledgement(self, instruction_id, status, websocket):
        acknowledgement_message = {
            "type": "acknowledgement",
            "instructionId": instruction_id,
            "status": status,
            "panelName": self.client_name,
        }
        await websocket.send(json.dumps(acknowledgement_message))
        print(f"Acknowledgement sent for instruction {instruction_id} with status {status}")

    async def set_rebooting_state(self, websocket):
        self.current_state = "rebooting"
        await self.send_heartbeat_to_server(websocket)
        print("Panel state set to rebooting and heartbeat sent.")


    async def send_rebooting_status(self, websocket):
        try:
            data = {
                "type": "heartbeat",
                "state": "rebooting",
                "cpuTemp": await self.get_cpu_temperature(),
                "sectorStatus": GPIO.input(self.sector_status_pin) == GPIO.LOW,
                "isDoorOpen": GPIO.input(self.door_sensor_pin) == GPIO.HIGH,
                "maintenanceMode": GPIO.input(self.button_pin) == GPIO.HIGH,
                "name": self.client_name
            }
            await websocket.send(json.dumps(data))
            print("Sent rebooting status to server.")
        except Exception as e:
            print(f"Failed to send rebooting status: {e}")

    async def reboot(self):
        print("Rebooting panel...")
        env = os.environ.copy()
        self.current_state = None  # Reset the state after reboot
        await asyncio.sleep(1)
        subprocess.run(["sudo", "reboot"], env=env)

    async def send_heartbeat(self, websocket):
        while True:
            try:
                await self.send_heartbeat_to_server(websocket)
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                print("Heartbeat task cancelled, exiting...")
                break
            except Exception as e:
                print(f"Error during heartbeat: {e}")
                break  # Exit the loop to reconnect

    async def send_heartbeat_to_server(self, websocket):
        try:
            display_state = await self.get_display_state()
            state = self.current_state if self.current_state == 'rebooting' else display_state
            data = {
                "type": "heartbeat",
                "state": state,
                "cpuTemp": await self.get_cpu_temperature(),
                "sectorStatus": GPIO.input(self.sector_status_pin) == GPIO.LOW,
                "isDoorOpen": GPIO.input(self.door_sensor_pin) == GPIO.HIGH,
                "maintenanceMode": GPIO.input(self.button_pin) == GPIO.HIGH,
                "name": self.client_name
            }
            await websocket.send(json.dumps(data))
            print(f"Heartbeat sent with state '{state}' at interval {self.heartbeat_interval}s")
        except Exception as e:
            print(f"Failed to send heartbeat: {e}")


    async def get_cpu_temperature(self):
        try:
            temp_files = subprocess.check_output("cat /sys/class/thermal/thermal_zone*/temp", shell=True)
            temp_lines = temp_files.splitlines()
            temp_milli_celsius = int(temp_lines[0])
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
        subprocess.run(["xset", "-dpms"], env=env)

    async def turn_off_screen(self):
        env = os.environ.copy()
        env["DISPLAY"] = ":0"
        subprocess.run(["xrandr", "--output", self.display_output, "--off"], env=env)
        GPIO.output(self.led1_pin, GPIO.LOW)
        GPIO.output(self.led2_pin, GPIO.LOW)
        print("Screen turned off.")

    async def turn_on_screen(self):
        env = os.environ.copy()
        env["DISPLAY"] = ":0"
        subprocess.run(["xrandr", "--output", self.display_output, "--auto"], env=env)
        GPIO.output(self.led1_pin, GPIO.HIGH)
        GPIO.output(self.led2_pin, GPIO.HIGH)
        print("Screen turned on.")


    def cleanup(self):
        GPIO.cleanup()

if __name__ == "__main__":
    env = os.environ.copy()
    subprocess.run(["xrandr", "--output", "HDMI-1", "--off"], env=env)

    controller = PanelController()
    try:
        asyncio.run(controller.connect())
    finally:
        GPIO.cleanup()
        controller.cleanup()
