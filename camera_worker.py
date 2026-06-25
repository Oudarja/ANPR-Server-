# import cv2
# import time
# import os
# import numpy as np
# from ultralytics import YOLO
# from sort import Sort
# from clip import ClipManager

# from config import (
#     MONITOR_WIDTH, MONITOR_HEIGHT,
#     PLATE_CONF_TH, SPEED_LIMIT_KMPH, PIXELS_PER_METER,
#     VEHICLE_MODEL, PLATE_MODEL, VEHICLE_CLASSES
# )
# from helpers import update_plate_buffer, clear_vote_store, VehicleColorDetector
# from database import (
#     insert_detected_plate,
#     insert_speed_violation, set_camera_status,
#     get_camera_signal
# )

# _color_detector = VehicleColorDetector()

# _SIGNAL_MAP = {
#     "red":     ((0,   0,   255), True,    "RED"),
#     "green":   ((0,   255, 0),   False,   "GREEN"),
#     "orange":  ((0,   165, 255), False,   "ORANGE"),
#     "unknown": ((128, 128, 128), False,   "NO SIGNAL"),
# }

# _SIGNAL_POLL_INTERVAL = 2
# _SIGNAL_DEBOUNCE_SEC  = 3.0


# # ─────────────────────────────────────────────────────
# # RTSP/file stream open
# # ─────────────────────────────────────────────────────
# def _open_stream(stream_url: str) -> cv2.VideoCapture:
#     """
#     RTSP এ:
#       - FFmpeg backend
#       - Buffer = 1 frame  (real-time, lag নেই)
#       - Timeout 5s
#     File/MJPEG এও কাজ করে।
#     """
#     is_rtsp = stream_url.lower().startswith("rtsp://")

#     if is_rtsp:
#         # os-level env দিয়ে FFmpeg কে RTSP UDP transport বলো
#         os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
#             "rtsp_transport;udp|"
#             "stimeout;5000000"        # socket timeout 5s
#         )
#         cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
#         cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
#     else:
#         cap = cv2.VideoCapture(stream_url)
#         cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

#     return cap


# # ─────────────────────────────────────────────────────
# # Main camera worker
# # ─────────────────────────────────────────────────────
# def run_camera(camera_info: dict, roi_polygon: np.ndarray,
#                preview_queue=None):
#     """
#     camera_info  : DB cameras row (dict)
#     roi_polygon  : np.array shape (N,2) int32, or empty array to disable ROI filtering
#     preview_queue: multiprocessing.Queue — preview frame পাঠানোর জন্য
#                    None হলে preview skip
#     """
#     cam_id   = camera_info["id"]
#     cam_name = camera_info.get("name", f"Camera-{cam_id}")
#     stream   = camera_info["stream_url"]
#     TAG      = f"[CAM-{cam_id} | {cam_name}]"

#     print(f"{TAG} Starting...")

#     # vio_dir  = os.path.abspath(f"violations/cam_{cam_id}")
#     # clip_dir = os.path.join(vio_dir, "clips")
#     # os.makedirs(vio_dir, exist_ok=True)
#     vio_dir  = f"violations/cam_{cam_id}"
#     clip_dir = os.path.join(vio_dir, "clips")
#     os.makedirs(vio_dir, exist_ok=True)

#     cap = None
#     clip_manager = None
#     counts = {}
#     result = False

#     try:
#         # ── Stream open ──
#         cap = _open_stream(stream)
#         if not cap.isOpened():
#             print(f"{TAG}  Cannot open: {stream}")
#             set_camera_status(cam_id, "offline")
#             return False

#         set_camera_status(cam_id, "active")

#         fps = cap.get(cv2.CAP_PROP_FPS)
#         if fps <= 0 or np.isnan(fps):
#             fps = float(camera_info.get("frame_rate", 25))

#         # ── Models ──
#         print(f"{TAG} Loading models...")
#         model        = YOLO(VEHICLE_MODEL)
#         plate_model  = YOLO(PLATE_MODEL)
#         tracker      = Sort(max_age=20, min_hits=3, iou_threshold=0.2)
#         clip_manager = ClipManager(fps, (MONITOR_WIDTH, MONITOR_HEIGHT), clip_dir)

#         # ── State ──
#         counts              = {v: 0 for v in VEHICLE_CLASSES.values()}
#         counted_ids         = set()
#         speed_violation_ids = set()
#         track_plate_buffer  = {}
#         track_last_position = {}
#         track_speed_history = {}
#         track_color_buffer  = {}
#         db_logged_tracks    = set()
#         active_tracks       = {}

#         # ── Signal state ──
#         _displayed_signal = "unknown"
#         _pending_signal   = None
#         _pending_since    = 0.0
#         last_signal_poll  = 0.0

