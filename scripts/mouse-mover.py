#!/usr/bin/env python3
import time
import subprocess

while True:
    subprocess.run(["xdotool", "mousemove_relative", "--", "1", "0"])
    time.sleep(15)
    subprocess.run(["xdotool", "mousemove_relative", "--", "-1", "0"])
    time.sleep(15)
