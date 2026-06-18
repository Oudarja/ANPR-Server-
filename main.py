# # =====================================================
# # main.py — Multi-camera launcher
# # Features:
# #   - DB থেকে camera + ROI load
# #   - RTSP stream support (reconnect সহ)
# #   - Live preview window (সব camera একসাথে)
# #   - Ctrl+C দিয়ে graceful shutdown
# # =====================================================

# import cv2
# import time
# import os
# import numpy as np
# import multiprocessing as mp
# from pathlib import Path
# from datetime import date

# from database      import init_db, get_active_cameras, print_summary
# from camera_worker import run_camera
# from config        import (
#     MONITOR_WIDTH, MONITOR_HEIGHT,
#     UPLOAD_ROOT, UPLOAD_POLL_INTERVAL,
#     VIDEO_RETRY_SECONDS, VIDEO_STABLE_CHECK_SECONDS,
#     VIDEO_EXTENSIONS, CAMERA_FOLDER_MAP, PROCESS_TODAY_VIDEOS,
# )


# # ─────────────────────────────────────────────────────
# # Worker process entry
# # ─────────────────────────────────────────────────────
# def _worker_entry(camera_info: dict, roi_list, preview_queue):
#     roi_polygon = np.array(roi_list, dtype=np.int32)
#     try:
#         _camera_folder_worker(camera_info, roi_polygon, preview_queue)
#     except KeyboardInterrupt:
#         pass
#     except Exception as e:
#         import traceback
#         print(f"[CAM-{camera_info['id']}] Worker crashed: {e}")
#         traceback.print_exc()


# def _video_is_pending(path: Path) -> bool:
#     return (
#         path.is_file()
#         and path.suffix.lower() in VIDEO_EXTENSIONS
#         and not path.stem.endswith("_done")
#     )


# def _wait_for_stable_file(path: Path) -> bool:
#     try:
#         size1 = path.stat().st_size
#     except OSError:
#         return False
#     if size1 == 0:
#         return False
#     time.sleep(VIDEO_STABLE_CHECK_SECONDS)
#     try:
#         size2 = path.stat().st_size
#     except OSError:
#         return False
#     return size1 == size2


# def _probe_video_file(path: Path) -> bool:
#     """
#     Thoroughly check if video is valid and not corrupted:
#     - Opens successfully
#     - Has valid properties (width, height, fps)
#     - Can read multiple frames without issues
#     """
#     try:
#         cap = cv2.VideoCapture(str(path))
#         if not cap.isOpened():
#             cap.release()
#             print(f"    Cannot open video: {path.name}")
#             return False
        
#         # Check video properties
#         width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#         height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#         fps = cap.get(cv2.CAP_PROP_FPS)
#         frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
#         if width <= 0 or height <= 0:
#             cap.release()
#             print(f"    Invalid video dimensions: {width}x{height}")
#             return False
        
#         if fps <= 0:
#             cap.release()
#             print(f"    Invalid FPS: {fps}")
#             return False
        
#         if frame_count <= 0:
#             cap.release()
#             print(f"    No frames detected in video")
#             return False
        
#         # Try to read first 5 frames to ensure integrity
#         frames_read = 0
#         for _ in range(min(5, frame_count)):
#             ret, frame = cap.read()
#             if not ret or frame is None:
#                 cap.release()
#                 print(f"    Failed to read frame {frames_read+1}")
#                 return False
#             frames_read += 1
        
#         cap.release()
#         print(f"    ✓ Video OK: {width}x{height} @{fps}fps, {frame_count} frames")
#         return True
        
#     except Exception as e:
#         print(f"    Error probing video: {e}")
#         return False


# def _mark_done(path: Path) -> Path:
#     dest = path.with_name(f"{path.stem}_done{path.suffix}")
#     path.rename(dest)
#     return dest


# def _parse_date_folder(folder: Path):
#     name = folder.name
#     try:
#         return date.fromisoformat(name)
#     except ValueError:
#         pass

#     try:
#         return date.fromisoformat(f"{name[:4]}-{name[4:6]}-{name[6:8]}")
#     except Exception:
#         return None


# def _find_pending_videos(upload_folder: Path):
#     today = date.today()
#     pending = []

#     if not upload_folder.exists():
#         return pending

#     for child in sorted(upload_folder.iterdir(), key=lambda p: p.name.lower()):
#         if child.is_dir():
#             folder_date = _parse_date_folder(child)
            
