


# =====================================================
# helpers.py — Helper functions (multi-camera compatible)
# =====================================================

import cv2
import time
import numpy as np
from config import LICENSE_TYPE_MAP

# ashraf.pt model এর city/division class নাম
CITY_NAMES = {'dhaka', 'chattogram', 'khulna', 'jashore', 'metro'}


# =====================================================
def is_same_plate(img1, img2, th=0.15):
    a = cv2.resize(img1, (64, 32))
    b = cv2.resize(img2, (64, 32))
    return np.mean(cv2.absdiff(a, b)) / 255.0 < th


# =====================================================
def find_best_plate_for_vehicle(vehicle_box, plate_boxes, frame):
    vx1, vy1, vx2, vy2 = vehicle_box
    vw   = max(vx2 - vx1, 1)
    vh   = max(vy2 - vy1, 1)
    vcx  = (vx1 + vx2) / 2
    vcy  = (vy1 + vy2) / 2
    diag = np.sqrt(vw**2 + vh**2)

    best_crop, best_score = None, 0.0

    for (px1, py1, px2, py2, pconf) in plate_boxes:
        pw = px2 - px1
        ph = py2 - py1

        inter_x1 = max(px1, vx1); inter_y1 = max(py1, vy1)
        inter_x2 = min(px2, vx2); inter_y2 = min(py2, vy2)
        inter_w  = max(inter_x2 - inter_x1, 0)
        inter_h  = max(inter_y2 - inter_y1, 0)
        overlap_ratio = (inter_w * inter_h) / max(pw * ph, 1)

        if overlap_ratio < 0.60:
            continue

        pcx = (px1 + px2) / 2
        pcy = (py1 + py2) / 2
        dist          = np.sqrt((pcx - vcx)**2 + (pcy - vcy)**2)
        norm_dist     = dist / diag
        position_bonus = 1.0 if pcy > (vy1 + vh * 0.4) else 0.7
        score = pconf * (1.0 - min(norm_dist, 1.0)) * overlap_ratio * position_bonus

        if score > best_score:
            crop = frame[py1:py2, px1:px2]
            if crop.size == 0:
                continue
            best_crop  = crop.copy()
            best_score = score

    return best_crop, best_score


# =====================================================
def _preprocess_plate(crop):
    """৪টা variant — different conditions এ ভালো result দেবে।"""
    h, w  = crop.shape[:2]
    scale = 120 / max(h, 1)
    base  = cv2.resize(crop, (max(int(w * scale), 1), 120),
                       interpolation=cv2.INTER_CUBIC)

    kernel   = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]], dtype=np.float32)
    sharp    = cv2.filter2D(base, -1, kernel)
    gray     = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    clahe    = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4))
    eq3      = cv2.cvtColor(clahe.apply(gray), cv2.COLOR_GRAY2BGR)
    sharp_eq = cv2.filter2D(eq3, -1, kernel)

    return [base, sharp, eq3, sharp_eq]


