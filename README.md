# Tool Support Agent

The Tool Support Agent is a demo that introduces LangGraph orchestration and LangSmith traceability through a concrete support workflow.

The right panel is a deliberately broken time-series plotter. Its data file is pipe-delimited, while the initial pandas configuration expects commas. The left panel streams a support triage run, highlights each active LangGraph node, and returns a specific remediation. Applying that remediation makes the chart render.

## Architecture

```text
Browser
  └─ Streamlit :8501 (interactive HTML component)
       └─ FastAPI :8000 (SSE + plotter API)
            ├─ LangGraph support workflow
            │    ├─ coordinator_agent
            │    ├─ review_agent
            │    └─ inspect_plotter_tool
            ├─ OpenAI response generation (optional)
            └─ LangSmith tracing (optional)
```

The demo remains usable without credentials to function offline. With `OPENAI_API_KEY`, the final response node uses OpenAI and its tokens stream through LangGraph. With the LangSmith variables, the graph and named coordinator/review/tool spans are traced.

## Run locally with uv

Prerequisites: WSL, Python 3.11+, and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
uv sync
```

Optionally add your OpenAI and LangSmith keys to `.env`. Then run these in separate WSL terminals:

```bash
uv run uvicorn app.backend.main:app --reload --port 8000
```

```bash
uv run streamlit run app/frontend/streamlit_app.py --server.port 8501
```

Open [http://localhost:8501](http://localhost:8501). The API reference is at [http://localhost:8000/docs](http://localhost:8000/docs).

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

Then open [http://localhost:8501](http://localhost:8501). Both published ports must remain available.

## Verify

```bash
uv run pytest -q
```

Click **Reset demo** in the UI or call `POST /plotter/reset` to restore the failure.
