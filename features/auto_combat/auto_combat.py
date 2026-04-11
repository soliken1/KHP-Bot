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
    get_combat_max_retries,
    get_combat_wait,
    get_team_section_position,
    get_combat_max_attempts
)

logger = logging.getLogger(__name__)

# ── Image asset paths (relative to this file) ─────────────────────────────
def _get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "features", "auto_combat")
    return os.path.dirname(os.path.abspath(__file__))

_DIR = _get_base_dir()

IMAGES = {
    "support_btn":        os.path.join(_DIR, "images", "icon/{slot}_element_icon.png"),
    "click_support":      os.path.join(_DIR, "images", "icon/my_support_icon.png"),
    
    "start_combat":       os.path.join(_DIR, "images", "button/go_to_quest_btn.png"),
    "start_attack":       os.path.join(_DIR, "images", "button/attack_btn.png"),
    "next_btn":           os.path.join(_DIR, "images", "button/next_btn.png"),
    "retry_btn":          os.path.join(_DIR, "images", "button/retry_btn.png"),
    "ok_btn":             os.path.join(_DIR, "images", "button/ok_btn.png"),
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

def _wait_for_combat_result(stop_event: threading.Event, timeout: float = 300.0) -> str:
    """
    Poll every 1s for combat end indicators:
      - next_btn  → battle won (SUCCESS)
      - retry_btn → battle lost (FAILURE)
    Returns CombatResult.SUCCESS / FAILURE / TIMEOUT.
    """
    logger.info("[auto_combat] Waiting for combat result (polling every 1s)...")
    deadline = time.time() + timeout

    while time.time() < deadline:
        if stop_event.is_set():
            return CombatResult.TIMEOUT

        if _find("next_btn"):
            logger.info("[auto_combat] next_btn detected — battle won.")
            return CombatResult.SUCCESS

        if _find("retry_btn"):
            logger.info("[auto_combat] retry_btn detected — battle lost.")
            return CombatResult.FAILURE

        time.sleep(1.0)  # check every 1 second

    logger.warning("[auto_combat] Timed out waiting for combat result.")
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
        section_x, section_y = get_team_section_position(section)
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
        
        if not _click("click_support"):
            logger.error(f"[auto_combat] Could not click support. Aborting.")
            return CombatResult(CombatResult.FAILURE, attempts)
        time.sleep(0.3)

        if stop_event.is_set(): return CombatResult(CombatResult.FAILURE, attempts)

        # 1. Click the section tab by fixed coordinate
        logger.debug(f"[auto_combat] Clicking section {section} at ({section_x}, {section_y})")
        pyautogui.click(section_x, section_y)
        time.sleep(0.5)

        if stop_event.is_set(): return CombatResult(CombatResult.FAILURE, attempts)

        # 2. Click the team slot by fixed coordinate
        logger.debug(f"[auto_combat] Clicking slot {slot} at ({slot_x}, {slot_y})")
        pyautogui.click(slot_x, slot_y)
        time.sleep(0.5)

        if stop_event.is_set(): return CombatResult(CombatResult.FAILURE, attempts)

        # 3. Start combat
        if not _click("start_combat"):
            logger.error("[auto_combat] Could not click Start Combat. Aborting.")
        time.sleep(1.5)

        # Perform Attack
        if not _click("start_attack"):
            logger.error("[auto_combat] Could not click Attack. Aborting.")
            return CombatResult(CombatResult.FAILURE, attempts)

       # 4. Brief buffer then poll for result
        logger.info("[auto_combat] Combat started. Polling for result...")
        time.sleep(2.0)  # short buffer for combat to start before polling begins

        if stop_event.is_set(): return CombatResult(CombatResult.FAILURE, attempts)

        # 5. Poll for result
        status = _wait_for_combat_result(stop_event)
        logger.info(f"[auto_combat] Result: {status}")

       # 6. Dismiss result and click retry to loop back to support screen
        if status == CombatResult.SUCCESS:
            _click("next_btn")   # advance past win screen to retry_btn
            time.sleep(1.5)
            _click("ok_btn")     # optional first-clear reward — skipped if not found
            time.sleep(0.5)
            _click("retry_btn")  # back to support screen for next attempt or exit
            time.sleep(1.0)
            return CombatResult(CombatResult.SUCCESS, attempts)

        if status == CombatResult.TIMEOUT:
            logger.warning("[auto_combat] Timed out waiting for combat result.")
            return CombatResult(CombatResult.TIMEOUT, attempts)

        # FAILURE — click retry_btn to return to support selection screen, then loop
        if attempt <= max_retries:
            logger.info(f"[auto_combat] Failed. Clicking retry ({attempt}/{max_retries})...")
            if not _click("retry_btn"):
                logger.warning("[auto_combat] Could not click retry_btn — aborting retries.")
                return CombatResult(CombatResult.FAILURE, attempts)
            time.sleep(1.0)
        else:
            logger.info("[auto_combat] Max retries reached.")
            _click("retry_btn")  # still need to exit the result screen cleanly
            time.sleep(1.0)

    return CombatResult(CombatResult.FAILURE, attempts)

def run(stop_event: threading.Event = None):
    """Entry point matching app.py run(stop_event) contract."""
    if stop_event is None:
        stop_event = threading.Event()

    max_attempts = get_combat_max_attempts()
    wins = 0
    losses = 0

    print(f"  → Auto Combat started — {max_attempts} attempt(s) planned.")

    for i in range(1, max_attempts + 1):
        if stop_event.is_set():
            print("  → Stopped by user.")
            break

        print(f"  → Run {i}/{max_attempts}...")
        result = run_combat(stop_event=stop_event)

        if result.success:
            wins += 1
            print(f"  ✔ Run {i} — Win ({wins}W/{losses}L)")
        elif result.status == CombatResult.TIMEOUT:
            print(f"  ✘ Run {i} — Timeout. Stopping.")
            break
        else:
            losses += 1
            print(f"  ✘ Run {i} — Loss ({wins}W/{losses}L)")

    print(f"  ✔ Auto Combat finished — {wins} win(s), {losses} loss(es) out of {i} run(s).")

# ── Standalone test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_combat()
    print(f"Combat finished: {result}")