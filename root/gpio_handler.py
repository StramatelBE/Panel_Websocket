import RPi.GPIO as GPIO
from utils import write_log

class GPIOHandler:
    def __init__(self, loop):
        self.loop = loop

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

        GPIO.add_event_detect(self.door_sensor_pin, GPIO.BOTH, callback=self.gpio_event_detected, bouncetime=200)
        GPIO.add_event_detect(self.sector_status_pin, GPIO.BOTH, callback=self.gpio_event_detected, bouncetime=200)
        GPIO.add_event_detect(self.button_pin, GPIO.BOTH, callback=self.gpio_event_detected, bouncetime=200)

        write_log("GPIO initialized")

    def gpio_event_detected(self, channel):
        self.loop.call_soon_threadsafe(self.handle_gpio_event, channel)

    def handle_gpio_event(self, channel):
        if channel == self.door_sensor_pin:
            write_log("Door sensor event detected")
        elif channel == self.sector_status_pin:
            write_log("Sector status event detected")
        elif channel == self.button_pin:
            write_log("Button press event detected")

    def set_leds(self, led1_status, led2_status):
        GPIO.output(self.led1_pin, GPIO.HIGH if led1_status else GPIO.LOW)
        GPIO.output(self.led2_pin, GPIO.HIGH if led2_status else GPIO.LOW)

    def cleanup(self):
        GPIO.cleanup()
        write_log("GPIO cleanup completed")
