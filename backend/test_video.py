import requests
import cv2
import numpy as np
import time
import os

print("Creating dummy video...")
fps = 30
width, height = 640, 480
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter('dummy.mp4', fourcc, fps, (width, height))

for i in range(60): # 2 seconds of video
    frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    out.write(frame)
out.release()
print("Dummy video created.")

print("Starting test...")
with open('dummy.mp4', 'rb') as f:
    files = {'file': ('dummy.mp4', f, 'video/mp4')}
    data = {'conf_threshold': '0.5'}
    try:
        t0 = time.time()
        print("Sending POST request to http://localhost:8000/api/predict/video")
        response = requests.post('http://localhost:8000/api/predict/video', files=files, data=data)
        t1 = time.time()
        print(f"Status Code: {response.status_code} in {t1-t0:.2f}s")
        print(f"Response: {response.text}")
    except Exception as e:
        print("Error sending request:", e)

if os.path.exists('dummy.mp4'):
    os.remove('dummy.mp4')
