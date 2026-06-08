import streamlit as st
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import time

st.set_page_config(page_title="Posture Detector", layout="centered")

st.title("🧍 Posture Detection")
st.markdown("Upload an image, video, or use your webcam to detect posture quality.")

@st.cache_resource
def load_model(path):
    from ultralytics import YOLO
    return YOLO(path)

model_path = st.sidebar.text_input("Model path (.pt)", value="./best.pt")

model = None
if os.path.exists(model_path):
    model = load_model(model_path)
    st.sidebar.success("✅ Model loaded")
else:
    st.sidebar.warning("⚠️ Model file not found. Enter a valid path.")

conf_threshold = st.sidebar.slider("Confidence threshold", 0.1, 1.0, 0.5, 0.05)

# ── Helper ───────────────────────────────────────────────────────────────────
def predict_and_annotate(frame_bgr, model, conf):
    results = model.predict(frame_bgr, conf=conf, verbose=False)[0]
    annotated = frame_bgr.copy()

    label_text = "No detection"
    color = (128, 128, 128)

    if results.boxes and len(results.boxes):
        # Pick highest-confidence box
        best = max(results.boxes, key=lambda b: float(b.conf))
        cls = int(best.cls)
        confidence = float(best.conf)
        x1, y1, x2, y2 = map(int, best.xyxy[0])

        is_good = cls == 1
        label_text = f"{'✔ Good Posture' if is_good else '✘ Bad Posture'} ({confidence:.0%})"
        color = (0, 200, 0) if is_good else (0, 0, 220)

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)
        cv2.putText(annotated, label_text, (x1, max(y1 - 12, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)

    return cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), label_text, color

def status_banner(label, color_bgr):
    is_good = "Good" in label
    bg = "#d4edda" if is_good else "#f8d7da"
    fg = "#155724" if is_good else "#721c24"
    icon = "✅" if is_good else "❌"
    st.markdown(
        f"<div style='background:{bg};color:{fg};padding:14px 20px;"
        f"border-radius:10px;font-size:1.2rem;font-weight:600;text-align:center'>"
        f"{icon} {label}</div>",
        unsafe_allow_html=True,
    )

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📷 Image", "🎬 Video", "📹 Webcam"])

# ── IMAGE ─────────────────────────────────────────────────────────────────────
with tab1:
    uploaded = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png", "bmp", "webp"])
    if uploaded and model:
        img = Image.open(uploaded).convert("RGB")
        frame_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        annotated_rgb, label, color = predict_and_annotate(frame_bgr, model, conf_threshold)
        st.image(annotated_rgb, use_container_width=True)
        status_banner(label, color)
    elif uploaded and not model:
        st.error("Please load a model first.")

# ── VIDEO ─────────────────────────────────────────────────────────────────────
with tab2:
    video_file = st.file_uploader("Upload a video", type=["mp4", "avi", "mov", "mkv"])
    if video_file and model:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(video_file.read())
            tmp_path = tmp.name

        cap = cv2.VideoCapture(tmp_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps   = cap.get(cv2.CAP_PROP_FPS) or 30
        step  = max(1, int(fps // 4))   # process ~4 frames/sec

        stframe   = st.empty()
        status_ph = st.empty()
        prog      = st.progress(0)

        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1
            if frame_idx % step != 0:
                continue

            ann_rgb, label, color = predict_and_annotate(frame, model, conf_threshold)
            stframe.image(ann_rgb, use_container_width=True)
            with status_ph.container():
                status_banner(label, color)
            if total:
                prog.progress(min(frame_idx / total, 1.0))

        cap.release()
        os.unlink(tmp_path)
        prog.empty()
        st.success("Video processing complete.")
    elif video_file and not model:
        st.error("Please load a model first.")

# ── WEBCAM ────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown("Live webcam inference (runs on the **server** camera).")
    run = st.checkbox("▶ Start webcam")

    stframe   = st.empty()
    status_ph = st.empty()

    if run and model:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            st.error("Could not open webcam. Make sure a camera is connected to the server.")
        else:
            while run:
                ret, frame = cap.read()
                if not ret:
                    break
                ann_rgb, label, color = predict_and_annotate(frame, model, conf_threshold)
                stframe.image(ann_rgb, channels="RGB", use_container_width=True)
                with status_ph.container():
                    status_banner(label, color)
                # Re-read checkbox state each loop
                run = st.session_state.get("run_webcam", True)
                time.sleep(0.03)
            cap.release()
    elif run and not model:
        st.error("Please load a model first.")