#             # If it's a date folder, look for videos directly in it
#             if folder_date is not None:
#                 # Skip folders from the future
#                 if folder_date > today:
#                     continue
#                 # Skip today's folder if configured not to process today's videos
#                 if not PROCESS_TODAY_VIDEOS and folder_date == today:
#                     continue
#                 # Prefer a `validations` subfolder inside the date folder, but
#                 # fall back to videos placed directly in the date folder.
#                 validations_dir = child / "validations"
#                 sources = []
#                 if validations_dir.exists() and validations_dir.is_dir():
#                     sources.append(validations_dir)
#                 sources.append(child)

#                 for src in sources:
#                     try:
#                         pending.extend(
#                             sorted(
#                                 [p for p in src.iterdir() if _video_is_pending(p)],
#                                 key=lambda p: p.name.lower()
#                             )
#                         )
#                     except (OSError, PermissionError):
#                         pass
#             else:
#                 # If it's not a date folder (e.g., 201, 202, 101, 102), 
#                 # look for date folders inside it
#                 for grandchild in sorted(child.iterdir(), key=lambda p: p.name.lower()):
#                     if grandchild.is_dir():
#                         subfolder_date = _parse_date_folder(grandchild)
#                         if subfolder_date is None:
#                             continue
#                         # Skip folders from the future
#                         if subfolder_date > today:
#                             continue
#                         # Skip today's folder if configured not to process today's videos
#                         if not PROCESS_TODAY_VIDEOS and subfolder_date == today:
#                             continue
#                         # Look for `validations` inside the date subfolder first.
#                         validations_dir = grandchild / "validations"
#                         sources = []
#                         if validations_dir.exists() and validations_dir.is_dir():
#                             sources.append(validations_dir)
#                         sources.append(grandchild)

#                         for src in sources:
#                             try:
#                                 pending.extend(
#                                     sorted(
#                                         [p for p in src.iterdir() if _video_is_pending(p)],
#                                         key=lambda p: p.name.lower()
#                                     )
#                                 )
#                             except (OSError, PermissionError):
#                                 print(f"    Warning: Cannot read {src}")
#         elif _video_is_pending(child):
#             pending.append(child)

#     return pending


# def _camera_folder_worker(camera_info: dict, roi_polygon: np.ndarray, preview_queue):
#     cam_id = camera_info["id"]
    
#     # Get the upload folder name from the mapping, fallback to cam_id if not found
#     folder_name = CAMERA_FOLDER_MAP.get(cam_id, str(cam_id))
#     upload_folder = Path(UPLOAD_ROOT) / folder_name
#     upload_folder.mkdir(parents=True, exist_ok=True)

#     print(f"[CAM-{cam_id}] Watching: {upload_folder}")

#     failed_videos = {}  # path -> retry_after_time

#     while True:
#         try:
#             now = time.time()

#             # সব pending video খোঁজো (previous-date folders only)
#             all_pending = _find_pending_videos(upload_folder)

#             if not all_pending:
#                 time.sleep(UPLOAD_POLL_INTERVAL)
#                 continue

#             # cooldown এ নেই এমন প্রথম video নাও
#             next_video = None
#             for p in all_pending:
#                 if failed_videos.get(p, 0) <= now:
#                     next_video = p
#                     break

#             if next_video is None:
#                 next_retry = min(failed_videos[p] for p in all_pending if p in failed_videos)
#                 wait = max(1, min(next_retry - now, UPLOAD_POLL_INTERVAL))
#                 print(f"[CAM-{cam_id}] all video cooldown  {wait:.0f}s পরে check করব...")
#                 time.sleep(wait)
#                 continue

#             if not _wait_for_stable_file(next_video):
#                 print(f"[CAM-{cam_id}] File writting not done: {next_video.name}, i will try leter")     
#                 failed_videos[next_video] = now + 10
#                 continue

#             print(f"[CAM-{cam_id}] Checking: {next_video.name}")
#             if not _probe_video_file(next_video):
#                 print(f"[CAM-{cam_id}] ✗ Bad video: {next_video.name} — 5 মিনিট পরে retry")
#                 failed_videos[next_video] = now + VIDEO_RETRY_SECONDS
#                 continue

#             print(f"[CAM-{cam_id}] ▶ Processing: {next_video.name}")
#             proc_info = dict(camera_info)
#             proc_info["stream_url"] = str(next_video)

#             success = run_camera(proc_info, roi_polygon, preview_queue=preview_queue)
#             failed_videos.pop(next_video, None)

#             if success:
#                 done_path = _mark_done(next_video)
#                 print(f"[CAM-{cam_id}] ✓ Done: {done_path.name}")
#             else:
#                 print(f"[CAM-{cam_id}] ✗ Failed: {next_video.name} — after  5 min  retry")
#                 failed_videos[next_video] = now + VIDEO_RETRY_SECONDS

