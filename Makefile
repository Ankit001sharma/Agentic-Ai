.PHONY: up down logs seed demo test backend-dev frontend-dev

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f backend

seed:
	docker compose exec backend python -m infra.seed_jailbreaks

demo:
	@echo "Open http://localhost:3000/sandbox"

test:
	docker compose exec backend pytest -q

backend-dev:
	cd backend && uv sync && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd frontend && pnpm install && pnpm dev
