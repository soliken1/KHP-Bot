"""
features/auto_combat/auto_combat.py

Handles a single combat session end-to-end:
  1. Select the configured team slot
  2. Start combat
  3. Wait for result
  4. Retry on failure up to config max_retries
  5. Return CombatResult to the caller

Used by auto_epic_quest.py — can also be run standalone for testing.
"""

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
    get_combat_max_retries,
    get_combat_wait,
)

logger = logging.getLogger(__name__)

# ── Image asset paths (relative to this file) ─────────────────────────────
import os
_DIR = os.path.dirname(__file__)

IMAGES = {
    # 7 support buttons — image matched (predictable, not dynamic)
    "support_btn":        os.path.join(_DIR, "images", "support_{slot}.png"),
    # 7 section tab buttons — image matched (predictable appearance)
    "team_section":       os.path.join(_DIR, "images", "section_{section}.png"),
    # combat flow
    "start_combat":       os.path.join(_DIR, "images", "start_combat.png"),
    "combat_result_win":  os.path.join(_DIR, "images", "combat_result_win.png"),
    "combat_result_loss": os.path.join(_DIR, "images", "combat_result_loss.png"),
    "combat_ok":          os.path.join(_DIR, "images", "combat_ok.png"),
    # team_slot is NOT here — slots use fixed coordinates from config, not image matching
}


# ── Result type ────────────────────────────────────────────────────────────

class CombatResult:
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"

    def __init__(self, status: str, attempts: int):
        self.status = status
        self.attempts = attempts
        self.success = status == self.SUCCESS

    def __repr__(self):
        return f"CombatResult(status={self.status}, attempts={self.attempts})"


# ── Helpers ────────────────────────────────────────────────────────────────

def _find(image_key: str, section: int = None, slot: int = None) -> pyautogui.Point | None:
    """Locate an image on screen. Returns center Point or None."""
    path = IMAGES[image_key]
    if section is not None:
        path = path.format(section=section)
    if slot is not None:
        path = path.format(slot=slot)
    try:
        loc = pyautogui.locateOnScreen(path, confidence=get_confidence())
        if loc:
            return pyautogui.center(loc)
    except Exception as e:
        logger.debug(f"[auto_combat] _find '{image_key}': {e}")
    return None


def _click(image_key: str, section: int = None, slot: int = None, retries: int = 5) -> bool:
    """Find and click an image. Returns True on success."""
    for _ in range(retries):
        pt = _find(image_key, section=section, slot=slot)
        if pt:
            pyautogui.click(pt)
            logger.debug(f"[auto_combat] Clicked '{image_key}' at {pt}")
            return True
        time.sleep(get_poll_interval())
    logger.warning(f"[auto_combat] Could not find '{image_key}' after {retries} tries")
    return False


def _wait_for_combat_result(stop_event: threading.Event, timeout: float = 60.0) -> str:
    """
    Poll until win or loss screen appears.
    Returns CombatResult.SUCCESS / FAILURE / TIMEOUT.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if stop_event.is_set():
            return CombatResult.TIMEOUT
        if _find("combat_result_win"):
            return CombatResult.SUCCESS
        if _find("combat_result_loss"):
            return CombatResult.FAILURE
        time.sleep(get_poll_interval())
    return CombatResult.TIMEOUT


# ── Main entry point ───────────────────────────────────────────────────────

def run_combat(max_retries: int = None, stop_event: threading.Event = None) -> CombatResult:
    """
    Execute a full combat session with retries.

    Args:
        max_retries:  Override config value if provided.
        stop_event:   threading.Event — checked at each step so Stop button works.

    Returns:
        CombatResult with .success bool and .attempts count.
    """
    if stop_event is None:
        stop_event = threading.Event()  # no-op event for standalone use
    if max_retries is None:
        max_retries = get_combat_max_retries()

    slot = get_team_slot()
    section = get_team_section()
    support_slot = get_support_slot()
    attempts = 0

    # Resolve slot coordinates once — fail early if not calibrated
    try:
        slot_x, slot_y = get_team_slot_position(slot)
    except ValueError as e:
        logger.error(f"[auto_combat] {e}")
        return CombatResult(CombatResult.FAILURE, 0)

    for attempt in range(1, max_retries + 2):
        if stop_event.is_set():
            logger.info("[auto_combat] Stop requested.")
            return CombatResult(CombatResult.FAILURE, attempts)

        attempts = attempt
        logger.info(f"[auto_combat] Attempt {attempt}/{max_retries + 1}")

        # 0. Click support unit (image-matched, before team selection)
        if support_slot > 0:
            if not _click("support_btn", slot=support_slot):
                logger.error(f"[auto_combat] Could not click support slot {support_slot}. Aborting.")
                return CombatResult(CombatResult.FAILURE, attempts)
            time.sleep(0.3)

        if stop_event.is_set(): return CombatResult(CombatResult.FAILURE, attempts)

        # 1. Click the section tab (image-matched)
        if not _click("team_section", section=section):
            logger.error(f"[auto_combat] Could not click section tab {section}. Aborting.")
            return CombatResult(CombatResult.FAILURE, attempts)

        time.sleep(0.3)

        if stop_event.is_set(): return CombatResult(CombatResult.FAILURE, attempts)

        # 2. Click the team slot by fixed coordinate
        logger.debug(f"[auto_combat] Clicking slot {slot} at ({slot_x}, {slot_y})")
        pyautogui.click(slot_x, slot_y)
        time.sleep(0.5)

        if stop_event.is_set(): return CombatResult(CombatResult.FAILURE, attempts)

        # 3. Start combat
        if not _click("start_combat"):
            logger.error("[auto_combat] Could not click Start Combat. Aborting.")
            return CombatResult(CombatResult.FAILURE, attempts)

        # 4. Wait for combat to play out
        logger.info(f"[auto_combat] Combat started. Waiting {get_combat_wait()}s...")
        time.sleep(get_combat_wait())

        if stop_event.is_set(): return CombatResult(CombatResult.FAILURE, attempts)

        # 5. Poll for result
        status = _wait_for_combat_result(stop_event)
        logger.info(f"[auto_combat] Result: {status}")

        # 6. Dismiss result screen
        _click("combat_ok")
        time.sleep(1.0)

        if status == CombatResult.SUCCESS:
            return CombatResult(CombatResult.SUCCESS, attempts)

        if status == CombatResult.TIMEOUT:
            logger.warning("[auto_combat] Timed out waiting for combat result.")
            return CombatResult(CombatResult.TIMEOUT, attempts)

        # FAILURE — retry if attempts remain
        if attempt <= max_retries:
            logger.info(f"[auto_combat] Failed. Retrying ({attempt}/{max_retries})...")
        else:
            logger.info("[auto_combat] Max retries reached.")

    return CombatResult(CombatResult.FAILURE, attempts)


# ── Standalone test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_combat()
    print(f"Combat finished: {result}")