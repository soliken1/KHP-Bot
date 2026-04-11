"""
features/auto_epic_quest/quest_shop.py

Handles the shop flow entered from a quest entry.

Flow:
  Enter shop
    ├─ Shop empty?  → back → back → done
    └─ Shop not empty:
         └─ Click buy btn → click dropdown → select max qty → click buy → click ok
              └─ Repeat until buy btn is greyed/locked
                   → back → back → done
"""

import time
import threading
import logging

import numpy as np
import pyautogui

import features.auto_epic_quest.quest_states as qs
from config_loader import (
    get_poll_interval,
    get_shop_dropdown_scroll,
    get_shop_dropdown_last,
)

logger = logging.getLogger(__name__)

# Max purchase iterations per shop to prevent infinite loops
_MAX_BUY_ITERATIONS = 30


def _sleep(seconds: float, stop_event: threading.Event):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if stop_event.is_set():
            return
        time.sleep(min(0.2, deadline - time.time()))


def _is_shop_empty() -> bool:
    """True if the shop-empty indicator image is visible."""
    return qs.find("shop_empty") is not None


def _is_buy_locked() -> bool:
    """True if the buy/exchange button is in its greyed-out/locked state."""
    return qs.find("shop_buy_btn_locked") is not None


def _do_exit_shop() -> None:
    """Back out of shop → back to entry list."""
    logger.info("[shop] Exiting shop...")
    qs.click("entry_back_btn")   # shop → entry detail
    time.sleep(0.5)
    qs.click("entry_back_btn")   # entry detail → entry list
    time.sleep(0.5)


def _scroll_to_bottom(scroll_x: int, scroll_y: int, stop_event: threading.Event) -> bool:
    """
    Scroll the open dropdown until no visual change is detected (bottom reached).
    Returns True when at bottom, False if stopped.
    """
    region = (scroll_x - 100, scroll_y - 75, 200, 150)
    _MAX_SCROLL_ATTEMPTS = 20

    for _ in range(_MAX_SCROLL_ATTEMPTS):
        if stop_event.is_set():
            return False
        before = np.array(pyautogui.screenshot(region=region))
        pyautogui.scroll(-3, x=scroll_x, y=scroll_y)
        time.sleep(0.3)
        after = np.array(pyautogui.screenshot(region=region))
        if np.array_equal(before, after):
            logger.info("[shop] Dropdown scrolled to bottom.")
            return True

    logger.warning("[shop] Max scroll attempts reached — proceeding anyway.")
    return True


def _select_max_quantity(stop_event: threading.Event) -> bool:
    """
    After the dropdown is open:
      - If scrollbar image detected → scroll to bottom → click shop_dropdown_last coord
      - If no scrollbar → image-match rows 3, 2, 1 in order → click the last found (= max)
    Returns True on success.
    """
    # ── Scrollable dropdown (>3 items) ────────────────────────────────────
    if qs.find("dropdown_scrollbar") is not None:
        print("  ↕ Scrollbar detected — scrolling to bottom for max quantity.")

        scroll_x, scroll_y = get_shop_dropdown_scroll()
        if scroll_x == 0 and scroll_y == 0:
            logger.warning("[shop] shop_dropdown_scroll not calibrated.")
            return False

        if not _scroll_to_bottom(scroll_x, scroll_y, stop_event):
            return False
        if stop_event.is_set(): return False

        last_x, last_y = get_shop_dropdown_last()
        if last_x == 0 and last_y == 0:
            logger.warning("[shop] shop_dropdown_last not calibrated in config.yaml.")
            return False

        print(f"  ✔ Selecting max quantity (scrolled) at ({last_x}, {last_y})")
        qs.click_coords(last_x, last_y)
        time.sleep(0.3)
        return True

    # ── Non-scrollable dropdown (1–3 items) ───────────────────────────────
    # Check rows from bottom up — first match found is the max (lowest row = highest qty)
    print("  ↕ No scrollbar — checking visible rows.")

    for row_key in ("dropdown_row_3", "dropdown_row_2", "dropdown_row_1"):
        pt = qs.find(row_key)
        if pt is not None:
            print(f"  ✔ Selecting max quantity via {row_key} at {pt}")
            pyautogui.click(pt)
            time.sleep(0.3)
            return True

    logger.warning("[shop] No dropdown rows found — cannot select quantity.")
    return False


def _do_buy_cycle(stop_event: threading.Event) -> bool:
    """
    Execute one buy cycle:
      click buy → open dropdown → detect scroll → select max qty → confirm buy → ok
    Returns True if the cycle completed, False if something wasn't found.
    """
    # Step 1 — click the buy/exchange button
    if not qs.wait_and_click("shop_buy_btn", timeout=5.0):
        logger.warning("[shop] Buy button not found.")
        return False

    if stop_event.is_set(): return False

    # Step 2 — open the quantity dropdown
    if not qs.wait_and_click("shop_dropdown", timeout=5.0):
        logger.warning("[shop] Dropdown not found.")
        return False

    time.sleep(0.4)  # wait for dropdown animation
    if stop_event.is_set(): return False

    # Step 3 — detect scroll and select max quantity
    if not _select_max_quantity(stop_event):
        return False

    if stop_event.is_set(): return False

    # Step 4 — confirm with the Exchange button
    if not qs.wait_and_click("shop_exchange_btn", timeout=5.0):
        logger.warning("[shop] Exchange button not found.")
        return False

    if stop_event.is_set(): return False

    # Step 5 — dismiss ok dialog
    if not qs.wait_and_click("shop_ok_btn", timeout=5.0):
        logger.warning("[shop] Ok button not found after exchange.")
        return False

    _sleep(0.5, stop_event)
    return True


def run_shop_flow(stop_event: threading.Event) -> bool:
    """
    Main shop flow. Called after entering a quest entry.

    Returns True when done (whether shop was empty or fully bought out).
    Returns False if stop_event was set mid-flow.
    """
    logger.info("[shop] Entered shop flow.")

    if stop_event.is_set(): return False

    # ── Shop already empty ─────────────────────────────────────────────────
    if _is_shop_empty():
        logger.info("[shop] Shop is empty. Exiting.")
        _do_exit_shop()
        return True

    # ── Buy loop ───────────────────────────────────────────────────────────
    logger.info("[shop] Shop has items. Starting buy loop...")

    for i in range(1, _MAX_BUY_ITERATIONS + 1):
        if stop_event.is_set():
            return False

        # Check if buy button is now locked/greyed before attempting
        if _is_buy_locked():
            logger.info(f"[shop] Buy button locked after {i - 1} cycle(s). Done.")
            break

        logger.info(f"[shop] Buy cycle #{i}")
        success = _do_buy_cycle(stop_event)

        if stop_event.is_set():
            return False

        if not success:
            logger.warning("[shop] Buy cycle failed — exiting shop.")
            break

        _sleep(get_poll_interval(), stop_event)

        # Re-check empty state mid-loop (all items may be sold out now)
        if _is_shop_empty():
            logger.info("[shop] Shop became empty after purchase.")
            break

    else:
        logger.warning(f"[shop] Reached max buy iterations ({_MAX_BUY_ITERATIONS}).")

    _do_exit_shop()
    return not stop_event.is_set()