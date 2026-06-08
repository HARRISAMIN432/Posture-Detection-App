import { useState, useRef } from 'react';
import { Upload, Activity, Award, AlertCircle, Info } from 'lucide-react';

export default function ImageProcessor() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setResult(null);
    }
  };

  const processImage = async () => {
    if (!selectedFile) return;
    setLoading(true);
    setResult(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('conf_threshold', '0.5');

    try {
      const response = await fetch('http://localhost:8000/api/predict/image', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Failed to process image');

      const data = await response.json();
      setResult(data);
    } catch (err) {
      console.error(err);
      alert('Error processing image. Make sure backend is running.');
    } finally {
      setLoading(false);
    }
  };

  // Helper to parse confidence percentage and get comments
  const getFeedback = (label, isGood) => {
    if (!label || label === "No detection") {
      return {
        percentage: null,
        title: "No Detection",
        text: "We couldn't detect a clear posture profile. Please upload a clear side-view or full-body photo where your back and neck are visible.",
        color: "var(--text-muted)",
        icon: <Info size={24} />
      };
    }

    const match = label.match(/(\d+)%/);
    const pct = match ? parseInt(match[1]) : 70; // default to 70 if not parsed

    if (isGood) {
      if (pct >= 85) {
        return {
          percentage: pct,
          title: "Excellent Alignment",
          text: "Fantastic posture! Your spine and neck are in optimal alignment. Keep maintaining this neutral position to minimize muscular stress and fatigue.",
          color: "#10b981",
          icon: <Award size={24} color="#10b981" />
        };
      } else if (pct >= 70) {
        return {
          percentage: pct,
          title: "Good Posture",
          text: "Your alignment is generally good. Try to slightly pull your shoulders back and keep your head aligned over your spine to make it perfect.",
          color: "#34d399",
          icon: <Award size={24} color="#34d399" />
        };
      } else {
        return {
          percentage: pct,
          title: "Fair Posture",
          text: "You are currently in a good posture range, but sitting near the limit. Try stretching your neck muscles and sitting slightly more upright.",
          color: "#60a5fa",
          icon: <Info size={24} color="#60a5fa" />
        };
      }
    } else {
      if (pct >= 80) {
        return {
          percentage: pct,
          title: "Severe Slouching",
          text: "Critical poor posture detected. Your spine is heavily curved. Pull your shoulders back, raise your chest, and adjust your workspace screen to eye level immediately.",
          color: "#ef4444",
          icon: <AlertCircle size={24} color="#ef4444" />
        };
      } else if (pct >= 50) {
        return {
          percentage: pct,
          title: "Moderate Slouching",
          text: "Poor posture detected. You are leaning forward or hunching. Take a deep breath, sit all the way back in your chair, and keep your feet flat on the floor.",
          color: "#f87171",
          icon: <AlertCircle size={24} color="#f87171" />
        };
      } else {
        return {
          percentage: pct,
          title: "Mild Poor Posture",
          text: "Slight deviation from correct posture. A quick posture check and reset will help prevent muscle tension from building up.",
          color: "#fb923c",
          icon: <Info size={24} color="#fb923c" />
        };
      }
    }
  };

  const feedback = result ? getFeedback(result.label, result.is_good) : null;

  return (
    <div>
      <div 
        className="upload-area"
        onClick={() => fileInputRef.current?.click()}
      >
        <Upload size={48} color="var(--primary)" style={{ marginBottom: '1rem' }} />
        <h3>Click or Drag Image to Upload</h3>
        <p>Supports JPG, PNG, WEBP</p>
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleFileChange} 
          accept="image/*" 
          style={{ display: 'none' }} 
        />
      </div>

      {previewUrl && (
        <div style={{ marginTop: '2rem' }}>
          {!result ? (
            <div style={{ textAlign: 'center' }}>
              <div className="preview-container-square" style={{ maxWidth: '400px', margin: '0 auto' }}>
                <img src={previewUrl} alt="Preview" />
              </div>
              <div style={{ marginTop: '1.5rem' }}>
                <button className="btn" onClick={processImage} disabled={loading}>
                  <Activity size={18} className={loading ? 'loading' : ''} />
                  {loading ? 'Processing...' : 'Analyze Posture'}
                </button>
              </div>
            </div>
          ) : (
            <div className="image-analysis-layout">
              <div className="analysis-left">
                <div className="preview-container-square">
                  <img src={result.image} alt="Analyzed Result" />
                </div>
              </div>
              
              <div className="analysis-right">
                <div className="feedback-card">
                  <div className="feedback-header">
                    {feedback.icon}
                    <h3 style={{ margin: 0, color: feedback.color }}>{feedback.title}</h3>
                  </div>
                  {feedback.percentage && (
                    <div className="feedback-pct" style={{ color: feedback.color }}>
                      Confidence Score: {feedback.percentage}%
                    </div>
                  )}
                  <p className="feedback-text">{feedback.text}</p>
                  
                  <div className={`status-banner ${result.is_good ? 'status-good' : 'status-bad'}`} style={{ marginTop: '1.5rem' }}>
                    {result.is_good ? '✔' : '✘'} {result.label}
                  </div>

                  <button 
                    className="btn" 
                    style={{ marginTop: '1.5rem', width: '100%', justifyContent: 'center' }} 
                    onClick={() => { setResult(null); setSelectedFile(null); setPreviewUrl(null); }}
                  >
                    Analyze New Image
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