#         # ── RTSP reconnect ──
#         MAX_RECONNECT     = 10
#         RECONNECT_DELAY   = 3.0
#         reconnect_count   = 0
#         consecutive_fails = 0
#         MAX_CONSEC_FAILS  = 30   # এতবার fail → reconnect

#         # ── Preview interval ──
#         PREVIEW_EVERY = 10   # প্রতি ১০ frame এ একটা preview
#         frame_count   = 0

#         print(f"{TAG} ✅ Ready.")

#         while True:
#             ret, frame = cap.read()

#             # ── Stream fail / reconnect ───────────────────────────
#             if not ret:
#                 consecutive_fails += 1
#                 if consecutive_fails >= MAX_CONSEC_FAILS:
#                     if reconnect_count >= MAX_RECONNECT:
#                         print(f"{TAG}  Max reconnects. Stopping.")
#                         break
#                     reconnect_count  += 1
#                     consecutive_fails = 0
#                     print(f"{TAG} 🔄 Reconnecting ({reconnect_count}/{MAX_RECONNECT})...")
#                     cap.release()
#                     time.sleep(RECONNECT_DELAY)
#                     cap = _open_stream(stream)
#                     if not cap.isOpened():
#                         set_camera_status(cam_id, "offline")
#                         continue
#                     print(f"{TAG} ✅ Reconnected.")
#                     set_camera_status(cam_id, "active")
#                 else:
#                     time.sleep(0.03)
#                 continue

#             consecutive_fails = 0
#             reconnect_count   = 0
#             frame_count      += 1

#             frame_resized = cv2.resize(frame, (MONITOR_WIDTH, MONITOR_HEIGHT))

#             # ── Signal poll ──
#             now = time.time()
#             if now - last_signal_poll >= _SIGNAL_POLL_INTERVAL:
#                 raw_signal       = get_camera_signal(cam_id)
#                 last_signal_poll = now
#                 clip_is_active   = clip_manager.has_active_clips()

#                 if not clip_is_active:
#                     if raw_signal == _displayed_signal:
#                         _pending_signal = None
#                     else:
#                         if _pending_signal != raw_signal:
#                             _pending_signal = raw_signal
#                             _pending_since  = now
#                         elif now - _pending_since >= _SIGNAL_DEBOUNCE_SEC:
#                             print(f"{TAG} Signal: {_displayed_signal} → {_pending_signal}")
#                             _displayed_signal = _pending_signal
#                             _pending_signal   = None

#             sig_color, is_red, sig_text = _SIGNAL_MAP[_displayed_signal]

#             # ── Draw ROI + label ──
#             if roi_polygon is not None and roi_polygon.size >= 3:
#                 cv2.polylines(frame_resized, [roi_polygon], isClosed=True,
#                               color=sig_color, thickness=2)
#             cv2.putText(frame_resized, f"{cam_name} | {sig_text}",
#                         (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, sig_color, 2)

#             # ── Vehicle detection ──
#             detections = []
#             for r in model(frame_resized, verbose=False):
#                 for box in r.boxes:
#                     cls = int(box.cls[0])
#                     if cls in VEHICLE_CLASSES:
#                         x1, y1, x2, y2 = map(int, box.xyxy[0])
#                         detections.append([x1, y1, x2, y2, float(box.conf[0]), cls])

#             # ── Plate detection ──
#             current_plate_boxes = []
#             for pr in plate_model(frame_resized, verbose=False):
#                 for pbox in pr.boxes:
#                     px1, py1, px2, py2 = map(int, pbox.xyxy[0])
#                     pconf = float(pbox.conf[0])
#                     if pconf < PLATE_CONF_TH:
#                         continue
#                     if frame_resized[py1:py2, px1:px2].size == 0:
#                         continue
#                     current_plate_boxes.append((px1, py1, px2, py2, pconf))
#                     cv2.rectangle(frame_resized, (px1, py1), (px2, py2), (255, 0, 255), 2)

#             # ── SORT tracking ──
#             tracks = tracker.update(
#                 np.array([d[:5] for d in detections])
#             ) if detections else []

#             current_track_ids = set()

#             for track in tracks:
#                 x1, y1, x2, y2, track_id = map(int, track)

#                 cls_name = None
#                 for d in detections:
#                     if abs(x1 - d[0]) < 50 and abs(y1 - d[1]) < 50:
#                         cls_name = VEHICLE_CLASSES[d[5]]; break

#                 if cls_name is None and track_id not in active_tracks:
#                     continue

