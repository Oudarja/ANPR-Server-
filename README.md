# ANPR Project

Automatic Number Plate Recognition and traffic-violation processing system for multi-camera video feeds. The project combines vehicle detection, plate detection, OCR, tracking, speed estimation, clip generation, and MySQL logging.

## What It Does

- Processes multiple cameras in parallel
- Supports RTSP streams and local/uploaded video files
- Detects vehicles with YOLO
- Detects license plates with a separate YOLO model
- Reads plate text with OCR and multi-frame voting
- Estimates vehicle speed and flags speed violations
- Saves evidence clips for violations
- Extracts timestamps from video frames
- Stores detections and violations in MySQL
- Watches upload folders and processes new videos automatically

## Main Components

- `main_new.py` - launcher that loads active cameras and starts worker processes
- `camera_worker.py` - per-camera detection, tracking, OCR, and violation handling
- `helpers.py` - plate matching, OCR voting, and plate text parsing
- `ocr.py` - timestamp extraction from video frames
- `clip.py` - non-blocking clip writer for violation evidence
- `database.py` - MySQL schema and query helpers
- `config.py` - model paths, database settings, thresholds, and folder mapping

## Repository Layout

```text
.
├── main_new.py
├── camera_worker.py
├── database.py
├── helpers.py
├── ocr.py
├── clip.py
├── sort.py
├── config.py
├── req.txt
├── yolov8n.pt
├── ashraf.pt
├── yolov8n.onnx
├── ashraf.onnx
└── Image_Sharpening/
```

## Runtime Flow

```text
Camera / Video File
        │
        ▼
Vehicle Detection (YOLO)
        │
        ▼
Tracking (SORT)
        │
        ├──► Speed Estimation
        ├──► Vehicle Color Detection
        ▼
Plate Detection (YOLO)
        │
        ▼
OCR + Voting
        │
        ▼
MySQL Logging
        ├── detected_plates
        ├── violations
        └── speed_violations
```

## Installation

1. Create and activate a virtual environment.

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r req.txt
```

3. Make sure MySQL is running and the database credentials in `config.py` are correct.

## Configuration

Key settings live in `config.py`:

- `DB_CONFIG` - MySQL connection details
- `UPLOAD_ROOT` - root folder watched for videos
- `CAMERA_FOLDER_MAP` - camera ID to upload-folder mapping
- `VEHICLE_MODEL` - vehicle detector path
- `PLATE_MODEL` - plate detector path
- `SPEED_LIMIT_KMPH` - speed threshold
- `PIXELS_PER_METER` - calibration value used for speed estimation
- `MONITOR_WIDTH` / `MONITOR_HEIGHT` - processing frame size

The project currently uses:

- `yolov8n.pt` for vehicle detection
- `ashraf.pt` for plate detection
- `easyocr` for OCR-based timestamp reading in `ocr.py`

## Database

The application initializes and uses these tables:

- `cameras`
- `detected_plates`
- `violations`
- `speed_violations`

The schema is created by `init_db()` in `database.py` when the app starts.

## Running

Start the main launcher:

```bash
python main_new.py
```

The app loads active cameras from MySQL, starts a worker for each one, and begins processing available streams or files.

## Output

Processed videos and evidence are organized under the upload root defined in `config.py`. A typical structure looks like:

```text
uploads/
└── 201/
    └── 20260617/
        └── validations/
            ├── clips/
            ├── detected_*.jpg
            ├── plate_*.jpg
            └── vehicle_*.jpg
```

Violation clips are saved as browser-friendly MP4 files with a short pre-roll and post-roll.

## OCR Notes

`ocr.py` extracts timestamp overlays from the top-left area of each frame. It uses multiple preprocessing strategies and is designed to be called safely from threaded or multi-process camera workers without changing the OCR logic. When OCR fails, it falls back safely.

## Calibration Notes

Speed estimation depends on camera geometry and calibration values in `config.py`. If the camera angle or coverage changes, update:

- `CAMERA_ANGLE_DEG`
- `COVERAGE_FEET`
- `PIXELS_PER_METER`

## Optional Utilities

The repository also includes a few helper/test scripts such as:

- `test_ocr.py`
- `check_video.py`
- `calibrate_camera.py`
- `move_file.py`
- `sort.py`

## Requirements

Python packages are listed in `req.txt`.

## License

No license file is included yet. Add one if you plan to share or publish the project.
