import json, uuid
from types import SimpleNamespace
import anthropic, httpx2, pytest
from app.core.config import settings
from app.services import claude_service, llm_service, text_service
from app.services.llm_common import LLMError
from helpers import register_user

RAW = {"corrected_text": "Ça va.", "score": 88, "feedback": "Bien", "grammar_errors": [
    {"original": "sa", "corrected": "ça", "explanation": "cédille", "error_type": "orthographe", "severity": "high"}]}

def mistral_fails(*_a, **_k): raise LLMError("Le service d'analyse est momentanément indisponible.")

# ---------- orchestration ----------
def test_mistral_ok_claude_not_called(monkeypatch):
    monkeypatch.setattr(llm_service, "_analyze_with_mistral", lambda s, u, t="": RAW)
    monkeypatch.setattr(claude_service, "analyze", lambda s, u: pytest.fail("Claude ne doit pas être appelé"))
    assert llm_service.generate_analysis("sa va", "correction", "B1")["score"] == 88.0

def test_fallback_to_claude(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm_service, "_analyze_with_mistral", mistral_fails)
    seen = {}
    def fake(system_prompt, user_prompt): seen["prompt"] = user_prompt; return RAW
    monkeypatch.setattr(claude_service, "analyze", fake)
    r = llm_service.generate_analysis("sa va", "simple", "C1")
    assert r["grammar_errors"][0]["severity"] == "high" and "C1" in seen["prompt"] and "sa va" in seen["prompt"]

def test_no_anthropic_key_keeps_mistral_error(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(llm_service, "_analyze_with_mistral", mistral_fails)
    monkeypatch.setattr(claude_service, "analyze", lambda s, u: pytest.fail("pas de repli sans clé"))
    with pytest.raises(LLMError): llm_service.generate_analysis("x", "correction", None)

def test_both_fail_returns_502_and_saves_nothing(client, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm_service, "_analyze_with_mistral", mistral_fails)
    monkeypatch.setattr(claude_service, "analyze", lambda s, u: (_ for _ in ()).throw(LLMError("Claude indisponible")))
    h, _ = register_user(client)
    r = client.post("/texts/analyze", json={"text": "Bonjour"}, headers=h)
    assert r.status_code == 502 and r.json()["detail"] == "Claude indisponible"
    assert client.get("/texts/history", params={"period": "all"}, headers=h).json() == []

def test_endpoint_uses_claude_when_mistral_down(client, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm_service, "_analyze_with_mistral", mistral_fails)
    monkeypatch.setattr(claude_service, "analyze", lambda s, u: RAW)
    h, _ = register_user(client)
    r = client.post("/texts/analyze", json={"text": "sa va"}, headers=h)
    assert r.status_code == 200 and r.json()["corrected_text"] == "Ça va." and r.json()["errors"][0]["severity"] == "high"

# ---------- claude_service.analyze avec client Anthropic simulé ----------
class FakeClient:
    def __init__(self, outcome): self.outcome, self.kwargs = outcome, None; self.beta = SimpleNamespace(messages=self)
    def create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.outcome, Exception): raise self.outcome
        return self.outcome

def response(stop_reason="end_turn", text=json.dumps(RAW)):
    return SimpleNamespace(stop_reason=stop_reason, _request_id="req_test",
                           content=[SimpleNamespace(type="text", text=text)])

@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test")
    holder = {}
    def install(outcome):
        holder["client"] = FakeClient(outcome)
        monkeypatch.setattr(claude_service.anthropic, "Anthropic", lambda **_: holder["client"])
        return holder["client"]
    return install

def test_request_shape_and_success(fake):
    c = fake(response())
    assert claude_service.analyze("SYS", "USER") == RAW
    k = c.kwargs
    assert k["model"] == settings.ANTHROPIC_MODEL == "claude-opus-5"
    assert k["betas"] == ["server-side-fallback-2026-07-01"] and k["fallbacks"] == "default"
    assert k["system"] == "SYS" and k["messages"] == [{"role": "user", "content": "USER"}]
    schema = k["output_config"]["format"]["schema"]
    assert "préposition" in schema["properties"]["grammar_errors"]["items"]["properties"]["error_type"]["enum"]

@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_refusal_and_truncation(fake, stop_reason):
    fake(response(stop_reason=stop_reason))
    with pytest.raises(LLMError): claude_service.analyze("S", "U")

def test_api_errors_become_llm_error(fake):
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    for exc in (anthropic.RateLimitError("limite", response=httpx2.Response(429, request=req), body=None),
                anthropic.InternalServerError("boom", response=httpx2.Response(500, request=req), body=None),
                anthropic.APIConnectionError(request=req)):
        fake(exc)
        with pytest.raises(LLMError): claude_service.analyze("S", "U")

def test_missing_anthropic_package_disables_claude(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(claude_service, "anthropic", None)
    assert claude_service.is_configured() is False