#         except KeyboardInterrupt:
#             break
#         except Exception as e:
#             import traceback
#             print(f"[CAM-{cam_id}] Exception: {e}")
#             traceback.print_exc()
#             time.sleep(5)

# # def _camera_folder_worker(camera_info: dict, roi_polygon: np.ndarray, preview_queue):
# #     cam_id   = camera_info["id"]
# #     cam_name = camera_info.get("name", f"Camera-{cam_id}")
# #     upload_folder = Path(UPLOAD_ROOT) / str(cam_id)
# #     upload_folder.mkdir(parents=True, exist_ok=True)

# #     print(f"[CAM-{cam_id}] Watching uploads folder: {upload_folder}")
    
# #     # Track files that failed probing and their next retry time
# #     failed_videos = {}  # path -> retry_after_time

# #     while True:
# #         try:
# #             now = time.time()
            
# #             # Find all pending videos
# #             all_pending = [p for p in upload_folder.iterdir() if _video_is_pending(p)]
            
# #             # Filter out files that are still in cooldown
# #             available_videos = [
# #                 p for p in all_pending 
# #                 if p not in failed_videos or failed_videos[p] <= now
# #             ]
            
# #             if not available_videos:
# #                 # All videos are either processing or in cooldown
# #                 if all_pending:
# #                     next_retry = min(failed_videos.get(p, now) for p in all_pending)
# #                     wait_time = max(1, min(next_retry - now, UPLOAD_POLL_INTERVAL))
# #                     print(f"[CAM-{cam_id}] No available videos. Next check in {wait_time:.0f}s")
# #                     time.sleep(wait_time)
# #                 else:
# #                     time.sleep(UPLOAD_POLL_INTERVAL)
# #                 continue
            
# #             # Sort by modification time (FIFO)
# #             next_video = sorted(available_videos, key=lambda p: (p.stat().st_mtime, p.name))[0]

# #             if not _wait_for_stable_file(next_video):
# #                 print(f"[CAM-{cam_id}] File still writing: {next_video.name}, will retry later")
# #                 time.sleep(UPLOAD_POLL_INTERVAL)
# #                 continue

# #             print(f"[CAM-{cam_id}] Checking video: {next_video.name}")
# #             if not _probe_video_file(next_video):
# #                 # Video is corrupted or invalid
# #                 print(f"[CAM-{cam_id}] ✗ Bad video: {next_video.name} — will retry in 5 minutes")
# #                 failed_videos[next_video] = now + VIDEO_RETRY_SECONDS
# #                 time.sleep(2)  # Brief pause before checking next
# #                 continue

# #             # Video is good, process it
# #             print(f"[CAM-{cam_id}] Processing video: {next_video.name}")
# #             proc_info = dict(camera_info)
# #             proc_info["stream_url"] = str(next_video)

# #             success = run_camera(proc_info, roi_polygon, preview_queue=preview_queue)
            
# #             # Clean up tracking
# #             failed_videos.pop(next_video, None)
            
# #             if success:
# #                 done_path = _mark_done(next_video)
# #                 print(f"[CAM-{cam_id}] ✓ Completed: {done_path.name}")
# #                 print(f"[CAM-{cam_id}] Looking for next video...")
# #                 continue  # Immediately check for next video
# #             else:
# #                 print(f"[CAM-{cam_id}] ✗ Processing failed for {next_video.name}. Retrying in 5 minutes.")
# #                 failed_videos[next_video] = now + VIDEO_RETRY_SECONDS
# #                 time.sleep(2)
# #                 continue  # Move to next iteration to find another video

# #         except KeyboardInterrupt:
# #             break
# #         except Exception as e:
# #             import traceback
# #             print(f"[CAM-{cam_id}] Worker exception: {e}")
# #             traceback.print_exc()
# #             time.sleep(5)


# # ─────────────────────────────────────────────────────
# # Preview window — সব camera এর frame একসাথে দেখায়
# # ─────────────────────────────────────────────────────
# def _build_preview_grid(frames_by_cam: dict, grid_cols: int = 2) -> np.ndarray:
#     """
#     frames_by_cam: {cam_id: (cam_name, frame_640x360)}
#     সব frame গুলো একটা grid এ রাখে।
#     """
#     items = list(frames_by_cam.values())
#     if not items:
#         return np.zeros((360, 640, 3), dtype=np.uint8)

#     CELL_W, CELL_H = 640, 360
#     n        = len(items)
#     cols     = min(grid_cols, n)
#     rows     = (n + cols - 1) // cols
#     grid     = np.zeros((rows * CELL_H, cols * CELL_W, 3), dtype=np.uint8)

