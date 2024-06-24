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
    
    # Configuration des entrées avec pull-up
    GPIO.setup(DOOR_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(SECTOR_STATUS_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Configuration des sorties
    GPIO.setup(LED1_PIN, GPIO.OUT)
    GPIO.setup(LED2_PIN, GPIO.OUT)

def read_inputs():
    door_state = GPIO.input(DOOR_SENSOR_PIN)
    sector_state = GPIO.input(SECTOR_STATUS_PIN)
    button_state = GPIO.input(BUTTON_PIN)
    
    print(f"Door Sensor (GPIO {DOOR_SENSOR_PIN}): {'1 (Open)' if door_state else '0 (Closed)'}")
    print(f"Sector Status (GPIO {SECTOR_STATUS_PIN}): {'1 (Active)' if sector_state else '0 (Inactive)'}")
    print(f"Button (GPIO {BUTTON_PIN}): {'1 (On)' if button_state else '0 (Off)'}")

def update_leds(door_state, sector_state):
    GPIO.output(LED1_PIN, door_state)
    GPIO.output(LED2_PIN, sector_state)
    print(f"LED1 (GPIO {LED1_PIN}): {'On' if door_state else 'Off'}")
    print(f"LED2 (GPIO {LED2_PIN}): {'On' if sector_state else 'Off'}")

def main():
    setup()
    try:
        while True:
            door_state = GPIO.input(DOOR_SENSOR_PIN)
            sector_state = GPIO.input(SECTOR_STATUS_PIN)
            
            read_inputs()
            update_leds(door_state, sector_state)
            print(f"Time: {time.time()}")
            print("-" * 30)
            time.sleep(1)  # Lecture plus fréquente
    except KeyboardInterrupt:
        print("\nProgram stopped by user")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()