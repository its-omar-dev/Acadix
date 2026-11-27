from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_fly_configuration_matches_application_health_endpoint():
    config = tomllib.loads((ROOT / "fly.toml").read_text(encoding="utf-8"))

    assert config["primary_region"] == "fra"
    assert config["http_service"]["internal_port"] == 8000
    assert config["http_service"]["min_machines_running"] == 1
    assert config["http_service"]["checks"][0]["path"] == "/health"
    assert config["http_service"]["checks"][0]["method"] == "GET"


def test_docker_image_runs_as_non_root_user():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "USER app" in dockerfile
    assert "gunicorn" in dockerfile
    assert "0.0.0.0:" in dockerfile
