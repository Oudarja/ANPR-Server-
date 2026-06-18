import os
import time
from pathlib import Path
import cv2


def is_file_stable(file_path: Path, wait_time: int = 2) -> bool:
    """চেক করে ফাইলটি এখনো রাইট (write) হচ্ছে কিনা।

    ২ সেকেন্ড পর ফাইলের সাইজ পরিবর্তন না হলে ফাইলটি স্ট্যাবল।
    """
    try:
        initial_size = file_path.stat().st_size
        time.sleep(wait_time)
        final_size = file_path.stat().st_size
        return initial_size == final_size
    except (FileNotFoundError, PermissionError):
        return False


def is_good_video(file_path: Path) -> bool:
    """OpenCV দিয়ে ভিডিও ফাইলটি খুলে চেক করে সেটি ভালো নাকি নষ্ট।"""
    # ফাইল পুরোপুরি রেডি হওয়া পর্যন্ত অপেক্ষা করি
    if not is_file_stable(file_path):
        print(f"file upload incomplete: {file_path.name}")
        return False

    # OpenCV দিয়ে ভিডিও ওপেন করার চেষ্টা
    cap = cv2.VideoCapture(str(file_path))

    if not cap.isOpened():
        # ভিডিও ফাইলটি ওপেনই করা যায়নি (করাপ্টেড)
        return False

    # ভিডিওর মোট ফ্রেম সংখ্যা এবং সাইজ চেক করি
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # যদি ফ্রেম সংখ্যা ০ হয় বা রেজোলিউশন ইনভ্যালিড হয়, তবে ভিডিও খারাপ
    if frame_count <= 0 or width <= 0 or height <= 0:
        cap.release()
        return False

    # (ঐচ্ছিক) প্রথম ফ্রেমটি আসলেই রিড করা যাচ্ছে কিনা চেক করি
    ret, frame = cap.read()
    cap.release()

    return ret  # প্রথম ফ্রেম সফলভাবে রিড হলে True, নাহলে False


def scan_video_folder(folder_path: str):
    """পুরো ফোল্ডার স্ক্যান করে ভালো এবং নষ্ট ভিডিওর তালিকা তৈরি করে।"""
    target_dir = Path(folder_path)

    if not target_dir.exists() or not target_dir.is_dir():
        print(f"Error: ফোল্ডারটি পাওয়া যায়নি: {folder_path}")
        return

    # যেসব এক্সটেনশন আমরা চেক করব
    video_extensions = {".mp4", ".avi", ".mkv", ".ts", ".flv", ".wmv"}

    good_videos = []
    failed_videos = []

    print(f"Scanning folder: {target_dir.resolve()}\n" + "-" * 50)

    # ফোল্ডারের ভেতরের সব ফাইল চেক করা
    for file in target_dir.iterdir():
        if file.is_file() and file.suffix.lower() in video_extensions:
            print(f"check: {file.name}...")

            if is_good_video(file):
                good_videos.append(file.name)
            else:
                failed_videos.append(file.name)

    # --- রিপোর্ট প্রিন্ট করা ---
    print("\n" + "=" * 20 + " রিপোর্ট " + "=" * 20)

    print(f"\n✓ good video ({len(good_videos)}):")
    if good_videos:
        for vid in good_videos:
            print(f"  - {vid}")
    else:
        print("  (no good videos found)")

    print(f"\n✗ broken ({len(failed_videos)}):")
    if failed_videos:
        for vid in failed_videos:
            print(f"  - {vid}")
    else:
        print("  (all videos are good!)")


# --- স্ক্রিপ্ট রান করার অংশ ---
if __name__ == "__main__":
    # আপনার ফোল্ডারের পাথটি এখানে দিন (যেমন: "C:/Users/Name/Videos" বা "./uploads")
    TARGET_FOLDER = "/mnt/second_drive/ftpman/uploads/202/20260617"

    # টেস্ট করার জন্য ফোল্ডারটি না থাকলে তৈরি করে নিবে
    Path(TARGET_FOLDER).mkdir(exist_ok=True)

    scan_video_folder(TARGET_FOLDER)