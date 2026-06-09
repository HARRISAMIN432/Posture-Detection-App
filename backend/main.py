import os
import cv2
import numpy as np
from PIL import Image
import io
import base64
import tempfile
import uuid
import time
import json
import math
from fastapi import FastAPI, File, UploadFile, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import asyncio
from ultralytics import YOLO
import logging

# ── MediaPipe (optional but strongly recommended) ────────────────────────────
# Newer mediapipe versions (0.10+) moved the legacy solutions API.
# We try the legacy path first, then the new path, then disable gracefully.
MEDIAPIPE_AVAILABLE = False
_mp_pose = None
_mp_draw = None

try:
    import mediapipe as mp

    try:
        _mp_pose = mp.solutions.pose
        _mp_draw = mp.solutions.drawing_utils
        MEDIAPIPE_AVAILABLE = True
    except AttributeError:
        import mediapipe as mp

        mp_pose = mp.solutions.pose
        mp_drawing = mp.solutions.drawing_utils
        import types
        MEDIAPIPE_AVAILABLE = True

except (ImportError, Exception) as _mp_err:
    import logging as _log
    _log.getLogger("PostureAPI").warning(f"MediaPipe not available: {_mp_err}. Skeleton overlay disabled.")

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s')
logger = logging.getLogger("PostureAPI")