# =====================================================
def _parse_one_result(result, crop_h):
    """
    একটা YOLO result থেকে:
      digits  → নিচের row (sorted x)
      texts   → উপরের row city + নিচের row series letter (sorted x)

    Returns: (digits_list, texts_list)
    e.g. (['5','6','6','4','7','2'], ['dhaka','metro','gha'])
    """
    names = result.names
    boxes = result.boxes.xyxy.tolist()
    clses = result.boxes.cls.tolist()
    confs = result.boxes.conf.tolist()

    if not boxes:
        return [], []

    dets = []
    for box, cls, conf in zip(boxes, clses, confs):
        x1, y1, x2, y2 = box
        name = names[int(cls)]
        if name == "License Plate":
            continue
        dets.append({
            "name":     name,
            "x":        x1,
            "y_cen":    (y1 + y2) / 2,
            "conf":     conf,
            "is_digit": name.isdigit(),
        })

    digit_dets = [d for d in dets if d["is_digit"]]
    text_dets  = [d for d in dets if not d["is_digit"]]

    if not digit_dets:
        return [], [d["name"] for d in sorted(text_dets, key=lambda d: d["x"])]

    # Digit row baseline
    digit_baseline = sorted(d["y_cen"] for d in digit_dets)[len(digit_dets) // 2]
    gap = crop_h * 0.20

    # Text গুলো উপরে/নিচে ভাগ করো
    top_texts = [d for d in text_dets if d["y_cen"] < digit_baseline - gap]
    bot_texts = [d for d in text_dets if d["y_cen"] >= digit_baseline - gap]

    # Duplicate বাদ — same name থেকে high conf রাখো
    def dedup(lst):
        seen, out = set(), []
        for d in sorted(lst, key=lambda d: -d["conf"]):
            if d["name"] not in seen:
                seen.add(d["name"])
                out.append(d)
        return out

    top_sorted = sorted(dedup(top_texts), key=lambda d: d["x"])
    bot_sorted = sorted(dedup(bot_texts), key=lambda d: d["x"])
    dig_sorted = sorted(digit_dets,       key=lambda d: d["x"])

    # সব text: city (top) + series letter (bot)
    all_texts  = [d["name"] for d in top_sorted + bot_sorted]
    all_digits = [d["name"] for d in dig_sorted]

    return all_digits, all_texts


# =====================================================
def read_plate_text(plate_crop, plate_model):
    """
    plate_crop  : raw BGR plate image
    plate_model : loaded ashraf.pt YOLO model

    Returns:
      number  → "56-6472"          (শুধু registration number)
      vtype   → "dhaka metro gha"  (city + series, number ছাড়া)

    ৪টা preprocessed variant এ model চালায়, majority voting করে।
    """
    if plate_crop is None or plate_crop.size == 0:
        return "", "unknown"

    try:
        variants = _preprocess_plate(plate_crop)
        crop_h   = variants[0].shape[0]

        vote_numbers = {}   # number_str → count
        all_text_results = []

        for var in variants:
            res_list = list(plate_model.predict(
                var, conf=0.25, iou=0.35, verbose=False, stream=True))
            if not res_list or res_list[0].boxes is None:
                continue

            digits, texts = _parse_one_result(res_list[0], crop_h)

            # Number voting
            num_str = ''.join(digits)
            if len(num_str) >= 4:
                formatted = num_str[:2] + '-' + num_str[2:]
            elif num_str:
                formatted = num_str
            else:
                formatted = ""

            if formatted:
                vote_numbers[formatted] = vote_numbers.get(formatted, 0) + 1

            if texts:
                all_text_results.append(texts)

        # ── Best number by majority vote ──
        if vote_numbers:
            number = max(vote_numbers, key=lambda k: (vote_numbers[k], len(k)))
        else:
            number = ""

        # ── Best text list (সবচেয়ে বেশি element আছে এমনটা নাও) ──
        best_texts = max(all_text_results, key=len) if all_text_results else []

        # ── vtype: city + series letter (number ছাড়া) ──
        city_parts   = [t for t in best_texts if t.lower() in CITY_NAMES]
        series_parts = [t for t in best_texts if t.lower() not in CITY_NAMES]

        # city গুলো আগে, তারপর series letter
        vtype_parts = city_parts + series_parts
        vtype = ' '.join(vtype_parts) if vtype_parts else "unknown"

        return number, vtype

    except Exception:
        return "", "unknown"


# =====================================================
def update_plate_buffer(track_id, vehicle_box, current_plate_boxes,
                        frame, plate_model, track_plate_buffer,
                        max_age_seconds=4.0,
                        _vote_store: dict = {}):
    """
    Multi-frame voting সহ plate buffer update।

    number → majority voted number (e.g. "56-6472")
    vtype  → majority voted region+series (e.g. "dhaka metro gha")
    """
    MAX_VOTES = 7

    now  = time.time()
    prev = track_plate_buffer.get(track_id)

    # Expire
    if prev is not None:
        if now - prev.get("timestamp", now) > max_age_seconds:
            track_plate_buffer.pop(track_id, None)
            _vote_store.pop(track_id, None)
            prev = None

    p_now, s_now = find_best_plate_for_vehicle(
        vehicle_box, current_plate_boxes, frame)

    if p_now is None:
        return track_plate_buffer.get(track_id)

    num, vtype = read_plate_text(p_now, plate_model)

    store = _vote_store.setdefault(track_id, {"nums": [], "vtypes": []})

    if num:
        store["nums"].append(num)
        if len(store["nums"]) > MAX_VOTES:
            store["nums"].pop(0)

    if vtype and vtype != "unknown":
        store["vtypes"].append(vtype)
        if len(store["vtypes"]) > MAX_VOTES:
            store["vtypes"].pop(0)

    def _majority(lst):
        if not lst: return ""
        counts = {}
        for v in lst:
            counts[v] = counts.get(v, 0) + 1
        return max(counts, key=lambda k: (counts[k], len(k)))

    best_num   = _majority(store["nums"])
    best_vtype = _majority(store["vtypes"]) if store["vtypes"] else vtype

    if prev is None or s_now > prev["score"]:
        track_plate_buffer[track_id] = {
            "crop":      p_now,
            "score":     s_now,
            "number":    best_num,
            "vtype":     best_vtype,
            "timestamp": now
        }
    else:
        prev["number"] = best_num
        prev["vtype"]  = best_vtype

    return track_plate_buffer.get(track_id)


# =====================================================
def clear_vote_store(track_id):
    """Stale track cleanup এ call করুন।"""
    _store = update_plate_buffer.__defaults__[-1]
    _store.pop(track_id, None)


# =====================================================
def select_polygon_roi(frame_resized, window_title="Select ROI"):
    points = []

    def mouse_cb(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))
        elif event == cv2.EVENT_RBUTTONDOWN and points:
            points.pop()

    cv2.namedWindow(window_title)
    cv2.setMouseCallback(window_title, mouse_cb)
    t0 = time.time()

    while True:
        temp = frame_resized.copy()
        if points:
            pts = np.array(points, dtype=np.int32)
            cv2.polylines(temp, [pts], isClosed=False, color=(0,255,0), thickness=2)
            for px, py in points:
                cv2.circle(temp, (px, py), 4, (0,255,0), -1)
        if len(points) > 2:
            cv2.line(temp, points[-1], points[0], (0,255,0), 2)
            ov = temp.copy()
            cv2.fillPoly(ov, [np.array(points)], (0,255,0))
            cv2.addWeighted(ov, 0.15, temp, 0.85, 0, temp)

        cv2.putText(temp, "Left=add  Right=undo  S=confirm  ESC=exit",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
        cv2.putText(temp, window_title,
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,220,255), 2)
        cv2.imshow(window_title, temp)
        k = cv2.waitKey(1)

        if k == ord('s'):
            if len(points) >= 3:
                break
            print("Minimum 3 points needed.")
        elif k == 27:
            cv2.destroyAllWindows()
            exit()
        elif time.time() - t0 > 20:
            print(f"[{window_title}] ROI timeout.")
            break

    cv2.destroyWindow(window_title)

    if len(points) < 3:
        raise ValueError(f"[{window_title}] ROI not set — minimum 3 points required.")

    return np.array(points, dtype=np.int32)



