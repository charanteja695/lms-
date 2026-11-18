import os
import zipfile
import shutil

FRONTEND_DIR = os.path.abspath("Lms_frontend_Gz")
OUTPUT_ZIP_1 = os.path.abspath("examlms_frontend_total.zip")
OUTPUT_ZIP_2 = os.path.abspath(r"C:\Users\tejac\.gemini\antigravity\brain\b799b301-d413-419b-a1fa-5d822b118c0c\examlms_frontend_total.zip")

EXCLUDE_DIRS = {"node_modules", "dist", ".git", "__pycache__"}
EXCLUDE_EXTS = {".tsbuildinfo"}

print(f"Creating zip from {FRONTEND_DIR}...")

if os.path.exists(OUTPUT_ZIP_1):
    os.remove(OUTPUT_ZIP_1)

file_count = 0
with zipfile.ZipFile(OUTPUT_ZIP_1, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for root, dirs, files in os.walk(FRONTEND_DIR):
        # Filter directories in place to prevent os.walk from entering them
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in EXCLUDE_EXTS:
                continue
            if file.endswith(".mjs") and "verify_" in file:
                continue
            
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, os.path.dirname(FRONTEND_DIR))
            zf.write(full_path, rel_path)
            file_count += 1

print(f"Archived {file_count} files into {OUTPUT_ZIP_1}")
size_bytes = os.path.getsize(OUTPUT_ZIP_1)
print(f"Zip size: {size_bytes / (1024 * 1024):.2f} MB ({size_bytes} bytes)")

# Copy to brain artifact directory
shutil.copyfile(OUTPUT_ZIP_1, OUTPUT_ZIP_2)
print(f"Copied to artifact directory: {OUTPUT_ZIP_2}")
