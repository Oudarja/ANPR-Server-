import os
import re
from datetime import datetime

import cv2
import numpy as np
import pytesseract


def _timestamp_roi(image):
    h, w = image.shape[:2]
    print(f"Frame dimensions: {w}x{h} px — extracting top-left region for timestamp")
    return image[0:int(h * 0.07), 0:int(w * 0.25)]

# def _timestamp_roi(image):
#     h, w = image.shape[:2]
#     return image[0:int(h * 0.0417), 0:int(w * 0.1172)]


def _preprocess_timestamp(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    results = []

    # Strategy 1: fixed threshold at 140
    _, mask1 = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
    results.append(mask1)

    # Strategy 2: Otsu auto threshold (adapts to each frame's brightness)
    _, mask2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results.append(mask2)

    # Strategy 3: invert Otsu (for dark text on light background)
    _, mask3 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    results.append(mask3)

    # Strategy 4: CLAHE + Otsu (handles uneven lighting)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)
    _, mask4 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results.append(mask4)

    return results   # return all 4, try each


def _upscale(mask):
    return cv2.resize(mask, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

def _extract_parts(text):
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = cleaned.replace("O", "0").replace("o", "0")
    cleaned = cleaned.replace(";", ":").replace(",", "/")

    # ── NEW: collapse spaces between digit pairs that look like time ──
    # turns "13:50 44" → "13:50:44"
    cleaned = re.sub(r"(\d{2})[:;](\d{2})\s(\d{2})", r"\1:\2:\3", cleaned)
    # also fix date with spaces: "15 /06/2026" → "15/06/2026"
    cleaned = re.sub(r"(\d{2})\s[/\-]\s(\d{2})\s[/\-]\s(\d{4})", r"\1/\2/\3", cleaned)

    print("CLEANED OCR:", repr(cleaned))

    match = re.search(
        r"(\d{2})[/\-](\d{2})[/\-](\d{4})[\s]*(\d{2})[:;](\d{2})[:;](\d{2})",
        cleaned,
    )
    if not match:
        return None

    day, month, year, hour, minute, second = match.groups()
    date_text = f"{year}-{month}-{day}"
    time_text  = f"{hour}:{minute}:{second}"

    try:
        datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    return date_text, time_text

def find_date_time(image):
    roi = _timestamp_roi(image)
    masks = _preprocess_timestamp(roi)

    config = "--psm 6 -c tessedit_char_whitelist=0123456789/:- "

    for i, mask in enumerate(masks):
        upscaled = _upscale(mask)

        if os.environ.get("OCR_DEBUG") == "1":
            cv2.imshow(f"OCR mask strategy {i+1}", upscaled)
            cv2.waitKey(0)

        text = pytesseract.image_to_string(upscaled, config=config)
        print(f"[Strategy {i+1}] RAW OCR: {repr(text)}")

        parts = _extract_parts(text)
        if parts:
            print(f"[Strategy {i+1}] SUCCESS: {parts}")
            return parts

    print("[WARN] All strategies failed — falling back to now()")
    now = datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")