"""
features/auto_main_quest/auto_main_quest.py

Automates main quest progression:
  1. Click coordinate to initiate quest
  2. Handle support/team selection if on support screen
  3. Skip cutscenes
  4. Run through combat (auto-attack)
  5. Dismiss popups, return to quests, loop

stop_event (threading.Event) is checked at every checkpoint
so the Stop button in the UI halts execution cleanly.
"""

import os
import sys
import time
import threading
import logging
import pyautogui

from config_loader import (
    get_confidence,
    get_poll_interval,
    get_support_slot,
    get_team_section,
    get_team_slot,
    get_team_slot_position,
    get_team_section_position,
    get_main_quest_initial_click,
    get_main_quest_max_iterations,
    get_main_quest_combat_wait,
    get_main_quest_cleared_check_region,
    get_energy_regen_positions,
)

logger = logging.getLogger(__name__)


# ── Image asset paths ─────────────────────────────────────────────────────

def _get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "features", "auto_main_quest")
    return os.path.dirname(os.path.abspath(__file__))


def _get_combat_base_dir() -> str:
    """Resolve auto_combat image dir for shared support/team icons."""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "features", "auto_combat")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "auto_combat")


_DIR = _get_base_dir()
_COMBAT_DIR = _get_combat_base_dir()

IMAGES = {
    # ── Local buttons (auto_main_quest/images/buttons/) ──
    "skip_btn":             os.path.join(_DIR, "images", "buttons", "skip_btn.png"),
    "skip_summary_btn":     os.path.join(_DIR, "images", "buttons", "skip_summary_btn.png"),
    "intim_btn":            os.path.join(_DIR, "images", "buttons", "intim_btn.png"),
    "atk_btn":              os.path.join(_DIR, "images", "buttons", "atk_btn.png"),
    "ok_btn":               os.path.join(_DIR, "images", "buttons", "ok_btn.png"),
    "use_btn":              os.path.join(_DIR, "images", "buttons", "use_btn.png"),
    "return_to_quests_btn": os.path.join(_DIR, "images", "buttons", "return_to_quests_btn.png"),
    "cleared":              os.path.join(_DIR, "images", "buttons", "cleared.png"),
    "to_world_map_btn":     os.path.join(_DIR, "images", "buttons", "to_world_map_btn.png"),

    # ── Local icons (auto_main_quest/images/icons/) ──
    "support_screen":       os.path.join(_DIR, "images", "icons", "support_screen.png"),

    # ── Shared from auto_combat ──
    "not_enough_ap":        os.path.join(_COMBAT_DIR, "images", "icon", "not_enough_ap_icon.png"),
    "support_btn":          os.path.join(_COMBAT_DIR, "images", "icon", "{slot}_element_icon.png"),
    "release":              os.path.join(_COMBAT_DIR, "images", "icon", "release.png"),
    "click_support":        os.path.join(_COMBAT_DIR, "images", "icon", "my_support_icon.png"),
    "start_combat":         os.path.join(_COMBAT_DIR, "images", "button", "go_to_quest_btn.png"),
    "attack_btn":           os.path.join(_COMBAT_DIR, "images", "button", "attack_btn.png"),
    "combat_ok_btn":        os.path.join(_COMBAT_DIR, "images", "button", "ok_btn.png"),
    "next_btn":             os.path.join(_COMBAT_DIR, "images", "button", "next_btn.png"),
    "retry_btn":            os.path.join(_COMBAT_DIR, "images", "button", "retry_btn.png"),
}


# ── Helpers ───────────────────────────────────────────────────────────────

def _sleep(seconds: float, stop_event: threading.Event):
    """Sleep in small increments so stop_event is checked frequently."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if stop_event.is_set():
            return
        time.sleep(min(0.2, deadline - time.time()))


def _find(image_key: str, slot: int = None) -> pyautogui.Point | None:
    """Locate an image on screen. Returns center Point or None."""
    path = IMAGES[image_key]
    if slot is not None:
        path = path.format(slot=slot)
    try:
        loc = pyautogui.locateOnScreen(path, confidence=get_confidence())
        if loc:
            return pyautogui.center(loc)
    except Exception as e:
        logger.debug(f"[main_quest] _find '{image_key}': {e}")
    return None


def _click(image_key: str, slot: int = None, retries: int = 5) -> bool:
    """Find and click an image. Returns True on success."""
    for _ in range(retries):
        pt = _find(image_key, slot=slot)
        if pt:
            pyautogui.click(pt)
            logger.debug(f"[main_quest] Clicked '{image_key}' at {pt}")
            return True
        time.sleep(get_poll_interval())
    logger.warning(f"[main_quest] Could not find '{image_key}' after {retries} tries")
    return False


def _wait_and_click(image_key: str, timeout: float = 15.0, slot: int = None) -> bool:
    """Poll for an image and click it once found. Returns True on success."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        pt = _find(image_key, slot=slot)
        if pt:
            pyautogui.click(pt)
            logger.debug(f"[main_quest] wait_and_click '{image_key}' at {pt}")
            return True
        time.sleep(get_poll_interval())
    logger.warning(f"[main_quest] wait_and_click '{image_key}' timed out after {timeout}s")
    return False


