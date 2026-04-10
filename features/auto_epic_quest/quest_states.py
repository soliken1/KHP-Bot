"""
features/auto_epic_quest/quest_states.py

Image-detection helpers used by auto_epic_quest.py.
Each function returns a bool or a pyautogui Point/None.

Add your screenshot images to features/auto_epic_quest/images/
"""

import os
import time
import logging
import pyautogui

from config_loader import get_confidence, get_poll_interval

logger = logging.getLogger(__name__)

_DIR = os.path.dirname(__file__)

# ── Image asset registry ───────────────────────────────────────────────────
IMAGES = {
    # Entry list navigation
    "entry_back_btn":       os.path.join(_DIR, "images", "buttons/back_btn.png"),
    "entry_down_btn":       os.path.join(_DIR, "images", "buttons/entry_down_btn.png"),  # down arrow — next page
    "entry_shop_btn":       os.path.join(_DIR, "images", "buttons/entry_shop_btn.png"),

    # Post-quest flow
    "return_to_quest_btn":  os.path.join(_DIR, "images", "buttons/return_quest_btn.png"),
    "confirm_ok_btn":       os.path.join(_DIR, "images", "buttons/ok_btn.png"),

    # Quest list icons
    "first_clear_icon":     os.path.join(_DIR, "images", "icons/first_clear_icon.png"),
    "new_badge":            os.path.join(_DIR, "images", "icons/new_icon.png"),
    "cleared_badge":        os.path.join(_DIR, "images", "icons/clear_icon.png"),
    "beginner_raid_icon":   os.path.join(_DIR, "images", "icons/beginner_icon.png"),
    "standard_raid_icon":   os.path.join(_DIR, "images", "icons/standard_icon.png"),

    # Entry slot state — one shared locked icon (same appearance across all 3 slots)
    # Slot positions are coordinate-based (defined in config.yaml entry_slot_positions)
    "epic_quests_btn":      os.path.join(_DIR, "images", "buttons/epic_quests_btn.png"),
    "entry_locked":         os.path.join(_DIR, "images", "icons/entry_locked_icon.png"),

    # Shop states
    "shop_empty":           os.path.join(_DIR, "images", "icons/no_items_icon.png"),
    "shop_buy_btn":         os.path.join(_DIR, "images", "buttons/exchange_unlock_btn.png"),
    "shop_buy_btn_locked":  os.path.join(_DIR, "images", "buttons/exchange_lock_btn.png"),
    "shop_exchange_btn":    os.path.join(_DIR, "images", "buttons/shop_exchange_btn.png"),
    "shop_ok_btn":          os.path.join(_DIR, "images", "buttons/ok_btn.png"),

     # Dropdown — button to open it
    "shop_dropdown":        os.path.join(_DIR, "images", "buttons/shop_dropdown.png"),
 
    # Dropdown — scrollbar indicator (visible only when >3 items exist)
    "dropdown_scrollbar":   os.path.join(_DIR, "images", "icons/dropdown_scrollbar.png"),
 
    # Dropdown — row positions (image-matched, same style regardless of value)
    # Row 1 is topmost, row 3 is bottommost of the visible area
    "dropdown_row_1":       os.path.join(_DIR, "images", "icons/dropdown_row_1.png"),
    "dropdown_row_2":       os.path.join(_DIR, "images", "icons/dropdown_row_2.png"),
    "dropdown_row_3":       os.path.join(_DIR, "images", "icons/dropdown_row_3.png"),
}


# ── Low-level find helper ──────────────────────────────────────────────────

def find(image_key: str) -> pyautogui.Point | None:
    """Return center Point if image found on screen, else None."""
    path = IMAGES.get(image_key)
    if not path:
        logger.error(f"[quest_states] Unknown image key: '{image_key}'")
        return None
    if not os.path.exists(path):                                          
        logger.error(f"[quest_states] Image file missing: '{path}'")     
        print(f"  ✘ [{image_key}] IMAGE FILE MISSING: {path}")            
        return None                                                        
    try:
        loc = pyautogui.locateOnScreen(path, confidence=get_confidence())
        if loc:
            pt = pyautogui.center(loc)
            print(f"  ✔ [{image_key}] found at {pt} (conf ≥ {get_confidence()})")
            return pt
    except Exception as e:
        logger.debug(f"[quest_states] find '{image_key}': {e}")
    return None


def click(image_key: str, wait_after: float = 0.5) -> bool:
    """Find and click. Returns True on success."""
    pt = find(image_key)
    if pt:
        pyautogui.click(pt)
        logger.debug(f"[quest_states] Clicked '{image_key}' at {pt}")
        time.sleep(wait_after)
        return True
    return False


def click_coords(x: int, y: int, wait_after: float = 0.5) -> None:
    """Click at a fixed coordinate (used for entry slots and team slots)."""
    pyautogui.click(x, y)
    logger.debug(f"[quest_states] Clicked coords ({x}, {y})")
    time.sleep(wait_after)


def wait_and_click(image_key: str, timeout: float = 15.0, wait_after: float = 0.5) -> bool:
    """Poll until image appears then click it. Returns True on success."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if click(image_key, wait_after=wait_after):
            return True
        time.sleep(get_poll_interval())
    print(f"  ✘ [{image_key}] not found after {timeout}s")
    logger.warning(f"[quest_states] Timed out waiting for '{image_key}'")
    return False


# ── Quest state detectors ──────────────────────────────────────────────────

def is_first_clear_available() -> bool:
    return find("first_clear_icon") is not None

def has_new_badge() -> bool:
    return find("new_badge") is not None

def is_cleared() -> bool:
    return find("cleared_badge") is not None

def is_beginner_raid_active() -> bool:
    return find("beginner_raid_icon") is not None

def is_standard_raid_available() -> bool:
    return find("standard_raid_icon") is not None

def is_quest_list_visible() -> bool:
    return find("quest_btn") is not None

def is_entry_locked_at(x: int, y: int, row_height: int = 80, row_width: int = 400) -> bool:
    """
    Check if the entry_locked icon appears within the banner row at (x, y).
    Region spans the full width of the banner row so the lock icon on the
    left side of the row is always within the search area.
    row_height: half-height of the banner crop (80 = 160px tall region)
    row_width:  half-width of the banner crop (400 = 800px wide region)
    """
    region = (x - row_width, y - row_height, row_width * 2, row_height * 2)
    path = IMAGES.get("entry_locked")
    try:
        loc = pyautogui.locateOnScreen(path, confidence=get_confidence(), region=region)
        if loc is not None:
            print(f"  🔒 Entry at ({x},{y}) is locked — skipping.")
            return True
        print(f"  🔓 Entry at ({x},{y}) is unlocked — proceeding.")
        return False
    except Exception as e:
        logger.debug(f"[quest_states] is_entry_locked_at ({x},{y}): {e}")
        return False


# ── Reusable action sequences ──────────────────────────────────────────────

def do_skip_episode() -> bool:
    """Click Skip Episode → Skip Confirm."""
    if not wait_and_click("skip_episode_btn"):
        logger.warning("[quest_states] skip_episode_btn not found")
        return False
    if not wait_and_click("skip_confirm_btn"):
        logger.warning("[quest_states] skip_confirm_btn not found")
        return False
    return True

def do_return_to_quest() -> bool:
    """Click Return to Quest → Confirm Ok."""
    if not wait_and_click("return_to_quest_btn"):
        logger.warning("[quest_states] return_to_quest_btn not found")
        return False
    if not wait_and_click("confirm_ok_btn"):
        logger.warning("[quest_states] confirm_ok_btn not found")
        return False
    return True