import sys
import os

CONFIDENCE_THRESHOLD = 0.90
CLICK_DELAY = 1        # wait after each click
SCAN_TIMEOUT = 10        # seconds to wait per button before giving up
MAX_RETRIES = 5
REGION = None            # set to (x, y, w, h) to limit scan area

def resource_path(relative_path):
    """Gets the correct path whether running as script or .exe"""
    if hasattr(sys, '_MEIPASS'):
        # Running as bundled .exe
        return os.path.join(sys._MEIPASS, relative_path)
    # Running as normal script
    return os.path.join(os.path.dirname(__file__), relative_path)

