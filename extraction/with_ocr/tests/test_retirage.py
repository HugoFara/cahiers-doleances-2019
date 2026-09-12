"""Le retirage des dérives, backend bouchonné."""

from extraction.with_ocr.backends import OcrResult, transcrire_propre
from extraction.with_ocr.config import OcrConfig

DERIVE = "la même ligne\n" * 200


class _Backend:
    """Rend les résultats dans l'ordre, et note les graines demandées."""

    retirable = True

    def __init__(self, *resultats):
        self.resultats = list(resultats)
        self.graines = []

    def transcrire(self, image, format="png", seed=None):
        self.graines.append(seed)
        return self.resultats.pop(0)


def test_un_resultat_propre_n_est_pas_retire():
    backend = _Backend(OcrResult("un texte sage"))
    texte, _, retirages = transcrire_propre(backend, b"png", "png")
    assert texte == "un texte sage"
    assert retirages == 0
    assert backend.graines == [None]


def test_une_derive_est_retiree_a_graine_fixee_jusqu_au_propre():
    backend = _Backend(
        OcrResult(DERIVE), OcrResult("encore", plafonne=True), OcrResult("propre")
    )
    texte, resultat, retirages = transcrire_propre(backend, b"png", "png")
    assert texte == "propre"
    assert resultat.plafonne is False
    assert retirages == 2
    assert backend.graines == [None, 1, 2]


def test_le_dernier_tirage_est_garde_si_tout_derive():
    n = OcrConfig.OLLAMA_RETIRAGES.value
    backend = _Backend(*[OcrResult(DERIVE) for _ in range(n + 1)])
    texte, _, retirages = transcrire_propre(backend, b"png", "png")
    assert retirages == n
    assert texte.startswith("la même ligne")


def test_un_backend_sans_retirage_garde_son_premier_resultat():
    class _Mistral:
        def __init__(self):
            self.appels = 0

        def transcrire(self, image, format="png"):
            self.appels += 1
            return OcrResult(DERIVE)

    backend = _Mistral()
    _, _, retirages = transcrire_propre(backend, b"png", "png")
    assert retirages == 0
    assert backend.appels == 1
