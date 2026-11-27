from types import SimpleNamespace

from acadix.ai import client as ai_client
from acadix.ai.prompts import roadmap_prompt


def test_prompt_keeps_arabic_four_phase_markdown_contract():
    prompt = roadmap_prompt("تحليل البيانات", "متوسط")
    assert "تحليل البيانات" in prompt
    assert "المرحلة 1" in prompt
    assert "نفس الشكل للمراحل 2 إلى 4" in prompt


def test_generate_roadmap_uses_configured_fallback_model(monkeypatch):
    class FakeCompletions:
        def create(self, **kwargs):
            assert kwargs["model"] == ai_client.MODELS[0]
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="## خارطة تجريبية"))]
            )

    fake = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(ai_client, "_get_client", lambda: fake)
    assert ai_client.generate_roadmap("Python", "مبتدئ") == "## خارطة تجريبية"