#                 center_pt  = ((x1 + x2) // 2, (y1 + y2) // 2)
#                 corners    = [(x1,y1),(x2,y1),(x2,y2),(x1,y2), center_pt]
#                 if roi_polygon is not None and roi_polygon.size >= 3:
#                     inside_roi = any(
#                         cv2.pointPolygonTest(
#                             roi_polygon, (float(p[0]), float(p[1])), False) >= 0
#                         for p in corners
#                     )
#                 else:
#                     inside_roi = True

#                 buf = update_plate_buffer(
#                     track_id, (x1, y1, x2, y2),
#                     current_plate_boxes, frame_resized,
#                     plate_model, track_plate_buffer,
#                     max_age_seconds=3.0
#                 )

#                 # ── Color (একবার per track) ──
#                 if track_id not in track_color_buffer:
#                     color_name, _ = _color_detector.detect(frame_resized[y1:y2, x1:x2])
#                     if color_name != "UNKNOWN":
#                         track_color_buffer[track_id] = color_name
#                 vehicle_color = track_color_buffer.get(track_id, "UNKNOWN")

#                 # ── Frame label ──
#                 if buf and buf["number"]:
#                     display = buf["number"]
#                     if buf["vtype"] not in ("unknown", ""):
#                         display = f"{buf['vtype']} {buf['number']}"
#                     display = f"{vehicle_color} | {display}"
#                     cv2.putText(frame_resized, display,
#                                 (x1, y2 + 18),
#                                 cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 200, 0), 1)

#                 # ── Speed ──
#                 speed_kmph = 0.0
#                 now_t = time.time()
#                 if track_id in track_last_position:
#                     lx, ly, lt = track_last_position[track_id]
#                     dt     = max(now_t - lt, 1e-3)
#                     dist_m = np.sqrt(
#                         (center_pt[0]-lx)**2 + (center_pt[1]-ly)**2
#                     ) / PIXELS_PER_METER
#                     speed_kmph = (dist_m / dt) * 3.6
#                 track_last_position[track_id] = (center_pt[0], center_pt[1], now_t)

#                 hist = track_speed_history.setdefault(track_id, [])
#                 hist.append(speed_kmph)
#                 if len(hist) > 5: hist.pop(0)
#                 speed_kmph = min(sum(hist) / len(hist), 260.0)

#                 cv2.putText(frame_resized, f"{speed_kmph:.1f} km/h",
#                             (x1, y2 + 36),
#                             cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

#                 if inside_roi:
#                     if track_id not in counted_ids:
#                         counted_ids.add(track_id)
#                         if cls_name: counts[cls_name] += 1

#                     stored_cls = cls_name or (
#                         active_tracks[track_id][1]
#                         if track_id in active_tracks else "vehicle"
#                     )

#                     # detected_plates
#                     if buf and track_id not in db_logged_tracks:
#                         db_logged_tracks.add(track_id)
#                         v_path = os.path.join(vio_dir, f"detected_{track_id}_vehicle.jpg")
#                         p_path = os.path.join(vio_dir, f"detected_{track_id}_plate.jpg")
#                         vcrop  = frame_resized[y1:y2, x1:x2]
#                         if vcrop.size > 0:
#                             cv2.imwrite(v_path, vcrop)
#                         cv2.imwrite(p_path, buf["crop"])
#                         insert_detected_plate(
#                             camera_id=cam_id, track_id=track_id,
#                             plate_number=buf["number"], vehicle_type=buf["vtype"],
#                             vehicle_class=stored_cls,
#                             plate_img_path=p_path,       
#                             vehicle_img_path=v_path,     
#                             confidence=buf["score"], vehicle_color=vehicle_color
#                         )

#                     # Speed violation
#                     if speed_kmph > SPEED_LIMIT_KMPH and track_id not in speed_violation_ids and buf:
#                         speed_violation_ids.add(track_id)
#                         vcrop     = frame_resized[y1:y2, x1:x2]
#                         v_path    = os.path.join(vio_dir, f"s{track_id}_vehicle.jpg")
#                         p_path    = os.path.join(vio_dir, f"s{track_id}_plate.jpg")
#                         clip_path = clip_manager.start_clip(track_id + 100000)
#                         clip_path = os.path.relpath(clip_path) 
#                         print(f"{TAG} 🎬 SPEED | track:{track_id} | {speed_kmph:.1f}")
#                         if vcrop.size > 0: cv2.imwrite(v_path, vcrop)
#                         cv2.imwrite(p_path, buf["crop"])
#                         insert_speed_violation(
#                             camera_id=cam_id, track_id=track_id,
#                             plate_number=buf["number"], vehicle_type=buf["vtype"],
#                             vehicle_class=stored_cls,
#                             plate_img_path=p_path,
#                             vehicle_img_path=v_path,
#                             confidence=buf["score"], speed_kmph=speed_kmph,
#                             speed_limit=SPEED_LIMIT_KMPH, clip_path=clip_path,
#                             vehicle_color=vehicle_color
#                         )
#                         cv2.putText(frame_resized, "SPEED!",
#                                     (x1, y1-28), cv2.FONT_HERSHEY_SIMPLEX,
#                                     0.6, (0, 140, 255), 2)

