"""Le mode batch : lots sous la taille limite, jobs notés dans le run,
récolte des réponses, reprise — client bouchonné, SQLite en mémoire."""

import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from database.models import Base, PageExtraction, PageTranscription
from extraction.with_ocr import batch
from extraction.with_ocr.persist import ouvrir_run


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def pages(session) -> list[PageExtraction]:
    lignes = [
        PageExtraction(
            pdf_name="CC_01000_190304_01053_MD_15462.pdf",
            page_number=n,
            text="",
            quality_score=0.1,
            needs_ocr=True,
        )
        for n in range(3, 8)
    ]
    session.add_all(lignes)
    session.flush()
    return lignes


@pytest.fixture
def run(session):
    run = ouvrir_run(
        session,
        backend="mistral",
        model="mistral-ocr-latest",
        dpi=300,
        perimetre="manuscrit",
        format="jpeg",
        batch=True,
    )
    session.commit()
    return run


@pytest.fixture
def rendu_bouchonne(monkeypatch):
    """Le rendu rend 1 000 octets par page, sans PDF."""
    monkeypatch.setattr(batch, "rendre_page", lambda nom, num, dpi, fmt: bytes(1000))


class ClientBouchon:
    """Un client batch en mémoire : les jobs aboutissent quand on le décide."""

    def __init__(self):
        self.fichiers: dict[str, bytes] = {}
        self.jobs: dict[str, dict] = {}
        self.televerses: list[str] = []

    def televerser(self, nom, contenu):
        file_id = f"f{len(self.fichiers) + 1}"
        self.fichiers[file_id] = contenu
        self.televerses.append(nom)
        return file_id

    def ouvrir_job(self, file_id, model, metadata):
        job_id = f"j{len(self.jobs) + 1}"
        self.jobs[job_id] = {"id": job_id, "status": "QUEUED", "input": file_id}
        return job_id

    def job(self, job_id):
        return self.jobs[job_id]

    def contenu(self, file_id):
        return self.fichiers[file_id].decode()

    def aboutir(
        self, job_id, reponses: dict[str, dict], erreurs: dict[str, str] | None = None
    ):
        """Fait aboutir le job avec, par custom_id, un corps OCR ou une erreur."""
        sortie = "".join(
            json.dumps(
                {"custom_id": cid, "response": {"status_code": 200, "body": corps}}
            )
            + "\n"
            for cid, corps in reponses.items()
        )
        self.fichiers[f"{job_id}-out"] = sortie.encode()
        self.jobs[job_id] |= {"status": "SUCCESS", "output_file": f"{job_id}-out"}
        if erreurs:
            fautes = "".join(
                json.dumps({"custom_id": cid, "error": msg}) + "\n"
                for cid, msg in erreurs.items()
            )
            self.fichiers[f"{job_id}-err"] = fautes.encode()
            self.jobs[job_id]["error_file"] = f"{job_id}-err"


def _corps(texte: str) -> dict:
    return {"pages": [{"lines": [{"text": texte, "polygon": [{"x": 0, "y": 0}]}]}]}


class TestLots:
    def test_une_ligne_est_une_requete_ocr_a_l_identique(self, pages):
        ligne = json.loads(batch._ligne(pages[0], b"img", "mistral-ocr-latest", "jpeg"))
        assert ligne["custom_id"] == str(pages[0].id)
        assert ligne["body"]["model"] == "mistral-ocr-latest"
        assert ligne["body"]["document"]["image_url"].startswith(
            "data:image/jpeg;base64,"
        )
        assert ligne["body"]["include_image_base64"] is False

    def test_les_lots_restent_sous_la_taille_limite(self, pages, rendu_bouchonne):
        lots = list(
            batch.constituer_lots(
                pages, model="m", dpi=300, format="jpeg", taille_max=3000
            )
        )
        # ~1 500 octets par ligne : deux lignes par lot, cinq pages -> 3 lots
        assert [len(lot) for lot, _ in lots] == [2, 2, 1]
        assert all(len(contenu) <= 3000 for _, contenu in lots)
        assert [p.id for lot, _ in lots for p in lot] == [p.id for p in pages]

    def test_une_page_qui_ne_se_rend_pas_est_sautee(self, pages, monkeypatch):
        def rendre(nom, num, dpi, fmt):
            if num == 5:
                raise ValueError("hors limites")
            return b"img"

        monkeypatch.setattr(batch, "rendre_page", rendre)
        lots = list(batch.constituer_lots(pages, model="m", dpi=300, format="png"))
        assert len(lots) == 1
        assert [p.page_number for p in lots[0][0]] == [3, 4, 6, 7]


class TestSoumission:
    def test_chaque_lot_ouvre_un_job_note_dans_le_run(
        self, session, run, pages, rendu_bouchonne, monkeypatch
    ):
        client = ClientBouchon()
        # taille_max n'est pas exposée par soumettre : on passe par constituer_lots
        monkeypatch.setattr(
            batch,
            "constituer_lots",
            lambda p, **kw: [(p[:3], b"a" * 10), (p[3:], b"b" * 10)],
        )
        ouverts = batch.soumettre(
            session, run, client, pages, model="m", dpi=300, format="jpeg"
        )
        assert ouverts == 2
        session.refresh(run)
        lots = batch.lots_du_run(run)
        assert [lot["job_id"] for lot in lots] == ["j1", "j2"]
        assert lots[0]["pages"] == [p.id for p in pages[:3]]
        assert lots[1]["pages"] == [p.id for p in pages[3:]]
        assert not any(lot["termine"] for lot in lots)
        assert client.televerses == [
            f"run{run.id}-lot1.jsonl",
            f"run{run.id}-lot2.jsonl",
        ]
        assert batch.pages_en_attente(run) == {p.id for p in pages}