#color detection helper



class VehicleColorDetector:
    """
    Detects dominant vehicle color using HSV masking on the
    center 40% of the vehicle crop (avoids road/sky bleed).
    Red needs two HSV ranges because it wraps around H=0/180.
    """
    COLOR_RANGES = [
        ("WHITE",   (240, 240, 240), [(0,  180,  0,  40, 200, 255)]),
        ("SILVER",  (192, 192, 192), [(0,  180,  0,  60, 130, 200)]),
        ("BLACK",   ( 40,  40,  40), [(0,  180,  0,  80,   0,  60)]),
        ("RED",     ( 30,  30, 220), [(0,   10, 80, 255,  60, 255),
                                      (160, 180, 80, 255,  60, 255)]),
        ("BLUE",    (220, 100,  20), [(90,  130, 80, 255,  40, 255)]),
        ("GREEN",   ( 30, 180,  30), [(36,   85, 80, 255,  40, 255)]),
        ("YELLOW",  ( 30, 230, 230), [(20,   35, 80, 255, 120, 255)]),
        ("ORANGE",  ( 30, 140, 230), [(10,   20, 80, 255, 120, 255)]),
        ("BROWN",   ( 42,  82, 139), [(10,   20, 40, 200,  30, 130)]),
    ]
 
    def detect(self, bgr_crop):
        """Returns (COLOR_NAME: str, bgr_dot: tuple)."""
        if bgr_crop is None or bgr_crop.size == 0:
            # 128,128 is a neutral grey for "unknown" (not black which can be a real color)
            return "UNKNOWN", (128, 128, 128)
        
        # assign first 2 value to h and w respectively
        # In OpenCV, an image looks like:(height, width, channels)
        # so we are getting the height and width as first 2 values bgr_crop.shape
        # gives (height, width, channels)
 
        h, w = bgr_crop.shape[:2]
        y0, y1 = int(h * 0.30), int(h * 0.70)
        x0, x1 = int(w * 0.20), int(w * 0.80)
 
        roi = bgr_crop[y0:y1, x0:x1]
 
        # roi = center cropped region of vehicle
        # Sometimes it can be empty (bad crop / very small box)
        # Use entire vehicle crop instead
        if roi.size == 0:
            roi = bgr_crop
 
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
 
        # Initialize with "unknown" defaults in case no color matches
        best_name, best_bgr, best_count = "UNKNOWN", (128, 128, 128), 0
 
        # Loop over all colors and their HSV ranges, create masks, and count pixels
        for name, bgr_dot, ranges in self.COLOR_RANGES:
            mask = None
            # h->hue, s->saturation, v->value in HSV color space
            for (h_lo, h_hi, s_lo, s_hi, v_lo, v_hi) in ranges:
                # hsv shape is (height, width, channels), and we want to create a mask of shape (height, width)
                # by comparing each pixel's HSV values to the lower and upper bounds for the current color
                m = cv2.inRange(hsv,
                                np.array([h_lo, s_lo, v_lo]),
                                np.array([h_hi, s_hi, v_hi]))
                
                mask = m if mask is None else cv2.bitwise_or(mask, m)
 
            count = int(np.sum(mask > 0))
            
            if count > best_count:
                best_count, best_name, best_bgr = count, name, bgr_dot
 
        return best_name, best_bgr
 






