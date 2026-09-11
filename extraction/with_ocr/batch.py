"""Mistral OCR en batch : moitié prix, résultats en heures, passe reprenable.

En séquentiel, le corpus manuscrit (2 510 pages) coûte ~6 h et le plein
tarif. L'API batch prend un fichier JSONL de requêtes — une par page, image
en base64 —, les traite dans les 24 h et rend un fichier de réponses, à
moitié prix. Les fichiers sont limités à 512 Mo : la passe découpe les pages
en **lots**, téléverse chaque lot et ouvre un job par lot.

Chaque job ouvert est noté dans ``run.parameters["lots"]`` (job, fichier,
pages) et commité aussitôt : une interruption ne perd rien, ``--run-id``
reprend — les lots en attente sont récoltés, pas renvoyés. Les réponses sont
dépouillées comme celles du backend séquentiel (`MistralBackend`).
"""

import base64
import copy
import json
import time
from collections.abc import Iterator

import requests
from sqlalchemy.orm import Session

from database.models import PageExtraction, Run
from extraction.with_ocr.backends import ErreurOcr, MistralBackend
from extraction.with_ocr.config import OcrConfig
from extraction.with_ocr.normalize import normaliser
from extraction.with_ocr.persist import enregistrer
from extraction.with_ocr.render import PdfIntrouvable, rendre_page
from extraction.with_ocr.settings import logger, settings
from extraction.without_ocr.extract_text import wordfreq_quality_score

ETATS_FINAUX = ("SUCCESS", "FAILED", "TIMEOUT_EXCEEDED", "CANCELLED")


class ClientBatch:
    """Les quatre appels de l'API batch : fichier, job, état, contenu."""

    def __init__(self, api_key: str, url: str | None = None):
        self.url = (url or settings.mistral_api_url).rstrip("/")
        self.entetes = {"Authorization": f"Bearer {api_key}"}

    def _verifier(self, reponse: requests.Response, quoi: str) -> requests.Response:
        if reponse.status_code != 200:
            raise ErreurOcr(
                f"{quoi} : HTTP {reponse.status_code} : {reponse.text[:200]}"
            )
        return reponse

    def televerser(self, nom: str, contenu: bytes) -> str:
        """Téléverse un JSONL de requêtes ; rend l'id du fichier."""
        reponse = requests.post(
            f"{self.url}/files",
            headers=self.entetes,
            files={"file": (nom, contenu, "application/jsonl")},
            data={"purpose": "batch"},
            timeout=OcrConfig.MISTRAL_TIMEOUT_S.value * 10,
        )
        return self._verifier(reponse, "téléversement").json()["id"]

    def ouvrir_job(self, file_id: str, model: str, metadata: dict) -> str:
        """Ouvre un job OCR sur le fichier ; rend l'id du job."""
        reponse = requests.post(
            f"{self.url}/batch/jobs",
            headers=self.entetes,
            json={
                "input_files": [file_id],
                "model": model,
                "endpoint": "/v1/ocr",
                "metadata": metadata,
            },
            timeout=OcrConfig.MISTRAL_TIMEOUT_S.value,
        )
        return self._verifier(reponse, "ouverture du job").json()["id"]

    def job(self, job_id: str) -> dict:
        """L'état du job : status, output_file, error_file, compteurs."""
        reponse = requests.get(
            f"{self.url}/batch/jobs/{job_id}",
            headers=self.entetes,
            timeout=OcrConfig.MISTRAL_TIMEOUT_S.value,
        )
        return self._verifier(reponse, f"job {job_id}").json()

    def contenu(self, file_id: str) -> str:
        """Le contenu d'un fichier de réponses (JSONL)."""
        reponse = requests.get(
            f"{self.url}/files/{file_id}/content",
            headers=self.entetes,
            timeout=OcrConfig.MISTRAL_TIMEOUT_S.value * 10,
        )
        return self._verifier(reponse, f"fichier {file_id}").text


def _ligne(page: PageExtraction, image: bytes, model: str, format: str) -> bytes:
    """Une requête OCR, telle que le backend séquentiel l'enverrait."""
    b64 = base64.b64encode(image).decode()
    requete = {
        "custom_id": str(page.id),
        "body": {
            "model": model,
            "document": {
                "type": "image_url",
                "image_url": f"data:image/{format};base64,{b64}",
            },
            "include_image_base64": False,
        },
    }
    return (json.dumps(requete, ensure_ascii=False) + "\n").encode()


def constituer_lots(
    pages: list[PageExtraction],
    *,
    model: str,
    dpi: int,
    format: str,
    taille_max: int = OcrConfig.MISTRAL_BATCH_FILE_MAX_BYTES.value,
) -> Iterator[tuple[list[PageExtraction], bytes]]:
    """Rend les pages et les groupe en fichiers JSONL sous la taille limite.

    Une page qui ne se rend pas (cahier absent, page hors limites) est
    loggée et sautée : elle n'entre dans aucun lot.

    Yields:
        (pages du lot, contenu JSONL), dans l'ordre des pages.
    """
    lot: list[PageExtraction] = []
    lignes: list[bytes] = []
    taille = 0
    for page in pages:
        try:
            image = rendre_page(page.pdf_name, page.page_number, dpi, format)
        except (PdfIntrouvable, ValueError, OSError) as exc:
            logger.warning(
                "page %d (%s p%d) non rendue : %s",
                page.id,
                page.pdf_name,
                page.page_number,
                exc,
            )
            continue
        ligne = _ligne(page, image, model, format)
        if lot and taille + len(ligne) > taille_max:
            yield lot, b"".join(lignes)
            lot, lignes, taille = [], [], 0
        lot.append(page)
        lignes.append(ligne)
        taille += len(ligne)
    if lot:
        yield lot, b"".join(lignes)


