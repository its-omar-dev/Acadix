import json
from types import SimpleNamespace

import acadix.ai.client as ai_client
import acadix.routes as routes
from acadix import create_app
from acadix.ai.validate import validate_stage


def make_stage(number):
    return {
        "stage": number,
        "name": f"المرحلة التجريبية {number}",
        "description": "وصف مختصر",
        "tasks": ["مهمة أولى", "مهمة ثانية", "مهمة ثالثة"],
        **({"summary": "ملخص الخارطة"} if number == 1 else {}),
    }


def parse_events(response):
    events = []
    for frame in response.get_data(as_text=True).strip().split("\n\n"):
        lines = frame.splitlines()
        event = next(line[6:].strip() for line in lines if line.startswith("event:"))
        payload = json.loads(next(line[5:] for line in lines if line.startswith("data:")))
        events.append((event, payload))
    return events


def configured_client():
    app = create_app({"TESTING": True, "GROQ_API_KEY": "test-key-not-real"})
    return app.test_client()


def patch_stream_dependencies(monkeypatch, deltas):
    monkeypatch.setattr(routes, "get_cached", lambda topic, level: None)
    monkeypatch.setattr(routes, "too_many", lambda ip: False)
    monkeypatch.setattr(routes, "stream_roadmap", lambda topic, level: iter(deltas))
    monkeypatch.setattr(routes, "set_cached", lambda topic, level, roadmap: None)
    monkeypatch.setattr(routes, "search_learning_links", lambda topic: [])


def test_validate_stage_accepts_valid_stage_and_rejects_invalid_data():
    assert validate_stage(make_stage(1))
    assert not validate_stage({"stage": True, "name": "bad", "tasks": ["x"]})
    assert not validate_stage({**make_stage(2), "tasks": []})
    assert not validate_stage({**make_stage(3), "name": " "})


def test_stream_endpoint_emits_valid_json_stage_events_and_complete(monkeypatch):
    lines = [json.dumps(make_stage(i), ensure_ascii=False) + "\n" for i in range(1, 5)]
    patch_stream_dependencies(monkeypatch, lines)

    response = configured_client().post(
        "/generate/stream",
        json={"topic": "Python", "level": "مبتدئ"},
        buffered=True,
    )

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    events = parse_events(response)
    stage_events = [payload for event, payload in events if event == "stage"]
    assert [item["stage"] for item in stage_events] == [1, 2, 3, 4]
    assert events[-1][0] == "complete"
    assert "المرحلة 4" in events[-1][1]["roadmap"]


def test_invalid_and_incomplete_stream_falls_back_to_legacy_markdown(monkeypatch):
    partial = json.dumps(make_stage(1), ensure_ascii=False) + "\nnot-json\n"
    patch_stream_dependencies(monkeypatch, [partial])
    monkeypatch.setattr(routes, "generate_roadmap", lambda topic, level: "## خارطة قديمة")

    response = configured_client().post(
        "/generate/stream",
        json={"topic": "Python", "level": "مبتدئ"},
        buffered=True,
    )

    events = parse_events(response)
    assert any(event == "stage" for event, _ in events)
    assert events[-1] == (
        "fallback",
        {
            "roadmap": "## خارطة قديمة",
            "topic": "Python",
            "level": "مبتدئ",
            "courses": [],
        },
    )


def test_stream_emits_error_when_stream_and_fallback_fail(monkeypatch):
    patch_stream_dependencies(monkeypatch, [])
    monkeypatch.setattr(routes, "generate_roadmap", lambda topic, level: None)

    response = configured_client().post(
        "/generate/stream",
        json={"topic": "Python", "level": "مبتدئ"},
        buffered=True,
    )

    assert parse_events(response)[-1][0] == "error"


def test_stream_endpoint_rejects_invalid_input():
    response = configured_client().post("/generate/stream", json={"topic": "", "level": "مبتدئ"})
    assert response.status_code == 400


def test_stream_roadmap_requests_groq_streaming(monkeypatch):
    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["stream"] is True
            return iter(
                [
                    SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content='{"stage":1}'))]
                    ),
                    SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content="\n"))]
                    ),
                ]
            )

    fake = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(ai_client, "_get_client", lambda: fake)
    assert "".join(ai_client.stream_roadmap("Python", "مبتدئ")) == '{"stage":1}\n'