# color_detector = VehicleColorDetector()
 
# crop = frame[y1:y2, x1:x2]   # vehicle crop

# color_name, color_bgr = color_detector.detect(crop)
 
# print(color_name)
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 # =====================================================
# helpers.py — Helper functions (multi-camera compatible)
# =====================================================

# import cv2
# import time
# import numpy as np
# from config import LICENSE_TYPE_MAP

# # ashraf.pt model এর city/division class নাম
# CITY_NAMES = {'dhaka', 'chattogram', 'khulna', 'jashore', 'metro'}


# # =====================================================
# def is_same_plate(img1, img2, th=0.15):
#     a = cv2.resize(img1, (64, 32))
#     b = cv2.resize(img2, (64, 32))
#     return np.mean(cv2.absdiff(a, b)) / 255.0 < th


# # =====================================================
# def find_best_plate_for_vehicle(vehicle_box, plate_boxes, frame):
#     vx1, vy1, vx2, vy2 = vehicle_box
#     vw   = max(vx2 - vx1, 1)
#     vh   = max(vy2 - vy1, 1)
#     vcx  = (vx1 + vx2) / 2
#     vcy  = (vy1 + vy2) / 2
#     diag = np.sqrt(vw**2 + vh**2)

#     best_crop, best_score = None, 0.0

#     for (px1, py1, px2, py2, pconf) in plate_boxes:
#         pw = px2 - px1
#         ph = py2 - py1

#         inter_x1 = max(px1, vx1); inter_y1 = max(py1, vy1)
#         inter_x2 = min(px2, vx2); inter_y2 = min(py2, vy2)
#         inter_w  = max(inter_x2 - inter_x1, 0)
#         inter_h  = max(inter_y2 - inter_y1, 0)
#         overlap_ratio = (inter_w * inter_h) / max(pw * ph, 1)

