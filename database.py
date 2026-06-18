

# # =====================================================
# # database.py — MySQL handler (multi-camera)
# #
# # Tables:
# #   cameras          — camera registry
# #   detected_plates  — সব detected plate
# #   violations       — red-light violations
# #   speed_violations — speed violations
# # =====================================================

# from ast import literal_eval

# import mysql.connector
# from mysql.connector import Error
# from config import DB_CONFIG


# # ─────────────────────────────────────────────────────
# # Connection
# # ─────────────────────────────────────────────────────

# def get_connection():
#     try:
#         return mysql.connector.connect(**DB_CONFIG)
#     except Error as e:
#         print(f" DB connection error: {e}")
#         return None


# def _create_database_if_needed():
#     try:
#         cfg = {k: v for k, v in DB_CONFIG.items() if k != "database"}
#         conn = mysql.connector.connect(**cfg)
#         cur  = conn.cursor()
#         cur.execute(
#             f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} "
#             f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
#         )
#         conn.commit()
#         cur.close(); conn.close()
#     except Error as e:
#         print(f"Could not create database: {e}")


# # ─────────────────────────────────────────────────────
# # Schema init
# # ─────────────────────────────────────────────────────

# def init_db():
#     _create_database_if_needed()
#     conn = get_connection()
#     if not conn:
#         return
#     cur = conn.cursor()

#     # cameras
#     cur.execute("""
#         CREATE TABLE IF NOT EXISTS cameras (
#             id                   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
#             name                 VARCHAR(255)  NOT NULL,
#             description          TEXT          NULL,
#             stream_url           VARCHAR(512)  NOT NULL,
#             stream_type          VARCHAR(50)   NOT NULL DEFAULT 'rtsp'
#                                  COMMENT 'rtsp | mjpeg | file',
#             location             VARCHAR(255)  NULL,
#             latitude             VARCHAR(50)   NULL,
#             longitude            VARCHAR(50)   NULL,
#             status               VARCHAR(50)   NOT NULL DEFAULT 'active'
#                                  COMMENT 'active | inactive | offline',
#             frame_rate           INT           NOT NULL DEFAULT 30,
#             resolution           VARCHAR(50)   NOT NULL DEFAULT '1920x1080',
#             processing_interval  INT           NOT NULL DEFAULT 5
#                                  COMMENT 'seconds between processing frames',
#             traffic_signal       VARCHAR(10)   NULL DEFAULT NULL
#                                  COMMENT 'red | green | orange — live signal state from external controller',
#             is_active            TINYINT(1)    NOT NULL DEFAULT 1,
#             created_at           TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP,
#             updated_at           TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP
#                                  ON UPDATE CURRENT_TIMESTAMP,
#             deleted_at           TIMESTAMP     NULL DEFAULT NULL,
#             INDEX idx_status  (status),
#             INDEX idx_active  (is_active)
#         ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
#     """)

#     # detected_plates
#     # cur.execute("""
#     #     CREATE TABLE IF NOT EXISTS detected_plates (
#     #         id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
#     #         camera_id        BIGINT UNSIGNED NOT NULL,
#     #         track_id         INT             NOT NULL,
#     #         plate_number     VARCHAR(50),
#     #         vehicle_type     VARCHAR(50),
#     #         vehicle_class    VARCHAR(50),
#     #         plate_img_path   VARCHAR(500),
#     #         vehicle_img_path VARCHAR(500),
#     #         confidence       FLOAT,
#     #         detected_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
#     #         INDEX idx_camera (camera_id),
#     #         INDEX idx_track  (track_id),
#     #         INDEX idx_plate  (plate_number)
#     #     ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
#     # """)

#     # detected_plates
#     cur.execute("""
#         CREATE TABLE IF NOT EXISTS detected_plates (
#             id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
#             camera_id        BIGINT UNSIGNED NOT NULL,
#             track_id         INT             NOT NULL,
#             plate_number     VARCHAR(50),
#             vehicle_type     VARCHAR(50),
#             vehicle_class    VARCHAR(50),
#             plate_img_path   VARCHAR(500),
#             vehicle_img_path VARCHAR(500),
#             confidence       FLOAT,

