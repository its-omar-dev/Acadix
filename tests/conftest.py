import importlib
import os

import pytest

os.environ["GROQ_API_KEY"] = "test-key-not-real"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ADMIN_TOKEN", None)

flask_app = importlib.import_module("app").app


@pytest.fixture
def app():
    flask_app.config.update(TESTING=True)
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()
