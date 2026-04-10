import time
from detector import find_state
from actions import click_result
from config import SCAN_TIMEOUT, CLICK_DELAY, MAX_RETRIES

# Scoped to feature_b's own states
INITIAL_CLICKS = [
    {"name": "Some Click", "x": 500, "y": 300},
]

SEQUENCE = [
    {"name": "Button 1", "image": "states/feature_b/buttons/btn_1.png"},
    {"name": "Button 2", "image": "states/feature_b/buttons/btn_2.png"},
]

def wait_and_click(step): ...
def check_state(name, image_path, timeout=SCAN_TIMEOUT): ...
def run_steps(steps): ...

def run(stop_event=None):
    print("Feature B started!")
    time.sleep(3)

    cycle = 0
    retries = 0

    while True:
        if stop_event and stop_event.is_set():
            print("  → Bot stopped.")
            break

        cycle += 1