#             status           VARCHAR(50) DEFAULT NULL,
#             notes            TEXT DEFAULT NULL,
#             location_id      BIGINT DEFAULT NULL,

#             vehicle_color    VARCHAR(20) DEFAULT 'UNKNOWN',

#             detected_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
#             created_at       TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
#             updated_at       TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
#                             ON UPDATE CURRENT_TIMESTAMP,

#             INDEX idx_camera   (camera_id),
#             INDEX idx_track    (track_id),
#             INDEX idx_plate    (plate_number),
#             INDEX idx_status   (status),
#             INDEX idx_location (location_id)

#         ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
#     """)

#     # violations (red-light)
#     cur.execute("""
#         CREATE TABLE IF NOT EXISTS violations (
#             id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
#             camera_id        BIGINT UNSIGNED NOT NULL,
#             track_id         INT             NOT NULL,
#             plate_number     VARCHAR(50),
#             vehicle_type     VARCHAR(50),
#             vehicle_class    VARCHAR(50),
#             plate_img_path   VARCHAR(500),
#             vehicle_img_path VARCHAR(500),
#             confidence       FLOAT,
#             signal_state     VARCHAR(10)  DEFAULT 'RED',
#             clip_path        VARCHAR(500),
#             violated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
#             INDEX idx_camera (camera_id),
#             INDEX idx_track  (track_id),
#             INDEX idx_plate  (plate_number)
#         ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
#     """)

#     # speed_violations
#     cur.execute("""
#         CREATE TABLE IF NOT EXISTS speed_violations (
#             id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
#             camera_id        BIGINT UNSIGNED NOT NULL,
#             track_id         INT             NOT NULL,
#             plate_number     VARCHAR(50),
#             vehicle_type     VARCHAR(50),
#             vehicle_class    VARCHAR(50),
#             plate_img_path   VARCHAR(500),
#             vehicle_img_path VARCHAR(500),
#             confidence       FLOAT,
#             speed_kmph       FLOAT,
#             speed_limit      FLOAT,
#             clip_path        VARCHAR(500),
#             violated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
#             INDEX idx_camera (camera_id),
#             INDEX idx_track  (track_id),
#             INDEX idx_plate  (plate_number)
#         ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
#     """)

#     conn.commit()

#     # ── পুরনো table এ camera_id না থাকলে যোগ করো ──
#     for table in ("detected_plates", "violations", "speed_violations"):
#         try:
#             cur.execute(f"""
#                 ALTER TABLE {table}
#                 ADD COLUMN camera_id BIGINT UNSIGNED NOT NULL DEFAULT 1
#                 AFTER id
#             """)
#             conn.commit()
#             print(f" camera_id added to {table}")
#         except Error:
#             pass  # আগে থেকেই আছে

#     # ── cameras table এ traffic_signal column না থাকলে যোগ করো ──
#     try:
#         cur.execute("""
#             ALTER TABLE cameras
#             ADD COLUMN traffic_signal VARCHAR(10) NULL DEFAULT NULL
#             COMMENT 'red | green | orange'
#             AFTER processing_interval
#         """)
#         conn.commit()
#         print(" traffic_signal column added to cameras")
#     except Error:
#         pass  # আগে থেকেই আছে

#     # ── vehicle_color column না থাকলে সব table এ যোগ করো ──
#     for table in ("detected_plates", "violations", "speed_violations"):
#         try:
#             cur.execute(f"""
#                 ALTER TABLE {table}
#                 ADD COLUMN vehicle_color VARCHAR(20) DEFAULT 'UNKNOWN'
#             """)
#             conn.commit()
#             print(f" vehicle_color added to {table}")
#         except Error:
#             pass  # আগে থেকেই আছে

#     cur.close(); conn.close()
#     print(" All tables ready.")


# # ─────────────────────────────────────────────────────
# # Camera helpers
# # ─────────────────────────────────────────────────────

