@echo off
echo Starting Posture Detection App...

echo Installing backend dependencies...
cd backend
pip install -r requirements.txt
cd ..

echo Starting FastAPI Backend...
start cmd /k "cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

echo Starting Vite Frontend...
start cmd /k "cd frontend && npm run dev"

echo Both servers are starting up! Backend on http://localhost:8000 and Frontend on http://localhost:5173
