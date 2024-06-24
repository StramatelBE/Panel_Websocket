import RPi.GPIO as GPIO
import time

PIN_TO_TEST = 17
GPIO.setmode(GPIO.BCM)
GPIO.setup(PIN_TO_TEST, GPIO.IN)

last_state = None
try:
    while True:
        current_state = GPIO.input(PIN_TO_TEST)
        if current_state != last_state:
            print(f"Pin {PIN_TO_TEST} changed to {current_state} at {time.time()}")
            last_state = current_state
        time.sleep(0.01)
except KeyboardInterrupt:
    GPIO.cleanup()