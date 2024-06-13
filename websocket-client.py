import asyncio
import websockets
import json
import subprocess
import os
import psutil  # You need to install the psutil package
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

URI = os.getenv('URI')
PORT = os.getenv('PORT')
CLIENT_NAME = os.getenv('CLIENT_NAME')
CLIENT_TYPE = os.getenv('CLIENT_TYPE')

DISPLAY_OUTPUT = "HDMI-1"  # Replace with your actual display output
HEARTBEAT_INTERVAL = 5  # 5 seconds

# Initialize state
current_state = "off"

async def get_cpu_temperature():
    try:
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps:
            return temps['coretemp'][0].current
        elif 'cpu-thermal' in temps:
            return temps['cpu-thermal'][0].current
        else:
            return None
    except Exception as e:
        print(f"Error reading CPU temperature: {e}")
        return None

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
        print(cpu_temp)
        heartbeat_message = {
                "type": "heartbeat",
                "state": current_state,
                "cpuTemp": cpu_temp
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
