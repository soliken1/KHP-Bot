import os
import sys
import time
import pyautogui
from detector import find_state, find_all_states
from actions import click_result
from config import SCAN_TIMEOUT, CLICK_DELAY, MAX_RETRIES

def _get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "features", "skip_episodes")
    return os.path.dirname(os.path.abspath(__file__))

_DIR = _get_base_dir()

INITIAL_CLICKS = [
    {"name": "Click 1st Grid", "x": 700, "y": 450},
]

BACK_BUTTON = {"name": "Back Button", "image": os.path.join(_DIR, "images/buttons/back_btn.png")}

PLAY_NORMAL_SEQUENCE = [
    {"name": "Normal Play Button", "image": os.path.join(_DIR, "images/buttons/play_btn.png")},
]

PLAY_INTIM_SEQUENCE = [
    {"name": "Intim Play Button", "image": os.path.join(_DIR, "images/buttons/intim_ep_unlocked_btn.png")},
]

POST_NORMAL_SEQUENCE = [
    {"name": "Skip Button",       "image": os.path.join(_DIR, "images/buttons/skip_btn.png")},
    {"name": "Skip Story Button", "image": os.path.join(_DIR, "images/buttons/skip_story_btn.png")},
    {"name": "Return Episode",    "image": os.path.join(_DIR, "images/buttons/return_episode_btn.png")},
    {"name": "Ok Button",         "image": os.path.join(_DIR, "images/buttons/ok_btn.png")},
]

POST_INTIM_SEQUENCE = [
    {"name": "Skip Button",       "image": os.path.join(_DIR, "images/buttons/skip_btn.png")},
    {"name": "Skip Story Button", "image": os.path.join(_DIR, "images/buttons/skip_story_btn.png")},
    {"name": "Intim Skip Button", "image": os.path.join(_DIR, "images/buttons/intim_skip_btn.png")},
    {"name": "Intim Skip Story",  "image": os.path.join(_DIR, "images/buttons/ok_btn.png")},
    {"name": "Return Episode",    "image": os.path.join(_DIR, "images/buttons/return_episode_btn.png")},
    {"name": "Ok Button",         "image": os.path.join(_DIR, "images/buttons/ok_btn.png")},
]

CHECK_NORMAL_EP_FINISHED  = os.path.join(_DIR, "images/icons/normal_ep_finished_icon.png")
CHECK_INTIM_EP_UNLOCKED   = os.path.join(_DIR, "images/buttons/intim_ep_unlocked_btn.png")
CHECK_INTIM_EP_UNFINISHED = os.path.join(_DIR, "images/icons/intim_ep_unlocked_icon.png")
CHECK_BLANK_LIST          = os.path.join(_DIR, "images/icons/blank_list_icon.png")

INTIM_EPISODES = [
    {
        "name": "Intim EP 1",
        "index": 0,
        "check_unlocked":   os.path.join(_DIR, "images/buttons/intim_ep_unlocked_btn.png"),
        "check_unfinished": os.path.join(_DIR, "images/icons/intim_ep_unlocked_icon.png"),
        "check_finished":   os.path.join(_DIR, "images/icons/intim_ep_finished_icon.png"),
        "play_button":      os.path.join(_DIR, "images/buttons/intim_ep_unlocked_btn.png"),
    },
    {
        "name": "Intim EP 2",
        "index": 1,
        "check_unlocked":   os.path.join(_DIR, "images/buttons/intim_ep_unlocked_btn.png"),
        "check_unfinished": os.path.join(_DIR, "images/icons/intim_ep_2_unlocked_icon.png"),
        "check_finished":   os.path.join(_DIR, "images/icons/intim_ep_2_finished_icon.png"),
        "play_button":      os.path.join(_DIR, "images/buttons/intim_ep_unlocked_btn.png"),
    },
]
# --- Helpers ---

def do_initial_clicks():
    for step in INITIAL_CLICKS:
        print(f"Clicking [{step['name']}] at ({step['x']}, {step['y']})")
        pyautogui.moveTo(step["x"], step["y"], duration=0.2)
        pyautogui.click()
        time.sleep(CLICK_DELAY)

def wait_and_click(step):
    print(f"Looking for: {step['name']}...")

    # ── Guard: catch missing image files before silent timeout ────────────
    if not os.path.exists(step["image"]):
        print(f"  ✘ [{step['name']}] IMAGE FILE MISSING: {step['image']}")
        return False

    timeout = step.get("timeout", SCAN_TIMEOUT)
    start = time.time()
    while True:
        result = find_state(step["image"])
        if result:
            x, y, confidence = result
            print(f"  ✔ Found [{step['name']}] at ({x}, {y}) — confidence: {confidence:.2f}")
            click_result(result)
            time.sleep(CLICK_DELAY)
            return True
        if time.time() - start > timeout:
            print(f"  ✘ [{step['name']}] not found after {timeout}s")
            return False
        time.sleep(0.3)

