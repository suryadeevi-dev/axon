.PHONY: help backend frontend setup

help:
	@echo "AXON — local development"
	@echo ""
	@echo "  make setup     Install all dependencies"
	@echo "  make backend   Start FastAPI backend (localhost:8000)"
	@echo "  make frontend  Start Next.js frontend (localhost:3000)"

setup:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && uvicorn main:app --reload --port 8000

frontend:
	cd frontend && npm run dev
