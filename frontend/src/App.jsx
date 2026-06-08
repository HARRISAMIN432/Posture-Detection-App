import { useState } from 'react';
import { Camera, Image as ImageIcon, Film } from 'lucide-react';
import ImageProcessor from './components/ImageProcessor';
import WebcamProcessor from './components/WebcamProcessor';
import VideoProcessor from './components/VideoProcessor';

function App() {
  const [activeTab, setActiveTab] = useState('image');

  return (
    <>
      <header style={{ textAlign: 'center', marginBottom: '2rem' }}>
        <h1>Posture Analysis</h1>
        <p>Advanced real-time AI posture detection</p>
      </header>

      <main className="card">
        <div className="tabs">
          <button 
            className={`tab-btn ${activeTab === 'image' ? 'active' : ''}`}
            onClick={() => setActiveTab('image')}
          >
            <ImageIcon size={20} />
            Image
          </button>
          <button 
            className={`tab-btn ${activeTab === 'video' ? 'active' : ''}`}
            onClick={() => setActiveTab('video')}
          >
            <Film size={20} />
            Video
          </button>
          <button 
            className={`tab-btn ${activeTab === 'webcam' ? 'active' : ''}`}
            onClick={() => setActiveTab('webcam')}
          >
            <Camera size={20} />
            Live Analytics
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'image' && <ImageProcessor />}
          {activeTab === 'video' && <VideoProcessor />}
          {activeTab === 'webcam' && <WebcamProcessor />}
        </div>
      </main>
    </>
  );
}

export default App;
