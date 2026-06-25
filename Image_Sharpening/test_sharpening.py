
# import cv2
# import os

# input_folder = "."          # folder containing original plate images
# output_folder = "plates_sharp"   # folder to save sharpened images

# os.makedirs(output_folder, exist_ok=True)

# for filename in os.listdir(input_folder):

#     if filename.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):

#         image_path = os.path.join(input_folder, filename)

#         plate_img = cv2.imread(image_path)

#         if plate_img is None:
#             print(f"Could not read: {filename}")
#             continue

#         blur = cv2.GaussianBlur(plate_img, (0, 0), 2)

#         sharp = cv2.addWeighted(plate_img, 2.5, blur, -1.5, 0)

#         output_path = os.path.join(output_folder, filename)
#         cv2.imwrite(output_path, sharp)

#         print(f"Processed: {filename}")

# print("Done.")

# kernel-based spatial filtering (convolution sharpening) 
# This increases local contrast around edges, making edges and characters appear sharper.
import cv2
import matplotlib.pyplot as plt
import numpy as np
import os
input_folder = "."          # folder containing original plate images
output_folder = "plates_sharp_"   # folder to save sharpened images

os.makedirs(output_folder, exist_ok=True)

for filename in os.listdir(input_folder):

    if filename.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):

        image_path = os.path.join(input_folder, filename)

        plate_img = cv2.imread(image_path)

        if plate_img is None:
            print(f"Could not read: {filename}")
            continue

        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])

        sharpened_image = cv2.filter2D(plate_img, -1, kernel)

        output_path = os.path.join(output_folder, filename)
        cv2.imwrite(output_path, sharpened_image)

        print(f"Processed: {filename}")

