import json
import httpx, pytest
from app.core.config import settings
from app.services import claude_service, llm_service, ollama_service
from app.services.llm_common import LLMError, drop_incoherent

SOURCE = "Je pense que sa va bien marcher demain.Nous avons été au marché hier."
GOOD = {"corrected_text": "Je pense que ça va bien marcher demain. Nous sommes allés au marché hier.", "score": 70, "feedback": "ok",
        "grammar_errors": [{"original": "sa va", "corrected": "ça va", "explanation": "cédille", "error_type": "orthographe", "severity": "high"}]}

# ---------- nettoyage ----------
@pytest.mark.parametrize("content", [
    json.dumps(GOOD),
    "<think>Alright, let's tackle this…</think>\n" + json.dumps(GOOD),
    "```json\n" + json.dumps(GOOD) + "\n```",
    "<THINK>a</THINK>```json\n" + json.dumps(GOOD) + "```",
])
def test_strip_reasoning(content):
    assert json.loads(ollama_service.strip_reasoning(content)) == GOOD

def test_strip_unclosed_think_leaves_nothing():
    assert ollama_service.strip_reasoning("<think>réflexion coupée…") == ""

def test_clean_drops_incoherent_errors_and_contradictory_score():
    raw = {"corrected_text": "Je pense que sa va bien marcher demain. nous avons été au marché hier.", "score": 100, "feedback": "correct",
           "grammar_errors": [
               {"original": "Je pense que sa va bien marcher demain.", "corrected": "correct", "error_type": "orthographe", "severity": "low", "explanation": "x"},
               {"original": "phrase inventée", "corrected": "autre", "error_type": "style", "severity": "low", "explanation": "x"},
               {"original": "sa va", "corrected": "sa va", "error_type": "orthographe", "severity": "low", "explanation": "x"},
               {"original": "Nous  avons été", "corrected": "Nous sommes allés", "error_type": "conjugaison", "severity": "high", "explanation": "aller"},
               "pas un objet"]}
    cleaned = drop_incoherent(raw, SOURCE)
    assert [e["corrected"] for e in cleaned["grammar_errors"]] == ["Nous sommes allés"]
    assert cleaned["score"] is None  # 100 avec une erreur restante

def test_clean_keeps_perfect_score_when_nothing_to_fix():
    raw = {"corrected_text": "Bonjour.", "score": 100, "feedback": "", "grammar_errors": []}
    assert drop_incoherent(raw, "Bonjour.")["score"] == 100

# ---------- appel HTTP simulé ----------
def fake_post(status=200, body=None, exc=None, seen=None):
    def post(url, json=None, timeout=None):
        if seen is not None: seen.update(url=url, payload=json, timeout=timeout)
        if exc: raise exc
        return httpx.Response(status, json=body if body is not None else {}, request=httpx.Request("POST", url))
    return post

@pytest.fixture
def ollama_on(monkeypatch):
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "deepseek-r1:1.5b")

def test_analyze_success_and_payload(ollama_on, monkeypatch):
    seen = {}
    body = {"message": {"role": "assistant", "thinking": "Alright…", "content": "<think>x</think>" + json.dumps(GOOD)}, "done_reason": "stop"}
    monkeypatch.setattr(ollama_service.httpx, "post", fake_post(body=body, seen=seen))
    assert ollama_service.analyze("SYS", "USER", SOURCE) == GOOD
    p = seen["payload"]
    assert seen["url"].endswith("/api/chat") and p["model"] == "deepseek-r1:1.5b" and p["stream"] is False
    assert p["think"] is True and p["format"]["properties"]["grammar_errors"]["items"]["properties"]["severity"]["enum"] == ["low", "medium", "high"]
    assert seen["timeout"] == settings.OLLAMA_TIMEOUT

@pytest.mark.parametrize("kwargs", [
    {"exc": httpx.ConnectError("refused")},
    {"exc": httpx.ReadTimeout("slow")},
    {"status": 404, "body": {"error": "model not found"}},
    {"status": 500, "body": {"error": "boom"}},
    {"body": {"message": {"content": "{\"corrected_text\": \"Je"}, "done_reason": "length"}},
    {"body": {"message": {"content": "pas du json"}, "done_reason": "stop"}},
])
def test_analyze_failures_raise_llm_error(ollama_on, monkeypatch, kwargs):
    monkeypatch.setattr(ollama_service.httpx, "post", fake_post(**kwargs))
    with pytest.raises(LLMError):
        ollama_service.analyze("S", "U", SOURCE)

# ---------- chaîne de fournisseurs ----------
def fail(name):
    def f(*_a, **_k): raise LLMError(f"{name} KO")
    return f

def test_chain_mistral_then_ollama(ollama_on, monkeypatch):
    calls = []
    monkeypatch.setattr(llm_service, "_analyze_with_mistral", lambda *a: calls.append("mistral") or fail("m")())
    monkeypatch.setattr(ollama_service, "analyze", lambda s, u, t: calls.append(("ollama", t)) or GOOD)
    monkeypatch.setattr(claude_service, "analyze", lambda s, u: pytest.fail("Claude ne doit pas être appelé"))
    r = llm_service.generate_analysis(SOURCE, "correction", "B1")
    assert calls == ["mistral", ("ollama", SOURCE)] and r["grammar_errors"][0]["corrected"] == "ça va"

def test_chain_ollama_down_then_claude(ollama_on, monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm_service, "_analyze_with_mistral", fail("mistral"))
    monkeypatch.setattr(ollama_service, "analyze", fail("ollama"))
    monkeypatch.setattr(claude_service, "analyze", lambda s, u: GOOD)
    assert llm_service.generate_analysis(SOURCE, "correction", None)["score"] == 70.0

def test_chain_order_is_configurable(ollama_on, monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "LLM_PROVIDERS", "ollama, mistral")
    monkeypatch.setattr(ollama_service, "analyze", lambda s, u, t: calls.append("ollama") or GOOD)
    monkeypatch.setattr(llm_service, "_analyze_with_mistral", lambda *a: pytest.fail("Mistral ne doit pas être appelé"))
    llm_service.generate_analysis(SOURCE, "correction", None)
    assert calls == ["ollama"]

def test_all_fail_raises_last_error(ollama_on, monkeypatch):
    monkeypatch.setattr(llm_service, "_analyze_with_mistral", fail("mistral"))
    monkeypatch.setattr(ollama_service, "analyze", fail("ollama"))
    with pytest.raises(LLMError, match="ollama KO"):
        llm_service.generate_analysis(SOURCE, "correction", None)

def test_nothing_configured(monkeypatch):
    monkeypatch.setattr(settings, "MISTRAL_API_KEY", None)
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    with pytest.raises(LLMError, match="pas configuré"):
        llm_service.generate_analysis(SOURCE, "correction", None)