#         if overlap_ratio < 0.60:
#             continue

#         pcx = (px1 + px2) / 2
#         pcy = (py1 + py2) / 2
#         dist           = np.sqrt((pcx - vcx)**2 + (pcy - vcy)**2)
#         norm_dist      = dist / diag
#         position_bonus = 1.0 if pcy > (vy1 + vh * 0.4) else 0.7
#         score = pconf * (1.0 - min(norm_dist, 1.0)) * overlap_ratio * position_bonus

#         if score > best_score:
#             crop = frame[py1:py2, px1:px2]
#             if crop.size == 0:
#                 continue
#             best_crop  = crop.copy()
#             best_score = score

#     return best_crop, best_score


# # =====================================================
# def _preprocess_plate(crop):
#     """৪টা variant — different conditions এ ভালো result দেবে।"""
#     h, w  = crop.shape[:2]
#     scale = 120 / max(h, 1)
#     base  = cv2.resize(crop, (max(int(w * scale), 1), 120),
#                        interpolation=cv2.INTER_CUBIC)

#     kernel   = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]], dtype=np.float32)
#     sharp    = cv2.filter2D(base, -1, kernel)
#     gray     = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
#     clahe    = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4))
#     eq3      = cv2.cvtColor(clahe.apply(gray), cv2.COLOR_GRAY2BGR)
#     sharp_eq = cv2.filter2D(eq3, -1, kernel)

#     return [base, sharp, eq3, sharp_eq]


# # =====================================================
# def _nms_dets(dets, iou_threshold=0.45):
#     """
#     Simple NMS for detection dicts with 'box' and 'conf'.
#     Overlapping box গুলো থেকে highest confidence টা রেখে বাকি সরায়।
#     এটা same digit দুইবার detect হওয়ার সমস্যা fix করে।
#     """
#     if not dets:
#         return dets

#     dets = sorted(dets, key=lambda d: -d["conf"])
#     kept = []

#     for d in dets:
#         x1, y1, x2, y2 = d["box"]
#         suppress = False

#         for k in kept:
#             kx1, ky1, kx2, ky2 = k["box"]
#             ix1 = max(x1, kx1); iy1 = max(y1, ky1)
#             ix2 = min(x2, kx2); iy2 = min(y2, ky2)
#             iw  = max(ix2 - ix1, 0)
#             ih  = max(iy2 - iy1, 0)
#             inter   = iw * ih
#             area_d  = max((x2 - x1) * (y2 - y1), 1)
#             area_k  = max((kx2 - kx1) * (ky2 - ky1), 1)
#             iou     = inter / (area_d + area_k - inter)

#             if iou > iou_threshold:
#                 suppress = True
#                 break

#         if not suppress:
#             kept.append(d)

#     return kept


# # =====================================================
# def _validate_bd_plate(num_str):
#     """
#     Bangladesh plate format: 2 digits + 4 digits → 'XX-XXXX'
#     e.g. "566472" → "56-6472"
#     6 digit ছাড়া অন্য কিছু হলে None return করে।
#     """
#     digits_only = num_str.replace('-', '').strip()
#     if not digits_only.isdigit():
#         return None
#     if len(digits_only) != 6:
#         return None
#     return digits_only[:2] + '-' + digits_only[2:]


# # =====================================================
# def _parse_one_result(result, crop_h):
#     """
#     একটা YOLO result থেকে:
#       digits  → নিচের row (sorted x)
#       texts   → উপরের row city + নিচের row series letter (sorted x)

#     Returns: (digits_list, texts_list)
#     e.g. (['5','6','6','4','7','2'], ['dhaka','metro','gha'])
#     """
#     names = result.names
#     boxes = result.boxes.xyxy.tolist()
#     clses = result.boxes.cls.tolist()
#     confs = result.boxes.conf.tolist()

#     if not boxes:
#         return [], []

