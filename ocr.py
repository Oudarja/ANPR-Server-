# -------------------------------------pytesseract---------------------------------
# import os
# import re
# from datetime import datetime

# import cv2
# import numpy as np
# import pytesseract




# def _timestamp_roi(image):
#     h, w = image.shape[:2]
#     # print(f"Frame dimensions: {w}x{h} px — extracting top-left region for timestamp")
#     return image[0:int(h * 0.1), 0:int(w * 0.30)]



# def _preprocess_timestamp(roi):
#     gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

#     results = []

#     # Strategy 1: fixed threshold at 140
#     _, mask1 = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
#     results.append(mask1)

#     # Strategy 2: Otsu auto threshold (adapts to each frame's brightness)
#     _, mask2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

#     results.append(mask2)

#     # Strategy 3: invert Otsu (for dark text on light background)
#     _, mask3 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
#     results.append(mask3)

#     # Strategy 4: CLAHE + Otsu (handles uneven lighting)
#     clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
#     enhanced = clahe.apply(gray)
#     _, mask4 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
#     results.append(mask4)

#     return results   # return all 4, try each





# def _upscale(mask):
#     return cv2.resize(mask, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

# def _extract_parts(text):
#     cleaned = re.sub(r"\s+", " ", text).strip()
#     cleaned = cleaned.replace("O", "0").replace("o", "0")
#     cleaned = cleaned.replace(";", ":").replace(",", "/")

#     cleaned = re.sub(r"(\d{2})[:;](\d{2})\s(\d{2})", r"\1:\2:\3", cleaned)
#     cleaned = re.sub(r"(\d{2})\s[/\-]\s(\d{2})\s[/\-]\s(\d{4})", r"\1/\2/\3", cleaned)

#     print("CLEANED OCR:", repr(cleaned))

#     match = re.search(
#         r"(\d{2})[/\-](\d{2})[/\-](\d{4})[\s]*(\d{2})[:;](\d{2})[:;](\d{2})",
#         cleaned,
#     )
#     if not match:
#         return None

#     _, _, _, hour, minute, second = match.groups()   # date parts ignored

#     date_text = datetime.now().strftime("%Y-%m-%d")  # always use current date
#     time_text  = f"{hour}:{minute}:{second}"

#     try:
#         datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M:%S")
#     except ValueError:
#         return None

#     return date_text, time_text

# def find_date_time(image):
#     roi = _timestamp_roi(image)
#     masks = _preprocess_timestamp(roi)

#     config = "--psm 6 -c tessedit_char_whitelist=0123456789/:- "

#     for i, mask in enumerate(masks):
#         upscaled = _upscale(mask)

#         if os.environ.get("OCR_DEBUG") == "1":
#             cv2.imshow(f"OCR mask strategy {i+1}", upscaled)
#             cv2.waitKey(0)

#         text = pytesseract.image_to_string(upscaled, config=config)
#         print(f"[Strategy {i+1}] RAW OCR: {repr(text)}")

#         parts = _extract_parts(text)
#         if parts:
#             print(f"[Strategy {i+1}] SUCCESS: {parts}")
#             return parts

#     print("[WARN] All strategies failed — falling back to now()")
#     now = datetime.now()
#     return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")


# --------------------------------easy ocr----------------------------
import os
import re
from datetime import datetime
import cv2
import easyocr
import numpy as np

# Initialise once at module level — loading the model on every call is slow
_reader = easyocr.Reader(["en"], gpu=False, verbose=False)


def _timestamp_roi(image):
    h, w = image.shape[:2]
    return image[0:int(h * 0.1), 0:int(w * 0.30)]


def _preprocess_timestamp(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    results = []

    # Strategy 1: fixed threshold at 140
    _, mask1 = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
    results.append(mask1)

    # Strategy 2: Otsu auto threshold
    _, mask2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results.append(mask2)

    # Strategy 3: invert Otsu
    _, mask3 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    results.append(mask3)

    # Strategy 4: CLAHE + Otsu
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)
    _, mask4 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results.append(mask4)

    return results


def _upscale(mask):
    return cv2.resize(mask, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)


def _extract_parts(text):
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = cleaned.replace("O", "0").replace("o", "0")
    cleaned = cleaned.replace(";", ":").replace(",", "/")

    cleaned = re.sub(r"(\d{2})[:;](\d{2})\s(\d{2})", r"\1:\2:\3", cleaned)
    cleaned = re.sub(r"(\d{2})\s[/\-]\s(\d{2})\s[/\-]\s(\d{4})", r"\1/\2/\3", cleaned)

    print("CLEANED OCR:", repr(cleaned))

    match = re.search(
        r"(\d{2})[/\-](\d{2})[/\-](\d{4})[\s]*(\d{2})[:;](\d{2})[:;](\d{2})",
        cleaned,
    )
    if not match:
        return None

    _, _, _, hour, minute, second = match.groups()

    date_text = datetime.now().strftime("%Y-%m-%d")
    time_text  = f"{hour}:{minute}:{second}"

    try:
        datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    return date_text, time_text


