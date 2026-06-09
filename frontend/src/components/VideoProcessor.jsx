import { useState, useRef } from "react";
import {
  Film,
  Upload,
  Activity,
  Download,
  CheckCircle,
  XCircle,
  Clock,
} from "lucide-react";

// ── Posture Timeline Heatmap ──────────────────────────────────────────────────
function PostureTimeline({ timeline }) {
  if (!timeline || timeline.length === 0) return null;

  const goodCount = timeline.filter(Boolean).length;
  const pct = Math.round((goodCount / timeline.length) * 100);

  return (
    <div
      style={{
        marginTop: "2rem",
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: "1rem",
        padding: "1.5rem",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Clock size={18} color="var(--primary)" />
          <span
            style={{
              fontWeight: 700,
              fontSize: "1rem",
              color: "var(--text-main)",
            }}
          >
            Posture Timeline
          </span>
        </div>
        <span
          style={{
            fontWeight: 700,
            fontSize: "0.95rem",
            color: pct >= 60 ? "#34d399" : "#f87171",
          }}
        >
          {pct}% Good Posture
        </span>
      </div>

      {/* Heatmap bar */}
      <div
        style={{
          display: "flex",
          height: "28px",
          borderRadius: "6px",
          overflow: "hidden",
          gap: "1px",
          background: "rgba(0,0,0,0.3)",
        }}
      >
        {timeline.map((isGood, i) => (
          <div
            key={i}
            title={`${i}s – ${i + 1}s: ${isGood ? "Good" : "Bad"} Posture`}
            style={{
              flex: 1,
              background: isGood
                ? "rgba(52, 211, 153, 0.85)"
                : "rgba(248, 113, 113, 0.85)",
              transition: "opacity 0.15s",
              cursor: "default",
              minWidth: "2px",
            }}
          />
        ))}
      </div>

      {/* Legend + second labels */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginTop: "0.6rem",
        }}
      >
        <div style={{ display: "flex", gap: "1.2rem" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              fontSize: "0.8rem",
              color: "var(--text-muted)",
            }}
          >
            <span
              style={{
                width: 12,
                height: 12,
                background: "rgba(52,211,153,0.85)",
                borderRadius: 2,
                display: "inline-block",
              }}
            />
            Good Posture
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              fontSize: "0.8rem",
              color: "var(--text-muted)",
            }}
          >
            <span
              style={{
                width: 12,
                height: 12,
                background: "rgba(248,113,113,0.85)",
                borderRadius: 2,
                display: "inline-block",
              }}
            />
            Bad Posture
          </div>
        </div>
        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
          {timeline.length}s total
        </span>
      </div>

      {/* Summary pills */}
      <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
        <div
          style={{
            flex: 1,
            background: "rgba(52,211,153,0.08)",
            border: "1px solid rgba(52,211,153,0.2)",
            borderRadius: "0.75rem",
            padding: "0.75rem",
            textAlign: "center",
          }}
        >
          <CheckCircle size={18} color="#34d399" style={{ marginBottom: 4 }} />
          <div
            style={{ fontWeight: 700, fontSize: "1.2rem", color: "#34d399" }}
          >
            {goodCount}s
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Good posture
          </div>
        </div>
        <div
          style={{
            flex: 1,
            background: "rgba(248,113,113,0.08)",
            border: "1px solid rgba(248,113,113,0.2)",
            borderRadius: "0.75rem",
            padding: "0.75rem",
            textAlign: "center",
          }}
        >
          <XCircle size={18} color="#f87171" style={{ marginBottom: 4 }} />
          <div
            style={{ fontWeight: 700, fontSize: "1.2rem", color: "#f87171" }}
          >
            {timeline.length - goodCount}s
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Bad posture
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────
export default function VideoProcessor() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [filename, setFilename] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setVideoUrl(null);
      setTimeline([]);
      setFilename(null);
    }
  };

  const processVideo = async () => {
    if (!selectedFile) return;
    setLoading(true);
    setVideoUrl(null);
    setTimeline([]);

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("conf_threshold", "0.35");

    try {
      const response = await fetch("http://127.0.0.1:8000/api/predict/video", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) throw new Error(`Status ${response.status}`);

      const data = await response.json();
      setVideoUrl(data.video_url);
      setFilename(data.filename || "annotated_video.mp4");
      setTimeline(data.timeline || []);
    } catch (err) {
      console.error("[VideoProcessor]", err);
      alert("Error processing video. Make sure the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  // ── Direct download of the processed MP4 from the backend ─────────────────
  const handleDownload = async () => {
    if (!videoUrl) return;
    try {
      const res = await fetch(videoUrl);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || "posture_analysis.mp4";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // fallback: open in new tab
      window.open(videoUrl, "_blank");
    }
  };

  const reset = () => {
    setVideoUrl(null);
    setSelectedFile(null);
    setTimeline([]);
    setFilename(null);
  };

  // ── Summary stats for timeline ─────────────────────────────────────────────
  const goodPct = timeline.length
    ? Math.round((timeline.filter(Boolean).length / timeline.length) * 100)
    : null;

  return (
    <div>
      {/* ── Upload area ───────────────────────────────────────────────────── */}
      {!videoUrl && (
        <>
          <div
            className="upload-area"
            onClick={() => fileInputRef.current?.click()}
          >
            <Film
              size={48}
              color="var(--primary)"
              style={{ marginBottom: "1rem" }}
            />
            <h3>Click or Drag Video to Upload</h3>
            <p>Supports MP4, AVI, MOV — keep it short for quick processing!</p>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept="video/*"
              style={{ display: "none" }}
            />
          </div>

          {selectedFile && (
            <div style={{ marginTop: "2rem", textAlign: "center" }}>
              <p>
                Selected:{" "}
                <strong style={{ color: "var(--text-main)" }}>
                  {selectedFile.name}
                </strong>
              </p>
              <button
                className="btn"
                onClick={processVideo}
                disabled={loading}
                style={{ marginTop: "1rem" }}
              >
                <Activity size={18} className={loading ? "loading" : ""} />
                {loading
                  ? "Processing… (this may take a while)"
                  : "Analyse Posture"}
              </button>
            </div>
          )}
        </>
      )}

      {/* ── Results ───────────────────────────────────────────────────────── */}
      {videoUrl && (
        <div style={{ marginTop: "1.5rem" }}>
          {/* ── Score badge ─────────────────────────────────────────────── */}
          {goodPct !== null && (
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                marginBottom: "1.25rem",
              }}
            >
              <div
                style={{
                  background:
                    goodPct >= 60
                      ? "rgba(52,211,153,0.1)"
                      : "rgba(248,113,113,0.1)",
                  border: `1px solid ${goodPct >= 60 ? "rgba(52,211,153,0.3)" : "rgba(248,113,113,0.3)"}`,
                  borderRadius: "2rem",
                  padding: "0.5rem 1.5rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.6rem",
                  fontWeight: 700,
                  fontSize: "1rem",
                  color: goodPct >= 60 ? "#34d399" : "#f87171",
                }}
              >
                {goodPct >= 60 ? (
                  <CheckCircle size={18} />
                ) : (
                  <XCircle size={18} />
                )}
                Overall posture score: {goodPct}%
              </div>
            </div>
          )}

          {/* ── Video player ─────────────────────────────────────────────── */}
          <div className="preview-container">
            <video
              src={videoUrl}
              controls
              autoPlay
              loop
              style={{ width: "100%", borderRadius: "1rem" }}
            />
          </div>

          {/* ── Action buttons ───────────────────────────────────────────── */}
          <div
            style={{
              display: "flex",
              gap: "1rem",
              marginTop: "1.5rem",
              justifyContent: "center",
              flexWrap: "wrap",
            }}
          >
            {/* DOWNLOAD BUTTON (Feature 4) */}
            <button
              className="btn"
              onClick={handleDownload}
              style={{
                background: "var(--accent)",
                minWidth: "200px",
                justifyContent: "center",
              }}
            >
              <Download size={18} />
              Download Annotated Video
            </button>

            <button
              className="btn"
              onClick={reset}
              style={{
                background: "transparent",
                border: "1px solid var(--border)",
                color: "var(--text-muted)",
                minWidth: "180px",
                justifyContent: "center",
              }}
            >
              <Upload size={18} />
              Upload Another Video
            </button>
          </div>

          {/* ── Posture Heatmap Timeline (Feature 6) ─────────────────────── */}
          <PostureTimeline timeline={timeline} />
        </div>
      )}
    </div>
  );
}