#     dets = []
#     for box, cls, conf in zip(boxes, clses, confs):
#         x1, y1, x2, y2 = box
#         name = names[int(cls)]
#         if name == "License Plate":
#             continue
#         dets.append({
#             "name":     name,
#             "x":        x1,
#             "y_cen":    (y1 + y2) / 2,
#             "conf":     conf,
#             "is_digit": name.isdigit(),
#             "box":      (x1, y1, x2, y2),
#         })

#     digit_dets = [d for d in dets if d["is_digit"]]
#     text_dets  = [d for d in dets if not d["is_digit"]]

#     if not digit_dets:
#         return [], [d["name"] for d in sorted(text_dets, key=lambda d: d["x"])]

#     # ── NMS: overlapping digit box গুলো থেকে best conf টা রাখো ──
#     # এটাই মূল fix — same digit দুইবার detect হয়ে 7 digit হওয়া বন্ধ করে
#     digit_dets = _nms_dets(digit_dets, iou_threshold=0.45)

#     # Digit row baseline
#     digit_baseline = sorted(d["y_cen"] for d in digit_dets)[len(digit_dets) // 2]
#     gap = crop_h * 0.20

#     # Text গুলো উপরে/নিচে ভাগ করো
#     top_texts = [d for d in text_dets if d["y_cen"] < digit_baseline - gap]
#     bot_texts = [d for d in text_dets if d["y_cen"] >= digit_baseline - gap]

#     # Duplicate বাদ — same name থেকে high conf রাখো
#     def dedup(lst):
#         seen, out = set(), []
#         for d in sorted(lst, key=lambda d: -d["conf"]):
#             if d["name"] not in seen:
#                 seen.add(d["name"])
#                 out.append(d)
#         return out

#     top_sorted = sorted(dedup(top_texts), key=lambda d: d["x"])
#     bot_sorted = sorted(dedup(bot_texts), key=lambda d: d["x"])
#     dig_sorted = sorted(digit_dets,       key=lambda d: d["x"])

#     # সব text: city (top) + series letter (bot)
#     all_texts  = [d["name"] for d in top_sorted + bot_sorted]
#     all_digits = [d["name"] for d in dig_sorted]

#     return all_digits, all_texts


# # =====================================================
# def read_plate_text(plate_crop, plate_model):
#     """
#     plate_crop  : raw BGR plate image
#     plate_model : loaded ashraf.pt YOLO model

#     Returns:
#       number  → "56-6472"          (শুধু registration number)
#       vtype   → "dhaka metro gha"  (city + series, number ছাড়া)

#     ৪টা preprocessed variant এ model চালায়, majority voting করে।
#     শুধু valid 6-digit Bangladesh plate format accept করে।
#     """
#     if plate_crop is None or plate_crop.size == 0:
#         return "", "unknown"

#     try:
#         variants = _preprocess_plate(plate_crop)
#         crop_h   = variants[0].shape[0]

#         vote_numbers = {}   # number_str → count
#         all_text_results = []

#         for var in variants:
#             res_list = list(plate_model.predict(
#                 var, conf=0.25, iou=0.35, verbose=False, stream=True))
#             if not res_list or res_list[0].boxes is None:
#                 continue

#             digits, texts = _parse_one_result(res_list[0], crop_h)

#             # Number voting — validate করে তারপর vote দাও
#             num_str = ''.join(digits)
#             validated = _validate_bd_plate(num_str)

#             if validated:
#                 vote_numbers[validated] = vote_numbers.get(validated, 0) + 1
#             elif num_str and len(num_str) >= 4:
#                 # valid না হলেও raw টা রাখো fallback এর জন্য
#                 # কিন্তু separate key দিয়ে (prefix দিয়ে আলাদা করো)
#                 raw_key = f"RAW_{num_str}"
#                 vote_numbers[raw_key] = vote_numbers.get(raw_key, 0) + 1

#             if texts:
#                 all_text_results.append(texts)

#         # ── Best number by majority vote ──
#         if vote_numbers:
#             # প্রথমে শুধু valid (6-digit) numbers নাও
#             valid_votes = {k: v for k, v in vote_numbers.items()
#                            if not k.startswith("RAW_")}

