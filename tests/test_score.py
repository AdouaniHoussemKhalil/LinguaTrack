from app.services.llm_common import drop_incoherent, normalize_analysis

def test_perfect_text_with_typographic_apostrophe_keeps_100():
    # Cas signalé : texte sans faute, le modèle remplace ' par ’ et répond 100
    src = "J'espère que tu viens ce soir. Aujourd'hui, il fait beau !"
    raw = {"corrected_text": "J’espère que tu viens ce soir. Aujourd’hui, il fait beau\u00a0!", "score": 100, "feedback": "", "grammar_errors": []}
    assert normalize_analysis(drop_incoherent(raw, src))["score"] == 100.0

def test_rewrite_mode_changed_text_keeps_100():
    raw = {"corrected_text": "Pourriez-vous m'envoyer le document ?", "score": 100, "feedback": "", "grammar_errors": []}
    assert drop_incoherent(raw, "Tu peux m'envoyer le doc ?")["score"] == 100

def test_typographic_only_error_is_dropped():
    raw = {"corrected_text": "J’espère.", "score": 100, "feedback": "", "grammar_errors": [
        {"original": "J'espère", "corrected": "J’espère", "explanation": "apostrophe", "error_type": "ponctuation", "severity": "low"}]}
    cleaned = drop_incoherent(raw, "J'espère.")
    assert cleaned["grammar_errors"] == [] and cleaned["score"] == 100

def test_fragment_with_curly_apostrophe_matches_source():
    raw = {"corrected_text": "x", "score": 80, "feedback": "", "grammar_errors": [
        {"original": "l’enfants", "corrected": "les enfants", "explanation": "e", "error_type": "article", "severity": "medium"}]}
    assert len(drop_incoherent(raw, "Je vois l'enfants.")["grammar_errors"]) == 1

def test_100_with_listed_errors_still_ignored():
    raw = {"corrected_text": "Ils jouent.", "score": 100, "feedback": "", "grammar_errors": [
        {"original": "joue", "corrected": "jouent", "explanation": "e", "error_type": "accord", "severity": "high"}]}
    assert drop_incoherent(raw, "Ils joue.")["score"] is None
