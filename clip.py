# =====================================================
# clip.py — Non-blocking threaded clip writer
# শুধুমাত্র violation এ clip save হবে
# =====================================================

import cv2
import os
import threading
from collections import deque
import queue
import time
import subprocess

PRE_ROLL_SEC  = 1.5
POST_ROLL_SEC = 1.5


class ClipManager:
    def __init__(self, fps: float, frame_size: tuple, clip_dir: str):
        self.fps        = fps
        self.frame_size = frame_size
        self.clip_dir   = clip_dir
        os.makedirs(clip_dir, exist_ok=True)

        pre_frames   = int(PRE_ROLL_SEC * fps)
        self._buffer = deque(maxlen=pre_frames)
        self._writers = {}
        self._lock    = threading.Lock()

    def push_frame(self, frame):
        self._buffer.append(frame.copy())
        with self._lock:
            for w in self._writers.values():
                if not w["done"]:
                    try:
                        w["q"].put_nowait(frame.copy())
                    except queue.Full:
                        pass

    def start_clip(self, key: int) -> str:
        with self._lock:
            if key in self._writers:
                return self._writers[key]["path"]

        timestamp  = time.strftime("%Y%m%d_%H%M%S")
        path       = os.path.abspath(
            os.path.join(self.clip_dir, f"clip_{key}_{timestamp}.mp4"))
        pre_frames = list(self._buffer)
        post_count = int(POST_ROLL_SEC * self.fps)
        q          = queue.Queue(maxsize=post_count + 60)

        # def _write():
        #     fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        #     #fourcc = cv2.VideoWriter_fourcc(*"H264")
        #     # fourcc = cv2.VideoWriter_fourcc(*"avc1")
        #     writer = cv2.VideoWriter(path, fourcc, self.fps, self.frame_size)
        #     for f in pre_frames:
        #         writer.write(f)
        #     written = 0
        #     while written < post_count:
        #         try:
        #             writer.write(q.get(timeout=2.0))
        #             written += 1
        #         except queue.Empty:
        #             break
        #     writer.release()
        #     with self._lock:
        #         if key in self._writers:
        #             self._writers[key]["done"] = True
        #     print(f"   Clip saved: {path}")

        # t = threading.Thread(target=_write, daemon=True)
        # with self._lock:
        #     self._writers[key] = {
        #         "q": q, "path": path, "thread": t, "done": False
        #     }
        # t.start()
        # return path
        
        def _write():
            temp_path = path.replace(".mp4", "_temp.mp4")

            # temp save
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(temp_path, fourcc, self.fps, self.frame_size)

            if not writer.isOpened():
                print("Writer failed")
                return

            # pre frames
            for f in pre_frames:
                writer.write(f)

            # post frames
            written = 0
            while written < post_count:
                try:
                    writer.write(q.get(timeout=2.0))
                    written += 1
                except queue.Empty:
                    break

            writer.release()

            # browser-ready convert
            final_cmd = [
                "ffmpeg",
                "-y",
                "-i", temp_path,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-an",
                path
            ]

            subprocess.run(
                final_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # temp delete
            if os.path.exists(temp_path):
                os.remove(temp_path)

            with self._lock:
                if key in self._writers:
                    self._writers[key]["done"] = True

            print(f"   Browser Clip saved: {path}")


        t = threading.Thread(target=_write, daemon=True)

        with self._lock:
            self._writers[key] = {
                "q": q,
                "path": path,
                "thread": t,
                "done": False
            }

        t.start()
        return path

    def get_clip_path(self, key: int):
        with self._lock:
            w = self._writers.get(key)
            return w["path"] if (w and w["done"]) else None

    def release_all(self):
        with self._lock:
            keys = list(self._writers.keys())
        for key in keys:
            w = self._writers.get(key)
            if w:
                w["thread"].join(timeout=5)
        with self._lock:
            self._writers.clear()

    def has_active_clips(self) -> bool:
        with self._lock:
            return any(not w["done"] for w in self._writers.values())
       


