from app.backend.plotter import plotter


def test_demo_starts_broken_and_fix_restores_points():
    plotter.reset()
    broken = plotter.load()
    assert broken["status"] == "error"
    assert "Missing required column" in broken["message"]

    plotter.apply_fix()
    fixed = plotter.load()
    assert fixed["status"] == "healthy"
    assert len(fixed["points"]) == 10
    assert fixed["points"][0]["value"] == 118.0
    plotter.reset()

