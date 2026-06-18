### ANPR Server

Automatic Number Plate Recognition (ANPR) server for real-time and recorded video processing. The system detects vehicles, recognizes license plates, tracks vehicles across frames, estimates 
speed, detects violations, records evidence clips, and stores events in a database. The pipeline is built using YOLO, OpenCV, OCR, and multi-camera processing. ANPR systems commonly combine 
vehicle detection, plate localization, OCR, tracking, and database logging to automate traffic monitoring and enforcement workflows.

### Features
 - Multi-camera processing
 - RTSP and local video file support
 - Vehicle detection using YOLO
 - License plate detection and recognition
 - Vehicle tracking using SORT
 - Vehicle color classification
 - Speed estimation
 - Speed violation detection
 - Automatic evidence clip generation
 - OCR-based timestamp extraction
 - Database integration for event logging
 - Camera status monitoring 
 - Live preview dashboard
 - Automatic file watching and processing
 - Multiprocessing architecture for handling multiple cameras simultaneously

### System Architecture
```
Camera / Video File
        │
        ▼
 Vehicle Detection (YOLO)
        │
        ▼
 Vehicle Tracking (SORT)
        │
        ├────────► Speed Estimation
        │
        ├────────► Vehicle Color Detection
        │
        ▼
 Plate Detection (YOLO)
        │
        ▼
 OCR / Plate Recognition
        │
        ▼
 Database Logging
        │
        ├────────► Detected Vehicles
        ├────────► Speed Violations
        └────────► Evidence Clips
```

### Project Structure
```
ANPR-Server/
│
├── main_new.py                 # Main application entry point
├── camera_worker.py            # Camera processing worker
├── database.py                 # Database operations
├── helpers.py                  # Utility functions
├── config.py                   # Configuration settings
├── clip.py                     # Violation clip generation
├── ocr.py                      # Timestamp OCR extraction
├── sort.py                     # SORT tracker
│
├── uploads/
│   └── camera_id/
│       └── YYYYMMDD/
│           └── validations/
│
├── models/
│   ├── vehicle.pt
│   └── plate.pt
│
└── requirements.txt
```
### Detection Pipeline
#### Vehicle Detection
The system uses YOLO models to detect:
- Car
- Motorbike
- Bus
- Truck
#### Plate Recognition
  - Vehicle detected
  - License plate localized
  - Plate cropped
  - OCR applied
  - Voting mechanism used for improved accuracy
  - Result stored in database
#### Speed Detection
Vehicle speed is estimated using:

```
Distance Travelled (pixels)
           │
           ▼
Pixels Per Meter Calibration
           │
           ▼
Speed (km/h)
```
Speed violations are automatically recorded when:
```
Vehicle Speed > Configured Speed Limit
```
### OCR Timestamp Extraction

The system extracts timestamp overlays directly from video frames.

Features:

- Multiple preprocessing strategies
- Threshold voting
- OCR result voting
- Timestamp validation
- Automatic fallback handling

Example:
```
15/06/2026 13:50:44
```
Converted to:
```
2026-06-15 13:50:44
```

### Database Records

#### Detected Plates

Stores:

Camera ID
Track ID
Plate Number
Vehicle Type
Vehicle Color
Confidence Score
Plate Image
Vehicle Image
Timestamp

#### Speed Violations

Stores:

Camera ID
Track ID
Plate Number
Vehicle Type
Vehicle Color
Speed
Speed Limit
Violation Clip
Vehicle Image
Plate Image
Created Timestamp

### Installation
#### Clone Repository
```
git clone https://github.com/Oudarja/ANPR-Server.git
cd ANPR-Server
```
#### Create Virtual Environment
```
python -m venv .venv
source .venv/bin/activate
```
#### Install Dependencies

```
pip install -r requirements.txt
```
### Configuration

Update settings inside:

```
config.py
```
Important parameters:
```
SPEED_LIMIT_KMPH
PIXELS_PER_METER

VEHICLE_MODEL
PLATE_MODEL

UPLOAD_ROOT

MONITOR_WIDTH
MONITOR_HEIGHT

```

### Running the Server
```
python main_new.py
```
### Output Directory Structure
```
uploads/
└── 201/
    └── 20260617/
        └── validations/
            ├── clips/
            ├── detected_1_vehicle.jpg
            ├── detected_1_plate.jpg
            ├── s1_vehicle.jpg
            └── s1_plate.jpg
```
### Technologies Used
  - Python
  - OpenCV
  - YOLO
  - SORT Tracker
  - Tesseract OCR
  - NumPy
  - MySQL
  - Multiprocessing

### Use Cases
- Traffic Monitoring
- Smart City Applications
- Toll Booth Monitoring
- Parking Management
- Vehicle Access Control
- Speed Enforcement
- Security Surveillance
- Law Enforcement Analytics

Future Improvements
- TensorRT Optimization
- PaddleOCR Integration
- Vehicle Make/Model Recognition
- Lane Violation Detection
- Traffic Signal Violation Detection
- Real-Time Dashboard
- REST API
- Kafka-Based Event Streaming
- Distributed Multi-Server Processing