def find_date_time(image):
    roi   = _timestamp_roi(image)
    masks = _preprocess_timestamp(roi)

    for i, mask in enumerate(masks):
        upscaled = _upscale(mask)

        if os.environ.get("OCR_DEBUG") == "1":
            cv2.imshow(f"OCR mask strategy {i+1}", upscaled)
            cv2.waitKey(0)

        # EasyOCR replacement — allowlist = same restriction as Tesseract whitelist
        detections = _reader.readtext(
            upscaled,
            allowlist="0123456789/:-",
            detail=1,
            paragraph=False,
        )
        # Sort left-to-right and join — EasyOCR may split the timestamp into fragments
        detections.sort(key=lambda r: r[0][0][0])
        text = " ".join(r[1] for r in detections)

        print(f"[Strategy {i+1}] RAW OCR: {repr(text)}")

        parts = _extract_parts(text)
        if parts:
            print(f"[Strategy {i+1}] SUCCESS: {parts}")
            return parts

    print("[WARN] All strategies failed — falling back to now()")
    # return null
    return None,None


# ------------------------------TrOcr-------------------------------

# import os
# import re
# from datetime import datetime

# import cv2
# import numpy as np
# from PIL import Image
# from transformers import TrOCRProcessor, VisionEncoderDecoderModel

# # ── Model — initialise once at module level ───────────────────────────────────
# # printed/handwritten small: microsoft/trocr-small-printed
# # printed large (more accurate): microsoft/trocr-large-printed
# _processor = TrOCRProcessor.from_pretrained("microsoft/trocr-small-printed")
# _model     = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-small-printed")


# def _timestamp_roi(image):
#     h, w = image.shape[:2]
#     return image[0:int(h * 0.1), 0:int(w * 0.30)]


# def _preprocess_timestamp(roi):
#     gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

#     results = []

#     # Strategy 1: fixed threshold at 140
#     _, mask1 = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY)
#     results.append(mask1)

#     # Strategy 2: Otsu auto threshold
#     _, mask2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
#     results.append(mask2)

#     # Strategy 3: invert Otsu
#     _, mask3 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
#     results.append(mask3)

#     # Strategy 4: CLAHE + Otsu
#     clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
#     enhanced = clahe.apply(gray)
#     _, mask4 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
#     results.append(mask4)

#     return results


# def _upscale(mask):
#     return cv2.resize(mask, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)


# def _extract_parts(text):
#     cleaned = re.sub(r"\s+", " ", text).strip()
#     cleaned = cleaned.replace("O", "0").replace("o", "0")
#     cleaned = cleaned.replace(";", ":").replace(",", "/")

#     cleaned = re.sub(r"(\d{2})[:;](\d{2})\s(\d{2})", r"\1:\2:\3", cleaned)
#     cleaned = re.sub(r"(\d{2})\s[/\-]\s(\d{2})\s[/\-]\s(\d{4})", r"\1/\2/\3", cleaned)

#     print("CLEANED OCR:", repr(cleaned))

#     match = re.search(
#         r"(\d{2})[/\-](\d{2})[/\-](\d{4})[\s]*(\d{2})[:;](\d{2})[:;](\d{2})",
#         cleaned,
#     )
#     if not match:
#         return None

#     _, _, _, hour, minute, second = match.groups()

#     date_text = datetime.now().strftime("%Y-%m-%d")
#     time_text  = f"{hour}:{minute}:{second}"

#     try:
#         datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M:%S")
#     except ValueError:
#         return None

#     return date_text, time_text


# def _trocr_read(mask) -> str:
#     """Convert a grayscale mask to RGB PIL Image and run TrOCR."""
#     # TrOCR expects RGB — convert grayscale mask to 3-channel
#     rgb = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
#     pil_image = Image.fromarray(rgb)

#     pixel_values = _processor(images=pil_image, return_tensors="pt").pixel_values
#     generated_ids = _model.generate(pixel_values)
#     text = _processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
#     return text


# def find_date_time(image):
#     roi   = _timestamp_roi(image)
#     masks = _preprocess_timestamp(roi)

#     for i, mask in enumerate(masks):
#         upscaled = _upscale(mask)

#         if os.environ.get("OCR_DEBUG") == "1":
#             cv2.imshow(f"OCR mask strategy {i+1}", upscaled)
#             cv2.waitKey(0)

#         text = _trocr_read(upscaled)
#         print(f"[Strategy {i+1}] RAW OCR: {repr(text)}")

#         parts = _extract_parts(text)
#         if parts:
#             print(f"[Strategy {i+1}] SUCCESS: {parts}")
#             return parts

#     print("[WARN] All strategies failed — falling back to now()")
#     now = datetime.now()
#     return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")