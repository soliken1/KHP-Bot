import pyautogui
import time
from config import CLICK_DELAY

def click(x, y):
    pyautogui.moveTo(x, y, duration=0.1)  # slight move looks more human
    pyautogui.click()
    time.sleep(CLICK_DELAY)

def click_result(result):
    """Accepts the tuple from find_state()"""
    if result:
        click(result[0], result[1])