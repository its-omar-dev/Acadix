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
