from app.backend.graph import coordinator_agent, review_agent, route_coordinator


def test_coordinator_starts_with_issue_classification():
    update = coordinator_agent({"question": "Why is the plot broken?"})

    assert update["route"] == "classify_issue"
    assert route_coordinator(update) == "classify_issue"


def test_coordinator_approves_high_confidence_diagnosis():
    update = coordinator_agent({"diagnosis": "Delimiter mismatch", "confidence": 0.98, "review_attempts": 1})

    assert update["route"] == "return_solution"


def test_coordinator_requests_another_low_confidence_review():
    update = coordinator_agent({"diagnosis": "Uncertain mapping", "confidence": 0.42, "review_attempts": 1})

    assert update["route"] == "review_agent"
    assert review_agent({"review_attempts": 1})["review_attempts"] == 2


def test_coordinator_routes_uncertain_reviews_to_ask_follow_up():
    update = coordinator_agent({"diagnosis": "Still uncertain", "confidence": 0.42, "review_attempts": 2})

    assert update["route"] == "ask_follow_up"


def test_ask_follow_up_embeds_escalation_after_uncertain_reviews():
    from app.backend.graph import ask_follow_up

    answer = ask_follow_up(
        {
            "diagnosis": "Uncertain mapping",
            "confidence": 0.42,
            "review_attempts": 2,
        }
    )["answer"]

    assert "Please share any additional plotter context" in answer
    assert "safe confidence threshold" in answer
    assert "escalation" in answer


def test_ask_follow_up_requests_missing_context_without_prior_review():
    from app.backend.graph import ask_follow_up

    answer = ask_follow_up({})["answer"]

    assert "first row of the source file" in answer
    assert "escalation" not in answer
