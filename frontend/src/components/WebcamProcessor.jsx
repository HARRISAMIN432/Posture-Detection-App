import { useState, useRef, useEffect } from 'react';
import { Camera, Square, Clock, AlertTriangle } from 'lucide-react';

export default function WebcamProcessor() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [result, setResult] = useState(null);
  
  // Analytics State
  const [sessionTime, setSessionTime] = useState(0);
  const [goodFrames, setGoodFrames] = useState(0);
  const [totalFrames, setTotalFrames] = useState(0);
  const [badStreak, setBadStreak] = useState(0);
  
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const isStreamingRef = useRef(false);

  useEffect(() => {
    if (isStreaming) {
      console.log('[WebcamProcessor] isStreaming is true, starting session timer');
      timerRef.current = setInterval(() => {
        setSessionTime((prev) => prev + 1);
      }, 1000);
    } else {
      console.log('[WebcamProcessor] isStreaming is false, clearing session timer');
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [isStreaming]);

  const startStream = async () => {
    console.log('[WebcamProcessor] startStream triggered');
    try {
      console.log('[WebcamProcessor] Requesting getUserMedia...');
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      console.log('[WebcamProcessor] getUserMedia successful', stream.id);
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      
      isStreamingRef.current = true;
      setIsStreaming(true);
      setSessionTime(0);
      setGoodFrames(0);
      setTotalFrames(0);
      setBadStreak(0);

      console.log('[WebcamProcessor] Initializing WebSocket...');
      wsRef.current = new WebSocket('ws://127.0.0.1:8000/api/stream');
      
      wsRef.current.onopen = () => {
        console.log('[WebcamProcessor] WebSocket onopen fired');
        sendFrame();
      };

      wsRef.current.onmessage = (event) => {
        // Log minimal info to avoid console flood, just the size
        // console.log('[WebcamProcessor] WebSocket onmessage received, data size:', event.data.length);
        const data = JSON.parse(event.data);
        setResult(data);
        
        // Update analytics
        setTotalFrames(prev => prev + 1);
        if (data.is_good) {
           setGoodFrames(prev => prev + 1);
           setBadStreak(0);
        } else {
           setBadStreak(prev => prev + 1);
        }

        if (isStreamingRef.current) {
           requestAnimationFrame(sendFrame);
        } else {
           console.log('[WebcamProcessor] WebSocket onmessage - stream stopped, not requesting next frame');
        }
      };

      wsRef.current.onerror = (error) => {
        console.error('[WebcamProcessor] WebSocket onerror fired:', error);
      };

      wsRef.current.onclose = () => {
        console.log('[WebcamProcessor] WebSocket onclose fired');
      };

    } catch (err) {
      console.error('[WebcamProcessor] Error accessing webcam', err);
      alert('Could not access webcam. Please ensure permissions are granted.');
    }
  };

  const stopStream = () => {
    console.log('[WebcamProcessor] stopStream triggered');
    isStreamingRef.current = false;
    setIsStreaming(false);
    setResult(null);

    if (streamRef.current) {
      console.log('[WebcamProcessor] Stopping tracks');
      streamRef.current.getTracks().forEach(track => track.stop());
    }
    if (wsRef.current) {
      console.log('[WebcamProcessor] Closing WebSocket');
      wsRef.current.close();
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  useEffect(() => {
    return () => {
        console.log('[WebcamProcessor] Component unmounting, cleaning up');
        stopStream();
    };
  }, []);

  const sendFrame = () => {
    if (!wsRef.current) {
      console.warn('[WebcamProcessor] sendFrame aborted: wsRef is null');
      return;
    }
    if (wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('[WebcamProcessor] sendFrame aborted: WebSocket state is', wsRef.current.readyState);
      return;
    }
    if (!isStreamingRef.current) {
      console.warn('[WebcamProcessor] sendFrame aborted: isStreamingRef is false');
      return;
    }
    if (!videoRef.current || !canvasRef.current) {
      console.warn('[WebcamProcessor] sendFrame aborted: Missing video or canvas refs');
      return;
    }

    const canvas = canvasRef.current;
    const video = videoRef.current;

    if (video.videoWidth === 0) {
      console.log('[WebcamProcessor] videoWidth is 0, deferring sendFrame');
      requestAnimationFrame(sendFrame);
      return;
    }

    // console.log('[WebcamProcessor] Capturing frame from video');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    const dataUrl = canvas.toDataURL('image/jpeg', 0.6);
    // console.log('[WebcamProcessor] Sending frame dataUrl, size:', dataUrl.length);
    wsRef.current.send(dataUrl);
  };

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const scorePercentage = totalFrames > 0 ? Math.round((goodFrames / totalFrames) * 100) : 100;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <p style={{ margin: 0, color: 'var(--text-muted)' }}>Live Analytics Dashboard</p>
        {!isStreaming ? (
          <button className="btn" onClick={startStream}>
            <Camera size={18} /> Start Webcam
          </button>
        ) : (
          <button className="btn" style={{ background: 'var(--danger)' }} onClick={stopStream}>
            <Square size={18} fill="currentColor" /> Stop Webcam
          </button>
        )}
      </div>

      {isStreaming && (
        <div className="analytics-panel">
          <div className="stat-box">
            <Clock size={24} color="var(--primary)" />
            <div className="stat-value">{formatTime(sessionTime)}</div>
            <div className="stat-label">Session Time</div>
          </div>
          <div className="stat-box">
            <div className="progress-circle" style={{ '--percent': scorePercentage }}>
              <span>{scorePercentage}%</span>
            </div>
            <div className="stat-label">Posture Score</div>
          </div>
        </div>
      )}

      {badStreak > 15 && (
        <div className="alert-popup">
          <AlertTriangle size={24} color="#f59e0b" />
          <span>Straighten your back! You've been slouching.</span>
        </div>
      )}

      <div style={{ marginTop: '2rem', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <canvas ref={canvasRef} style={{ display: 'none' }} />
        <video ref={videoRef} autoPlay playsInline muted style={{ display: 'none' }} />

        <div className="preview-container">
          {result?.image ? (
            <img src={result.image} alt="Annotated Feed" />
          ) : (
             <div style={{ padding: '4rem', color: 'var(--text-muted)', border: '2px dashed var(--border)', borderRadius: '1rem' }}>
                {isStreaming ? 'Connecting to inference engine...' : 'Camera is offline'}
             </div>
          )}
        </div>

        {result && (
          <div className={`status-banner ${result.is_good ? 'status-good' : 'status-bad'}`}>
            {result.is_good ? '✔' : '✘'} {result.label}
          </div>
        )}
      </div>
    </div>
  );
}