def _is_cleared_in_region() -> bool:
    """
    Return True if the 'cleared' stamp is visible inside the configured region.
    Falls back to a full-screen search when no region is configured.
    """
    region = get_main_quest_cleared_check_region()
    try:
        loc = pyautogui.locateOnScreen(
            IMAGES["cleared"],
            confidence=get_confidence(),
            region=region,      # None → full screen
        )
        return loc is not None
    except Exception as e:
        logger.debug(f"[main_quest] _is_cleared_in_region: {e}")
        return False

def _handle_energy_regen(stop_event: threading.Event) -> bool:
    """
    If not_enough_ap icon is visible after clicking retry:
      tap_1 → tap_2 → ok_btn → back to support screen.
    Returns True if regen was performed, False if AP was fine.
    """
    if _find("not_enough_ap") is None:
        return False

    logger.info("[auto_combat] Not enough AP — attempting energy regen...")
    print("  ⚡ AP depleted — regenerating energy...")

    (x1, y1), (x2, y2) = get_energy_regen_positions()

    if x1 == 0 and y1 == 0:
        logger.warning("[auto_combat] energy_regen.tap_1 not calibrated in config.yaml.")
        return False

    pyautogui.click(x1, y1)
    time.sleep(0.5)
    if stop_event.is_set(): return False

    pyautogui.click(x2, y2)
    time.sleep(0.5)
    if stop_event.is_set(): return False

    _click("use_btn")
    time.sleep(1.5)

    _click("ok_btn")
    time.sleep(0.5)

    print("  ✔ Energy regenerated — resuming combat.")
    return True

def _dismiss_ok_if_present(wait: float = 0.5) -> None:
    """Click ok_btn if visible — handles level up, first clear, or any reward popup."""
    if _find("ok_btn"):
        _click("ok_btn", retries=1)
        time.sleep(wait)
    if _find("combat_ok_btn"):
        _click("combat_ok_btn", retries=1)
        time.sleep(wait)


# ── Support / team selection ──────────────────────────────────────────────

def _select_support(stop_event: threading.Event) -> bool:
    """Click support element icon + 'My Support' confirm."""
    support_slot = get_support_slot()

    if support_slot > 0:
        if not _click("support_btn", slot=support_slot):
            logger.error(f"[main_quest] Could not click support slot {support_slot}.")
            return False
        time.sleep(0.3)

    if stop_event.is_set():
        return False

    if not _click("click_support"):
        logger.error("[main_quest] Could not click 'My Support' confirm.")
        return False
    time.sleep(0.3)
    return True


def _select_team(stop_event: threading.Event) -> bool:
    """Click team section tab + team slot by fixed coordinates."""
    section = get_team_section()
    slot = get_team_slot()

    try:
        section_x, section_y = get_team_section_position(section)
        slot_x, slot_y = get_team_slot_position(slot)
    except ValueError as e:
        logger.error(f"[main_quest] {e}")
        return False

    pyautogui.click(section_x, section_y)
    time.sleep(0.5)
    if stop_event.is_set():
        return False

    pyautogui.click(slot_x, slot_y)
    time.sleep(0.5)
    return True


# ── Quest iteration ───────────────────────────────────────────────────────