app = FastAPI(title="Posture Detection API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("temp_videos", exist_ok=True)
app.mount("/videos", StaticFiles(directory="temp_videos"), name="videos")

# ── Load YOLO model ───────────────────────────────────────────────────────────
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


# ── Angle helpers ─────────────────────────────────────────────────────────────
def _angle_3pt(a, b, c):
    """Return the angle (degrees) at point B formed by A-B-C."""
    ab = (a[0] - b[0], a[1] - b[1])
    cb = (c[0] - b[0], c[1] - b[1])
    dot = ab[0]*cb[0] + ab[1]*cb[1]
    mag = (math.hypot(*ab) * math.hypot(*cb)) or 1e-9
    return math.degrees(math.acos(max(-1, min(1, dot / mag))))


def _lm_xy(landmarks, idx, w, h):
    lm = landmarks[idx]
    return int(lm.x * w), int(lm.y * h)


def _box_iou(a, b):
    """Intersection-over-union for (x1, y1, x2, y2) boxes."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def _box_containment(inner, outer):
    """Fraction of the inner box covered by the outer box."""
    ix1, iy1 = max(inner[0], outer[0]), max(inner[1], outer[1])
    ix2, iy2 = min(inner[2], outer[2]), min(inner[3], outer[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    inner_area = (inner[2] - inner[0]) * (inner[3] - inner[1])
    return inter / inner_area if inner_area else 0.0


def _dedupe_detections(detections):
    """
    Remove duplicate/overlapping boxes for the same person.
    YOLO NMS is per-class, so one person can get both Good and Bad boxes.
    Keeps the highest-confidence box when regions overlap significantly.
    """
    ranked = sorted(detections, key=lambda d: d["confidence"], reverse=True)
    kept = []
    for det in ranked:
        box = det["box"]
        cls = det["cls"]
        suppress = False
        for kept_det in kept:
            kept_box = kept_det["box"]
            overlap = _box_iou(box, kept_box)
            if overlap >= 0.65:
                suppress = True
                break
            if (
                _box_containment(box, kept_box) >= 0.9
                or _box_containment(kept_box, box) >= 0.9
            ):
                suppress = True
                break
            if cls != kept_det["cls"] and overlap >= 0.45:
                suppress = True
                break
        if not suppress:
            kept.append(det)
    return kept


def run_mediapipe(frame_bgr, x1, y1, x2, y2):
    """
    Run MediaPipe Pose on the detected person crop.
    Returns (annotated_frame, neck_angle, back_angle) where angles can be None.
    """
    if not MEDIAPIPE_AVAILABLE:
        return frame_bgr, None, None

    h, w = frame_bgr.shape[:2]
    # Expand crop slightly for better pose estimation
    pad = 20
    cx1, cy1 = max(0, x1 - pad), max(0, y1 - pad)
    cx2, cy2 = min(w, x2 + pad), min(h, y2 + pad)
    crop = frame_bgr[cy1:cy2, cx1:cx2]
    if crop.size == 0:
        return frame_bgr, None, None

    crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    ch, cw = crop.shape[:2]

    with _mp_pose.Pose(
        static_image_mode=True,
        model_complexity=1,
        enable_segmentation=False,
        min_detection_confidence=0.4,
    ) as pose:
        results = pose.process(crop_rgb)

    if not results.pose_landmarks:
        return frame_bgr, None, None

    lms = results.pose_landmarks.landmark

    # ── Draw skeleton on the FULL frame (map crop coords → full frame coords) ─
    annotated = frame_bgr.copy()

    # Build a shifted landmark set for drawing on full frame
    # We'll do it manually for the connections we care about
    CONNECTIONS = _mp_pose.POSE_CONNECTIONS

    # Draw each landmark dot
    for lm in lms:
        px = int(lm.x * cw) + cx1
        py = int(lm.y * ch) + cy1
        cv2.circle(annotated, (px, py), 4, (0, 255, 255), -1)

    # Draw connections
    for conn in CONNECTIONS:
        a_idx, b_idx = conn
        la, lb = lms[a_idx], lms[b_idx]
        if la.visibility < 0.3 or lb.visibility < 0.3:
            continue
        ax = int(la.x * cw) + cx1;  ay = int(la.y * ch) + cy1
        bx = int(lb.x * cw) + cx1;  by = int(lb.y * ch) + cy1
        cv2.line(annotated, (ax, ay), (bx, by), (0, 220, 220), 2)

    # ── Angle calculations ────────────────────────────────────────────────────
    # Neck angle: ear → shoulder → hip  (forward-head tilt)
    # Landmarks: LEFT_EAR=7, LEFT_SHOULDER=11, LEFT_HIP=23
    #            RIGHT_EAR=8, RIGHT_SHOULDER=12, RIGHT_HIP=24
    neck_angle = None
    back_angle = None

    try:
        # Use the more-visible side
        l_vis = (lms[7].visibility + lms[11].visibility + lms[23].visibility) / 3
        r_vis = (lms[8].visibility + lms[12].visibility + lms[24].visibility) / 3
        side = "left" if l_vis >= r_vis else "right"

        if side == "left":
            ear_pt  = (lms[7].x  * cw + cx1, lms[7].y  * ch + cy1)
            sho_pt  = (lms[11].x * cw + cx1, lms[11].y * ch + cy1)
            hip_pt  = (lms[23].x * cw + cx1, lms[23].y * ch + cy1)
            knee_pt = (lms[25].x * cw + cx1, lms[25].y * ch + cy1)
        else:
            ear_pt  = (lms[8].x  * cw + cx1, lms[8].y  * ch + cy1)
            sho_pt  = (lms[12].x * cw + cx1, lms[12].y * ch + cy1)
            hip_pt  = (lms[24].x * cw + cx1, lms[24].y * ch + cy1)
            knee_pt = (lms[26].x * cw + cx1, lms[26].y * ch + cy1)

        if lms[7 if side=="left" else 8].visibility > 0.3:
            neck_angle = round(_angle_3pt(ear_pt, sho_pt, hip_pt), 1)
        if lms[23 if side=="left" else 24].visibility > 0.3:
            back_angle = round(_angle_3pt(sho_pt, hip_pt, knee_pt), 1)

    except Exception:
        pass

    return annotated, neck_angle, back_angle


# ── Core detection (multi-person) ─────────────────────────────────────────────
def predict_and_annotate(frame_bgr, conf=0.5):
    """
    Detects ALL persons in the frame (multi-person support).
    Returns (annotated_frame, summary_label, is_good, metrics_list)
    where metrics_list is a list of dicts per person.
    """
    if model is None:
        return frame_bgr, "Model not loaded", False, []

    results = model.predict(frame_bgr, conf=conf, verbose=False)[0]
    annotated = frame_bgr.copy()

    if not results.boxes or len(results.boxes) == 0:
        return annotated, "No detection", False, []

    raw_detections = []
    for box in results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        raw_detections.append({
            "cls":        int(box.cls),
            "confidence": float(box.conf),
            "box":        (x1, y1, x2, y2),
        })

    detections = _dedupe_detections(raw_detections)
    metrics_list = []

    for det in detections:
        cls        = det["cls"]
        confidence = det["confidence"]
        x1, y1, x2, y2 = det["box"]

        is_good    = cls == 1
        label_text = f"{'Good' if is_good else 'Bad'} ({confidence:.0%})"
        color      = (0, 200, 0) if is_good else (0, 0, 220)

        # ── YOLO bounding box ──────────────────────────────────────────────
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)

        # ── MediaPipe skeleton + angles ────────────────────────────────────
        annotated, neck_angle, back_angle = run_mediapipe(annotated, x1, y1, x2, y2)

        # ── Angle overlays on frame ────────────────────────────────────────
        overlay_y = max(y1 - 14, 20)
        cv2.putText(annotated, label_text,
                    (x1, overlay_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 2, cv2.LINE_AA)

        if neck_angle is not None:
            cv2.putText(annotated, f"Neck:{neck_angle:.0f}°",
                        (x1, overlay_y + 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
        if back_angle is not None:
            cv2.putText(annotated, f"Back:{back_angle:.0f}°",
                        (x1, overlay_y + 42),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)

        metrics_list.append({
            "is_good":    is_good,
            "confidence": round(confidence, 3),
            "label":      label_text,
            "neck_angle": neck_angle,
            "back_angle": back_angle,
        })

    # ── Summary label (worst-case logic: any bad = bad) ────────────────────
    n_total = len(metrics_list)
    n_bad   = sum(1 for m in metrics_list if not m["is_good"])
    n_good  = n_total - n_bad

    if n_bad > 0:
        if n_bad == n_total:
            summary = f"Bad Posture — {n_bad} person{'s' if n_bad > 1 else ''} detected"
        else:
            summary = f"Bad Posture — {n_bad} of {n_total} person{'s' if n_total > 1 else ''} detected"
        is_good = False
    else:
        summary = f"Good Posture — {n_good} person{'s' if n_good > 1 else ''} detected"
        is_good = True

    return annotated, summary, is_good, metrics_list


# ── Video processing with posture timeline ────────────────────────────────────
def process_video_file(tmp_path, output_path, conf_threshold):
    logger.info(f"[Video Process] Starting processing of {tmp_path}")

    cap = cv2.VideoCapture(tmp_path, cv2.CAP_FFMPEG)
    if not cap.isOpened():
        logger.error(f"[Video Process] Failed to open video file {tmp_path}")
        return []

    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps          = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps
    logger.info(f"[Video Process] {width}x{height} @ {fps}fps, {total_frames} frames")

    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out    = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    if not out.isOpened():
        logger.error(f"[Video Process] Failed to initialize VideoWriter")
        cap.release()
        return []

    step = max(1, int(fps // 4))  # analyse ~4 fps

    # Per-second timeline accumulator: list of bool (True = good)
    timeline_seconds = []
    sec_good_count   = 0
    sec_total_count  = 0
    current_sec      = 0

    frames_processed  = 0
    frame_idx         = 0
    start_time        = time.time()
    last_annotated    = None
    last_is_good      = True

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_sec = int(frame_idx / fps)

        # New second boundary
        if frame_sec > current_sec:
            if sec_total_count > 0:
                timeline_seconds.append(sec_good_count / sec_total_count >= 0.5)
            current_sec    = frame_sec
            sec_good_count  = 0
            sec_total_count = 0

        # Run YOLO on every Nth frame
        if frame_idx % step == 0 or last_annotated is None:
            annotated, _, is_good, _ = predict_and_annotate(frame, conf=conf_threshold)
            last_annotated = annotated
            last_is_good   = is_good

        sec_good_count  += int(last_is_good)
        sec_total_count += 1

        out.write(last_annotated)
        frames_processed += 1
        frame_idx        += 1

        if frames_processed % 50 == 0:
            logger.info(f"[Video Process] {frames_processed}/{total_frames} frames...")

    # Flush last partial second
    if sec_total_count > 0:
        timeline_seconds.append(sec_good_count / sec_total_count >= 0.5)

    cap.release()
    out.release()
    elapsed = time.time() - start_time
    logger.info(f"[Video Process] Done in {elapsed:.2f}s → {output_path}")
    logger.info(f"[Video Process] Timeline: {timeline_seconds}")
    return timeline_seconds


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.post("/api/predict/image")
async def predict_image(file: UploadFile = File(...), conf_threshold: float = Form(0.35)):
    logger.info(f"[Image] {file.filename}")
    contents   = await file.read()
    img        = Image.open(io.BytesIO(contents)).convert("RGB")
    frame_bgr  = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    annotated, label, is_good, metrics_list = await asyncio.to_thread(
        predict_and_annotate, frame_bgr, conf_threshold
    )

    _, buffer  = cv2.imencode('.jpg', annotated)
    img_b64    = base64.b64encode(buffer).decode('utf-8')

    # Aggregate angle info for the first detected person (for UI display)
    neck_angle = metrics_list[0]["neck_angle"] if metrics_list else None
    back_angle = metrics_list[0]["back_angle"] if metrics_list else None

    return {
        "image":      f"data:image/jpeg;base64,{img_b64}",
        "label":      label,
        "is_good":    is_good,
        "neck_angle": neck_angle,
        "back_angle": back_angle,
        "metrics":    metrics_list,
    }


@app.post("/api/predict/video")
async def predict_video(file: UploadFile = File(...), conf_threshold: float = Form(0.35)):
    logger.info(f"[Video] {file.filename}")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    output_filename = f"{uuid.uuid4().hex}.mp4"
    output_path     = os.path.join("temp_videos", output_filename)

    try:
        timeline = await asyncio.to_thread(
            process_video_file, tmp_path, output_path, conf_threshold
        )
    except Exception as e:
        logger.exception("[Video] Error during processing")
        raise e
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    url = f"http://127.0.0.1:8000/videos/{output_filename}"
    logger.info(f"[Video] URL: {url}")
    return {
        "video_url":   url,
        "filename":    output_filename,
        "timeline":    timeline,           # list of bool per second
    }


@app.websocket("/api/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    client = websocket.client
    logger.info(f"[Webcam] Connected: {client}")
    try:
        frame_idx = 0
        while True:
            data = await websocket.receive_text()
            if data.startswith("data:image"):
                header, encoded = data.split(",", 1)
                img_bytes = base64.b64decode(encoded)
                nparr     = np.frombuffer(img_bytes, np.uint8)
                frame     = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                annotated, label, is_good, metrics = await asyncio.to_thread(
                    predict_and_annotate, frame, 0.35
                )

                _, buffer = cv2.imencode('.jpg', annotated)
                out_b64   = base64.b64encode(buffer).decode('utf-8')

                neck_angle = metrics[0]["neck_angle"] if metrics else None
                back_angle = metrics[0]["back_angle"] if metrics else None

                await websocket.send_json({
                    "image":      f"data:image/jpeg;base64,{out_b64}",
                    "label":      label,
                    "is_good":    is_good,
                    "neck_angle": neck_angle,
                    "back_angle": back_angle,
                    "metrics":    metrics,
                })
                frame_idx += 1
                if frame_idx % 100 == 0:
                    logger.info(f"[Webcam] {frame_idx} frames for {client}")
    except WebSocketDisconnect:
        logger.info(f"[Webcam] {client} disconnected.")
    except Exception as e:
        logger.exception(f"[Webcam] Error: {e}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)