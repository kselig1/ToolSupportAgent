from __future__ import annotations

import os
from typing import Literal, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langsmith import traceable

from app.backend.plotter import plotter


class TriageState(TypedDict, total=False):
    question: str
    issue_type: str
    enough_information: bool
    evidence: dict
    diagnosis: str
    confidence: float
    review_attempts: int
    answer: str
    route: str


def emit(node: str, phase: str, detail: str) -> None:
    try:
        get_stream_writer()({"event": "node", "node": node, "phase": phase, "detail": detail})
    except RuntimeError:
        # Makes nodes directly unit-testable outside a graph stream.
        pass


@traceable(name="coordinator_agent", run_type="chain", tags=["coordinator", "triage"])
def coordinator_agent(state: TriageState) -> dict:
    if "diagnosis" not in state:
        emit("coordinator_agent", "active", "Planning the investigation")
        return {"route": "classify_issue", "issue_type": "data_plotter_configuration"}

    confidence = state.get("confidence", 0)
    emit("coordinator_agent", "active", f"Evaluating diagnosis confidence {confidence:.0%}")
    if confidence >= 0.8:
        return {"route": "return_solution"}
    if state.get("review_attempts", 0) >= 2:
        return {"route": "ask_follow_up"}
    return {"route": "review_agent"}


def route_coordinator(
    state: TriageState,
) -> Literal["classify_issue", "review_agent", "return_solution", "ask_follow_up"]:
    return state["route"]


def classify_issue(state: TriageState) -> dict:
    emit("classify_issue", "active", "Classifying the support request")
    question = state.get("question", "").lower()
    issue = "data_plotter_configuration" if any(word in question for word in ("plot", "chart", "data", "column", "error")) else "general_support"
    return {"issue_type": issue}


def information_check(state: TriageState) -> dict:
    emit("information_check", "active", "Checking available runtime evidence")
    result = plotter.load()
    enough = result["status"] == "error" and bool(result.get("config"))
    return {"enough_information": enough, "evidence": result}


def route_information(state: TriageState) -> Literal["review_agent", "ask_follow_up"]:
    return "review_agent" if state.get("enough_information") else "ask_follow_up"


def ask_follow_up(state: TriageState) -> dict:
    if state.get("review_attempts", 0) >= 2 and state.get("diagnosis"):
        emit("ask_follow_up", "active", "Embedding escalation details in the follow-up")
        return {
            "answer": (
                "Please share any additional plotter context so I can continue the investigation.\n\n"
                "I could not reach a safe confidence threshold. I drafted an escalation with the "
                "parser configuration, source header, and observed error attached."
            )
        }
    emit("ask_follow_up", "active", "Requesting the missing error context")
    return {
        "answer": (
            "Please share the plotter error and the first row of the source file so I can compare "
            "the parser configuration with the data format."
        )
    }


@traceable(name="tool_review_agent", run_type="chain", tags=["review-agent", "configuration"])
def review_agent(state: TriageState) -> dict:
    attempt = state.get("review_attempts", 0) + 1
    emit("review_agent", "active", f"Reviewing the plotter setup (attempt {attempt})")
    return {"route": "inspect_tool", "review_attempts": attempt}


@traceable(name="inspect_plotter_tool", run_type="tool", tags=["tool", "plotter"])
def review_agent_tool_node(state: TriageState) -> dict:
    emit("review_agent_tool_node", "active", "Reading parser config and source header")
    evidence = dict(state.get("evidence", {}))
    evidence["inspection"] = plotter.inspect()
    return {"evidence": evidence}


def generate_diagnosis(state: TriageState) -> dict:
    emit("generate_diagnosis", "active", "Comparing expected and observed schema")
    inspection = state["evidence"]["inspection"]
    mismatch = inspection["configured_delimiter"] != "|" and "|" in inspection["header"]
    diagnosis = (
        "The source is pipe-delimited, but the plotter calls pandas with sep=','. That makes the entire header one column, so latency_ms cannot be found."
        if mismatch
        else "The delimiter is correct; inspect the timestamp and metric mappings next."
    )
    return {"diagnosis": diagnosis, "confidence": 0.98 if mismatch else 0.42}


