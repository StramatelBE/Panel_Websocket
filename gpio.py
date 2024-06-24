import RPi.GPIO as GPIO
import time

# Configuration des pins
DOOR_SENSOR_PIN = 17
SECTOR_STATUS_PIN = 27
BUTTON_PIN = 4
LED1_PIN = 22
LED2_PIN = 10

def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # Configuration des entrées
    GPIO.setup(DOOR_SENSOR_PIN, GPIO.IN)
    GPIO.setup(SECTOR_STATUS_PIN, GPIO.IN)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Configuration des sorties
    GPIO.setup(LED1_PIN, GPIO.OUT)
    GPIO.setup(LED2_PIN, GPIO.OUT)

def read_inputs():
    door_state = GPIO.input(DOOR_SENSOR_PIN)
    sector_state = GPIO.input(SECTOR_STATUS_PIN)
    button_state = GPIO.input(BUTTON_PIN)
    
    print(f"Door Sensor: {'Open' if door_state else 'Closed'}")
    print(f"Sector Status: {'Active' if sector_state else 'Inactive'}")
    print(f"Button: {'Pressed' if button_state == GPIO.LOW else 'Not Pressed'}")

def toggle_leds():
    GPIO.output(LED1_PIN, not GPIO.input(LED1_PIN))
    GPIO.output(LED2_PIN, not GPIO.input(LED2_PIN))
    print(f"LED1: {'On' if GPIO.input(LED1_PIN) else 'Off'}")
    print(f"LED2: {'On' if GPIO.input(LED2_PIN) else 'Off'}")

def main():
    setup()
    try:
        while True:
            read_inputs()
            toggle_leds()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nProgram stopped by user")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()