#     for idx, (name, frame) in enumerate(items):
#         r = idx // cols
#         c = idx % cols
#         y0, y1 = r * CELL_H, (r+1) * CELL_H
#         x0, x1 = c * CELL_W, (c+1) * CELL_W

#         if frame is not None:
#             cell = cv2.resize(frame, (CELL_W, CELL_H))
#         else:
#             cell = np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8)
#             cv2.putText(cell, f"{name} — No Frame",
#                         (20, CELL_H//2), cv2.FONT_HERSHEY_SIMPLEX,
#                         0.7, (100,100,100), 2)

#         # Camera name label
#         # cv2.putText(cell, name, (10, 25),
#         #             cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,220,255), 2)

#         grid[y0:y1, x0:x1] = cell

#     # Grid border lines
#     for r in range(1, rows):
#         cv2.line(grid, (0, r*CELL_H), (cols*CELL_W, r*CELL_H), (60,60,60), 1)
#     for c in range(1, cols):
#         cv2.line(grid, (c*CELL_W, 0), (c*CELL_W, rows*CELL_H), (60,60,60), 1)

#     return grid


# # ─────────────────────────────────────────────────────
# # Main
# # ─────────────────────────────────────────────────────
# def main():
#     init_db()

#     all_cameras = get_active_cameras()
#     if not all_cameras:
#         print(" No active cameras in DB.")
#         return

#     print(f"\n {len(all_cameras)} active camera(s) found.")
#     print(f" Upload root: {UPLOAD_ROOT}\n")

#     upload_root = Path(UPLOAD_ROOT)
#     upload_root.mkdir(parents=True, exist_ok=True)

#     camera_rois = [(cam, []) for cam in all_cameras]

#     # Ensure upload folders exist for each camera
#     today_compact = date.today().strftime("%Y%m%d")
#     for cam, _ in camera_rois:
#         folder_name = CAMERA_FOLDER_MAP.get(cam["id"], str(cam["id"]))
#         folder = upload_root / folder_name
#         folder.mkdir(parents=True, exist_ok=True)
#         # Ensure today's compact date folder and validations subfolder exist
#         today_folder_compact = folder / today_compact
#         validations_compact = today_folder_compact / "validations"
#         validations_compact.mkdir(parents=True, exist_ok=True)

#         print(f"  [CAM-{cam['id']}] Upload folder: {folder} (today: {validations_compact})")

#     # ── Step 4: Shared preview queue ──
#     # সব camera এর preview frame এখানে আসবে
#     preview_queue = mp.Queue(maxsize=len(camera_rois) * 3)

#     # ── Step 5: Spawn processes ──
#     print(f"\n Starting {len(camera_rois)} camera process(es)...\n")
#     processes = []

#     for cam, roi_list in camera_rois:
#         p = mp.Process(
#             target=_worker_entry,
#             args=(cam, roi_list, preview_queue),
#             name=f"cam-{cam['id']}"
#         )
#         p.start()
#         processes.append((p, cam))
#         print(f"  ▶ PID={p.pid} | Camera {cam['id']} — {cam['name']}")
#         time.sleep(0.3)

#     print("\n[Main] Preview window খুলছে... ESC বা Q চাপলে বন্ধ হবে.\n")

#     # ── Step 6: Preview loop (main process এ) ──
#     # latest frame per camera
#     frames_by_cam = {
#         cam["id"]: (cam["name"], None)
#         for cam, _ in camera_rois
#     }

#     cv2.namedWindow("ANPR — Live Preview", cv2.WINDOW_NORMAL)

#     try:
#         while True:
#             # Queue থেকে নতুন frames নাও
#             drained = 0
#             while drained < 20:   # প্রতি loop এ max 20 frame drain
#                 try:
#                     cam_id, cam_name, preview = preview_queue.get_nowait()
#                     frames_by_cam[cam_id] = (cam_name, preview)
#                     drained += 1
#                 except Exception:
#                     break

#             # Grid বানাও ও দেখাও
#             grid = _build_preview_grid(frames_by_cam, grid_cols=2)
#             cv2.imshow("ANPR — Live Preview", grid)

#             key = cv2.waitKey(30) & 0xFF   # ~33 fps refresh
#             if key in (27, ord('q')):       # ESC or Q
#                 print("\n[Main] Preview বন্ধ করা হচ্ছে...")
#                 break

#             # Dead process check
#             alive = []
#             for p, cam in processes:
#                 if p.is_alive():
#                     alive.append((p, cam))
#                 else:
#                     print(f" {p.name} exited (code={p.exitcode})")
#             processes[:] = alive

#             if not processes:
#                 print("[Main] সব camera process শেষ হয়ে গেছে.")
#                 break

