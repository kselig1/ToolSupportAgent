.PHONY: install api ui test demo

install:
	uv sync

api:
	uv run uvicorn app.backend.main:app --reload --port 8000

ui:
	uv run streamlit run app/frontend/streamlit_app.py --server.port 8501

test:
	uv run pytest -q

demo:
	docker compose up --build