#             if valid_votes:
#                 # সবচেয়ে বেশি voted valid number
#                 number = max(valid_votes, key=lambda k: (valid_votes[k], len(k)))
#             else:
#                 # Valid কিছু না পেলে raw থেকে best টা নাও, তারপর validate try করো
#                 raw_votes = {k.replace("RAW_", ""): v
#                              for k, v in vote_numbers.items()
#                              if k.startswith("RAW_")}
#                 best_raw = max(raw_votes, key=lambda k: (raw_votes[k], len(k)))
#                 number = _validate_bd_plate(best_raw) or best_raw
#         else:
#             number = ""

#         # ── Best text list (সবচেয়ে বেশি element আছে এমনটা নাও) ──
#         best_texts = max(all_text_results, key=len) if all_text_results else []

#         # ── vtype: city + series letter (number ছাড়া) ──
#         city_parts   = [t for t in best_texts if t.lower() in CITY_NAMES]
#         series_parts = [t for t in best_texts if t.lower() not in CITY_NAMES]

#         # city গুলো আগে, তারপর series letter
#         vtype_parts = city_parts + series_parts
#         vtype = ' '.join(vtype_parts) if vtype_parts else "unknown"

#         return number, vtype

#     except Exception:
#         return "", "unknown"


# # =====================================================
# def update_plate_buffer(track_id, vehicle_box, current_plate_boxes,
#                         frame, plate_model, track_plate_buffer,
#                         max_age_seconds=4.0,
#                         _vote_store: dict = {}):
#     """
#     Multi-frame voting সহ plate buffer update।

#     number → majority voted number (e.g. "56-6472")
#     vtype  → majority voted region+series (e.g. "dhaka metro gha")
#     """
#     MAX_VOTES = 7

#     now  = time.time()
#     prev = track_plate_buffer.get(track_id)

#     # Expire
#     if prev is not None:
#         if now - prev.get("timestamp", now) > max_age_seconds:
#             track_plate_buffer.pop(track_id, None)
#             _vote_store.pop(track_id, None)
#             prev = None

#     p_now, s_now = find_best_plate_for_vehicle(
#         vehicle_box, current_plate_boxes, frame)

#     if p_now is None:
#         return track_plate_buffer.get(track_id)

#     num, vtype = read_plate_text(p_now, plate_model)

#     store = _vote_store.setdefault(track_id, {"nums": [], "vtypes": []})

#     if num:
#         store["nums"].append(num)
#         if len(store["nums"]) > MAX_VOTES:
#             store["nums"].pop(0)

#     if vtype and vtype != "unknown":
#         store["vtypes"].append(vtype)
#         if len(store["vtypes"]) > MAX_VOTES:
#             store["vtypes"].pop(0)

#     def _majority(lst):
#         if not lst: return ""
#         counts = {}
#         for v in lst:
#             counts[v] = counts.get(v, 0) + 1
#         return max(counts, key=lambda k: (counts[k], len(k)))

#     best_num   = _majority(store["nums"])
#     best_vtype = _majority(store["vtypes"]) if store["vtypes"] else vtype

#     if prev is None or s_now > prev["score"]:
#         track_plate_buffer[track_id] = {
#             "crop":      p_now,
#             "score":     s_now,
#             "number":    best_num,
#             "vtype":     best_vtype,
#             "timestamp": now
#         }
#     else:
#         prev["number"] = best_num
#         prev["vtype"]  = best_vtype

#     return track_plate_buffer.get(track_id)


# # =====================================================
# def clear_vote_store(track_id):
#     """Stale track cleanup এ call করুন।"""
#     _store = update_plate_buffer.__defaults__[-1]
#     _store.pop(track_id, None)


# # =====================================================
# def select_polygon_roi(frame_resized, window_title="Select ROI"):
#     points = []

#     def mouse_cb(event, x, y, flags, param):
#         if event == cv2.EVENT_LBUTTONDOWN:
#             points.append((x, y))
#         elif event == cv2.EVENT_RBUTTONDOWN and points:
#             points.pop()

#     cv2.namedWindow(window_title)
#     cv2.setMouseCallback(window_title, mouse_cb)
#     t0 = time.time()

