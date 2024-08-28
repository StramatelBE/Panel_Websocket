import subprocess
import math
import os
from datetime import datetime

def get_cpu_temperature():
    try:
        temp_files = subprocess.check_output("cat /sys/class/thermal/thermal_zone*/temp", shell=True)
        temp_milli_celsius = int(temp_files.splitlines()[0])
        temp_celsius = temp_milli_celsius / 1000.0
        return math.floor(temp_celsius)
    except Exception as e:
        write_log(f"Error reading CPU temperature: {e}")
        return None

def write_log(message):
    log_file = "panel_logs.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"[{timestamp}] {message}")