def _noter_lots(session: Session, run: Run, lots: list[dict]) -> None:
    """Écrit les lots dans `run.parameters` et commite : rien à perdre.

    La colonne est un JSON sans suivi des mutations : on assigne un nouveau
    dict, et `lots_du_run` rend une copie profonde pour que l'ancienne valeur,
    celle à laquelle SQLAlchemy compare, ne soit jamais modifiée en place.
    """
    run.parameters = {**(run.parameters or {}), "lots": lots}
    session.commit()


def lots_du_run(run: Run) -> list[dict]:
    """Les lots notés dans le run — une copie, à modifier librement."""
    return copy.deepcopy((run.parameters or {}).get("lots", []))


def pages_en_attente(run: Run) -> set[int]:
    """Les pages des lots pas encore récoltés — à ne pas renvoyer."""
    return {
        page_id
        for lot in lots_du_run(run)
        if not lot.get("termine")
        for page_id in lot["pages"]
    }


def soumettre(
    session: Session,
    run: Run,
    client: ClientBatch,
    pages: list[PageExtraction],
    *,
    model: str,
    dpi: int,
    format: str,
) -> int:
    """Téléverse les pages par lots et ouvre un job par lot.

    Returns:
        Le nombre de lots ouverts.
    """
    lots = lots_du_run(run)
    ouverts = 0
    for numero, (pages_du_lot, contenu) in enumerate(
        constituer_lots(pages, model=model, dpi=dpi, format=format), start=1
    ):
        nom = f"run{run.id}-lot{len(lots) + 1}.jsonl"
        logger.info(
            "lot %d : %d page(s), %.0f Mo — téléversement",
            numero,
            len(pages_du_lot),
            len(contenu) / 1e6,
        )
        file_id = client.televerser(nom, contenu)
        try:
            job_id = client.ouvrir_job(
                file_id, model, {"run_id": str(run.id), "lot": nom}
            )
        except ErreurOcr:
            # Le fichier est déjà chez Mistral : le dire, pour qu'on le retire.
            logger.error("fichier %s téléversé sans job — à supprimer", file_id)
            raise
        lots.append(
            {
                "job_id": job_id,
                "fichier": file_id,
                "pages": [p.id for p in pages_du_lot],
                "termine": False,
            }
        )
        _noter_lots(session, run, lots)
        ouverts += 1
        logger.info("lot %d : job %s ouvert", numero, job_id)
    return ouverts


def _depouiller_reponses(contenu: str) -> Iterator[tuple[int, dict | None, str]]:
    """Les lignes d'un fichier de réponses : (page_id, corps ou None, erreur)."""
    for brute in contenu.splitlines():
        if not brute.strip():
            continue
        ligne = json.loads(brute)
        page_id = int(ligne["custom_id"])
        reponse = ligne.get("response") or {}
        erreur = ligne.get("error")
        if erreur or reponse.get("status_code") != 200:
            yield page_id, None, str(erreur or reponse.get("body"))[:200]
        else:
            yield page_id, reponse.get("body") or {}, ""


def recolter(session: Session, run: Run, client: ClientBatch) -> tuple[int, int]:
    """Persiste les lots aboutis, laisse les autres en attente.

    Returns:
        (lots encore en attente, pages en échec dans les lots récoltés).
    """
    lots = lots_du_run(run)
    en_attente = 0
    echecs = 0
    for lot in lots:
        if lot.get("termine"):
            continue
        etat = client.job(lot["job_id"])
        statut = etat.get("status")
        if statut not in ETATS_FINAUX:
            en_attente += 1
            logger.info(
                "job %s : %s (%s/%s)",
                lot["job_id"],
                statut,
                etat.get("completed_requests", "?"),
                etat.get("total_requests", "?"),
            )
            continue
        pages = {
            p.id: p
            for p in session.query(PageExtraction).filter(
                PageExtraction.id.in_(lot["pages"])
            )
        }
        vues: set[int] = set()
        persistees = 0
        for file_id in (etat.get("output_file"), etat.get("error_file")):
            if not file_id:
                continue
            for page_id, corps, erreur in _depouiller_reponses(client.contenu(file_id)):
                vues.add(page_id)
                page = pages.get(page_id)
                if page is None or corps is None:
                    logger.warning(
                        "page %s en échec : %s", page_id, erreur or "inconnue"
                    )
                    echecs += 1
                    continue
                resultat = MistralBackend._depouiller(corps, 0.0)
                texte = normaliser(resultat.texte)
                enregistrer(
                    session,
                    run,
                    page,
                    texte,
                    resultat.layout,
                    round(wordfreq_quality_score(texte), 3),
                )
                persistees += 1
        manquantes = set(lot["pages"]) - vues
        if manquantes or statut != "SUCCESS":
            logger.warning(
                "job %s : %s, %d page(s) sans réponse",
                lot["job_id"],
                statut,
                len(manquantes),
            )
            echecs += len(manquantes)
        lot["termine"] = True
        lot["statut"] = statut
        _noter_lots(session, run, lots)
        logger.info(
            "job %s : %s — %d page(s) persistées", lot["job_id"], statut, persistees
        )
    return en_attente, echecs


def attendre(
    session: Session,
    run: Run,
    client: ClientBatch,
    *,
    intervalle_s: int = OcrConfig.MISTRAL_BATCH_POLL_S.value,
) -> int:
    """Récolte les lots à mesure qu'ils aboutissent, jusqu'au dernier.

    Returns:
        Le nombre de pages en échec.
    """
    echecs = 0
    while True:
        en_attente, nouveaux = recolter(session, run, client)
        echecs += nouveaux
        if not en_attente:
            return echecs
        time.sleep(intervalle_s)