#     except KeyboardInterrupt:
#         print("\n[Main] Ctrl+C — সব camera বন্ধ করা হচ্ছে...")

#     finally:
#         cv2.destroyAllWindows()

#         for p, cam in processes:
#             if p.is_alive():
#                 print(f"  Terminating {p.name}...")
#                 p.terminate()

#         for p, cam in processes:
#             p.join(timeout=5)

#     print_summary()
#     print("\n Done.")


# if __name__ == "__main__":
#     mp.set_start_method("spawn", force=True)   # Windows + Linux compatible
#     main()








# =====================================================
# main.py — Multi-camera launcher
# Features:
#   - DB থেকে camera + ROI load
#   - RTSP stream support (reconnect সহ)
#   - Live preview window (সব camera একসাথে)
#   - Ctrl+C দিয়ে graceful shutdown
# =====================================================

import cv2
import time
import os
import numpy as np
import multiprocessing as mp
from pathlib import Path
from datetime import date

from database      import init_db, get_active_cameras, print_summary
from camera_worker import run_camera
from config        import (
    MONITOR_WIDTH, MONITOR_HEIGHT,
    UPLOAD_ROOT, UPLOAD_POLL_INTERVAL,
    VIDEO_RETRY_SECONDS, VIDEO_STABLE_CHECK_SECONDS,
    VIDEO_EXTENSIONS, CAMERA_FOLDER_MAP, PROCESS_TODAY_VIDEOS,
)


# ─────────────────────────────────────────────────────
# Worker process entry
# ─────────────────────────────────────────────────────
def _worker_entry(camera_info: dict, roi_list, preview_queue):
    roi_polygon = np.array(roi_list, dtype=np.int32)
    try:
        _camera_folder_worker(camera_info, roi_polygon, preview_queue)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        import traceback
        print(f"[CAM-{camera_info['id']}] Worker crashed: {e}")
        traceback.print_exc()


def _video_is_pending(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
        and not path.stem.endswith("_done")
    )


def _wait_for_stable_file(path: Path) -> bool:
    try:
        st = path.stat()
    except OSError:
        return False
    # reject empty files
    if st.st_size == 0:
        return False

    # Make sure size and mtime are stable over a couple of short checks.
    # Some writers update metadata intermittently; multiple checks reduce
    # false-positives where the file is actually complete.
    checks = 2
    prev_size = st.st_size
    prev_mtime = st.st_mtime
    for _ in range(checks):
        time.sleep(VIDEO_STABLE_CHECK_SECONDS)
        try:
            st2 = path.stat()
        except OSError:
            return False
        if st2.st_size == 0:
            return False
        if st2.st_size == prev_size and st2.st_mtime == prev_mtime:
            return True
        prev_size = st2.st_size
        prev_mtime = st2.st_mtime

    # Final fallback: accept if the file's mtime is older than the stability
    # interval (meaning no recent writes were observed).
    try:
        age = time.time() - path.stat().st_mtime
        return age >= VIDEO_STABLE_CHECK_SECONDS
    except OSError:
        return False


def _probe_video_file(path: Path) -> bool:
    """
    Thoroughly check if video is valid and not corrupted:
    - Opens successfully
    - Has valid properties (width, height, fps)
    - Can read multiple frames without issues
    """
    try:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            cap.release()
            print(f"    Cannot open video: {path.name}")
            return False
        
        # Check video properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if width <= 0 or height <= 0:
            cap.release()
            print(f"    Invalid video dimensions: {width}x{height}")
            return False
        
        if fps <= 0:
            cap.release()
            print(f"    Invalid FPS: {fps}")
            return False
        
        if frame_count <= 0:
            cap.release()
            print(f"    No frames detected in video")
            return False
        
        # Try to read first 5 frames to ensure integrity
        frames_read = 0
        for _ in range(min(5, frame_count)):
            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                print(f"    Failed to read frame {frames_read+1}")
                return False
            frames_read += 1
        
        cap.release()
        print(f"    ✓ Video OK: {width}x{height} @{fps}fps, {frame_count} frames")
        return True
        
    except Exception as e:
        print(f"    Error probing video: {e}")
        return False


def _mark_done(path: Path) -> Path:
    dest = path.with_name(f"{path.stem}_done{path.suffix}")
    path.rename(dest)
    return dest


def _parse_date_folder(folder: Path):
    name = folder.name
    try:
        return date.fromisoformat(name)
    except ValueError:
        pass

    try:
        return date.fromisoformat(f"{name[:4]}-{name[4:6]}-{name[6:8]}")
    except Exception:
        return None


