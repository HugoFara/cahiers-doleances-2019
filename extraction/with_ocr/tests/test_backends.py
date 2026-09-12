"""Les backends : parsing des réponses, retries, erreurs — requêtes bouchonnées."""

from types import SimpleNamespace

import pytest
import requests

from extraction.with_ocr import backends
from extraction.with_ocr.backends import (
    ErreurOcr,
    MistralBackend,
    OllamaBackend,
    fabrique_backend,
)


def _reponse(status_code=200, payload=None, texte_erreur=""):
    return SimpleNamespace(
        status_code=status_code,
        json=lambda: payload or {},
        text=texte_erreur,
    )


@pytest.fixture
def mistral():
    return MistralBackend(api_key="clef-de-test")


def test_mistral_depouille_les_lignes_avec_polygones(mistral, monkeypatch):
    payload = {
        "pages": [
            {
                "lines": [
                    {"text": "REÇU LE", "polygon": [{"x": 1, "y": 2}]},
                    {"text": "5 FEV. 2019", "polygon": [{"x": 3, "y": 4}]},
                ]
            }
        ]
    }
    monkeypatch.setattr(backends.requests, "post", lambda *a, **k: _reponse(payload=payload))
    resultat = mistral.transcrire(b"png")
    assert resultat.texte == "REÇU LE\n5 FEV. 2019"
    assert resultat.layout == payload["pages"][0]["lines"]


def test_mistral_retombe_sur_le_markdown_sans_lignes(mistral, monkeypatch):
    payload = {"pages": [{"markdown": "# AUGMENTATION DU SMIC"}]}
    monkeypatch.setattr(backends.requests, "post", lambda *a, **k: _reponse(payload=payload))
    resultat = mistral.transcrire(b"png")
    assert resultat.texte == "# AUGMENTATION DU SMIC"
    assert resultat.layout is None


def test_mistral_reessaie_puis_leve_erreur_ocr(mistral, monkeypatch):
    appels = []

    def post(*args, **kwargs):
        appels.append(args)
        return _reponse(status_code=500, texte_erreur="boom")

    monkeypatch.setattr(backends.requests, "post", post)
    with pytest.raises(ErreurOcr, match="500"):
        mistral.transcrire(b"png")
    assert len(appels) == 2  # OcrConfig.RETRIES


def test_mistral_sans_clef_leve_value_error():
    with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
        MistralBackend(api_key="")


def test_ollama_rend_le_texte_et_passe_num_ctx(monkeypatch):
    captures = {}

    def post(url, json=None, timeout=None):
        captures["url"] = url
        captures["payload"] = json
        return _reponse(payload={"response": "la transcription"})

    monkeypatch.setattr(backends.requests, "post", post)
    backend = OllamaBackend(model="glm-ocr", url="http://localhost:11434/")
    resultat = backend.transcrire(b"png")
    assert resultat.texte == "la transcription"
    assert captures["url"] == "http://localhost:11434/api/generate"
    assert captures["payload"]["options"]["num_ctx"] >= 8192
    assert captures["payload"]["stream"] is False


def test_ollama_plafonne_la_generation_et_le_dit(monkeypatch):
    captures = {}

    def post(url, json=None, timeout=None):
        captures["options"] = json["options"]
        return _reponse(payload={"response": "la la la", "done_reason": "length"})

    monkeypatch.setattr(backends.requests, "post", post)
    resultat = OllamaBackend(num_predict=2048).transcrire(b"png")
    assert captures["options"]["num_predict"] == 2048
    assert "seed" not in captures["options"]
    assert resultat.plafonne is True


def test_ollama_retire_a_graine_fixee(monkeypatch):
    captures = {}

    def post(url, json=None, timeout=None):
        captures["options"] = json["options"]
        return _reponse(payload={"response": "propre", "done_reason": "stop"})

    monkeypatch.setattr(backends.requests, "post", post)
    resultat = OllamaBackend().transcrire(b"png", seed=2)
    assert captures["options"]["seed"] == 2
    assert resultat.plafonne is False
    assert OllamaBackend.retirable is True
    assert not getattr(MistralBackend, "retirable", False)


def test_ollama_en_erreur_leve_erreur_ocr(monkeypatch):
    monkeypatch.setattr(
        backends.requests,
        "post",
        lambda *a, **k: _reponse(status_code=400, texte_erreur="exceed_context_size_error"),
    )
    with pytest.raises(ErreurOcr, match="400"):
        OllamaBackend().transcrire(b"png")


def test_une_exception_reseau_est_reessayee(mistral, monkeypatch):
    appels = []

    def post(*args, **kwargs):
        appels.append(args)
        raise requests.ConnectionError("coupure")

    monkeypatch.setattr(backends.requests, "post", post)
    with pytest.raises(ErreurOcr, match="coupure"):
        mistral.transcrire(b"png")
    assert len(appels) == 2


def test_fabrique_backend(mistral, monkeypatch):
    monkeypatch.setattr(backends.settings, "mistral_api_key", "clef")
    assert isinstance(fabrique_backend("mistral"), MistralBackend)
    assert isinstance(fabrique_backend("ollama", model="qwen3-vl"), OllamaBackend)
    with pytest.raises(ValueError, match="backend inconnu"):
        fabrique_backend("tesseract")
