import { useState, useRef } from 'react';
import { Film, Upload, Activity } from 'lucide-react';

export default function VideoProcessor() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setVideoUrl(null);
    }
  };

  const processVideo = async () => {
    if (!selectedFile) return;
    setLoading(true);
    setVideoUrl(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('conf_threshold', '0.5');

    try {
      const response = await fetch('http://localhost:8000/api/predict/video', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Failed to process video');

      const data = await response.json();
      setVideoUrl(data.video_url);
    } catch (err) {
      console.error(err);
      alert('Error processing video. It might be too large or the backend is not running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div 
        className="upload-area"
        onClick={() => fileInputRef.current?.click()}
      >
        <Film size={48} color="var(--primary)" style={{ marginBottom: '1rem' }} />
        <h3>Click or Drag Video to Upload</h3>
        <p>Supports MP4, AVI, MOV (Keep it short for quick processing!)</p>
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleFileChange} 
          accept="video/*" 
          style={{ display: 'none' }} 
        />
      </div>

      {selectedFile && !videoUrl && (
        <div style={{ marginTop: '2rem', textAlign: 'center' }}>
          <p>Selected: <strong>{selectedFile.name}</strong></p>
          <div style={{ marginTop: '1.5rem' }}>
            <button className="btn" onClick={processVideo} disabled={loading}>
              <Activity size={18} className={loading ? 'loading' : ''} />
              {loading ? 'Processing Video (This might take a while)...' : 'Analyze Video'}
            </button>
          </div>
        </div>
      )}

      {videoUrl && (
        <div style={{ marginTop: '2rem', textAlign: 'center' }}>
          <h3>Analysis Complete!</h3>
          <div className="preview-container">
            <video src={videoUrl} controls autoPlay loop style={{ width: '100%', borderRadius: '1rem' }} />
          </div>
          <div style={{ marginTop: '1.5rem' }}>
             <button className="btn" onClick={() => {setVideoUrl(null); setSelectedFile(null);}}>
                Upload Another Video
             </button>
          </div>
        </div>
      )}
    </div>
  );
}