class TestRecolte:
    def _soumis(self, session, run, pages, client):
        lots = [
            {
                "job_id": "j1",
                "fichier": "f1",
                "pages": [p.id for p in pages[:3]],
                "termine": False,
            },
            {
                "job_id": "j2",
                "fichier": "f2",
                "pages": [p.id for p in pages[3:]],
                "termine": False,
            },
        ]
        client.jobs = {j: {"id": j, "status": "RUNNING"} for j in ("j1", "j2")}
        batch._noter_lots(session, run, lots)
        return lots

    def test_un_job_en_cours_reste_en_attente(self, session, run, pages):
        client = ClientBouchon()
        self._soumis(session, run, pages, client)
        en_attente, echecs = batch.recolter(session, run, client)
        assert (en_attente, echecs) == (2, 0)
        assert session.scalar(select(PageTranscription).limit(1)) is None

    def test_un_job_abouti_est_persiste_et_marque_termine(self, session, run, pages):
        client = ClientBouchon()
        self._soumis(session, run, pages, client)
        client.aboutir(
            "j1",
            {str(p.id): _corps(f"**page {p.page_number}**") for p in pages[:3]},
        )
        en_attente, echecs = batch.recolter(session, run, client)
        assert (en_attente, echecs) == (1, 0)
        lignes = session.scalars(
            select(PageTranscription).order_by(PageTranscription.page_number)
        ).all()
        assert [t.page_number for t in lignes] == [3, 4, 5]
        assert lignes[0].text == "page 3"  # normalisé : le markdown est retiré
        assert lignes[0].layout[0]["text"] == "**page 3**"
        assert lignes[0].run_id == run.id
        session.refresh(run)
        assert [lot["termine"] for lot in batch.lots_du_run(run)] == [True, False]
        assert batch.pages_en_attente(run) == {p.id for p in pages[3:]}

    def test_une_page_en_erreur_ou_absente_compte_en_echec(self, session, run, pages):
        client = ClientBouchon()
        self._soumis(session, run, pages, client)
        # j2 couvre deux pages : l'une en erreur, l'autre sans réponse du tout
        client.aboutir("j2", {}, erreurs={str(pages[3].id): "timeout"})
        en_attente, echecs = batch.recolter(session, run, client)
        assert (en_attente, echecs) == (1, 2)
        session.refresh(run)
        assert batch.lots_du_run(run)[1]["statut"] == "SUCCESS"

    def test_attendre_boucle_jusqu_au_dernier_lot(
        self, session, run, pages, monkeypatch
    ):
        client = ClientBouchon()
        self._soumis(session, run, pages, client)
        tours = []

        def dormir(_):
            tours.append(1)
            client.aboutir("j1", {str(p.id): _corps("a") for p in pages[:3]}) if len(
                tours
            ) == 1 else client.aboutir(
                "j2", {str(p.id): _corps("b") for p in pages[3:]}
            )

        monkeypatch.setattr(batch.time, "sleep", dormir)
        echecs = batch.attendre(session, run, client, intervalle_s=0)
        assert echecs == 0
        assert len(tours) == 2
        assert session.scalar(
            select(PageTranscription).where(PageTranscription.run_id == run.id).limit(1)
        )
        assert batch.pages_en_attente(run) == set()


class TestClient:
    def test_les_appels_visent_les_bonnes_routes(self, monkeypatch):
        appels = []

        class Reponse:
            status_code = 200
            text = ""

            def __init__(self, corps):
                self._corps = corps

            def json(self):
                return self._corps

        def post(url, headers=None, json=None, files=None, data=None, timeout=None):
            appels.append(("POST", url, json, data))
            return Reponse({"id": "x"})

        def get(url, headers=None, timeout=None):
            appels.append(("GET", url, None, None))
            return Reponse({"status": "SUCCESS"})

        monkeypatch.setattr(batch.requests, "post", post)
        monkeypatch.setattr(batch.requests, "get", get)
        client = batch.ClientBatch("clef", url="https://api.test/v1/")
        assert client.televerser("lot.jsonl", b"{}") == "x"
        assert client.ouvrir_job("x", "mistral-ocr-latest", {"run_id": "1"}) == "x"
        assert client.job("x")["status"] == "SUCCESS"
        assert appels[0][1] == "https://api.test/v1/files"
        assert appels[0][3] == {"purpose": "batch"}
        assert appels[1][1] == "https://api.test/v1/batch/jobs"
        assert appels[1][2]["endpoint"] == "/v1/ocr"
        assert appels[1][2]["input_files"] == ["x"]
        assert appels[2][1] == "https://api.test/v1/batch/jobs/x"

    def test_une_erreur_http_leve_erreur_ocr(self, monkeypatch):
        class Reponse:
            status_code = 401
            text = "Unauthorized"

        monkeypatch.setattr(batch.requests, "get", lambda *a, **k: Reponse())
        with pytest.raises(batch.ErreurOcr, match="401"):
            batch.ClientBatch("clef").job("j1")