def _run_quest_iteration(iteration: int, stop_event: threading.Event) -> bool:
    """
    Execute one main quest iteration:
      1. Click initial coordinate
      2. Detect support screen → select support/team → start combat
      3. Skip cutscenes, handle combat, dismiss popups
      4. Return to quest list

    Returns True on success, False on failure/stop.
    """
    ix, iy = get_main_quest_initial_click()
    combat_wait = get_main_quest_combat_wait()

    # Check first for iteration if there's a new main story quest
    _sleep(1.0, stop_event)
    if _wait_and_click("ok_btn", timeout=5.0):
        logger.info("[main_quest] New quest detected.")
        _click("ok_btn", retries=1)

    # Step 1: Click initial coordinate to start quest
    logger.info(f"[main_quest] Iteration {iteration} — clicking ({ix}, {iy})")
    pyautogui.click(ix, iy)
    _sleep(2.0, stop_event)
    if stop_event.is_set():
        return False
    
    _handle_energy_regen(stop_event)
    _sleep(2.0, stop_event)

    # Step 2: Check for support screen
    if _find("support_screen"):
        print(f"  → [{iteration}] Support screen detected — selecting team...")
        logger.info("[main_quest] Support screen detected.")

        if not _select_support(stop_event):
            return False
        if stop_event.is_set():
            return False

        if not _select_team(stop_event):
            return False
        if stop_event.is_set():
            return False
        _sleep(1.5, stop_event)

        # Click start combat button
        if not _click("start_combat"):
            logger.error("[main_quest] Could not click start combat.")
            return False
        _sleep(1.5, stop_event)
        if stop_event.is_set():
            return False

        print(f"  → [{iteration}] Checking Cutscene...")
        # Cutscene before battle — guaranteed to appear, wait for it
        if _wait_and_click("skip_btn", timeout=10.0):
            print(f"  → [{iteration}] Skip button detected pre-combat.")
            logger.info("[main_quest] Skip button detected pre-combat.")
            _sleep(1.0, stop_event)
            _wait_and_click("skip_summary_btn", timeout=5.0)
            _sleep(1.0, stop_event)

        # Click attack button
        if not _click("attack_btn"):
            logger.error("[main_quest] Could not click attack button.")
            return False
        _sleep(2.0, stop_event)
        if stop_event.is_set():
            return False

        print(f"  → [{iteration}] Combat started — waiting for result...")

        # Step 3: Poll for combat completion
        deadline = time.time() + 300.0  # 5 minute timeout
        while time.time() < deadline:
            if stop_event.is_set():
                return False
            
            if _find("attack_btn"):
                logger.info("[main_quest] Attack button found.")
                _click("attack_btn", retries=1)
                _sleep(1.0, stop_event)

            # Mid-combat cutscene skip
            if _find("skip_btn"):
                logger.info("[main_quest] Skip button detected mid-combat.")
                _click("skip_btn", retries=1)
                _sleep(1.0, stop_event)
                if _find("skip_summary_btn"):
                    _click("skip_summary_btn", retries=1)
                    _sleep(1.0, stop_event)

            if _find("intim_btn"):
                logger.info("[main_quest] Skip button detected mid-combat.")
                _click("intim_btn", retries=1)
                _sleep(1.0, stop_event)
                if _find("ok_btn"):
                    _click("ok_btn", retries=1)
                    _sleep(1.0, stop_event)

            _dismiss_ok_if_present()

            if _find("release"):
                logger.info("[main_quest] Kamihime Released.")
                _click("release", retries=1)
                _sleep(1.0, stop_event)

            # Check for return button (quest complete without explicit result)
            if _find("return_to_quests_btn"):
                logger.info("[main_quest] Return button detected — quest complete.")
                break

            _sleep(combat_wait, stop_event)
        else:
            logger.warning("[main_quest] Timed out waiting for combat result.")
            print(f"  ✘ [{iteration}] Combat timed out.")
            return False

    else:
        # No support screen — might be a cutscene-only quest
        print(f"  → [{iteration}] No support screen — checking for cutscene...")
        logger.info("[main_quest] No support screen detected.")

        if _wait_and_click("ok_btn", timeout=5.0):
            logger.info("[main_quest] New quest detected.")
            _click("ok_btn", retries=1)

        # Try skipping cutscene
        _sleep(2.0, stop_event)
        if stop_event.is_set():
            return False

        if _find("skip_btn"):
            _click("skip_btn", retries=1)
            _sleep(1.0, stop_event)
            if _find("skip_summary_btn"):
                _click("skip_summary_btn", retries=1)
                _sleep(1.0, stop_event)

    if stop_event.is_set():
        return False

    # Step 4: Dismiss any OK popups (rewards, level up, etc.)
    _sleep(1.5, stop_event)
    _dismiss_ok_if_present()
    _sleep(1.5, stop_event)
    _dismiss_ok_if_present()  # sometimes multiple popups
    _sleep(1.5, stop_event)

    if stop_event.is_set():
        return False

    # Step 5: Click return to quests
    if _find("return_to_quests_btn"):
        _click("return_to_quests_btn", retries=3)
        _sleep(1.5, stop_event)

    _dismiss_ok_if_present()
        
    if _find("to_world_map_btn"):
        print(f"  ✔ [{iteration}] Quest iteration complete.")
        return True

# ── Public entry point ────────────────────────────────────────────────────

def run(stop_event: threading.Event):
    """Entry point matching app.py run(stop_event) contract."""
    logger.info("[main_quest] ════ Auto Main Quest started ════")
    print("  → Auto Main Quest started")

    max_iterations = get_main_quest_max_iterations()
    successes = 0
    failures = 0

    print(f"  → {max_iterations} iteration(s) planned.")

    if _is_cleared_in_region():
        print(f"  ✔ [{i}] Quest cleared — stopping early.")
        logger.info("[main_quest] Cleared stamp detected — exiting loop early.")
        return

    for i in range(1, max_iterations + 1):
        if stop_event.is_set():
            print("  → Stopped by user.")
            break

        print(f"  → Iteration {i}/{max_iterations}...")
        ok = _run_quest_iteration(i, stop_event)

        if ok:
            successes += 1
            if _is_cleared_in_region():
                print(f"  ✔ [{i}] Quest cleared — stopping early.")
                logger.info("[main_quest] Cleared stamp detected — exiting loop early.")
                break
        else:
            failures += 1
            if stop_event.is_set():
                break

        _sleep(get_poll_interval(), stop_event)

    print(f"  ✔ Auto Main Quest finished — {successes} success(es), {failures} failure(s).")


# ── Standalone test ───────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run(threading.Event())
