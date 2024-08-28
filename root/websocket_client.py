import asyncio
import websockets
import json
from utils import write_log

class WebSocketClient:
    def __init__(self, uri, client_name, client_type, controller):
        self.uri = uri
        self.client_name = client_name
        self.client_type = client_type
        self.controller = controller

    async def connect(self):
        while True:
            try:
                async with websockets.connect(self.uri) as websocket:
                    write_log("Connected to WebSocket server")
                    await self.register(websocket)
                    await self.main_loop(websocket)
            except websockets.ConnectionClosedError as e:
                write_log(f"Connection closed: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                write_log(f"Unexpected error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def register(self, websocket):
        registration_message = {
            "type": "register",
            "clientType": self.client_type,
            "name": self.client_name
        }
        await websocket.send(json.dumps(registration_message))
        write_log(f"Registered with server as {self.client_type}, name: {self.client_name}")

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
        try:
            data = json.loads(message)
            if data.get("type") == "instruction" and data.get("to") == "panel":
                await self.controller.process_instruction(data.get("instruction"))
            elif data.get("type") == "refresh" and data.get("to") == "panel":
                write_log("Received refresh command, sending heartbeat...")
                await self.send_heartbeat_to_server(websocket)
            elif data.get("type") == "reboot" and data.get("to") == "panel":
                await self.controller.reboot()
        except json.JSONDecodeError:
            write_log("Failed to decode message:", message)

    async def send_heartbeat(self, websocket):
        while True:
            try:
                await self.send_heartbeat_to_server(websocket)
                await asyncio.sleep(self.controller.heartbeat_interval)
            except asyncio.CancelledError:
                write_log("Heartbeat task cancelled, exiting...")
                break
            except Exception as e:
                write_log(f"Error during heartbeat: {e}")

    async def send_heartbeat_to_server(self, websocket):
        try:
            data = {
                "type": "heartbeat",
                "state": "on" if self.controller.gpio_handler.is_display_on() else "off",
                "cpuTemp": get_cpu_temperature(),
                "sectorStatus": self.controller.gpio_handler.get_sector_status(),
                "isDoorOpen": self.controller.gpio_handler.is_door_open(),
                "maintenanceMode": self.controller.gpio_handler.get_maintenance_mode(),
                "name": self.controller.client_name
            }
            await websocket.send(json.dumps(data))
            write_log("Heartbeat sent to server")
        except Exception as e:
            write_log(f"Failed to send heartbeat: {e}")
