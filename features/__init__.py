from features.skip_episodes import run as skip_episodes
from features.auto_epic_quest import run as auto_epic_quest

# Register features here — name shows in the UI dropdown
FEATURES = {
    "Skip Episode Bot":    skip_episodes,
    # "Auto Epic Quest":      auto_epic_quest,
    # "Feature C":    run_feature_c,
}