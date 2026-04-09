import cv2
import numpy as np
import pyautogui
from config import CONFIDENCE_THRESHOLD, REGION, resource_path

def capture_screen():
    screenshot = pyautogui.screenshot(region=REGION)
    return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

def find_state(template_path, threshold=CONFIDENCE_THRESHOLD):
    """
    Returns (center_x, center_y, confidence) if found, else None
    """
    screen = capture_screen()
    template = cv2.imread(resource_path(template_path)) 

    if template is None:
        raise FileNotFoundError(f"Template not found: {template_path}")

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= threshold:
        h, w = template.shape[:2]
        cx = max_loc[0] + w // 2
        cy = max_loc[1] + h // 2

        # Offset if using a region
        if REGION:
            cx += REGION[0]
            cy += REGION[1]

        return (cx, cy, max_val)
    
    return None

def find_all_states(template_path, threshold=CONFIDENCE_THRESHOLD):
    """
    Returns a list of all matches sorted left-to-right, top-to-bottom.
    Each entry is (center_x, center_y, confidence)
    """
    screen = capture_screen()
    template = cv2.imread(resource_path(template_path))

    if template is None:
        raise FileNotFoundError(f"Template not found: {template_path}")

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    h, w = template.shape[:2]

    # Find all locations above threshold
    locations = np.where(result >= threshold)
    matches = []

    for pt in zip(*locations[::-1]):  # x, y
        cx = pt[0] + w // 2
        cy = pt[1] + h // 2

        if REGION:
            cx += REGION[0]
            cy += REGION[1]

        confidence = result[pt[1], pt[0]]
        matches.append((cx, cy, float(confidence)))

    # Deduplicate nearby matches (same button found multiple times)
    matches = deduplicate_matches(matches, min_distance=20)

    # Sort top-to-bottom, then left-to-right
    matches.sort(key=lambda m: (m[1], m[0]))

    return matches  # [EP1, EP2, ...]

def deduplicate_matches(matches, min_distance=20):
    """Removes duplicate detections that are too close to each other."""
    filtered = []
    for match in matches:
        too_close = False
        for kept in filtered:
            dist = ((match[0] - kept[0])**2 + (match[1] - kept[1])**2) ** 0.5
            if dist < min_distance:
                too_close = True
                break
        if not too_close:
            filtered.append(match)
    return filtered