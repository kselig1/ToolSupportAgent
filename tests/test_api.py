from fastapi.testclient import TestClient

from app.backend.main import app
from app.backend.plotter import plotter


client = TestClient(app)


def test_health_and_graph_contract():
    assert client.get("/health").status_code == 200
    graph = client.get("/graph").json()
    ids = {node["id"] for node in graph["nodes"]}
    assert {"coordinator_agent", "review_agent", "review_agent_tool_node", "return_solution"} <= ids


def test_fix_endpoint_recovers_plotter():
    plotter.reset()
    assert client.get("/plotter").json()["status"] == "error"
    assert client.post("/plotter/fix").json()["status"] == "healthy"
    plotter.reset()

