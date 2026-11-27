from app import validate_roadmap


def valid_roadmap():
    return {
        "summary": "خارطة طريق تعليمية تجريبية",
        "phases": [{"tasks": ["إنجاز مهمة"]} for _ in range(4)],
    }


def test_rejects_non_dict_input():
    assert not validate_roadmap(["not", "a", "dict"])


def test_rejects_roadmap_without_summary():
    roadmap = valid_roadmap()
    roadmap.pop("summary")

    assert not validate_roadmap(roadmap)


def test_rejects_roadmap_with_wrong_phase_count():
    roadmap = valid_roadmap()
    roadmap["phases"].pop()

    assert not validate_roadmap(roadmap)


def test_rejects_phase_without_tasks():
    roadmap = valid_roadmap()
    roadmap["phases"][0].pop("tasks")

    assert not validate_roadmap(roadmap)


def test_accepts_minimal_valid_roadmap():
    assert validate_roadmap(valid_roadmap())
