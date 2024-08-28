from controller import PanelController
import asyncio

if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    # Pass the loop to GPIOHandler
    controller = PanelController(loop)

    try:
        loop.run_until_complete(controller.connect())
    finally:
        controller.cleanup()
        loop.close()
