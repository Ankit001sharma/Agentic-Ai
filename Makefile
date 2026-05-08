.PHONY: up down logs seed demo test backend-dev

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f backend

seed:
	docker compose exec backend python -m infra.seed_jailbreaks

demo:
	@echo "Gateway: curl http://localhost:8080/health"

test:
	docker compose exec backend pytest -q

backend-dev:
	cd backend && uv sync && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

frontend-dev:
	cd frontend && npm run dev

frontend-ci:
	cd frontend && npm ci && npm run lint && npm run typecheck && npm run build
