# THis file i will access a video and test using pytesseract to extract the date and time from the video clip. I will use the find_date_time function from ocr.py to extract the date and time from the video clip.

import cv2
from ocr import find_date_time



# there are 4 videoes to check
video_path=["video__/S20260615122721E00000000000000.ts", 
            "video__/S20260615135044E00000000000000.ts", 
            "video__/S20260615140124E20260615141419.ts", 
            "video__/S20260615141421E20260615141722.ts"]

# print(len(video_path))
for i in video_path:
    cap = cv2.VideoCapture(i)

    if not cap.isOpened():
        print(f"Error: Could not open video {i}.")
        continue

    # read the 2nd frame
    for _ in range(2):
        ret, frame = cap.read()

    if not ret:
        print(f"Error: Could not read frame from video {i}.")
        cap.release()
        continue

    # # show the 2nd frame
    # cv2.imshow("Second Frame", frame)
    # cv2.waitKey(0)  # press any key to continue
    # cv2.destroyAllWindows()

    # extract date and time from the frame using OCR
    date_time = find_date_time(frame)
    print(f"Extracted Date and Time from {i}: {date_time}")

    cap.release()