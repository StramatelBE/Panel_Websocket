import asyncio
import websockets
import json
import subprocess
import os
import RPi.GPIO as GPIO
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv('URI')
PORT = os.getenv('PORT')
CLIENT_NAME = os.getenv('CLIENT_NAME')
CLIENT_TYPE = os.getenv('CLIENT_TYPE')

DISPLAY_OUTPUT = "HDMI-1"
heartbeat_interval = 5

# GPIO setup
DOOR_SENSOR_PIN = 17
SECTOR_STATUS_PIN = 27
BUTTON_PIN = 4
LED1_PIN = 22
LED2_PIN = 10

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(DOOR_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(SECTOR_STATUS_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(LED1_PIN, GPIO.OUT)
GPIO.setup(LED2_PIN, GPIO.OUT)

current_state = "off"

async def get_cpu_temperature():
    try:
        temp_files = subprocess.check_output("cat /sys/class/thermal/thermal_zone*/temp", shell=True)
        temp_lines = temp_files.splitlines()
        temp_milli_celsius = int(temp_lines[0])
        temp_celsius = temp_milli_celsius / 1000.0
        return int(temp_celsius)
    except Exception as e:
        print(f"Error reading CPU temperature: {e}")
        return None

async def get_display_state():
    try:
        xrandr_output = subprocess.check_output("xrandr --listmonitors", shell=True).decode()
        if "Monitors: 1" in xrandr_output:
            return "on"
        else:
            return "off"
    except Exception as e:
        print(f"Error getting display state: {e}")
        return "unknown"

async def handle_message(message, websocket):
    global current_state
    try:
        data = json.loads(message)
        if data.get("type") == "instruction" and data.get("to") == "panel":
            instruction = data.get("instruction")
            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            if instruction == "on":
                subprocess.run(["xrandr", "--output", DISPLAY_OUTPUT, "--auto"], env=env)
                print("Screen turned on")
                current_state = "on"
                GPIO.output(LED1_PIN, GPIO.HIGH)
                GPIO.output(LED2_PIN, GPIO.HIGH)
            elif instruction == "off":
                subprocess.run(["xrandr", "--output", DISPLAY_OUTPUT, "--off"], env=env)
                subprocess.run(["xset", "dpms", "force", "off"], env=env)
                print("Screen turned off")
                current_state = "off"
                GPIO.output(LED1_PIN, GPIO.LOW)
                GPIO.output(LED2_PIN, GPIO.LOW)
            else:
                print(f"Unknown instruction: {instruction}")

            heartbeat_interval = data.get("heartbeatTimer", heartbeat_interval)
            await send_heartbeat_to_server(websocket)
    except json.JSONDecodeError:
        print("Failed to decode message:", message)

async def disable_screen_sleep():
    env = os.environ.copy()
    env["DISPLAY"] = ":0"
    subprocess.run(["xset", "s", "off"], env=env)
    subprocess.run(["xset", "s", "noblank"], env=env)
    subprocess.run(["xset", "-dpms"], env=env)
    print("Screen sleep disabled")

async def turn_off_screen():
    global current_state
    env = os.environ.copy()
    env["DISPLAY"] = ":0"
    subprocess.run(["xrandr", "--output", DISPLAY_OUTPUT, "--off"], env=env)
    subprocess.run(["xset", "dpms", "force", "off"], env=env)
    print("Screen turned off due to disconnection")
    current_state = "off"
    GPIO.output(LED1_PIN, GPIO.LOW)
    GPIO.output(LED2_PIN, GPIO.LOW)

async def register(websocket, client_type, name=None):
    registration_message = {
        "type": "register",
        "clientType": client_type,
        "name": name
    }
    await websocket.send(json.dumps(registration_message))
    print(f"Registered with server as {client_type}, name: {name}")
    await disable_screen_sleep()

async def send_heartbeat_to_server(websocket):
    cpu_temp = await get_cpu_temperature()
    display_state = await get_display_state()
    heartbeat_message = {
        "type": "heartbeat",
        "state": display_state,
        "cpuTemp": cpu_temp,
        "sectorStatus": GPIO.input(SECTOR_STATUS_PIN) == GPIO.LOW,
        "isDoorOpen": GPIO.input(DOOR_SENSOR_PIN) == GPIO.HIGH,
        "maintenanceMode": GPIO.input(BUTTON_PIN) == GPIO.HIGH,
        "name": CLIENT_NAME
    }
    await websocket.send(json.dumps(heartbeat_message))

async def send_heartbeat(websocket):
    while True:
        try:
            await send_heartbeat_to_server(websocket)
        except websockets.ConnectionClosed:
            print("Connection closed during heartbeat")
            break
        await asyncio.sleep(heartbeat_interval)

async def connect():
    uri = f"{URI}:{PORT}"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print("Connected to the server")
                await register(websocket, CLIENT_TYPE, CLIENT_NAME)
                heartbeat_task = asyncio.create_task(send_heartbeat(websocket))
                while True:
                    message = await websocket.recv()
                    print("Message received:", message)
                    await handle_message(message, websocket)
        except websockets.ConnectionClosedError as e:
            print(f"Connection closed: {e}. Turning off screen and reconnecting in 5 seconds...")
            await turn_off_screen()
            await asyncio.sleep(5)
        except websockets.InvalidURI as e:
            print(f"Invalid URI: {e}. Check the server address and port.")
            await turn_off_screen()
            return
        except ConnectionRefusedError as e:
            print(f"Connection refused: {e}. Turning off screen and reconnecting in 5 seconds...")
            await turn_off_screen()
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Unexpected error: {e}. Turning off screen and reconnecting in 5 seconds...")
            await turn_off_screen()
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        turn_off_screen()
        asyncio.run(connect())
    finally:
        GPIO.cleanup()