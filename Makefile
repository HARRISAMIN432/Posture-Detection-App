.PHONY: install-backend backend frontend run clean

install-backend:
	cd backend && pip install -r requirements.txt

backend:
	start cmd /k "cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

frontend:
	start cmd /k "cd frontend && npm run dev"

run:
	@echo Starting Posture Detection App...
	@echo Installing backend dependencies...
	$(MAKE) install-backend
	@echo Starting FastAPI Backend...
	$(MAKE) backend
	@echo Starting Vite Frontend...
	$(MAKE) frontend
	@echo Both servers are starting!
	@echo Backend: http://localhost:8000
	@echo Frontend: http://localhost:5173

clean:
	@echo Nothing to clean yet