def _find_pending_videos(upload_folder: Path):
    today = date.today()
    pending = []

    if not upload_folder.exists():
        return pending

    for child in sorted(upload_folder.iterdir(), key=lambda p: p.name.lower()):
        if child.is_dir():
            folder_date = _parse_date_folder(child)
            
            # If it's a date folder, look for videos directly in it
            if folder_date is not None:
                # Skip folders from the future
                if folder_date > today:
                    continue
                # Skip today's folder if configured not to process today's videos
                if not PROCESS_TODAY_VIDEOS and folder_date == today:
                    continue
                # Prefer a `validations` subfolder inside the date folder, but
                # fall back to videos placed directly in the date folder.
                validations_dir = child / "validations"
                sources = []
                if validations_dir.exists() and validations_dir.is_dir():
                    sources.append(validations_dir)
                sources.append(child)

                for src in sources:
                    try:
                        pending.extend(
                            sorted(
                                [p for p in src.iterdir() if _video_is_pending(p)],
                                key=lambda p: p.name.lower()
                            )
                        )
                    except (OSError, PermissionError):
                        pass
            else:
                # If it's not a date folder (e.g., 201, 202, 101, 102), 
                # look for date folders inside it
                for grandchild in sorted(child.iterdir(), key=lambda p: p.name.lower()):
                    if grandchild.is_dir():
                        subfolder_date = _parse_date_folder(grandchild)
                        if subfolder_date is None:
                            continue
                        # Skip folders from the future
                        if subfolder_date > today:
                            continue
                        # Skip today's folder if configured not to process today's videos
                        if not PROCESS_TODAY_VIDEOS and subfolder_date == today:
                            continue
                        # Look for `validations` inside the date subfolder first.
                        validations_dir = grandchild / "validations"
                        sources = []
                        if validations_dir.exists() and validations_dir.is_dir():
                            sources.append(validations_dir)
                        sources.append(grandchild)

                        for src in sources:
                            try:
                                pending.extend(
                                    sorted(
                                        [p for p in src.iterdir() if _video_is_pending(p)],
                                        key=lambda p: p.name.lower()
                                    )
                                )
                            except (OSError, PermissionError):
                                print(f"    Warning: Cannot read {src}")
        elif _video_is_pending(child):
            pending.append(child)

    return pending


def _camera_folder_worker(camera_info: dict, roi_polygon: np.ndarray, preview_queue):
    cam_id = camera_info["id"]
    
    # Get the upload folder name from the mapping, fallback to cam_id if not found
    folder_name = CAMERA_FOLDER_MAP.get(cam_id, str(cam_id))
    upload_folder = Path(UPLOAD_ROOT) / folder_name
    upload_folder.mkdir(parents=True, exist_ok=True)

    print(f"[CAM-{cam_id}] Watching: {upload_folder}")

    failed_videos = {}  # path -> retry_after_time

    while True:
        try:
            now = time.time()

            # সব pending video খোঁজো (previous-date folders only)
            all_pending = _find_pending_videos(upload_folder)

            if not all_pending:
                time.sleep(UPLOAD_POLL_INTERVAL)
                continue

            # cooldown এ নেই এমন প্রথম video নাও
            next_video = None
            for p in all_pending:
                if failed_videos.get(p, 0) <= now:
                    next_video = p
                    break

            if next_video is None:
                next_retry = min(failed_videos[p] for p in all_pending if p in failed_videos)
                wait = max(1, min(next_retry - now, UPLOAD_POLL_INTERVAL))
                print(f"[CAM-{cam_id}] all video cooldown  {wait:.0f}s পরে check করব...")
                time.sleep(wait)
                continue

            if not _wait_for_stable_file(next_video):
                print(f"[CAM-{cam_id}] File appears to be still writing: {next_video.name}; will retry shortly")
                failed_videos[next_video] = now + 10
                continue

            print(f"[CAM-{cam_id}] Checking: {next_video.name}")
            if not _probe_video_file(next_video):
                print(f"[CAM-{cam_id}] ✗ Bad video: {next_video.name} — 5 মিনিট পরে retry")
                failed_videos[next_video] = now + VIDEO_RETRY_SECONDS
                continue

            print(f"[CAM-{cam_id}] ▶ Processing: {next_video.name}")
            proc_info = dict(camera_info)
            proc_info["stream_url"] = str(next_video)

            success = run_camera(proc_info, roi_polygon, preview_queue=preview_queue)
            failed_videos.pop(next_video, None)

            if success:
                done_path = _mark_done(next_video)
                print(f"[CAM-{cam_id}] ✓ Done: {done_path.name}")
            else:
                print(f"[CAM-{cam_id}] ✗ Failed: {next_video.name} — after  5 min  retry")
                failed_videos[next_video] = now + VIDEO_RETRY_SECONDS

        except KeyboardInterrupt:
            break
        except Exception as e:
            import traceback
            print(f"[CAM-{cam_id}] Exception: {e}")
            traceback.print_exc()
            time.sleep(5)

