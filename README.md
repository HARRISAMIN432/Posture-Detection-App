# Ergonomics & Posture Alert System

## Folder Structure

```
posture-app/
│
├── backend/
│   ├── app.py                  # Flask API
│   ├── requirements.txt        # Python deps
│   ├── best.pt                 # ← PUT YOUR MODEL HERE (downloaded from Drive)
│   ├── uploads/                # Temp uploaded files (auto-created)
│   └── outputs/                # Annotated results (auto-created)
│
└── frontend/
    ├── public/
    │   └── index.html
    ├── src/
    │   ├── components/
    │   │   ├── Layout.js       # Sidebar + nav
    │   │   └── AlertBadge.js   # Reusable alert level badge
    │   ├── pages/
    │   │   ├── Dashboard.js    # Home / overview
    │   │   ├── ImageDetect.js  # Image upload + detection
    │   │   ├── VideoDetect.js  # Video / CCTV processing
    │   │   └── ModelStatus.js  # Model health check
    │   ├── App.js              # Router
    │   ├── index.js            # Entry point
    │   └── index.css           # Global styles
    ├── package.json
    └── .env                    # REACT_APP_API_URL if needed
```

## Setup

### Step 1 — Copy model from Drive to backend
Download `best.pt` from Google Drive and place it at:
```
posture-app/backend/best.pt
```

### Step 2 — Backend
```bash
cd backend
pip install -r requirements.txt
python app.py
# Runs on http://localhost:5000
```

### Step 3 — Frontend
```bash
cd frontend
npm install
npm start
# Runs on http://localhost:3000
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/health | Model status + classes |
| POST | /api/detect/image | Detect posture in image |
| POST | /api/detect/video | Start async video processing |
| GET | /api/detect/video/status/:id | Poll video job progress |
| GET | /api/output/:filename | Serve result file |

## Features
- Image detection with bounding boxes + confidence
- Video/CCTV processing with frame-by-frame analysis
- Real-time progress bar for video jobs
- Good / Warning / Critical alert levels
- Pie chart of bad vs good frames in video
- Download annotated output
- Model health status page