# def get_active_cameras():
#     """
#     DB এর cameras table থেকে সব active camera return করে।
#     Return: list of dict  — প্রতিটায় id, name, stream_url, ... আছে।
#     """
#     conn = get_connection()
#     if not conn:
#         return []
#     try:
#         cur = conn.cursor(dictionary=True)
#         cur.execute("""
#             SELECT id, name, stream_url, stream_type,
#                    location, frame_rate, resolution,
#                    processing_interval, status, traffic_signal
#             FROM   cameras
#             WHERE  is_active = 1
#               AND  deleted_at IS NULL
#             ORDER  BY id
#         """)
#         rows = cur.fetchall()
#         cur.close(); conn.close()
#         return rows
#     except Error as e:
#         print(f" get_active_cameras: {e}")
#         return []


# def set_camera_status(camera_id: int, status: str):
#     """
#     cameras.status কে update করে।
#     status: 'active' | 'offline' | 'inactive'
#     """
#     conn = get_connection()
#     if not conn:
#         return
#     try:
#         cur = conn.cursor()
#         cur.execute(
#             "UPDATE cameras SET status=%s WHERE id=%s",
#             (status, camera_id)
#         )
#         conn.commit()
#         cur.close(); conn.close()
#     except Error as e:
#         print(f" set_camera_status: {e}")


# # ─────────────────────────────────────────────────────
# # Traffic Signal — live DB poll
# # ─────────────────────────────────────────────────────

# # Valid signal values
# _VALID_SIGNALS = {"red", "green", "orange"}

# def get_camera_signal(camera_id: int) -> str:
#     """
#     cameras.traffic_signal থেকে live signal পড়ে।

#     Return values:
#         'red'    — লাল signal
#         'green'  — সবুজ signal
#         'orange' — হলুদ/কমলা signal
#         'unknown'— DB তে NULL বা invalid value আছে (warning print করে)

#     যেকোনো DB error এ 'unknown' return করে যাতে system crash না করে।
#     """
#     conn = get_connection()
#     if not conn:
#         return "unknown"
#     try:
#         cur = conn.cursor()
#         cur.execute(
#             "SELECT traffic_signal FROM cameras WHERE id = %s AND deleted_at IS NULL",
#             (camera_id,)
#         )
#         row = cur.fetchone()
#         cur.close()
#         conn.close()

#         if row is None:
#             print(f" [CAM-{camera_id}] Camera not found in DB.")
#             return "unknown"

#         raw = row[0]

#         # NULL চেক
#         if raw is None:
#             print(f"  [CAM-{camera_id}] traffic_signal is NULL in DB.")
#             return "unknown"

#         normalized = raw.strip().lower()

#         # Validation
#         if normalized not in _VALID_SIGNALS:
#             print(
#                 f" [CAM-{camera_id}] Invalid traffic_signal value: '{raw}' "
#                 f"(allowed: red | green | orange)"
#             )
#             return "unknown"

#         return normalized

#     except Error as e:
#         print(f" get_camera_signal cam={camera_id}: {e}")
#         return "unknown"


# # ─────────────────────────────────────────────────────
# # Insert functions
# # ─────────────────────────────────────────────────────

# def insert_detected_plate(camera_id, track_id, plate_number,
#                           vehicle_type, vehicle_class,
#                           plate_img_path, vehicle_img_path,
#                           confidence, vehicle_color="UNKNOWN"):
#     conn = get_connection()
#     if not conn:
#         return
#     try:
#         cur = conn.cursor()
#         cur.execute("""
#             INSERT INTO detected_plates
#                 (camera_id, track_id, plate_number, vehicle_type,
#                  vehicle_class, plate_img_path, vehicle_img_path,
#                  confidence, vehicle_color)
#             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
#         """, (camera_id, track_id, plate_number, vehicle_type,
#               vehicle_class, plate_img_path, vehicle_img_path,
#               confidence, vehicle_color))
#         conn.commit(); cur.close()
#     except Error as e:
#         print(f" insert_detected_plate: {e}")
#     finally:
#         conn.close()