# def _camera_folder_worker(camera_info: dict, roi_polygon: np.ndarray, preview_queue):
#     cam_id   = camera_info["id"]
#     cam_name = camera_info.get("name", f"Camera-{cam_id}")
#     upload_folder = Path(UPLOAD_ROOT) / str(cam_id)
#     upload_folder.mkdir(parents=True, exist_ok=True)

#     print(f"[CAM-{cam_id}] Watching uploads folder: {upload_folder}")
    
#     # Track files that failed probing and their next retry time
#     failed_videos = {}  # path -> retry_after_time

#     while True:
#         try:
#             now = time.time()
            
#             # Find all pending videos
#             all_pending = [p for p in upload_folder.iterdir() if _video_is_pending(p)]
            
#             # Filter out files that are still in cooldown
#             available_videos = [
#                 p for p in all_pending 
#                 if p not in failed_videos or failed_videos[p] <= now
#             ]
            
#             if not available_videos:
#                 # All videos are either processing or in cooldown
#                 if all_pending:
#                     next_retry = min(failed_videos.get(p, now) for p in all_pending)
#                     wait_time = max(1, min(next_retry - now, UPLOAD_POLL_INTERVAL))
#                     print(f"[CAM-{cam_id}] No available videos. Next check in {wait_time:.0f}s")
#                     time.sleep(wait_time)
#                 else:
#                     time.sleep(UPLOAD_POLL_INTERVAL)
#                 continue
            
#             # Sort by modification time (FIFO)
#             next_video = sorted(available_videos, key=lambda p: (p.stat().st_mtime, p.name))[0]

#             if not _wait_for_stable_file(next_video):
#                 print(f"[CAM-{cam_id}] File still writing: {next_video.name}, will retry later")
#                 time.sleep(UPLOAD_POLL_INTERVAL)
#                 continue

#             print(f"[CAM-{cam_id}] Checking video: {next_video.name}")
#             if not _probe_video_file(next_video):
#                 # Video is corrupted or invalid
#                 print(f"[CAM-{cam_id}] ✗ Bad video: {next_video.name} — will retry in 5 minutes")
#                 failed_videos[next_video] = now + VIDEO_RETRY_SECONDS
#                 time.sleep(2)  # Brief pause before checking next
#                 continue

#             # Video is good, process it
#             print(f"[CAM-{cam_id}] Processing video: {next_video.name}")
#             proc_info = dict(camera_info)
#             proc_info["stream_url"] = str(next_video)

#             success = run_camera(proc_info, roi_polygon, preview_queue=preview_queue)
            
#             # Clean up tracking
#             failed_videos.pop(next_video, None)
            
#             if success:
#                 done_path = _mark_done(next_video)
#                 print(f"[CAM-{cam_id}] ✓ Completed: {done_path.name}")
#                 print(f"[CAM-{cam_id}] Looking for next video...")
#                 continue  # Immediately check for next video
#             else:
#                 print(f"[CAM-{cam_id}] ✗ Processing failed for {next_video.name}. Retrying in 5 minutes.")
#                 failed_videos[next_video] = now + VIDEO_RETRY_SECONDS
#                 time.sleep(2)
#                 continue  # Move to next iteration to find another video

#         except KeyboardInterrupt:
#             break
#         except Exception as e:
#             import traceback
#             print(f"[CAM-{cam_id}] Worker exception: {e}")
#             traceback.print_exc()
#             time.sleep(5)