#                     active_tracks[track_id] = [(x1, y1, x2, y2), stored_cls]
#                 else:
#                     if track_id in active_tracks:
#                         active_tracks[track_id][0] = (x1, y1, x2, y2)

#                 current_track_ids.add(track_id)

#             # ── Stale track cleanup ──
#             for tid in list(active_tracks.keys()):
#                 if tid not in current_track_ids:
#                     del active_tracks[tid]
#                     track_plate_buffer.pop(tid, None)
#                     track_last_position.pop(tid, None)
#                     track_speed_history.pop(tid, None)
#                     track_color_buffer.pop(tid, None)
#                     clear_vote_store(tid)

#             # ── Draw boxes ──
#             for tid, (bbox, cname) in active_tracks.items():
#                 bx1, by1, bx2, by2 = bbox
#                 pk = "+" if tid in track_plate_buffer else ""
#                 cv2.rectangle(frame_resized, (bx1, by1), (bx2, by2), (0, 255, 255), 2)
#                 cv2.putText(frame_resized, f"{cname} #{tid}{pk}",
#                             (bx1, by1-16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,255,255), 1)

#             # ── Clip ──
#             clip_manager.push_frame(frame_resized)

#             # ── Preview → main process ──
#             if preview_queue is not None and frame_count % PREVIEW_EVERY == 0:
#                 preview = cv2.resize(frame_resized, (640, 360))
#                 try:
#                     while not preview_queue.empty():
#                         try: preview_queue.get_nowait()
#                         except Exception: break
#                     preview_queue.put_nowait((cam_id, cam_name, preview))
#                 except Exception:
#                     pass

#             if cv2.waitKey(1) & 0xFF == 27:
#                 break

#             result = True

#     except KeyboardInterrupt:
#         pass
#     except Exception as e:
#         import traceback
#         print(f"{TAG} Error: {e}")
#         traceback.print_exc()
#     finally:
#         if cap is not None:
#             cap.release()
#         cv2.destroyAllWindows()
#         if clip_manager is not None:
#             clip_manager.release_all()
#         set_camera_status(cam_id, "inactive")
#         print(f"{TAG} Stopped. Counts: {counts}")

#     return result


import cv2
import time
import os
import re
from pathlib import Path
from datetime import date
import numpy as np
from ultralytics import YOLO
from sort import Sort
from clip import ClipManager
from ocr import find_date_time

from collections import deque,Counter

from config import (
    MONITOR_WIDTH, MONITOR_HEIGHT,
    PLATE_CONF_TH, SPEED_LIMIT_KMPH, PIXELS_PER_METER,
    VEHICLE_MODEL, PLATE_MODEL, VEHICLE_CLASSES,
    UPLOAD_ROOT, CAMERA_FOLDER_MAP
)
from helpers import update_plate_buffer, clear_vote_store, VehicleColorDetector

from database import (
    insert_detected_plate,
    insert_speed_violation, set_camera_status,
    get_camera_signal
)

_color_detector = VehicleColorDetector()

_SIGNAL_MAP = {
    "red":     ((0,   0,   255), True,    "RED"),
    "green":   ((0,   255, 0),   False,   "GREEN"),
    "orange":  ((0,   165, 255), False,   "ORANGE"),
    "unknown": ((128, 128, 128), False,   "NO SIGNAL"),
}

_SIGNAL_POLL_INTERVAL = 2
_SIGNAL_DEBOUNCE_SEC  = 3.0