# def insert_violation(camera_id, track_id, plate_number,
#                      vehicle_type, vehicle_class,
#                      plate_img_path, vehicle_img_path,
#                      confidence, signal_state="RED",
#                      clip_path=None, vehicle_color="UNKNOWN"):
#     conn = get_connection()
#     if not conn:
#         return
#     try:
#         cur = conn.cursor()
#         cur.execute("""
#             INSERT INTO violations
#                 (camera_id, track_id, plate_number, vehicle_type,
#                  vehicle_class, plate_img_path, vehicle_img_path,
#                  confidence, signal_state, clip_path, vehicle_color)
#             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
#         """, (camera_id, track_id, plate_number, vehicle_type,
#               vehicle_class, plate_img_path, vehicle_img_path,
#               confidence, signal_state, clip_path, vehicle_color))
#         conn.commit(); cur.close()
#         print(f"    RED violation | cam:{camera_id} track:{track_id}")
#     except Error as e:
#         print(f"insert_violation: {e}")
#     finally:
#         conn.close()


# def insert_speed_violation(camera_id, track_id, plate_number,
#                            vehicle_type, vehicle_class,
#                            plate_img_path, vehicle_img_path,
#                            confidence, speed_kmph, speed_limit,
#                            clip_path=None, vehicle_color="UNKNOWN"):
#     conn = get_connection()
#     if not conn:
#         return
#     try:
#         cur = conn.cursor()
#         cur.execute("""
#             INSERT INTO speed_violations
#                 (camera_id, track_id, plate_number, vehicle_type,
#                  vehicle_class, plate_img_path, vehicle_img_path,
#                  confidence, speed_kmph, speed_limit, clip_path, vehicle_color)
#             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
#         """, (camera_id, track_id, plate_number, vehicle_type,
#               vehicle_class, plate_img_path, vehicle_img_path,
#               confidence, speed_kmph, speed_limit, clip_path, vehicle_color))
#         conn.commit(); cur.close()
#         print(f"    SPEED violation | cam:{camera_id} track:{track_id} | {speed_kmph:.1f} km/h")
#     except Error as e:
#         print(f" insert_speed_violation: {e}")
#     finally:
#         conn.close()


# def load_rois_from_db():
#     conn = mysql.connector.connect(**DB_CONFIG)
#     cur = conn.cursor(dictionary=True)

#     cur.execute("SELECT id, roi_value FROM cameras")
#     rows = cur.fetchall()

#     PREDEFINED_ROIS = {}

#     for row in rows:
#         cam_id  = row["id"]
#         roi_str = row["roi_value"]

#         if not roi_str:
#             continue

#         try:
#             roi_list = literal_eval(roi_str)

#             if len(roi_list) < 3:
#                 print(f" Camera {cam_id} ROI invalid (<3 points)")
#                 continue

#             PREDEFINED_ROIS[cam_id] = [
#                 (int(x), int(y)) for x, y in roi_list
#             ]

#         except Exception as e:
#             print(f" Camera {cam_id} ROI parse error: {e}")

#     cur.close()
#     conn.close()

#     return PREDEFINED_ROIS


# # ─────────────────────────────────────────────────────
# # Summary
# # ─────────────────────────────────────────────────────

# def print_summary():
#     conn = get_connection()
#     if not conn:
#         return
#     cur = conn.cursor()
#     cur.execute("SELECT COUNT(*) FROM detected_plates");  dp = cur.fetchone()[0]
#     cur.execute("SELECT COUNT(*) FROM violations");       v  = cur.fetchone()[0]
#     cur.execute("SELECT COUNT(*) FROM speed_violations"); s  = cur.fetchone()[0]
#     print(f"\nSUMMARY  Detected:{dp}  RedLight:{v}  Speed:{s}")
#     cur.close(); conn.close()


# if __name__ == "__main__":
#     init_db()
#     print_summary()




# =====================================================
# database.py — MySQL handler (multi-camera)
#
# Tables:
#   cameras          — camera registry
#   detected_plates  — সব detected plate
#   violations       — red-light violations
#   speed_violations — speed violations
# =====================================================

from ast import literal_eval

import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG


# ─────────────────────────────────────────────────────
# Connection
# ─────────────────────────────────────────────────────

def get_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        print(f" DB connection error: {e}")
        return None


def _create_database_if_needed():
    try:
        cfg = {k: v for k, v in DB_CONFIG.items() if k != "database"}
        conn = mysql.connector.connect(**cfg)
        cur  = conn.cursor()
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
        cur.close(); conn.close()
    except Error as e:
        print(f" Could not create database: {e}")