# ─────────────────────────────────────────────────────
# Preview window — সব camera এর frame একসাথে দেখায়
# ─────────────────────────────────────────────────────
def _build_preview_grid(frames_by_cam: dict, grid_cols: int = 2) -> np.ndarray:
    """
    frames_by_cam: {cam_id: (cam_name, frame_640x360)}
    সব frame গুলো একটা grid এ রাখে।
    """
    items = list(frames_by_cam.values())
    if not items:
        return np.zeros((360, 640, 3), dtype=np.uint8)

    CELL_W, CELL_H = 640, 360
    n        = len(items)
    cols     = min(grid_cols, n)
    rows     = (n + cols - 1) // cols
    grid     = np.zeros((rows * CELL_H, cols * CELL_W, 3), dtype=np.uint8)

    for idx, (name, frame) in enumerate(items):
        r = idx // cols
        c = idx % cols
        y0, y1 = r * CELL_H, (r+1) * CELL_H
        x0, x1 = c * CELL_W, (c+1) * CELL_W

        if frame is not None:
            cell = cv2.resize(frame, (CELL_W, CELL_H))
        else:
            cell = np.zeros((CELL_H, CELL_W, 3), dtype=np.uint8)
            cv2.putText(cell, f"{name} — No Frame",
                        (20, CELL_H//2), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (100,100,100), 2)

        # Camera name label
        # cv2.putText(cell, name, (10, 25),
        #             cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,220,255), 2)

        grid[y0:y1, x0:x1] = cell

    # Grid border lines
    for r in range(1, rows):
        cv2.line(grid, (0, r*CELL_H), (cols*CELL_W, r*CELL_H), (60,60,60), 1)
    for c in range(1, cols):
        cv2.line(grid, (c*CELL_W, 0), (c*CELL_W, rows*CELL_H), (60,60,60), 1)

    return grid


# ─────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────
def main():
    init_db()

    all_cameras = get_active_cameras()
    if not all_cameras:
        print(" No active cameras in DB.")
        return

    print(f"\n {len(all_cameras)} active camera(s) found.")
    print(f" Upload root: {UPLOAD_ROOT}\n")

    upload_root = Path(UPLOAD_ROOT)
    upload_root.mkdir(parents=True, exist_ok=True)

    camera_rois = [(cam, []) for cam in all_cameras]

    # Ensure upload folders exist for each camera
    today_compact = date.today().strftime("%Y%m%d")
    for cam, _ in camera_rois:
        folder_name = CAMERA_FOLDER_MAP.get(cam["id"], str(cam["id"]))
        folder = upload_root / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        # Ensure today's compact date folder and validations subfolder exist
        today_folder_compact = folder / today_compact
        validations_compact = today_folder_compact / "validations"
        validations_compact.mkdir(parents=True, exist_ok=True)

        print(f"  [CAM-{cam['id']}] Upload folder: {folder} (today: {validations_compact})")

    # ── Step 4: Shared preview queue ──
    # সব camera এর preview frame এখানে আসবে
    preview_queue = mp.Queue(maxsize=len(camera_rois) * 3)

    # ── Step 5: Spawn processes ──
    print(f"\n Starting {len(camera_rois)} camera process(es)...\n")
    processes = []

    for cam, roi_list in camera_rois:
        p = mp.Process(
            target=_worker_entry,
            args=(cam, roi_list, preview_queue),
            name=f"cam-{cam['id']}"
        )
        p.start()
        processes.append((p, cam))
        print(f"  ▶ PID={p.pid} | Camera {cam['id']} — {cam['name']}")
        time.sleep(0.3)

    print("\n[Main] Preview window খুলছে... ESC বা Q চাপলে বন্ধ হবে.\n")

    # ── Step 6: Preview loop (main process এ) ──
    # latest frame per camera
    frames_by_cam = {
        cam["id"]: (cam["name"], None)
        for cam, _ in camera_rois
    }

    cv2.namedWindow("ANPR — Live Preview", cv2.WINDOW_NORMAL)

    try:
        while True:
            # Queue থেকে নতুন frames নাও
            drained = 0
            while drained < 20:   # প্রতি loop এ max 20 frame drain
                try:
                    cam_id, cam_name, preview = preview_queue.get_nowait()
                    frames_by_cam[cam_id] = (cam_name, preview)
                    drained += 1
                except Exception:
                    break

            # Grid বানাও ও দেখাও
            grid = _build_preview_grid(frames_by_cam, grid_cols=2)
            cv2.imshow("ANPR — Live Preview", grid)

            key = cv2.waitKey(30) & 0xFF   # ~33 fps refresh
            if key in (27, ord('q')):       # ESC or Q
                print("\n[Main] Preview বন্ধ করা হচ্ছে...")
                break

            # Dead process check
            alive = []
            for p, cam in processes:
                if p.is_alive():
                    alive.append((p, cam))
                else:
                    print(f" {p.name} exited (code={p.exitcode})")
            processes[:] = alive

            if not processes:
                print("[Main] সব camera process শেষ হয়ে গেছে.")
                break

    except KeyboardInterrupt:
        print("\n[Main] Ctrl+C — সব camera বন্ধ করা হচ্ছে...")

    finally:
        cv2.destroyAllWindows()

        for p, cam in processes:
            if p.is_alive():
                print(f"  Terminating {p.name}...")
                p.terminate()

        for p, cam in processes:
            p.join(timeout=5)

    print_summary()
    print("\n Done.")


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)   # Windows + Linux compatible
    main()


















