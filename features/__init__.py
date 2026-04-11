from features.skip_episodes.skip_episodes import run as skip_episodes
from features.auto_epic_quest.auto_epic_quest import run as auto_epic_quest
from features.auto_combat.auto_combat import run as auto_combat
# Register features here — name shows in the UI dropdown
FEATURES = {
    "Skip Episode Bot":    skip_episodes,
    "Auto Epic Quest":     auto_epic_quest,
    "Auto Combat":         auto_combat
}