# ─────────────────────────────────────────────────────
# Schema init
# ─────────────────────────────────────────────────────

def init_db():
    _create_database_if_needed()
    conn = get_connection()
    if not conn:
        return
    cur = conn.cursor()

    # cameras
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cameras (
            id                   BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            name                 VARCHAR(255)  NOT NULL,
            description          TEXT          NULL,
            stream_url           VARCHAR(512)  NOT NULL,
            stream_type          VARCHAR(50)   NOT NULL DEFAULT 'rtsp'
                                 COMMENT 'rtsp | mjpeg | file',
            location             VARCHAR(255)  NULL,
            latitude             VARCHAR(50)   NULL,
            longitude            VARCHAR(50)   NULL,
            status               VARCHAR(50)   NOT NULL DEFAULT 'active'
                                 COMMENT 'active | inactive | offline',
            frame_rate           INT           NOT NULL DEFAULT 30,
            resolution           VARCHAR(50)   NOT NULL DEFAULT '1920x1080',
            processing_interval  INT           NOT NULL DEFAULT 5
                                 COMMENT 'seconds between processing frames',
            traffic_signal       VARCHAR(10)   NULL DEFAULT NULL
                                 COMMENT 'red | green | orange — live signal state from external controller',
            is_active            TINYINT(1)    NOT NULL DEFAULT 1,
            created_at           TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at           TIMESTAMP     NULL DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,
            deleted_at           TIMESTAMP     NULL DEFAULT NULL,
            INDEX idx_status  (status),
            INDEX idx_active  (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # detected_plates
    cur.execute("""
        CREATE TABLE IF NOT EXISTS detected_plates (
            id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            camera_id        BIGINT UNSIGNED NOT NULL,
            track_id         INT             NOT NULL,
            plate_number     VARCHAR(50),
            vehicle_type     VARCHAR(50),
            vehicle_class    VARCHAR(50),
            plate_img_path   VARCHAR(500),
            vehicle_img_path VARCHAR(500),
            confidence       FLOAT,
            detected_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_camera (camera_id),
            INDEX idx_track  (track_id),
            INDEX idx_plate  (plate_number)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # violations (red-light)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS violations (
            id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            camera_id        BIGINT UNSIGNED NOT NULL,
            track_id         INT             NOT NULL,
            plate_number     VARCHAR(50),
            vehicle_type     VARCHAR(50),
            vehicle_class    VARCHAR(50),
            plate_img_path   VARCHAR(500),
            vehicle_img_path VARCHAR(500),
            confidence       FLOAT,
            signal_state     VARCHAR(10)  DEFAULT 'RED',
            clip_path        VARCHAR(500),
            vehicle_color    VARCHAR(20)  DEFAULT 'UNKNOWN',
            violated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_at       TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
                             ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_camera (camera_id),
            INDEX idx_track  (track_id),
            INDEX idx_plate  (plate_number)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # speed_violations
    cur.execute("""
        CREATE TABLE IF NOT EXISTS speed_violations (
            id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            camera_id        BIGINT UNSIGNED NOT NULL,
            track_id         INT             NOT NULL,
            plate_number     VARCHAR(50),
            vehicle_type     VARCHAR(50),
            vehicle_class    VARCHAR(50),
            plate_img_path   VARCHAR(500),
            vehicle_img_path VARCHAR(500),
            confidence       FLOAT,
            speed_kmph       FLOAT,
            speed_limit      FLOAT,
            clip_path        VARCHAR(500),
            vehicle_color    VARCHAR(20)  DEFAULT 'UNKNOWN',
            violated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_at       TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at       TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
                             ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_camera (camera_id),
            INDEX idx_track  (track_id),
            INDEX idx_plate  (plate_number)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    conn.commit()

    # ── পুরনো table এ camera_id না থাকলে যোগ করো ──
    for table in ("detected_plates", "violations", "speed_violations"):
        try:
            cur.execute(f"""
                ALTER TABLE {table}
                ADD COLUMN camera_id BIGINT UNSIGNED NOT NULL DEFAULT 1
                AFTER id
            """)
            conn.commit()
            print(f" camera_id added to {table}")
        except Error:
            pass  # আগে থেকেই আছে

    # ── cameras table এ traffic_signal column না থাকলে যোগ করো ──
    try:
        cur.execute("""
            ALTER TABLE cameras
            ADD COLUMN traffic_signal VARCHAR(10) NULL DEFAULT NULL
            COMMENT 'red | green | orange'
            AFTER processing_interval
        """)
        conn.commit()
        print(" traffic_signal column added to cameras")
    except Error:
        pass  # আগে থেকেই আছে

    # ── vehicle_color column না থাকলে সব table এ যোগ করো ──
    for table in ("detected_plates", "violations", "speed_violations"):
        try:
            cur.execute(f"""
                ALTER TABLE {table}
                ADD COLUMN vehicle_color VARCHAR(20) DEFAULT 'UNKNOWN'
            """)
            conn.commit()
            print(f" vehicle_color added to {table}")
        except Error:
            pass  # আগে থেকেই আছে

    # ── detected_plates: status, notes, location_id ──
    for col_name, col_def in [
        ("status",      "VARCHAR(50) DEFAULT NULL"),
        ("notes",       "TEXT DEFAULT NULL"),
        ("location_id", "BIGINT DEFAULT NULL"),
    ]:
        try:
            cur.execute(f"ALTER TABLE detected_plates ADD COLUMN {col_name} {col_def}")
            conn.commit()
            print(f"{col_name} added to detected_plates")
        except Error:
            pass

    # ── created_at / updated_at — সব table এ ──
    for table in ("detected_plates", "violations", "speed_violations"):
        try:
            cur.execute(f"""
                ALTER TABLE {table}
                ADD COLUMN created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
            """)
            conn.commit()
            print(f" created_at added to {table}")
        except Error:
            pass

        try:
            cur.execute(f"""
                ALTER TABLE {table}
                ADD COLUMN updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP
            """)
            conn.commit()
            print(f" updated_at added to {table}")
        except Error:
            pass

    cur.close(); conn.close()
    print(" All tables ready.")


# ─────────────────────────────────────────────────────
# Camera helpers
# ─────────────────────────────────────────────────────

def get_active_cameras():
    """
    DB এর cameras table থেকে সব active camera return করে।
    Return: list of dict  — প্রতিটায় id, name, stream_url, ... আছে।
    """
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT id, name, stream_url, stream_type,
                   location, frame_rate, resolution,
                   processing_interval, status, traffic_signal
            FROM   cameras
            WHERE  is_active = 1
              AND  deleted_at IS NULL
            ORDER  BY id
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return rows
    except Error as e:
        print(f" get_active_cameras: {e}")
        return []


def set_camera_status(camera_id: int, status: str):
    """
    cameras.status কে update করে।
    status: 'active' | 'offline' | 'inactive'
    """
    conn = get_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE cameras SET status=%s WHERE id=%s",
            (status, camera_id)
        )
        conn.commit()
        cur.close(); conn.close()
    except Error as e:
        print(f"set_camera_status: {e}")


# ─────────────────────────────────────────────────────
# Traffic Signal — live DB poll
# ─────────────────────────────────────────────────────

# Valid signal values
_VALID_SIGNALS = {"red", "green", "orange"}

def get_camera_signal(camera_id: int) -> str:
    """
    cameras.traffic_signal থেকে live signal পড়ে।

    Return values:
        'red'    — লাল signal
        'green'  — সবুজ signal
        'orange' — হলুদ/কমলা signal
        'unknown'— DB তে NULL বা invalid value আছে (warning print করে)

    যেকোনো DB error এ 'unknown' return করে যাতে system crash না করে।
    """
    conn = get_connection()
    if not conn:
        return "unknown"
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT traffic_signal FROM cameras WHERE id = %s AND deleted_at IS NULL",
            (camera_id,)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row is None:
            print(f"  [CAM-{camera_id}] Camera not found in DB.")
            return "unknown"

        raw = row[0]

        # NULL চেক
        if raw is None:
            print(f" [CAM-{camera_id}] traffic_signal is NULL in DB.")
            return "unknown"

        normalized = raw.strip().lower()

        # Validation
        if normalized not in _VALID_SIGNALS:
            print(
                f"  [CAM-{camera_id}] Invalid traffic_signal value: '{raw}' "
                f"(allowed: red | green | orange)"
            )
            return "unknown"

        return normalized

    except Error as e:
        print(f" get_camera_signal cam={camera_id}: {e}")
        return "unknown"


# ─────────────────────────────────────────────────────
# Insert functions
# ─────────────────────────────────────────────────────

def insert_detected_plate(camera_id, track_id, plate_number,
                          vehicle_type, vehicle_class,
                          plate_img_path, vehicle_img_path,
                          confidence, vehicle_color="UNKNOWN",
                          status=None, notes=None, location_id=None):
    conn = get_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO detected_plates
                (camera_id, track_id, plate_number, vehicle_type,
                 vehicle_class, plate_img_path, vehicle_img_path,
                 confidence, vehicle_color,
                 status, notes, location_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (camera_id, track_id, plate_number, vehicle_type,
              vehicle_class, plate_img_path, vehicle_img_path,
              confidence, vehicle_color,
              status, notes, location_id))
        conn.commit(); cur.close()
    except Error as e:
        print(f" insert_detected_plate: {e}")
    finally:
        conn.close()


def insert_violation(camera_id, track_id, plate_number,
                     vehicle_type, vehicle_class,
                     plate_img_path, vehicle_img_path,
                     confidence, signal_state="RED",
                     clip_path=None, vehicle_color="UNKNOWN"):
    conn = get_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO violations
                (camera_id, track_id, plate_number, vehicle_type,
                 vehicle_class, plate_img_path, vehicle_img_path,
                 confidence, signal_state, clip_path, vehicle_color)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (camera_id, track_id, plate_number, vehicle_type,
              vehicle_class, plate_img_path, vehicle_img_path,
              confidence, signal_state, clip_path, vehicle_color))
        conn.commit(); cur.close()
        print(f"    RED violation | cam:{camera_id} track:{track_id}")
    except Error as e:
        print(f"insert_violation: {e}")
    finally:
        conn.close()


def insert_speed_violation(camera_id, track_id, plate_number,
                           vehicle_type, vehicle_class,
                           plate_img_path, vehicle_img_path,
                           confidence, speed_kmph, speed_limit,
                           clip_path=None, vehicle_color="UNKNOWN",created_at=None):
    
    conn = get_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO speed_violations
                (camera_id, track_id, plate_number, vehicle_type,
                 vehicle_class, plate_img_path, vehicle_img_path,
                 confidence, speed_kmph, speed_limit, clip_path, vehicle_color, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (camera_id, track_id, plate_number, vehicle_type,
              vehicle_class, plate_img_path, vehicle_img_path,
              confidence, speed_kmph, speed_limit, clip_path, vehicle_color, created_at))
        conn.commit(); cur.close()
        print(f"    SPEED violation | cam:{camera_id} track:{track_id} | {speed_kmph:.1f} km/h")
    except Error as e:
        print(f" insert_speed_violation: {e}")
    finally:
        conn.close()


def load_rois_from_db():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT id, roi_value FROM cameras")
    rows = cur.fetchall()

    PREDEFINED_ROIS = {}

    for row in rows:
        cam_id  = row["id"]
        roi_str = row["roi_value"]

        if not roi_str:
            continue

        try:
            roi_list = literal_eval(roi_str)

            if len(roi_list) < 3:
                print(f" Camera {cam_id} ROI invalid (<3 points)")
                continue

            PREDEFINED_ROIS[cam_id] = [
                (int(x), int(y)) for x, y in roi_list
            ]

        except Exception as e:
            print(f" Camera {cam_id} ROI parse error: {e}")

    cur.close()
    conn.close()

    return PREDEFINED_ROIS


# ─────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────

def print_summary():
    conn = get_connection()
    if not conn:
        return
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM detected_plates");  dp = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM violations");       v  = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM speed_violations"); s  = cur.fetchone()[0]
    print(f"\nSUMMARY  Detected:{dp}  RedLight:{v}  Speed:{s}")
    cur.close(); 
    conn.close()


if __name__ == "__main__":
    init_db()
    print_summary()
