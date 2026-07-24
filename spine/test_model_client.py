import model_client


def test_renamed_calls_exist():
    assert callable(model_client.call_pilot)
    assert callable(model_client.call_pilot_eval)
    assert callable(model_client.call_planner)
    # the old follower/leader names must be gone
    assert not hasattr(model_client, "call_follower")
    assert not hasattr(model_client, "call_leader")


def test_pilot_routes_to_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    url, key, model = model_client._endpoint("PILOT")
    assert "openrouter.ai" in url
    # regression guard: lowercase role must resolve identically (case-mismatch bug)
    url_lower, _, _ = model_client._endpoint("pilot")
    assert url_lower == url


def test_planner_routes_to_deepseek(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    url, key, model = model_client._endpoint("PLANNER")
    assert "deepseek" in url
