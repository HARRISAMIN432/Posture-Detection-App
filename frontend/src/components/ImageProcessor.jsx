import { useState, useRef } from 'react';
import { Upload, Activity } from 'lucide-react';

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
        <div style={{ marginTop: '2rem', textAlign: 'center' }}>
          <div className="preview-container">
            <img src={result?.image || previewUrl} alt="Preview" />
          </div>
          
          <div style={{ marginTop: '1.5rem' }}>
            <button className="btn" onClick={processImage} disabled={loading}>
              <Activity size={18} className={loading ? 'loading' : ''} />
              {loading ? 'Processing...' : 'Analyze Posture'}
            </button>
          </div>

          {result && (
            <div className={`status-banner ${result.is_good ? 'status-good' : 'status-bad'}`}>
              {result.is_good ? '✔' : '✘'} {result.label}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
