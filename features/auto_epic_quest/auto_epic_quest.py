"""
features/auto_epic_quest/auto_epic_quest.py

Main orchestrator for the Auto Epic Quest feature.

Flow:
  Lock → Ok → Skip Episode → Skip Confirm → Quest List
    └─ Quest Loop:
         ├─ Find first-clear / not-cleared quest → click → skip → return
         ├─ Beginner Raid branch (config-gated, with retries)
         └─ Standard Raid branch (config-gated, iterates new entries)

stop_event (threading.Event) is threaded through every loop and wait
so the Stop button in the UI halts execution cleanly at the next checkpoint.
"""

import time
import threading
import logging

import features.auto_epic_quest.quest_states as qs
from features.auto_epic_quest.quest_shop import run_shop_flow
from features.auto_combat.auto_combat import run_combat, CombatResult
from config_loader import (
    get_poll_interval,
    get_max_quest_iterations,
    get_entry_slot_position,
    is_beginner_raid_enabled,
    should_retry_beginner_raid,
    get_beginner_raid_max_retries,
    is_standard_raid_enabled,
    get_standard_raid_max_retries,
)

logger = logging.getLogger(__name__)


# ── Stop-aware sleep ───────────────────────────────────────────────────────

def _sleep(seconds: float, stop_event: threading.Event):
    """Sleep in small increments so stop_event is checked frequently."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if stop_event.is_set():
            return
        time.sleep(min(0.2, deadline - time.time()))


# ── Entry flow ─────────────────────────────────────────────────────────────

def _do_entry_flow(stop_event: threading.Event) -> bool:
    if stop_event.is_set(): return False
    logger.info("[epic_quest] Starting entry flow...")

    # ── Already on the entry list screen? ─────────────────────────────────
    # Detect by checking if any entry slot or next-page button is visible.
    # This happens when the bot is started while the game is already on the
    # quest entry list (e.g. the screen shown in the screenshot).
    if _is_on_entry_list():
        logger.info("[epic_quest] Already on entry list — skipping entry flow.")
        print("  → Already on quest entry list. Skipping intro flow.")
        return True

    # ── Full intro flow ────────────────────────────────────────────────────
    if not qs.wait_and_click("lock_btn"):
        logger.error("[epic_quest] Lock button not found.")
        return False

    if stop_event.is_set(): return False
    if not qs.wait_and_click("ok_btn"):
        logger.error("[epic_quest] Ok button not found after Lock.")
        return False

    if stop_event.is_set(): return False
    if not qs.do_skip_episode():
        logger.warning("[epic_quest] Skip episode failed — may already be past it.")

    if stop_event.is_set(): return False
    if not qs.wait_and_click("quest_btn"):
        logger.error("[epic_quest] Quest button not found.")
        return False

    logger.info("[epic_quest] Quest list opened.")
    return True


def _is_on_entry_list() -> bool:
    """
    Returns True if the game is already showing the quest entry list screen.
    Checks for the next-page button OR any entry slot locked/unlocked indicator.
    """
    if qs.find("epic_quests_btn") is not None:
        return True
    if qs.find("entry_down_btn") is not None:
        return True
    if qs.find("entry_locked") is not None:
        return True
    return False


# ── Beginner Raid branch ───────────────────────────────────────────────────

def _handle_beginner_raid(stop_event: threading.Event) -> bool:
    if not is_beginner_raid_enabled():
        logger.info("[epic_quest] Beginner raid disabled in config. Skipping.")
        return True

    if stop_event.is_set(): return False
    logger.info("[epic_quest] Beginner raid detected. Starting combat...")

    max_retries = get_beginner_raid_max_retries() if should_retry_beginner_raid() else 0
    result = run_combat(max_retries=max_retries, stop_event=stop_event)

    if stop_event.is_set(): return False

    if result.success:
        logger.info(f"[epic_quest] Beginner raid cleared in {result.attempts} attempt(s).")
        return True

    if not should_retry_beginner_raid():
        logger.info("[epic_quest] Beginner raid failed. retry_on_failure=false — falling through.")
        return False

    logger.warning(f"[epic_quest] Beginner raid failed after {result.attempts} attempt(s).")
    return False


# ── Standard Raid branch ───────────────────────────────────────────────────

def _handle_standard_raid(stop_event: threading.Event) -> bool:
    if not is_standard_raid_enabled():
        logger.info("[epic_quest] Standard raid disabled in config. Skipping.")
        return True

    max_retries = get_standard_raid_max_retries()
    iteration = 0

    while not stop_event.is_set():
        iteration += 1
        logger.info(f"[epic_quest] Standard raid check #{iteration}")

        if not qs.is_standard_raid_available():
            logger.info("[epic_quest] No standard raid found.")
            break

        if not (qs.has_new_badge() or qs.is_first_clear_available()):
            logger.info("[epic_quest] No new/first-clear standard raid entries. Done.")
            break

        if not qs.wait_and_click("standard_raid_icon"):
            logger.warning("[epic_quest] Could not click standard raid icon.")
            break

        if stop_event.is_set(): break
        qs.do_skip_episode()

        if stop_event.is_set(): break
        if not qs.is_standard_raid_available():
            logger.info("[epic_quest] Standard raid no longer available after entry.")
            break

        logger.info("[epic_quest] Launching standard raid combat...")
        result = run_combat(max_retries=max_retries, stop_event=stop_event)

        if stop_event.is_set(): break

        if result.success:
            logger.info(f"[epic_quest] Standard raid cleared in {result.attempts} attempt(s).")
        else:
            logger.warning(f"[epic_quest] Standard raid failed: {result.status}")

        qs.do_return_to_quest()
        _sleep(get_poll_interval(), stop_event)

    return True


# ── Quest loop ─────────────────────────────────────────────────────────────

def _run_quest_loop(stop_event: threading.Event):
    max_iter = get_max_quest_iterations()

    for iteration in range(1, max_iter + 1):
        if stop_event.is_set():
            logger.info("[epic_quest] Stop requested — exiting quest loop.")
            break

        logger.info(f"[epic_quest] ── Quest loop iteration {iteration}/{max_iter} ──")
        _sleep(get_poll_interval(), stop_event)
        if stop_event.is_set(): break

        # ── Beginner raid ────────────────────────────────
        if qs.is_beginner_raid_active() and qs.is_first_clear_available():
            logger.info("[epic_quest] Beginner raid with first clear detected.")
            beginner_cleared = _handle_beginner_raid(stop_event)
            if stop_event.is_set(): break

            qs.do_return_to_quest()
            _sleep(get_poll_interval(), stop_event)

            if not beginner_cleared:
                logger.info("[epic_quest] Falling through to standard raid.")
                _handle_standard_raid(stop_event)
                break
            continue

        # ── Standard raid ────────────────────────────────
        if qs.is_standard_raid_available():
            _handle_standard_raid(stop_event)
            break

        # ── Regular quest ────────────────────────────────
        if qs.is_first_clear_available() or not qs.is_cleared():
            logger.info("[epic_quest] Uncleared quest found. Clicking...")
            if not qs.wait_and_click("first_clear_badge"):
                logger.warning("[epic_quest] Could not click first_clear_badge.")
                break

            if stop_event.is_set(): break
            qs.do_skip_episode()
            qs.do_return_to_quest()
            _sleep(get_poll_interval(), stop_event)
            continue

        logger.info("[epic_quest] No actionable quests found. Done.")
        break

    else:
        logger.warning(f"[epic_quest] Reached max quest iterations ({max_iter}).")



# ── Entry loop (per-page, 3 entries max, multi-page) ──────────────────────

# Entry positions are fixed coordinates (set in config.yaml entry_slot_positions).
# Locked state is detected by image-matching entry_locked.png near each coordinate.
# Entry 1 is always present. Entries 2 & 3 only exist on non-final pages.
_ENTRY_SLOT_INDICES = [1, 2, 3]


def _process_entry(slot: int, x: int, y: int, stop_event: threading.Event) -> bool:
    logger.info(f"[epic_quest] Processing entry slot {slot} at ({x}, {y})...")

    qs.click_coords(x, y)
    _sleep(0.5, stop_event)
    if stop_event.is_set(): return False

    if not qs.wait_and_click("entry_shop_btn", timeout=8.0):
        logger.warning(f"[epic_quest] Shop button not found for slot {slot}. Backing out.")
        qs.click("entry_back_btn")  # back to entry list from entry detail
        return not stop_event.is_set()

    if stop_event.is_set(): return False

    return run_shop_flow(stop_event)  # shop flow handles both backs on exit


def _run_entry_loop(stop_event: threading.Event):
    """
    Iterate all pages of entries.

    Per page:
      - Resolve each slot's coordinate from config
      - Image-match entry_locked near that coordinate — if locked, skip
      - If unlocked → click entry → click shop btn → shop flow
      - After all 3 slots → advance to next page if the next-page button exists

    Stops when no next-page button is found (last page done).
    """
    page = 1

    while not stop_event.is_set():
        logger.info(f"[epic_quest] ── Entry loop page {page} ──")

        for slot in _ENTRY_SLOT_INDICES:
            if stop_event.is_set(): return

            # Resolve coordinate — skip slot if not calibrated
            try:
                x, y = get_entry_slot_position(slot)
            except ValueError as e:
                logger.error(f"[epic_quest] {e}")
                continue

            # Check locked state near this slot's coordinate
            if qs.is_entry_locked_at(x, y):
                logger.info(f"[epic_quest] Slot {slot} is locked. Skipping.")
                continue

            # Unlocked — process
            if not _process_entry(slot, x, y, stop_event):
                return

            _sleep(get_poll_interval(), stop_event)

        if stop_event.is_set(): return

        # Advance to next page if available
        if qs.find("page_down_btn") is not None:
            logger.info("[epic_quest] Advancing to next page...")
            qs.click("page_down_btn")
            _sleep(get_poll_interval(), stop_event)
            page += 1
        else:
            logger.info("[epic_quest] No next page — all entries processed.")
            break


# ── Public entry point — matches app.py run(stop_event) contract ───────────

def run(stop_event: threading.Event):
    logger.info("[epic_quest] ════ Auto Epic Quest started ════")
    print("  → Auto Epic Quest started")

    if not _is_on_entry_list():
        print("  ✘ Not on entry list screen.")
        logger.error("[epic_quest] Entry list screen not detected. Aborting.")
        return

    print("  → Entry list detected.")

    # Phase 1 — process all entry shops
    _run_entry_loop(stop_event)

    if stop_event.is_set():
        print("  → Stopped during entry loop.")
        return

    # Phase 2 — always runs after entry loop completes
    print("  → Entry loop done. Proceeding to quest loop...")
    _run_quest_loop(stop_event)

    if stop_event.is_set():
        print("  → Stopped by user.")
    else:
        print("  ✔ Auto Epic Quest finished.")


# ── Standalone test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run(threading.Event())