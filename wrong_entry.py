"""
╔══════════════════════════════════════════════════════════════╗
║        TRAFFIC VIOLATION DETECTOR (TRAP LOGIC)               ║
║  YOLOv8 + ByteTrack + Conditional Line Activation (Batch)    ║
╚══════════════════════════════════════════════════════════════╝
"""

import cv2
import numpy as np
import os
import json
from datetime import datetime
import supervision as sv
from ultralytics import YOLO

# ════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════
# এখানে আপনার মেইন ভিডিও ফোল্ডারের পাথ দিন
INPUT_DIR = "/mnt/second_drive/ftpman/dmphq/20260616" 
MODEL_PATH = "yolov8n.pt"
LINE_FILE = "lines_config.json"

CONF_THRESHOLD = 0.4
DISTANCE_THRESHOLD = 45  # পিক্সেল; লাইনের কত কাছে আসলে টাচ বা পার হওয়া ধরা হবে

# ইনপুট ফোল্ডারের ভেতরেই violations এবং clips ফোল্ডার পাথ সেটআপ
OUTPUT_DIR = os.path.join(INPUT_DIR, "violations")
CLIPS_DIR = os.path.join(OUTPUT_DIR, "clips")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)

# ════════════════════════════════════════════════════════════════
# LINE DRAWER HELPER
# ════════════════════════════════════════════════════════════════
class MultiLineDrawer:
    def __init__(self, frame):
        self.orig = frame.copy()
        self.lines = []
        self.current_line = []
        self.win_name = "Draw Line 1 (Trigger) then Line 2 (Trap)"

    def _mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(self.current_line) < 2:
                self.current_line.append((x, y))
            if len(self.current_line) == 2:
                self.lines.append(self.current_line)
                self.current_line = []
            self._redraw()

    def _redraw(self):
        img = self.orig.copy()
        for i, line in enumerate(self.lines):
            color = (255, 255, 0) if i == 0 else (0, 255, 0) 
            cv2.line(img, line[0], line[1], color, 3)
            cv2.putText(img, f"Line {i+1}", line[0], cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        if len(self.current_line) == 1:
            cv2.circle(img, self.current_line[0], 5, (0, 0, 255), -1)
            
        cv2.imshow(self.win_name, img)

    def get_lines(self):
        cv2.namedWindow(self.win_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.win_name, self._mouse_callback)
        self._redraw()
        
        while len(self.lines) < 2:
            key = cv2.waitKey(1) & 0xFF
            if key == 27: 
                break
        cv2.destroyWindow(self.win_name)
        return self.lines

# ════════════════════════════════════════════════════════════════
# MAIN DETECTOR CLASS
# ════════════════════════════════════════════════════════════════
class TrapViolationDetector:
    def __init__(self):
        print("🔄 YOLOv8 Model Load হচ্ছে...")
        self.model = YOLO(MODEL_PATH)
        self.target_classes = [2, 3, 5, 7] 
        
        # প্রতি ভিডিওর জন্য এই ভ্যারিয়েবলগুলো রিসেট হবে
        self.tracker = None
        self.violated_track_ids = set()
        self.line2_is_red_zone = False
        self.line1_active_timer = 0  
        self.ss_saved = set()        
        self.active_video_writers = {}  

    def _dist_to_line(self, p, a, b):
        px, py = float(p[0]), float(p[1])
        ax, ay = float(a[0]), float(a[1])
        bx, by = float(b[0]), float(b[1])
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return np.hypot(px - ax, py - ay)
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        projx, projy = ax + t * dx, ay + t * dy
        return float(np.hypot(px - projx, py - projy))

    def load_or_draw_lines(self, first_frame):
        if os.path.exists(LINE_FILE):
            with open(LINE_FILE, 'r') as f:
                data = json.load(f)
                self.line1 = [tuple(p) for p in data['line1']]
                self.line2 = [tuple(p) for p in data['line2']]
                print("✅ সেভ থাকা লাইনের কোঅর্ডিনেট লোড হয়েছে।")
        else:
            drawer = MultiLineDrawer(first_frame)
            drawn_lines = drawer.get_lines()
            if len(drawn_lines) < 2:
                raise SystemExit("❌ দুটি লাইন সঠিকভাবে আঁকা হয়নি।")
            self.line1, self.line2 = drawn_lines
            with open(LINE_FILE, 'w') as f:
                json.dump({'line1': self.line1, 'line2': self.line2}, f)
            print(f"✅ লাইনের কনফিগারেশন {LINE_FILE} এ সেভ হয়েছে।")

    def reset_for_new_video(self):
        """নতুন ভিডিও প্রসেস করার আগে ট্র্যাকিং ডাটা ক্লিয়ার করা"""
        self.tracker = sv.ByteTrack()
        self.violated_track_ids = set()
        self.line2_is_red_zone = False
        self.line1_active_timer = 0  
        self.ss_saved = set()        
        self.active_video_writers = {}  

    def process_video(self, video_path):
        self.reset_for_new_video()
        video_name = os.path.basename(video_path)
        video_base_name = os.path.splitext(video_name)[0]
        print(f"\n🎬 প্রসেস হচ্ছে: {video_name}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"❌ ভিডিও ফাইলটি ওপেন করা যায়নি: {video_path}")
            return False

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0 or fps is None:
            fps = 30.0
        
        # ৫ সেকেন্ডের ক্লিপ রেকর্ডিং ডিউরেশন ------------------------------------------------------------------
        clip_frames_duration = int(fps * 25)

        ret, frame = cap.read()
        if not ret:
            print("❌ ভিডিওর প্রথম ফ্রেম রিড করা যায়নি।")
            cap.release()
            return False

        frame_height, frame_width = frame.shape[:2]
        self.load_or_draw_lines(frame)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0) 

        box_annotator = sv.BoxAnnotator(thickness=2)
        label_annotator = sv.LabelAnnotator(text_scale=0.5, text_thickness=1)

        main_win_name = "Conditional Trap Detector"
        cv2.namedWindow(main_win_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(main_win_name, 1280, 720)

        user_quit = False
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            results = self.model(frame, conf=CONF_THRESHOLD, classes=self.target_classes, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(results)
            detections = self.tracker.update_with_detections(detections)

            any_vehicle_on_line1 = False
            current_frame_violators = []

            if detections.tracker_id is not None and len(detections.tracker_id) > 0:
                for idx, box in enumerate(detections.xyxy):
                    track_id = int(detections.tracker_id[idx])
                    cx = int((box[0] + box[2]) / 2)
                    cy = int((box[1] + box[3]) / 2)

                    d1 = self._dist_to_line((cx, cy), self.line1[0], self.line1[1])
                    if d1 <= DISTANCE_THRESHOLD:
                        any_vehicle_on_line1 = True

                    d2 = self._dist_to_line((cx, cy), self.line2[0], self.line2[1])
                    if d2 <= DISTANCE_THRESHOLD:
                        current_frame_violators.append((track_id, box))

            if any_vehicle_on_line1:
                self.line2_is_red_zone = True
                self.line1_active_timer = 45  
            else:
                if self.line1_active_timer > 0:
                    self.line1_active_timer -= 1
                else:
                    self.line2_is_red_zone = False 

            # RENDERING / VISUALIZATION
            labels = []
            for i in range(len(detections)):
                if detections.tracker_id is not None:
                    tid = int(detections.tracker_id[i])
                    labels.append(f"#{tid} {self.model.model.names[int(detections.class_id[i])]} ")
                else:
                    labels.append("Detecting...")

            frame = box_annotator.annotate(scene=frame, detections=detections)
            frame = label_annotator.annotate(scene=frame, detections=detections, labels=labels)

            if detections.tracker_id is not None:
                for i, box in enumerate(detections.xyxy):
                    tid = int(detections.tracker_id[i])
                    if tid in self.violated_track_ids or tid in [t for t, _ in current_frame_violators]:
                        x1, y1, x2, y2 = map(int, box)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3) 
                        lbl = f"VIOLATOR #{tid}"
                        (tw, th), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 10, y1), (0, 0, 255), -1)
                        cv2.putText(frame, lbl, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            cv2.line(frame, self.line1[0], self.line1[1], (255, 255, 0), 3)
            cv2.putText(frame, "Line 1 (Trigger)", self.line1[0], cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            l2_color = (0, 0, 255) if self.line2_is_red_zone else (0, 255, 0)
            l2_text = "Line 2 [RED ZONE - ACTIVATED]" if self.line2_is_red_zone else "Line 2 [NORMAL - INACTIVE]"
            cv2.line(frame, self.line2[0], self.line2[1], l2_color, 4 if self.line2_is_red_zone else 2)
            cv2.putText(frame, l2_text, self.line2[0], cv2.FONT_HERSHEY_SIMPLEX, 0.6, l2_color, 2)

            cv2.rectangle(frame, (0, 0), (320, 50), (0, 0, 0), -1)
            cv2.putText(frame, f"Trap Violations: {len(self.violated_track_ids)}", (10, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # ════════════════════════════════════════════════════════════════
            # ACTION LOGIC (INPUT_DIR/violations/ এবং INPUT_DIR/violations/clips/)
            # ════════════════════════════════════════════════════════════════
            if self.line2_is_red_zone and current_frame_violators:
                for tid, box in current_frame_violators:
                    if tid not in self.violated_track_ids:
                        self.violated_track_ids.add(tid)

                    # ১. ইমেজ সরাসরি 'violations' ফোল্ডারে সেভ হবে
                    if tid not in self.ss_saved:
                        self.ss_saved.add(tid)
                        ss_path = os.path.join(OUTPUT_DIR, f"{video_base_name}_id_{tid}.jpg")
                        cv2.imwrite(ss_path, frame)
                        print(f"🚨 TRAP ACTIVATED! ID: #{tid} 📸 SS সেভ হয়েছে: violations/{os.path.basename(ss_path)}")

                    # ২. ভিডিও ক্লিপ 'violations/clips' সাব-ফোল্ডারে সেভ হবে
                    if tid not in self.active_video_writers:
                        clip_path = os.path.join(CLIPS_DIR, f"{video_base_name}_id_{tid}.mp4")
                        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                        writer = cv2.VideoWriter(clip_path, fourcc, fps, (frame_width, frame_height))
                        self.active_video_writers[tid] = [writer, clip_frames_duration]
                        print(f"🎬 ID #{tid}-এর ভিডিও ক্লিপ রেকর্ডিং শুরু: violations/clips/{os.path.basename(clip_path)}")

            finished_writers = []
            for tid, (writer, remaining_frames) in self.active_video_writers.items():
                if remaining_frames > 0:
                    writer.write(frame)
                    self.active_video_writers[tid][1] -= 1
                else:
                    writer.release()
                    finished_writers.append(tid)
                    print(f"✅ ID #{tid}-এর ক্লিপ সেভ সম্পূর্ণ!")

            for tid in finished_writers:
                del self.active_video_writers[tid]

            cv2.imshow(main_win_name, frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("🛑 ব্যবহারকারী প্রসেসিং বন্ধ করেছেন।")
                user_quit = True
                break

        # রানিং রাইটারস ইমার্জেন্সি ক্লোজ করা
        for tid, (writer, _) in self.active_video_writers.items():
            writer.release()

        cap.release()
        cv2.destroyAllWindows()
        return user_quit

    def run_batch(self):
        if not os.path.exists(INPUT_DIR):
            print(f"❌ ইনপুট ডিরেক্টরি পাওয়া যায়নি: {INPUT_DIR}")
            return

        valid_extensions = ('.mp4', '.avi', '.mov', '.ts', '.mkv')
        all_files = sorted(os.listdir(INPUT_DIR))
        video_files = [f for f in all_files if f.lower().endswith(valid_extensions)]

        if not video_files:
            print("📁 ফোল্ডারে কোনো ভিডিও ফাইল পাওয়া যায়নি।")
            return

        print(f"🗂️ মোট {len(video_files)}টি মেইন ভিডিও ফাইল পাওয়া গেছে।")

        for file_name in video_files:
            # অলরেডি প্রসেসড ভিডিও স্কিপ করা হবে
            if "_done" in os.path.splitext(file_name)[0]:
                print(f"⏭️ স্কিপ করা হলো (ইতিমধ্যে প্রসেসড): {file_name}")
                continue

            full_video_path = os.path.join(INPUT_DIR, file_name)
            
            # ভিডিও প্রসেস রান করা
            user_quit = self.process_video(full_video_path)
            
            if user_quit:
                break

            # সোর্স ভিডিওর নামের শেষে '_done' যুক্ত করা
            name, ext = os.path.splitext(file_name)
            new_file_name = f"{name}_done{ext}"
            new_video_path = os.path.join(INPUT_DIR, new_file_name)
            
            try:
                os.rename(full_video_path, new_video_path)
                print(f"✔️ ভিডিওর নাম পরিবর্তন সম্পন্ন: {file_name} -> {new_file_name}")
            except Exception as e:
                print(f"❌ নাম পরিবর্তন করতে সমস্যা হয়েছে: {e}")

        print("\n🏁 সমস্ত ভিডিও ফাইল সফলভাবে প্রসেস করা হয়েছে!")

if __name__ == "__main__":
    detector = TrapViolationDetector()
    detector.run_batch()