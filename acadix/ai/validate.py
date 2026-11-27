"""Validation helpers for structured roadmap data."""


def validate_roadmap(roadmap):
    """Return True only when a roadmap has the minimum supported structure."""
    if not isinstance(roadmap, dict):
        return False

    summary = roadmap.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return False

    phases = roadmap.get("phases")
    if not isinstance(phases, list) or len(phases) != 4:
        return False

    for phase in phases:
        if not isinstance(phase, dict):
            return False
        tasks = phase.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            return False

    return True



def validate_stage(data):
    """Validate one independently streamable roadmap stage."""
    if not isinstance(data, dict):
        return False
    stage = data.get("stage")
    if not isinstance(stage, int) or isinstance(stage, bool) or stage not in (1, 2, 3, 4):
        return False
    name = data.get("name")
    description = data.get("description", "")
    tasks = data.get("tasks")
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        return False
    if not isinstance(description, str) or len(description) > 500:
        return False
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 5:
        return False
    if any(not isinstance(task, str) or not task.strip() or len(task) > 300 for task in tasks):
        return False
    summary = data.get("summary")
    if summary is not None and (
        not isinstance(summary, str) or len(summary) > 1000
    ):
        return False
    return True
