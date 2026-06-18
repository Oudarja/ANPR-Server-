# # =====================================================
# # config.py — Global configuration
# # Camera-specific settings DB এর cameras table থেকে আসে
# # =====================================================

# # ── Display ──
# MONITOR_WIDTH    = 1280
# MONITOR_HEIGHT   = 720

# # ── Signal timing (seconds) ──
# GREEN_TIME       = 20
# ORANGE_TIME      = 12
# RED_TIME         = 76
# CYCLE_TIME       = GREEN_TIME + ORANGE_TIME + RED_TIME

# # ── Detection thresholds ──
# PLATE_CONF_TH    = 0.25
# SPEED_LIMIT_KMPH = 100.0
# PIXELS_PER_METER = 25.0

# # ── Models ──
# VEHICLE_MODEL    = "yolov8n.pt"
# PLATE_MODEL      = "ashraf.pt"

# # ── YOLO vehicle class IDs ──
# VEHICLE_CLASSES  = {2: "car", 3: "motorbike", 5: "bus", 7: "truck"}

# # ── Upload folder processing ──
# UPLOAD_ROOT              = "/mnt/second_drive/ftpman/uploads"
# UPLOAD_POLL_INTERVAL     = 10
# VIDEO_RETRY_SECONDS      = 300
# VIDEO_STABLE_CHECK_SECONDS = 2
# VIDEO_EXTENSIONS         = {".mp4", ".mov", ".avi", ".mkv", ".mpg", ".mpeg", ".mov", ".mjpeg",".ts"}

# # ── Process videos from today and future dates (set False to process only older dates) ──
# PROCESS_TODAY_VIDEOS     = True

# # ── Camera ID to upload folder mapping ──
# # Maps database camera ID to the folder name under UPLOAD_ROOT
# # E.g., camera ID 1 watches uploads/201/, camera ID 2 watches uploads/202/
# CAMERA_FOLDER_MAP = {
#     1: "201",      # Camera 1 → uploads/201/
#     2: "202",      # Camera 2 → uploads/202/
#     3: "102",
#     # 4: "101",      # Camera 4 → uploads/102/
#     # Add more mappings as needed: 4: "102", etc.
# }

# # ── Bangladeshi license plate prefix → vehicle type ──
# LICENSE_TYPE_MAP = {
#     'a':'motorcycle','ha':'motorcycle','la':'motorcycle',
#     'ka':'car','kha':'car','bha':'car','ga':'car','gha':'car',
#     'cha':'microbus','pa':'taxi','ja':'bus','caa':'ambulance',
#     'ba':'bus','jha':'bus','sa':'bus','twa':'motorcycle',
#     'taw':'cng','dwa':'cng','tha':'van','ma':'van',
#     'na':'truck','au':'truck','da':'truck','u':'truck',
#     'ta':'truck','dha':'truck'
# }

# # ── MySQL connection ──
# DB_CONFIG = {
#     "host":     "localhost",
#     "port":     3306,
#     "user":     "khalil",
#     "password": "##DevsZone2015##",
#     "database": "traffic_db"
# }



# =====================================================
# config.py — Global configuration
# Camera-specific settings DB এর cameras table থেকে আসে
# =====================================================

import math

# ── Display ──
MONITOR_WIDTH    = 1280
MONITOR_HEIGHT   = 720

# ── Signal timing (seconds) ──
GREEN_TIME       = 20
ORANGE_TIME      = 12
RED_TIME         = 76
CYCLE_TIME       = GREEN_TIME + ORANGE_TIME + RED_TIME

# ── Detection thresholds ──
PLATE_CONF_TH    = 0.25
SPEED_LIMIT_KMPH = 10.0

# ── Camera geometry — এখানে আপনার values দিন ──
CAMERA_ANGLE_DEG     = 35.0          # camera tilt angle (degree)
COVERAGE_FEET        = 45.0          # camera যতটুকু ground cover করে (feet)
COVERAGE_METERS      = COVERAGE_FEET * 0.3048   # → 13.716 meter
FRAME_WIDTH_PX       = MONITOR_WIDTH             # → 1280 px

# ── PIXELS_PER_METER auto-calculate ──
# Formula:
#   base         = frame_width / ground_coverage_meters
#   cos_angle    = cos(camera_tilt) → perspective correction
#   px_per_meter = base / cos_angle
#
# Example:
#   base         = 1280 / 13.716  = 93.32 px/m
#   cos(35°)     = 0.8192
#   px_per_meter = 93.32 / 0.8192 = 113.9 px/m

_base            = FRAME_WIDTH_PX / COVERAGE_METERS
_cos_angle       = math.cos(math.radians(CAMERA_ANGLE_DEG))
PIXELS_PER_METER = round(_base / _cos_angle, 2)   # ≈ 113.9

# ── Models ──
VEHICLE_MODEL    = "yolov8n.pt"
PLATE_MODEL      = "ashraf.pt"

# ── YOLO vehicle class IDs ──
VEHICLE_CLASSES  = {2: "car", 3: "motorbike", 5: "bus", 7: "truck"}

# ── Upload folder processing ──
# UPLOAD_ROOT              = "/mnt/second_drive/ftpman/uploads"
UPLOAD_ROOT              = "/media/tanmoy002/HDD/anprppp/uploads"
UPLOAD_POLL_INTERVAL     = 10
VIDEO_RETRY_SECONDS      = 300
VIDEO_STABLE_CHECK_SECONDS = 2
VIDEO_EXTENSIONS         = {".mp4", ".mov", ".avi", ".mkv", ".mpg", ".mpeg", ".mov", ".mjpeg",".ts"}

# ── Process videos from today and future dates (set False to process only older dates) ──
PROCESS_TODAY_VIDEOS     = True

# ── Camera ID to upload folder mapping ──
CAMERA_FOLDER_MAP = {
    1: "201",
    2: "202",
    3: "102",
    6: "101",
}

# ── Bangladeshi license plate prefix → vehicle type ──
LICENSE_TYPE_MAP = {
    'a':'motorcycle','ha':'motorcycle','la':'motorcycle',
    'ka':'car','kha':'car','bha':'car','ga':'car','gha':'car',
    'cha':'microbus','pa':'taxi','ja':'bus','caa':'ambulance',
    'ba':'bus','jha':'bus','sa':'bus','twa':'motorcycle',
    'taw':'cng','dwa':'cng','tha':'van','ma':'van',
    'na':'truck','au':'truck','da':'truck','u':'truck',
    'ta':'truck','dha':'truck'
}

# ── MySQL connection ──
DB_CONFIG = {
    "host":     "localhost",
    "port":     3306,
    "user":     "root",
    "password": "root123",
    "database": "New_traffic_db"
}