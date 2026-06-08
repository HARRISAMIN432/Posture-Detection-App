import os
import cv2
import numpy as np
from PIL import Image
import io
import base64
import tempfile
import uuid
import time
from fastapi import FastAPI, File, UploadFile, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import asyncio
from ultralytics import YOLO
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')
logger = logging.getLogger("PostureAPI")

app = FastAPI(title="Posture Detection API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("temp_videos", exist_ok=True)
app.mount("/videos", StaticFiles(directory="temp_videos"), name="videos")

# Load the model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "best.pt")
model = None

try:
    if os.path.exists(MODEL_PATH):
        logger.info(f"Loading YOLO model from {MODEL_PATH}...")
        model = YOLO(MODEL_PATH)
        logger.info("✅ Model loaded successfully")
    else:
        logger.error(f"⚠️ Model file not found at {MODEL_PATH}")
except Exception as e:
    logger.exception(f"Error loading model: {e}")

def predict_and_annotate(frame_bgr, conf=0.5):
    if model is None:
        return frame_bgr, "Model not loaded", (128, 128, 128)
        
    results = model.predict(frame_bgr, conf=conf, verbose=False)[0]
    annotated = frame_bgr.copy()

    label_text = "No detection"
    color = (128, 128, 128)

    if results.boxes and len(results.boxes):
        best = max(results.boxes, key=lambda b: float(b.conf))
        cls = int(best.cls)
        confidence = float(best.conf)
        x1, y1, x2, y2 = map(int, best.xyxy[0])

        is_good = cls == 1
        label_text = f"{'Good Posture' if is_good else 'Bad Posture'} ({confidence:.0%})"
        color = (0, 200, 0) if is_good else (0, 0, 220)

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)
        cv2.putText(annotated, label_text, (x1, max(y1 - 12, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)

    return annotated, label_text, color

def process_video_file(tmp_path, output_path, conf_threshold):
    logger.info(f"[Video Process] Starting processing of {tmp_path}")
    
    # Use FFMPEG backend to avoid MSMF deadlocks on Windows
    cap = cv2.VideoCapture(tmp_path, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        logger.error(f"[Video Process] Failed to open video file {tmp_path}")
        return
        
    logger.info("[Video Process] Video file opened successfully.")
    
    # Switch video input decoding to MJPEG-compatible format
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logger.info(f"[Video Process] Source video: {width}x{height} @ {fps}fps, Total Frames: {total_frames}")
    
    # Use mp4v (built into OpenCV) to avoid OpenH264 dependency errors on Windows
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    if not out.isOpened():
        logger.error(f"[Video Process] Failed to initialize VideoWriter for {output_path}")
        cap.release()
        return

    # Process ~4 frames/sec to keep processing fast (just like the original Streamlit app)
    step = max(1, int(fps // 4))
    
    frames_processed = 0
    frame_idx = 0
    start_time = time.time()
    last_annotated_bgr = None
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            logger.info(f"[Video Process] End of video stream reached after {frames_processed} frames.")
            break
            
        frame_idx += 1
        
        # Only run YOLO on every Nth frame
        if frame_idx % step == 0 or last_annotated_bgr is None:
            annotated_bgr, _, _ = predict_and_annotate(frame, conf=conf_threshold)
            last_annotated_bgr = annotated_bgr
            
        # Write the most recently annotated frame (this keeps the video playback smooth)
        out.write(last_annotated_bgr)
        frames_processed += 1
        
        if frames_processed % 50 == 0:
            logger.info(f"[Video Process] Processed {frames_processed}/{total_frames} frames...")
            
    cap.release()
    out.release()
    elapsed = time.time() - start_time
    logger.info(f"[Video Process] Processing completed. Saved to {output_path} in {elapsed:.2f}s")

@app.post("/api/predict/image")
async def predict_image(file: UploadFile = File(...), conf_threshold: float = Form(0.5)):
    logger.info(f"[Image Upload] Received image file: {file.filename}")
    contents = await file.read()
    img = Image.open(io.BytesIO(contents)).convert("RGB")
    frame_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    
    annotated_bgr, label, color = await asyncio.to_thread(predict_and_annotate, frame_bgr, conf_threshold)
    
    _, buffer = cv2.imencode('.jpg', annotated_bgr)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    logger.info(f"[Image Upload] Analyzed image: {label}")
    
    return {
        "image": f"data:image/jpeg;base64,{img_base64}",
        "label": label,
        "is_good": "Good" in label
    }

@app.post("/api/predict/video")
async def predict_video(file: UploadFile = File(...), conf_threshold: float = Form(0.5)):
    logger.info(f"[Video Upload] Received video file: {file.filename}")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name
    
    output_filename = f"{uuid.uuid4().hex}.mp4"
    output_path = os.path.join("temp_videos", output_filename)
    logger.info(f"[Video Upload] Saved temp video to {tmp_path}. Will output to {output_path}")
    
    try:
        await asyncio.to_thread(process_video_file, tmp_path, output_path, conf_threshold)
    except Exception as e:
        logger.exception("[Video Upload] Error during process_video_file execution")
        raise e
    finally:
        try:
            os.unlink(tmp_path)
            logger.info(f"[Video Upload] Deleted temporary file {tmp_path}")
        except Exception as e:
            logger.warning(f"[Video Upload] Could not delete tmp file {tmp_path}: {e}")
    
    url = f"http://127.0.0.1:8000/videos/{output_filename}"
    logger.info(f"[Video Upload] Returning processed video URL: {url}")
    return {"video_url": url}

@app.websocket("/api/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    client = websocket.client
    logger.info(f"[Webcam] New WebSocket connection from {client}")
    try:
        frame_idx = 0
        while True:
            data = await websocket.receive_text()
            if data.startswith("data:image"):
                header, encoded = data.split(",", 1)
                img_bytes = base64.b64decode(encoded)
                nparr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is None:
                    logger.warning("[Webcam] Failed to decode received frame bytes into an image.")
                    continue

                # Offload inference
                annotated_bgr, label, color = await asyncio.to_thread(predict_and_annotate, frame, 0.5)
                
                _, buffer = cv2.imencode('.jpg', annotated_bgr)
                out_base64 = base64.b64encode(buffer).decode('utf-8')
                
                await websocket.send_json({
                    "image": f"data:image/jpeg;base64,{out_base64}",
                    "label": label,
                    "is_good": "Good" in label
                })
                frame_idx += 1
                if frame_idx % 100 == 0:
                    logger.info(f"[Webcam] Processed {frame_idx} frames for client {client}")
    except WebSocketDisconnect:
        logger.info(f"[Webcam] Client {client} disconnected normally.")
    except Exception as e:
        logger.exception(f"[Webcam] Error in websocket connection with {client}: {e}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