# ─────────────────────────────────────────────────────
# RTSP/file stream open
# ─────────────────────────────────────────────────────
def _open_stream(stream_url: str) -> cv2.VideoCapture:
    """
    RTSP এ:
      - FFmpeg backend
      - Buffer = 1 frame  (real-time, lag নেই)
      - Timeout 5s
    File/MJPEG এও কাজ করে।
    """
    is_rtsp = stream_url.lower().startswith("rtsp://")

    if is_rtsp:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;udp|"
            "stimeout;5000000"
        )
        cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    else:
        cap = cv2.VideoCapture(stream_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    return cap


def _is_file_stream(stream_url: str) -> bool:
    """RTSP নয়, local file কিনা check করে।"""
    lower = stream_url.lower()
    return not lower.startswith("rtsp://") and not lower.startswith("http")


def _normalize_db_path(path: str) -> str:
    """Store DB paths with an uploads-relative prefix."""
    try:
        rel = Path(path).relative_to(UPLOAD_ROOT)
        return str(Path("uploads") / rel)
    except Exception:
        try:
            return os.path.relpath(path)
        except Exception:
            return path


# ─────────────────────────────────────────────────────
# Main camera worker
# ─────────────────────────────────────────────────────
def run_camera(camera_info: dict, roi_polygon: np.ndarray,
               preview_queue=None):
    """
    camera_info  : DB cameras row (dict)
    roi_polygon  : np.array shape (N,2) int32, or empty array to disable ROI filtering
    preview_queue: multiprocessing.Queue — preview frame পাঠানোর জন্য
                   None হলে preview skip

    Return:
        True  — video সম্পূর্ণ process হয়েছে (file stream শেষ হয়েছে স্বাভাবিকভাবে)
        False — কোনো error হয়েছে বা stream খোলা যায়নি
    """
    cam_id   = camera_info["id"]
    cam_name = camera_info.get("name", f"Camera-{cam_id}")
    stream   = camera_info["stream_url"]
    TAG      = f"[CAM-{cam_id} | {cam_name}]"

    map_folder = CAMERA_FOLDER_MAP.get(cam_id, str(cam_id))
    try:
        db_camera_id = int(map_folder)
    except ValueError:
        db_camera_id = cam_id

    is_file  = _is_file_stream(stream)   # ← file নাকি RTSP

    print(f"{TAG} Starting... ({'file' if is_file else 'RTSP'})")

    # Determine validations save directory under uploads for this camera.
    # Prefer finding a date folder in the stream path (when processing a file),
    # otherwise use today's compact date format `YYYYMMDD`.
    folder_name = CAMERA_FOLDER_MAP.get(cam_id, str(cam_id))
    base_upload = Path(UPLOAD_ROOT) / folder_name
    base_upload.mkdir(parents=True, exist_ok=True)


    save_dir = None
    if is_file:
        try:
            stream_path = Path(stream)
            # Search parents for a date-like folder (YYYYMMDD or YYYY-MM-DD)
            for anc in [stream_path.parent] + list(stream_path.parents):
                if re.match(r'^\d{8}$', anc.name) or re.match(r'^\d{4}-\d{2}-\d{2}$', anc.name):
                    # if anc is the `validations` folder, go up one to get date folder
                    if anc.name == 'validations':
                        continue
                    date_folder = anc
                    save_dir = date_folder / 'validations'
                    break
        except Exception:
            save_dir = None

    if save_dir is None:
        today_compact = date.today().strftime("%Y%m%d")
        save_dir = base_upload / today_compact / 'validations'

    save_dir.mkdir(parents=True, exist_ok=True)
    clip_dir_path = save_dir / 'clips'
    clip_dir_path.mkdir(parents=True, exist_ok=True)

    # Keep legacy `vio_dir` name (string) used throughout the codebase
    vio_dir = str(save_dir)
    clip_dir = str(clip_dir_path)

    cap = None
    clip_manager = None
    counts = {}

    # ── return value ──
    # file stream → শেষ পর্যন্ত পড়লে True
    # RTSP       → loop ভাঙলে (KeyboardInterrupt / ESC) True
    # error      → False
    completed_successfully = False

    try:
        # ── Stream open ──
        cap = _open_stream(stream)
        if not cap.isOpened():
            print(f"{TAG} ✗ Cannot open: {stream}")
            set_camera_status(cam_id, "offline")
            return False

        set_camera_status(cam_id, "active")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or np.isnan(fps):
            fps = float(camera_info.get("frame_rate", 25))

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if is_file else -1
        if total_frames > 0:
            print(f"{TAG} Video: {total_frames} frames @ {fps:.1f} fps")

        # ── Models ──
        print(f"{TAG} Loading models...")
        model        = YOLO(VEHICLE_MODEL)
        plate_model  = YOLO(PLATE_MODEL)
        tracker      = Sort(max_age=20, min_hits=3, iou_threshold=0.2)
        clip_manager = ClipManager(fps, (MONITOR_WIDTH, MONITOR_HEIGHT), clip_dir)

        # ── State ──
        counts              = {v: 0 for v in VEHICLE_CLASSES.values()}
        counted_ids         = set()
        speed_violation_ids = set()
        track_plate_buffer  = {}
        track_last_position = {}
        track_speed_history = {}
        track_color_buffer  = {}
        db_logged_tracks    = set()
        active_tracks       = {}

        # ── Signal state ──
        _displayed_signal = "unknown"
        _pending_signal   = None
        _pending_since    = 0.0
        last_signal_poll  = 0.0

        # ── RTSP reconnect (file এ প্রযোজ্য নয়) ──
        MAX_RECONNECT     = 10
        RECONNECT_DELAY   = 3.0
        reconnect_count   = 0
        consecutive_fails = 0

        # file stream: কতবার পরপর fail হলে EOF ধরবে
        MAX_CONSEC_FAILS_FILE = 5
        # RTSP: কতবার fail হলে reconnect করবে
        MAX_CONSEC_FAILS_RTSP = 30

        # ── Preview interval ──
        PREVIEW_EVERY = 10
        frame_count   = 0

        print(f"{TAG} ✅ Ready. Processing...")

        ocr_frame_buffer = deque(maxlen=5)

        while True:
            ret, frame = cap.read()

            # # always keeps latest 5 frame and if it is more than 5 remove the more older than 5
            # while len(ocr_frame_buffer)>5:
            #     ocr_frame_buffer.pop_left()

            # ── Stream fail / EOF handling ──────────────────────
            if not ret:
                consecutive_fails += 1

                if is_file:
                    # File stream: কয়েকবার fail মানেই EOF
                    if consecutive_fails >= MAX_CONSEC_FAILS_FILE:
                        print(f"{TAG} ✅ Video ended (EOF). Frames processed: {frame_count}")
                        completed_successfully = True
                        break
                    time.sleep(0.01)
                    continue

                else:
                    # RTSP: reconnect logic
                    if consecutive_fails >= MAX_CONSEC_FAILS_RTSP:
                        if reconnect_count >= MAX_RECONNECT:
                            print(f"{TAG} ✗ Max reconnects reached. Stopping.")
                            break
                        reconnect_count  += 1
                        consecutive_fails = 0
                        print(f"{TAG} 🔄 Reconnecting ({reconnect_count}/{MAX_RECONNECT})...")
                        cap.release()
                        time.sleep(RECONNECT_DELAY)
                        cap = _open_stream(stream)
                        if not cap.isOpened():
                            set_camera_status(cam_id, "offline")
                            continue
                        print(f"{TAG} ✅ Reconnected.")
                        set_camera_status(cam_id, "active")
                    else:
                        time.sleep(0.03)
                    continue

            consecutive_fails = 0
            if not is_file:
                reconnect_count = 0

            frame_count += 1

            # ── Progress log (file stream, প্রতি 500 frame) ──
            if is_file and total_frames > 0 and frame_count % 500 == 0:
                pct = frame_count / total_frames * 100
                print(f"{TAG} Progress: {frame_count}/{total_frames} ({pct:.1f}%)")

            frame_resized = cv2.resize(frame, (MONITOR_WIDTH, MONITOR_HEIGHT))

            # ── Signal poll ──
            now = time.time()
            if now - last_signal_poll >= _SIGNAL_POLL_INTERVAL:
                raw_signal       = get_camera_signal(cam_id)
                last_signal_poll = now
                clip_is_active   = clip_manager.has_active_clips()

                if not clip_is_active:
                    if raw_signal == _displayed_signal:
                        _pending_signal = None
                    else:
                        if _pending_signal != raw_signal:
                            _pending_signal = raw_signal
                            _pending_since  = now
                        elif now - _pending_since >= _SIGNAL_DEBOUNCE_SEC:
                            print(f"{TAG} Signal: {_displayed_signal} → {_pending_signal}")
                            _displayed_signal = _pending_signal
                            _pending_signal   = None

            sig_color, is_red, sig_text = _SIGNAL_MAP[_displayed_signal]

            # ── Draw ROI + label ──
            if roi_polygon is not None and roi_polygon.size >= 3:
                cv2.polylines(frame_resized, [roi_polygon], isClosed=True,
                              color=sig_color, thickness=2)
            # cv2.putText(frame_resized, f"{cam_name} | {sig_text}",
            #             (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, sig_color, 2)

            # ── Vehicle detection ──
            detections = []
            for r in model(frame_resized, verbose=False):
                for box in r.boxes:
                    cls = int(box.cls[0])
                    if cls in VEHICLE_CLASSES:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        detections.append([x1, y1, x2, y2, float(box.conf[0]), cls])

            # ── Plate detection ──
            current_plate_boxes = []
            for pr in plate_model(frame_resized, verbose=False):
                for pbox in pr.boxes:
                    px1, py1, px2, py2 = map(int, pbox.xyxy[0])
                    pconf = float(pbox.conf[0])
                    if pconf < PLATE_CONF_TH:
                        continue
                    if frame_resized[py1:py2, px1:px2].size == 0:
                        continue
                    current_plate_boxes.append((px1, py1, px2, py2, pconf))
                    cv2.rectangle(frame_resized, (px1, py1), (px2, py2), (255, 0, 255), 2)

            # ── SORT tracking ──
            tracks = tracker.update(
                np.array([d[:5] for d in detections])
            ) if detections else []

            current_track_ids = set()

            for track in tracks:
                x1, y1, x2, y2, track_id = map(int, track)

                cls_name = None
                for d in detections:
                    if abs(x1 - d[0]) < 50 and abs(y1 - d[1]) < 50:
                        cls_name = VEHICLE_CLASSES[d[5]]; break

                if cls_name is None and track_id not in active_tracks:
                    continue

                center_pt  = ((x1 + x2) // 2, (y1 + y2) // 2)
                corners    = [(x1,y1),(x2,y1),(x2,y2),(x1,y2), center_pt]
                if roi_polygon is not None and roi_polygon.size >= 3:
                    inside_roi = any(
                        cv2.pointPolygonTest(
                            roi_polygon, (float(p[0]), float(p[1])), False) >= 0
                        for p in corners
                    )
                else:
                    inside_roi = True

                buf = update_plate_buffer(
                    track_id, (x1, y1, x2, y2),
                    current_plate_boxes, frame_resized,
                    plate_model, track_plate_buffer,
                    max_age_seconds=3.0
                )

                # ── Color (একবার per track) ──
                if track_id not in track_color_buffer:
                    color_name, _ = _color_detector.detect(frame_resized[y1:y2, x1:x2])
                    if color_name != "UNKNOWN":
                        track_color_buffer[track_id] = color_name
                vehicle_color = track_color_buffer.get(track_id, "UNKNOWN")

                # ── Frame label ──
                if buf and buf["number"]:
                    display = buf["number"]
                    if buf["vtype"] not in ("unknown", ""):
                        display = f"{buf['vtype']} {buf['number']}"
                    display = f"{vehicle_color} | {display}"
                    cv2.putText(frame_resized, display,
                                (x1, y2 + 18),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)

                # ── Speed ──
                speed_kmph = 0.0
                now_t = time.time()
                if track_id in track_last_position:
                    lx, ly, lt = track_last_position[track_id]
                    dt     = max(now_t - lt, 1e-3)
                    dist_m = np.sqrt(
                        (center_pt[0]-lx)**2 + (center_pt[1]-ly)**2
                    ) / PIXELS_PER_METER
                    speed_kmph = (dist_m / dt) * 3.6
                track_last_position[track_id] = (center_pt[0], center_pt[1], now_t)

                hist = track_speed_history.setdefault(track_id, [])
                hist.append(speed_kmph)
                if len(hist) > 5: hist.pop(0)
                speed_kmph = min(sum(hist) / len(hist), 260.0)

                # cv2.putText(frame_resized, f"{speed_kmph:.1f} km/h",
                #             (x1, y2 + 36),
                #             cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
                
                cv2.putText(frame_resized, f"{speed_kmph:.1f} km/h",
                            (x2 - 80, y1 - 10),                     # ← উপরে ডান পাশে
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 2)    # ← green color

                if inside_roi:
                    if track_id not in counted_ids:
                        counted_ids.add(track_id)
                        if cls_name: counts[cls_name] += 1

                    stored_cls = cls_name or (
                        active_tracks[track_id][1]
                        if track_id in active_tracks else "vehicle"
                    )

                    # detected_plates
                    if buf and track_id not in db_logged_tracks:
                        db_logged_tracks.add(track_id)
                        v_path = os.path.join(vio_dir, f"detected_{track_id}_vehicle.jpg")
                        p_path = os.path.join(vio_dir, f"detected_{track_id}_plate.jpg")
                        vcrop  = frame_resized[y1:y2, x1:x2]
                        if vcrop.size > 0:
                            cv2.imwrite(v_path, vcrop)
                        cv2.imwrite(p_path, buf["crop"])
                        
                        insert_detected_plate(
                            camera_id=db_camera_id, track_id=track_id,
                            plate_number=buf["number"], vehicle_type=buf["vtype"],
                            vehicle_class=stored_cls,
                            plate_img_path=_normalize_db_path(p_path),
                            vehicle_img_path=_normalize_db_path(v_path),
                            confidence=buf["score"], vehicle_color=vehicle_color
                        )
                    
                    # insert frame here for OCR voting whether it is speed violation or not
                    ocr_frame_buffer.append(frame_resized.copy())

                    # Speed violation
                    if speed_kmph > SPEED_LIMIT_KMPH and track_id not in speed_violation_ids and buf:
                        speed_violation_ids.add(track_id)
                        vcrop     = frame_resized[y1:y2, x1:x2]
                        v_path    = os.path.join(vio_dir, f"s{track_id}_vehicle.jpg")
                        p_path    = os.path.join(vio_dir, f"s{track_id}_plate.jpg")
                        clip_path = clip_manager.start_clip(track_id + 100000)
                        clip_path = _normalize_db_path(clip_path)
                        print(f"{TAG} 🎬 SPEED | track:{track_id} | {speed_kmph:.1f}")
                        if vcrop.size > 0: cv2.imwrite(v_path, vcrop)
                        cv2.imwrite(p_path, buf["crop"])

                        

                        # -----------here need to insert created at date from the clip by extracting using ocr (pytesseract) and then 
                        # insert into the database along with the other details.----------- 

                        # from this clip_path , extract the date and time using OCR and then pass it to the insert_speed_violation function.

                        # store the date and time extracted from the frame using OCR and pass in to insert function for insertion
                        # take clip from clip_path and extract the date and time from the frame using OCR and then pass it to the insert_speed_violation function.
                        results_ocr = []

                        for frm in ocr_frame_buffer:
                            d, t = find_date_time(frm)
                            if d is not None and t is not None:
                                results_ocr.append(f"{d} {t}")
                        
                        if results_ocr:
                            vote = Counter(results_ocr)
                            best_timestamp, count = vote.most_common(1)[0]
                        else:
                            best_timestamp=None

                        # date, time_ = find_date_time(frame_resized)
                        # field name in database is created_at, so we need to pass the date and time in the insert_speed_violation function as a string
                        # first date and time need to be combined into a single string in the format of "YYYY-MM-DD HH:MM:SS" and then pass it to the 
                        # insert_speed_violation function.
                        # date_time_str = f"{date} {time_}"

                        insert_speed_violation(
                            camera_id=db_camera_id, track_id=track_id,
                            plate_number=buf["number"], vehicle_type=buf["vtype"],
                            vehicle_class=stored_cls,
                            plate_img_path=_normalize_db_path(p_path),
                            vehicle_img_path=_normalize_db_path(v_path),
                            confidence=buf["score"], speed_kmph=speed_kmph,
                            speed_limit=SPEED_LIMIT_KMPH, clip_path=clip_path,
                            vehicle_color=vehicle_color,created_at=best_timestamp
                        )
                        cv2.putText(frame_resized, "SPEED!",
                                    (x1, y1-28), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.6, (0, 140, 255), 2)

                    active_tracks[track_id] = [(x1, y1, x2, y2), stored_cls]
                else:
                    if track_id in active_tracks:
                        active_tracks[track_id][0] = (x1, y1, x2, y2)

                current_track_ids.add(track_id)

            # ── Stale track cleanup ──
            for tid in list(active_tracks.keys()):
                if tid not in current_track_ids:
                    del active_tracks[tid]
                    track_plate_buffer.pop(tid, None)
                    track_last_position.pop(tid, None)
                    track_speed_history.pop(tid, None)
                    track_color_buffer.pop(tid, None)
                    clear_vote_store(tid)

            # ── Draw boxes ──
            for tid, (bbox, cname) in active_tracks.items():
                bx1, by1, bx2, by2 = bbox
                pk = "+" if tid in track_plate_buffer else ""
                cv2.rectangle(frame_resized, (bx1, by1), (bx2, by2), (0, 255, 255), 2)
                # cv2.putText(frame_resized, f"{cname} #{tid}{pk}",
                #             (bx1, by1-16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,255,255), 1)

            # ── Clip ──
            clip_manager.push_frame(frame_resized)

            # ── Preview → main process ──
            if preview_queue is not None and frame_count % PREVIEW_EVERY == 0:
                preview = cv2.resize(frame_resized, (640, 360))
                try:
                    while not preview_queue.empty():
                        try: preview_queue.get_nowait()
                        except Exception: break
                    preview_queue.put_nowait((cam_id, cam_name, preview))
                except Exception:
                    pass

            if cv2.waitKey(1) & 0xFF == 27:
                # ESC চাপলে — file stream হলে incomplete, RTSP হলে graceful stop
                if is_file:
                    print(f"{TAG} ESC pressed — video interrupted.")
                    completed_successfully = False
                else:
                    completed_successfully = True
                break

    except KeyboardInterrupt:
        # file stream interrupt → incomplete
        completed_successfully = not is_file

    except Exception as e:
        import traceback
        print(f"{TAG} Error: {e}")
        traceback.print_exc()
        completed_successfully = False

    finally:
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        if clip_manager is not None:
            clip_manager.release_all()
        set_camera_status(cam_id, "inactive")
        print(f"{TAG} Stopped. Counts: {counts}")

    return completed_successfully

