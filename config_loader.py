"""
config_loader.py
Reads config/config.yaml and exposes typed access helpers.
Both auto_combat.py and auto_epic_quest.py import from here.
"""

import os
import yaml

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.yaml")
_config: dict = {}


def load_config(path: str = _CONFIG_PATH) -> dict:
    """Load and cache config from YAML. Call once at startup."""
    global _config
    with open(path, "r") as f:
        _config = yaml.safe_load(f)
    return _config


def get_config() -> dict:
    """Return the cached config. Loads from default path if not yet loaded."""
    if not _config:
        load_config()
    return _config


# ── Convenience accessors ──────────────────────────────────────────────────

def general() -> dict:
    return get_config().get("general", {})

def auto_combat_cfg() -> dict:
    return get_config().get("auto_combat", {})

def auto_epic_quest_cfg() -> dict:
    return get_config().get("auto_epic_quest", {})

def beginner_raid_cfg() -> dict:
    return auto_epic_quest_cfg().get("beginner_raid", {})

def standard_raid_cfg() -> dict:
    return auto_epic_quest_cfg().get("standard_raid", {})


# ── Typed getters ──────────────────────────────────────────────────────────

def get_confidence() -> float:
    return float(general().get("confidence", 0.85))

def get_poll_interval() -> float:
    return float(general().get("poll_interval", 1.5))

def get_support_slot() -> int:
    """Returns the support button to click (1–7). 0 means skip support selection."""
    return int(auto_combat_cfg().get("support_slot", 1))

def get_team_section() -> int:
    return int(auto_combat_cfg().get("team_section", 1))

def get_team_slot() -> int:
    return int(auto_combat_cfg().get("team_slot", 1))

def get_team_slot_position(slot: int) -> tuple[int, int]:
    """
    Returns the (x, y) screen coordinate for the given slot number (1–12).
    Raises ValueError if the slot is not defined or coordinates are still at default (0, 0).
    """
    positions = auto_combat_cfg().get("team_slot_positions", {})
    entry = positions.get(slot)
    if not entry:
        raise ValueError(f"team_slot_positions[{slot}] is not defined in config.yaml")
    x, y = int(entry["x"]), int(entry["y"])
    if x == 0 and y == 0:
        raise ValueError(
            f"team_slot_positions[{slot}] is still at (0, 0) — "
            f"please calibrate the coordinates in config.yaml"
        )
    return x, y

def get_combat_max_retries() -> int:
    return int(auto_combat_cfg().get("max_retries", 3))

def get_combat_wait() -> float:
    return float(auto_combat_cfg().get("combat_wait", 5.0))

def is_auto_combat_enabled() -> bool:
    return bool(auto_combat_cfg().get("enabled", True))

def is_auto_quest_enabled() -> bool:
    return bool(auto_epic_quest_cfg().get("enabled", True))

def is_beginner_raid_enabled() -> bool:
    return bool(beginner_raid_cfg().get("enabled", True))

def should_retry_beginner_raid() -> bool:
    return bool(beginner_raid_cfg().get("retry_on_failure", True))

def get_beginner_raid_max_retries() -> int:
    return int(beginner_raid_cfg().get("max_retries", 2))

def is_standard_raid_enabled() -> bool:
    return bool(standard_raid_cfg().get("enabled", True))

def get_standard_raid_max_retries() -> int:
    return int(standard_raid_cfg().get("max_retries", 3))

def get_max_quest_iterations() -> int:
    return int(auto_epic_quest_cfg().get("max_quest_iterations", 20))

def get_shop_dropdown_scroll() -> tuple[int, int]:
    """(x, y) to scroll within the open dropdown list."""
    cfg = auto_epic_quest_cfg().get("shop_dropdown_scroll", {})
    return int(cfg.get("x", 0)), int(cfg.get("y", 0))

def get_shop_dropdown_last() -> tuple[int, int]:
    """(x, y) of the bottom-most dropdown item after scrolling to the end."""
    cfg = auto_epic_quest_cfg().get("shop_dropdown_last", {})
    return int(cfg.get("x", 0)), int(cfg.get("y", 0))

def get_entry_slot_position(slot: int) -> tuple[int, int]:
    """
    Returns the (x, y) coordinate for the given entry slot (1–3).
    Raises ValueError if not defined or still at default (0, 0).
    """
    positions = auto_epic_quest_cfg().get("entry_slot_positions", {})
    entry = positions.get(slot)
    if not entry:
        raise ValueError(f"entry_slot_positions[{slot}] is not defined in config.yaml")
    x, y = int(entry["x"]), int(entry["y"])
    if x == 0 and y == 0:
        raise ValueError(
            f"entry_slot_positions[{slot}] is still at (0, 0) — "
            f"please calibrate the coordinates in config.yaml"
        )
    return x, y

def get_combat_max_attempts() -> int:
    return int(auto_combat_cfg().get("max_attempts", 1))

def get_team_section_position(section: int) -> tuple[int, int]:
    positions = auto_combat_cfg().get("team_section_positions", {})
    entry = positions.get(section)
    if not entry:
        raise ValueError(f"team_section_positions[{section}] is not defined in config.yaml")
    x, y = int(entry["x"]), int(entry["y"])
    if x == 0 and y == 0:
        raise ValueError(
            f"team_section_positions[{section}] is still at (0, 0) — "
            f"please calibrate the coordinates in config.yaml"
        )
    return x, y