#     while True:
#         temp = frame_resized.copy()
#         if points:
#             pts = np.array(points, dtype=np.int32)
#             cv2.polylines(temp, [pts], isClosed=False, color=(0,255,0), thickness=2)
#             for px, py in points:
#                 cv2.circle(temp, (px, py), 4, (0,255,0), -1)
#         if len(points) > 2:
#             cv2.line(temp, points[-1], points[0], (0,255,0), 2)
#             ov = temp.copy()
#             cv2.fillPoly(ov, [np.array(points)], (0,255,0))
#             cv2.addWeighted(ov, 0.15, temp, 0.85, 0, temp)

#         cv2.putText(temp, "Left=add  Right=undo  S=confirm  ESC=exit",
#                     (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
#         cv2.putText(temp, window_title,
#                     (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,220,255), 2)
#         cv2.imshow(window_title, temp)
#         k = cv2.waitKey(1)

#         if k == ord('s'):
#             if len(points) >= 3:
#                 break
#             print("Minimum 3 points needed.")
#         elif k == 27:
#             cv2.destroyAllWindows()
#             exit()
#         elif time.time() - t0 > 20:
#             print(f"[{window_title}] ROI timeout.")
#             break

#     cv2.destroyWindow(window_title)

#     if len(points) < 3:
#         raise ValueError(f"[{window_title}] ROI not set — minimum 3 points required.")

#     return np.array(points, dtype=np.int32)


# # =====================================================
# # Color detection helper
# # =====================================================

# class VehicleColorDetector:
#     """
#     Detects dominant vehicle color using HSV masking on the
#     center 40% of the vehicle crop (avoids road/sky bleed).
#     Red needs two HSV ranges because it wraps around H=0/180.
#     """
#     COLOR_RANGES = [
#         ("WHITE",   (240, 240, 240), [(0,  180,  0,  40, 200, 255)]),
#         ("SILVER",  (192, 192, 192), [(0,  180,  0,  60, 130, 200)]),
#         ("BLACK",   ( 40,  40,  40), [(0,  180,  0,  80,   0,  60)]),
#         ("RED",     ( 30,  30, 220), [(0,   10, 80, 255,  60, 255),
#                                       (160, 180, 80, 255,  60, 255)]),
#         ("BLUE",    (220, 100,  20), [(90,  130, 80, 255,  40, 255)]),
#         ("GREEN",   ( 30, 180,  30), [(36,   85, 80, 255,  40, 255)]),
#         ("YELLOW",  ( 30, 230, 230), [(20,   35, 80, 255, 120, 255)]),
#         ("ORANGE",  ( 30, 140, 230), [(10,   20, 80, 255, 120, 255)]),
#         ("BROWN",   ( 42,  82, 139), [(10,   20, 40, 200,  30, 130)]),
#     ]

#     def detect(self, bgr_crop):
#         """Returns (COLOR_NAME: str, bgr_dot: tuple)."""
#         if bgr_crop is None or bgr_crop.size == 0:
#             return "UNKNOWN", (128, 128, 128)

#         h, w = bgr_crop.shape[:2]
#         y0, y1 = int(h * 0.30), int(h * 0.70)
#         x0, x1 = int(w * 0.20), int(w * 0.80)

#         roi = bgr_crop[y0:y1, x0:x1]

#         if roi.size == 0:
#             roi = bgr_crop

#         hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

#         best_name, best_bgr, best_count = "UNKNOWN", (128, 128, 128), 0

#         for name, bgr_dot, ranges in self.COLOR_RANGES:
#             mask = None
#             for (h_lo, h_hi, s_lo, s_hi, v_lo, v_hi) in ranges:
#                 m = cv2.inRange(hsv,
#                                 np.array([h_lo, s_lo, v_lo]),
#                                 np.array([h_hi, s_hi, v_hi]))
#                 mask = m if mask is None else cv2.bitwise_or(mask, m)

#             count = int(np.sum(mask > 0))

#             if count > best_count:
#                 best_count, best_name, best_bgr = count, name, bgr_dot

#         return best_name, best_bgr
 
 
 
 
 
 