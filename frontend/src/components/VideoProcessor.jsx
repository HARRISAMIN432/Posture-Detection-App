import { useState, useRef } from 'react';
import { Film, Upload, Activity } from 'lucide-react';

export default function VideoProcessor() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    console.log('[VideoProcessor] handleFileChange triggered');
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      console.log('[VideoProcessor] File selected:', file.name, 'Size:', file.size, 'Type:', file.type);
      setSelectedFile(file);
      setVideoUrl(null);
    } else {
      console.log('[VideoProcessor] No file selected');
    }
  };

  const processVideo = async () => {
    console.log('[VideoProcessor] processVideo triggered');
    if (!selectedFile) {
      console.warn('[VideoProcessor] processVideo aborted: no selectedFile');
      return;
    }
    setLoading(true);
    setVideoUrl(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('conf_threshold', '0.5');

    console.log('[VideoProcessor] FormData prepared, sending POST to /api/predict/video');

    try {
      console.log('[VideoProcessor] Fetch starting...');
      const response = await fetch('http://127.0.0.1:8000/api/predict/video', {
        method: 'POST',
        body: formData,
      });

      console.log('[VideoProcessor] Fetch returned. Status:', response.status);

      if (!response.ok) {
        throw new Error(`Failed to process video, Status: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      console.log('[VideoProcessor] Received JSON:', data);
      setVideoUrl(data.video_url);
    } catch (err) {
      console.error('[VideoProcessor] Fetch Error caught:', err);
      alert('Error processing video. Check console for details.');
    } finally {
      console.log('[VideoProcessor] Process finished, setting loading=false');
      setLoading(false);
    }
  };

  return (
    <div>
      <div 
        className="upload-area"
        onClick={() => {
          console.log('[VideoProcessor] Upload area clicked');
          fileInputRef.current?.click();
        }}
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
             <button className="btn" onClick={() => {
                 console.log('[VideoProcessor] Resetting state for new video');
                 setVideoUrl(null); 
                 setSelectedFile(null);
             }}>
                Upload Another Video
             </button>
          </div>
        </div>
      )}
    </div>
  );
}
