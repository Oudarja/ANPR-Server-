# import os
# import shutil
# import stat

# # Target tarikh folder er naam
# TARGET_DATE = "20260611"

# # Base paths
# SRC_BASE = "/home/ftpman/uploads"
# DEST_BASE = "/mnt/second_drive/ftp"

# # Main 4 ta folder list
# folders = ["101", "102", "201", "202"]

# print("------------------------------------------------")
# print("Python File Mover Script Shuru Hochhe...")
# print("------------------------------------------------")

# for folder in folders:
#     # Source ebong Destination path build kora
#     src_dir = os.path.join(SRC_BASE, folder, TARGET_DATE)
#     dest_dir = os.path.join(DEST_BASE, folder, TARGET_DATE)
    
#     # Check korche source folder ache kina
#     if os.path.exists(src_dir) and os.path.isdir(src_dir):
#         print(f"Checking folder: {src_dir}")
        
#         # Destination folder na thakle toiri korbe ebong 777 permission dibe
#         if not os.path.exists(dest_dir):
#             print(f"Creating destination: {dest_dir}")
#             os.makedirs(dest_dir, exist_ok=True)
#             os.chmod(dest_dir, 0o777) # Full write/read permission
            
#         # Source folder er sob file check korbe
#         for filename in os.listdir(src_dir):
#             # Check korche file-tir namer sheshe 'done.ts' ache kina
#             if filename.endswith("done.ts"):
#                 src_file_path = os.path.join(src_dir, filename)
#                 dest_file_path = os.path.join(dest_dir, filename)
                
#                 try:
#                     print(f"Moving: {filename} -> {dest_dir}")
                    
#                     # File move korche (shutil.move automatic source theke delete kore dey)
#                     shutil.move(src_file_path, dest_file_path)
                    
#                     # Moved file-tir permission 777 (rwxrwxrwx) kore dicche
#                     os.chmod(dest_file_path, 0o777)
                    
#                 except Exception as e:
#                     print(f"Error moving {filename}: {e}")
#     else:
#         print(f"Source folder paowa jayni: {src_dir}")

# print("------------------------------------------------")
# print("Kaj shesh! Sob done.ts file safollobhabe move hoyeche.")









import os
import shutil
import time
from datetime import datetime

# Base paths
SRC_BASE = "/home/ftpman/uploads"
DEST_BASE = "/mnt/second_drive/ftp"

# Main 4 ta folder list
folders = ["101", "102", "201", "202"]

print("------------------------------------------------")
print("Dynamic Python File Mover Script Active Hochhe...")
print("Script-ti proti 30 minute por por automatic cholbe.")
print("------------------------------------------------")

while True:
    # Ekhonkar borthoman date auto generate korbe (Format: YYYYMMDD, jemon: 20260611)
    TARGET_DATE = datetime.now().strftime("%Y%m%d")
    current_time = datetime.now().strftime("%H:%M:%S")
    
    print(f"\n[Run Time: {current_time}] Target Date: {TARGET_DATE} er jonno check kora hochhe...")
    
    for folder in folders:
        # Source ebong Destination path dynamically build kora
        src_dir = os.path.join(SRC_BASE, folder, TARGET_DATE)
        dest_dir = os.path.join(DEST_BASE, folder, TARGET_DATE)
        
        # Check korche borthoman tarikh-er source folder-ti ache kina
        if os.path.exists(src_dir) and os.path.isdir(src_dir):
            
            # Destination folder na thakle toiri korbe ebong 777 permission dibe
            if not os.path.exists(dest_dir):
                print(f"Creating destination folder: {dest_dir}")
                os.makedirs(dest_dir, exist_ok=True)
                os.chmod(dest_dir, 0o777)
                
            # Source folder er vitore thaka file gulo scan korche
            for filename in os.listdir(src_dir):
                if filename.endswith("done.ts"):
                    src_file_path = os.path.join(src_dir, filename)
                    dest_file_path = os.path.join(dest_dir, filename)
                    
                    try:
                        print(f"Moving: {folder}/{TARGET_DATE}/{filename} -> Destination")
                        
                        # File move (Kete niye jabe)
                        shutil.move(src_file_path, dest_file_path)
                        
                        # Full Read-Write-Execute permission apply
                        os.chmod(dest_file_path, 0o777)
                        
                    except Exception as e:
                        print(f"Error moving {filename}: {e}")
                        
    print(f"Check shesh! 30 minute-er jonno script sleep-e jachhe...")
    
    # 30 minute (30 * 60 seconds = 1800 seconds) script-ti thome thakbe
    time.sleep(1800)