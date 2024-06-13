import asyncio
import websockets
import json
import subprocess
import os
import RPi.GPIO as GPIO  # Ensure this is installed if you are using a Raspberry Pi
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

URI = os.getenv('URI')
PORT = os.getenv('PORT')
CLIENT_NAME = os.getenv('CLIENT_NAME')
CLIENT_TYPE = os.getenv('CLIENT_TYPE')

DISPLAY_OUTPUT = "HDMI-1"  # Replace with your actual display output
HEARTBEAT_INTERVAL = 0.5  # 5 seconds

# GPIO setup
DOOR_SENSOR_PIN = 17
SECTOR_STATUS_PIN = 27
BUTTON_PIN = 22
LED1_PIN = 5
LED2_PIN = 6

GPIO.setmode(GPIO.BCM)
GPIO.setup(DOOR_SENSOR_PIN, GPIO.IN)
GPIO.setup(SECTOR_STATUS_PIN, GPIO.IN)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(LED1_PIN, GPIO.OUT)
GPIO.setup(LED2_PIN, GPIO.OUT)

# Initialize state
current_state = "off"
maintenance_mode = False

async def get_cpu_temperature():
    try:
        # Read temperature from system files
        temp_files = subprocess.check_output("cat /sys/class/thermal/thermal_zone*/temp", shell=True)
        temp_lines = temp_files.splitlines()
        # Assuming the first line is the CPU temp in millidegree Celsius
        temp_milli_celsius = int(temp_lines[0])
        temp_celsius = temp_milli_celsius / 1000.0
        return int(temp_celsius)  # Return the integer part of the temperature
    except Exception as e:
        print(f"Error reading CPU temperature: {e}")
        return None

def is_door_open(): 
	return GPIO.input(DOOR_SENSOR_PIN) == GPIO.HIGH

def sector_status():
	return True
    #return GPIO.input(SECTOR_STATUS_PIN) == GPIO.HIGH

def button_pressed():
    global maintenance_mode
    if GPIO.input(BUTTON_PIN) == GPIO.LOW:
        maintenance_mode = not maintenance_mode
        return True
    return False

def set_leds(state):
    GPIO.output(LED1_PIN, GPIO.HIGH if state == "on" else GPIO.LOW)
    GPIO.output(LED2_PIN, GPIO.HIGH if state == "on" else GPIO.LOW)

async def handle_message(message):
    global current_state
    print(f"Raw message received: {message}")
    try:
        data = json.loads(message)
        print(f"Decoded message: {data}")
        if data.get("type") == "instruction" and data.get("to") == "panel":
            instruction = data.get("instruction")
            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            if instruction == "on":
                subprocess.run(["xrandr", "--output", DISPLAY_OUTPUT, "--auto"], env=env)
                print("Screen turned on")
                current_state = "on"
            elif instruction == "off":
                subprocess.run(["xrandr", "--output", DISPLAY_OUTPUT, "--off"], env=env)
                print("Screen turned off")
                current_state = "off"
            else:
                print(f"Unknown instruction: {instruction}")
            set_leds(current_state)
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
    print("Screen turned off due to disconnection")
    current_state = "off"
    set_leds(current_state)

async def register(websocket, client_type, name=None):
    registration_message = {
        "type": "register",
        "clientType": client_type,
        "name": name
    }
    await websocket.send(json.dumps(registration_message))
    print(f"Registered with server as {client_type}, name: {name}")
    await disable_screen_sleep()

async def send_heartbeat(websocket):
    while True:
        cpu_temp = await get_cpu_temperature()
        heartbeat_message = {
            "type": "heartbeat",
            "state": current_state,
            "cpuTemp": cpu_temp,
            "isDoorOpen": is_door_open(),
            "sectorStatus": sector_status(),
            "maintenanceMode": maintenance_mode
        }
        await websocket.send(json.dumps(heartbeat_message))
        await asyncio.sleep(HEARTBEAT_INTERVAL)

async def connect():
    uri = f"{URI}:{PORT}"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print("Connected to the server")
                await register(websocket, CLIENT_TYPE, CLIENT_NAME)
                asyncio.create_task(send_heartbeat(websocket))
                while True:
                    message = await websocket.recv()
                    print("Message received:", message)
                    await handle_message(message)
                    if button_pressed():
                        await websocket.send(json.dumps({
                            "type": "maintenanceMode",
                            "state": maintenance_mode
                        }))
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
    asyncio.run(connect())
