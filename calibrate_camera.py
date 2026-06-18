# =====================================================
# calibrate_camera.py
# Camera থেকে একটা frame নিয়ে real-world distance measure করে
# PIXELS_PER_METER automatically calculate করে
# =====================================================

import cv2
import math
import numpy as np

# ──────────────────────────────────────────────────
# CONFIG — আপনার camera অনুযায়ী বদলান
# ──────────────────────────────────────────────────
CAMERA_SOURCE = 0          # 0 = webcam, অথবা RTSP URL string, অথবা video file path
                           # e.g. "rtsp://admin:pass@192.168.1.64/stream"
                           # e.g. "test_video.mp4"

KNOWN_DISTANCE_METERS = 3.0  # আপনি road এ যে দুটো point mark করবেন তাদের real distance
                              # (meter এ) — আগে road এ গিয়ে tape দিয়ে measure করুন

# ──────────────────────────────────────────────────

click_points = []
frame_display = None


def mouse_callback(event, x, y, flags, param):
    global click_points, frame_display
    if event == cv2.EVENT_LBUTTONDOWN:
        if len(click_points) < 2:
            click_points.append((x, y))
            print(f"  Point {len(click_points)} marked: ({x}, {y})")


def get_one_frame(source):
    """Camera বা video থেকে একটা fresh frame নাও।"""
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open source: {source}")

    # প্রথম কয়েকটা frame skip করো (camera warm-up)
    for _ in range(10):
        cap.read()

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        raise RuntimeError("Could not read frame from source.")

    return frame


def draw_ui(frame, points):
    """Frame এর উপর instruction আর marked points আঁকো।"""
    vis = frame.copy()

    # Instructions
    cv2.putText(vis, "Click 2 points on the road (known distance apart)",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.putText(vis, f"Known distance = {KNOWN_DISTANCE_METERS} meters",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
    cv2.putText(vis, "Press 'R' to reset | Press 'C' to confirm | Press 'Q' to quit",
                (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

    # Marked points
    for i, (px, py) in enumerate(points):
        cv2.circle(vis, (px, py), 8, (0, 0, 255), -1)
        cv2.circle(vis, (px, py), 10, (255, 255, 255), 2)
        cv2.putText(vis, f"P{i+1}", (px + 12, py - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)

    # Line between points
    if len(points) == 2:
        cv2.line(vis, points[0], points[1], (0, 255, 0), 2)

        # Pixel distance label
        pixel_dist = math.dist(points[0], points[1])
        mid_x = (points[0][0] + points[1][0]) // 2
        mid_y = (points[0][1] + points[1][1]) // 2
        cv2.putText(vis, f"{pixel_dist:.1f} px", (mid_x + 5, mid_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)

        ppm = pixel_dist / KNOWN_DISTANCE_METERS
        cv2.putText(vis, f"px/m = {ppm:.2f}  -->  Press C to confirm",
                    (10, vis.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    return vis


def run_calibration():
    global click_points, frame_display

    print("=" * 55)
    print("  Camera Calibration Tool")
    print("=" * 55)
    print(f"  Source          : {CAMERA_SOURCE}")
    print(f"  Known distance  : {KNOWN_DISTANCE_METERS} m")
    print()
    print("  Step 1: Road এ দুটো point tape/chalk দিয়ে mark করুন")
    print(f"          যাদের মধ্যে real distance = {KNOWN_DISTANCE_METERS} meter")
    print("  Step 2: Frame এ সেই দুটো point এ click করুন")
    print("  Step 3: C চাপুন — PIXELS_PER_METER print হবে")
    print()

    # Frame নাও
    print("  Camera থেকে frame নেওয়া হচ্ছে...")
    frame = get_one_frame(CAMERA_SOURCE)
    frame_display = frame.copy()

    h, w = frame.shape[:2]
    print(f"  Frame size: {w} x {h}")
    print()
    print("  Window খুলছে — road এ mark করা দুটো point এ click করুন।")
    print()

    cv2.namedWindow("Calibration", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Calibration", min(w, 1280), min(h, 720))
    cv2.setMouseCallback("Calibration", mouse_callback)

    result_ppm = None

    while True:
        vis = draw_ui(frame_display, click_points)
        cv2.imshow("Calibration", vis)
        key = cv2.waitKey(30) & 0xFF

        if key == ord('r') or key == ord('R'):
            click_points = []
            print("  Reset — আবার দুটো point click করুন।")

        elif key == ord('c') or key == ord('C'):
            if len(click_points) == 2:
                pixel_dist = math.dist(click_points[0], click_points[1])
                result_ppm = pixel_dist / KNOWN_DISTANCE_METERS
                print(f"  Pixel distance  : {pixel_dist:.2f} px")
                print(f"  Real distance   : {KNOWN_DISTANCE_METERS} m")
                print()
                print("=" * 55)
                print(f"  PIXELS_PER_METER = {result_ppm:.2f}")
                print("=" * 55)
                print()
                print("  config.py তে এই line টা update করুন:")
                print(f"  PIXELS_PER_METER = {result_ppm:.2f}")
                break
            else:
                print(f"  এখনো {2 - len(click_points)} টা point বাকি আছে।")

        elif key == ord('q') or key == ord('Q') or key == 27:
            print("  Quit করা হয়েছে।")
            break

    cv2.destroyAllWindows()

    if result_ppm:
        # config.py auto-update করতে চান?
        print()
        ans = input("  config.py automatically update করবো? (y/n): ").strip().lower()
        if ans == 'y':
            update_config(result_ppm)

    return result_ppm


def update_config(ppm, config_path="config.py"):
    """config.py এর PIXELS_PER_METER line টা automatically update করো।"""
    try:
        with open(config_path, "r") as f:
            lines = f.readlines()

        updated = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("PIXELS_PER_METER"):
                new_lines.append(f"PIXELS_PER_METER = {ppm:.2f}   "
                                 f"# auto-calibrated\n")
                updated = True
                print(f"  config.py updated: PIXELS_PER_METER = {ppm:.2f}")
            else:
                new_lines.append(line)

        if updated:
            with open(config_path, "w") as f:
                f.writelines(new_lines)
        else:
            print("  config.py তে PIXELS_PER_METER line পাওয়া যায়নি।")
            print(f"  Manual এ এই line যোগ করুন: PIXELS_PER_METER = {ppm:.2f}")

    except FileNotFoundError:
        print(f"  {config_path} পাওয়া যায়নি — manually update করুন।")


# ──────────────────────────────────────────────────
if __name__ == "__main__":
    run_calibration()