def _deterministic_solution(state: TriageState) -> str:
    return (
        "I found a delimiter mismatch in the data plotter. The file header is pipe-delimited "
        "(`timestamp|latency_ms|...`), while the loader is configured with `sep=','`. Update "
        "`PlotterConfig.delimiter` to `'|'` (or call `pd.read_csv(..., sep='|')`). That restores "
        "the `timestamp` and `latency_ms` columns. Confidence: 98%. Use **Apply suggested fix** "
        "in the plotter panel, then retry the chart."
    )


def return_solution(state: TriageState) -> dict:
    emit("return_solution", "active", "Preparing the verified remediation")
    fallback = _deterministic_solution(state)
    if not os.getenv("OPENAI_API_KEY"):
        return {"answer": fallback}
    try:
        model = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-5.6-sol"), streaming=True, temperature=0)
        response = model.invoke([
            ("system", "You are an engineering support lead. Give a concise diagnosis and exact fix. Preserve the supplied facts and end by telling the user to apply the suggested fix and retry."),
            ("user", f"Question: {state.get('question')}\nDiagnosis: {state.get('diagnosis')}\nEvidence: {state.get('evidence')}"),
        ])
        return {"answer": str(response.content)}
    except Exception:
        return {"answer": fallback}


builder = StateGraph(TriageState)
builder.add_node("coordinator_agent", coordinator_agent)
builder.add_node("classify_issue", classify_issue)
builder.add_node("information_check", information_check)
builder.add_node("ask_follow_up", ask_follow_up)
builder.add_node("review_agent", review_agent)
builder.add_node("review_agent_tool_node", review_agent_tool_node)
builder.add_node("generate_diagnosis", generate_diagnosis)
builder.add_node("return_solution", return_solution)
builder.add_edge(START, "coordinator_agent")
builder.add_conditional_edges("coordinator_agent", route_coordinator)
builder.add_edge("classify_issue", "information_check")
builder.add_conditional_edges("information_check", route_information)
builder.add_edge("ask_follow_up", END)
builder.add_edge("review_agent", "review_agent_tool_node")
builder.add_edge("review_agent_tool_node", "generate_diagnosis")
builder.add_edge("generate_diagnosis", "coordinator_agent")
builder.add_edge("return_solution", END)
triage_graph = builder.compile().with_config({"run_name": "toolagent_support_triage", "tags": ["fde-demo", "toolagent"]})


GRAPH_SPEC = {
    "nodes": [
        {"id": "coordinator_agent", "label": "Coordinator · confidence gate", "kind": "agent", "x": 50, "y": 8},
        {"id": "classify_issue", "label": "Classify issue", "kind": "step", "x": 50, "y": 23},
        {"id": "information_check", "label": "Enough context?", "kind": "decision", "x": 50, "y": 38},
        {"id": "ask_follow_up", "label": "Ask follow-up", "kind": "muted", "x": 19, "y": 53},
        {"id": "review_agent", "label": "Review agent", "kind": "agent", "x": 68, "y": 53},
        {"id": "review_agent_tool_node", "label": "Inspect plotter", "kind": "tool", "x": 68, "y": 68},
        {"id": "generate_diagnosis", "label": "Generate diagnosis", "kind": "step", "x": 68, "y": 83},
        {"id": "return_solution", "label": "Return solution", "kind": "success", "x": 28, "y": 23},
    ],
    "edges": [
        ["coordinator_agent", "classify_issue"], ["classify_issue", "information_check"],
        ["information_check", "ask_follow_up"], ["information_check", "review_agent"],
        ["review_agent", "review_agent_tool_node"], ["review_agent_tool_node", "generate_diagnosis"],
        ["generate_diagnosis", "coordinator_agent"], ["coordinator_agent", "review_agent"],
        ["coordinator_agent", "return_solution"], ["coordinator_agent", "ask_follow_up"],
    ],
}

