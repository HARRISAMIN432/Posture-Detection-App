import os
import cv2
import numpy as np
from PIL import Image
import io
import base64
import tempfile
import uuid
from fastapi import FastAPI, File, UploadFile, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import asyncio
from ultralytics import YOLO

app = FastAPI(title="Posture Detection API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure temp directory for videos exists
os.makedirs("temp_videos", exist_ok=True)
app.mount("/videos", StaticFiles(directory="temp_videos"), name="videos")

# Load the model
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "best.pt")
model = None

try:
    if os.path.exists(MODEL_PATH):
        model = YOLO(MODEL_PATH)
        print("✅ Model loaded successfully")
    else:
        print(f"⚠️ Model file not found at {MODEL_PATH}")
except Exception as e:
    print(f"Error loading model: {e}")

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

@app.post("/api/predict/image")
async def predict_image(file: UploadFile = File(...), conf_threshold: float = Form(0.5)):
    contents = await file.read()
    img = Image.open(io.BytesIO(contents)).convert("RGB")
    frame_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    
    annotated_bgr, label, color = predict_and_annotate(frame_bgr, conf=conf_threshold)
    
    # Encode to base64
    _, buffer = cv2.imencode('.jpg', annotated_bgr)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    
    return {
        "image": f"data:image/jpeg;base64,{img_base64}",
        "label": label,
        "is_good": "Good" in label
    }

@app.post("/api/predict/video")
async def predict_video(file: UploadFile = File(...), conf_threshold: float = Form(0.5)):
    # Save uploaded video
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    cap = cv2.VideoCapture(tmp_path)
    
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    
    output_filename = f"{uuid.uuid4().hex}.webm"
    output_path = os.path.join("temp_videos", output_filename)
    
    # Use VP8/VP9 for better web compatibility without licensing issues usually tied to H264 on OpenCV
    fourcc = cv2.VideoWriter_fourcc(*'vp09')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    # To prevent extremely long processing, we might optionally skip frames
    # but for quality we process them all
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        annotated_bgr, _, _ = predict_and_annotate(frame, conf=conf_threshold)
        out.write(annotated_bgr)
        
    cap.release()
    out.release()
    os.unlink(tmp_path)
    
    return {"video_url": f"http://localhost:8000/videos/{output_filename}"}

@app.websocket("/api/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Expecting base64 image data: "data:image/jpeg;base64,..."
            if data.startswith("data:image"):
                header, encoded = data.split(",", 1)
                img_bytes = base64.b64decode(encoded)
                nparr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                annotated_bgr, label, color = predict_and_annotate(frame, conf=0.5)
                
                _, buffer = cv2.imencode('.jpg', annotated_bgr)
                out_base64 = base64.b64encode(buffer).decode('utf-8')
                
                await websocket.send_json({
                    "image": f"data:image/jpeg;base64,{out_base64}",
                    "label": label,
                    "is_good": "Good" in label
                })
    except WebSocketDisconnect:
        print("Client disconnected")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