def check_state(name, image_path, timeout=SCAN_TIMEOUT):
    print(f"Checking state: [{name}]...")

    # ── Guard: catch missing image files before silent timeout ────────────
    if not os.path.exists(image_path):
        print(f"  ✘ [{name}] IMAGE FILE MISSING: {image_path}")
        return False

    start = time.time()
    while True:
        result = find_state(image_path)
        if result:
            print(f"  ✔ [{name}] confirmed.")
            return True
        if time.time() - start > timeout:
            print(f"  ✘ [{name}] not confirmed after {timeout}s")
            return False
        time.sleep(0.3)

def run_steps(steps):
    for step in steps:
        if not wait_and_click(step):
            return False
    return True

def play_episode(ep_type, intim_ep=None):
    print(f"\n  → Playing [{ep_type}] episode...")

    if ep_type == "Normal":
        play_seq = PLAY_NORMAL_SEQUENCE
        post_seq = POST_NORMAL_SEQUENCE
    elif ep_type == "Intim" and intim_ep:
        # Build play sequence dynamically from the episode's play button
        play_seq = [{"name": intim_ep["name"], "image": intim_ep["play_button"]}]
        post_seq = POST_INTIM_SEQUENCE
    else:
        print(f"  ✘ Unknown episode type or missing intim_ep")
        return False

    if not run_steps(play_seq):
        return False
    if not run_steps(post_seq):
        return False
    return True

# --- Main Flow ---

def run(stop_event=None):
    print("Starting in 3 seconds... focus your game window!")
    time.sleep(3)

    cycle = 0
    retries = 0

    while True:
        if stop_event and stop_event.is_set():
            print("  → Bot stopped.")
            break

        cycle += 1
        print(f"\n{'='*30}")
        print(f"  Cycle {cycle}  |  Retry {retries}/{MAX_RETRIES}")
        print(f"{'='*30}")

        if retries >= MAX_RETRIES:
            print(f"\n  Max retries ({MAX_RETRIES}) reached. Bot stopped.")
            break

        # Step 1 — Check if list is empty (no more entries)
        print("\n--- Check List ---")
        if check_state("Blank List", CHECK_BLANK_LIST, 1.5):
            print("  → No more entries found. Bot finished!")
            break 

        # Step 2 — Click coordinates to open grid
        print("\n--- Initial Clicks ---")
        do_initial_clicks()

        # Step 3 — Check if Normal EP is finished
        print("\n--- Check Normal Episode ---")
        normal_finished = check_state("Normal EP Finished", CHECK_NORMAL_EP_FINISHED, 1.5)

        if not normal_finished:
            print("  → Normal EP not finished, playing it...")
            if not play_episode("Normal"):
                retries += 1
                print(f"  Play sequence failed. Retry {retries}/{MAX_RETRIES}")
                continue
            retries = 0
            print("  → Looping back to re-check state...")
            continue

        # Step 4 — Normal done, loop through each intim episode
        print("\n--- Check Intimate Episodes ---")
        any_intim_played = False
        intim_failed = False

        for ep in INTIM_EPISODES:
            print(f"\n  Checking [{ep['name']}]...")

            # Check if unlocked by index (same image, position-based)
            unlocked_matches = find_all_states(ep["check_unlocked"])

            if ep["index"] >= len(unlocked_matches):
                print(f"  → [{ep['name']}] is locked. Skipping...")
                continue

            print(f"  ✔ [{ep['name']}] is unlocked.")

            # Check if already finished — uses unique icon per EP so no index needed
            already_finished = find_state(ep["check_finished"])
            if already_finished:
                print(f"  → [{ep['name']}] already finished. Skipping...")
                continue

            # Check if unfinished — also unique per EP
            is_unfinished = find_state(ep["check_unfinished"])
            if not is_unfinished:
                print(f"  → [{ep['name']}] state unclear. Skipping...")
                continue

            # Unlocked, not finished — click its specific play button by index
            target = unlocked_matches[ep["index"]]
            print(f"  → Playing [{ep['name']}] at ({target[0]}, {target[1]})...")
            click_result(target)
            time.sleep(CLICK_DELAY)

            if not run_steps(POST_INTIM_SEQUENCE):
                retries += 1
                print(f"  Post sequence failed. Retry {retries}/{MAX_RETRIES}")
                intim_failed = True
                break

            any_intim_played = True
            print(f"  ✔ [{ep['name']}] done.")

        # Only go back if intim loop didn't fail mid-way
        if not intim_failed:
            print("\n  → Going back...")
            wait_and_click(BACK_BUTTON)
            time.sleep(1)
            retries = 0
            print(f"\n  ✔ Cycle {cycle} complete. (Intim played: {any_intim_played})")
            time.sleep(1)

        retries = 0
        print(f"\n  ✔ Cycle {cycle} complete. (Intim played: {any_intim_played})")
        time.sleep(1)

if __name__ == "__main__":
    run()