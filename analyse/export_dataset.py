"""Exporte les contributions de la base vers le dataset CSV de topic-builder.

C'est le chaînon manquant entre l'extraction et l'analyse : `extraction/`
écrit le texte page par page dans `page_extraction`, alors que
`topicbuilder screen` ne sait lire que des `.txt`/`.md` sur disque. Ce script
lit la base et produit directement le CSV `id,content` attendu par
`topicbuilder discover-topics` et `topicbuilder label`.

**L'`id` est `contribution.id`.** C'est le point important : la livraison de
l'équipe analyse renvoie ses labels indexés par l'`id` du document d'entrée
(`instances.json`, champ `documents[].id`). En donnant l'id de la
contribution comme identifiant de document, `load_analysis.py` peut résoudre
`instance.contribution_id` au lieu de le laisser à NULL — ce qui est
aujourd'hui la limite connue de la vue graphe et de la vue par commune.

Deux niveaux d'export, `--niveau` :

- `contribution` (défaut) : une ligne = une contribution, ses pages concaténées.
  C'est une page dans le pipeline actuel — plusieurs contributeurs peuvent s'y
  côtoyer, et une doléance longue y est coupée en deux.
- `doleance` : une ligne = le texte d'un contributeur, tel que `segmentation/`
  l'a découpé. C'est la bonne unité d'analyse ; les ids y sont préfixés `d`
  (voir `analyse/identifiants.py`).

Utilisation :
    uv run python -m analyse.export_dataset --output dataset.csv
    uv run python -m analyse.export_dataset --niveau doleance --output dataset.csv
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from analyse.identifiants import CONTRIBUTION, DOLEANCE, NIVEAUX, id_document
from database.db import check_connection, get_engine
from database.models import Doleance, PageExtraction
from database.runs import SEGMENTATION, run_actif

DEFAUT = Path("data/dataset.csv")


def lire_pages(session: Session, garder_pages_ocr: bool = False) -> list[PageExtraction]:
    """Lit les pages extraites, les manuscrites exclues par défaut.

    Les pages `needs_ocr` sont celles dont le score de qualité est trop bas :
    leur texte est du bruit d'extraction, il ferait dériver la découverte de
    thèmes. On les garde optionnellement pour inspecter le corpus complet.
    """
    requete = select(PageExtraction).order_by(
        PageExtraction.contribution_id, PageExtraction.page_number
    )
    if not garder_pages_ocr:
        requete = requete.where(PageExtraction.needs_ocr.is_not(True))
    return list(session.scalars(requete))


def construire_documents(pages: list[PageExtraction]) -> list[dict[str, str]]:
    """Regroupe les pages par contribution et renvoie les lignes `id,content`.

    Les pages arrivent déjà triées par (contribution, page) ; on conserve cet
    ordre pour que le texte reconstitué suive celui du cahier. Les
    contributions dont il ne reste aucun texte (cahier entièrement manuscrit,
    pages vides) sont écartées : topic-builder ne fait pas d'appel LLM dessus,
    autant ne pas les écrire.
    """
    par_contribution: dict[int, list[str]] = defaultdict(list)
    for page in pages:
        # contribution_id est nullable : une page orpheline donnerait un document
        # d'id "None", impossible à rattacher au retour de l'analyse.
        if page.contribution_id is None:
            continue
        if page.text and page.text.strip():
            par_contribution[page.contribution_id].append(page.text.strip())

    return [
        {"id": id_document(CONTRIBUTION, contribution_id), "content": "\n".join(textes)}
        for contribution_id, textes in par_contribution.items()
        if textes
    ]


def lire_doleances(session: Session, run_id: int | None = None) -> list[Doleance]:
    """Lit les doléances d'un découpage, dans l'ordre de lecture des cahiers.

    Le filtre sur le run n'est pas optionnel dans les faits : plusieurs
    découpages peuvent coexister, exporter la table entière mélangerait deux
    lectures du même corpus et doublerait les documents.

    Args:
        session: session ouverte sur la base.
        run_id: découpage à exporter ; ``None`` prend le run actif.

    Returns:
        Les doléances du run, vide s'il n'y a aucun découpage.
    """
    if run_id is None:
        run = run_actif(session, SEGMENTATION)
        if run is None:
            return []
        run_id = run.id
    return list(
        session.scalars(
            select(Doleance)
            .where(Doleance.run_id == run_id)
            .order_by(Doleance.pdf_name, Doleance.position)
        )
    )


def construire_documents_doleances(doleances: list[Doleance]) -> list[dict[str, str]]:
    """Une ligne `id,content` par doléance, les vides écartées."""
    return [
        {"id": id_document(DOLEANCE, d.id), "content": d.text.strip()}
        for d in doleances
        if d.text and d.text.strip()
    ]


def ecrire_dataset(documents: list[dict[str, str]], chemin: Path) -> None:
    """Écrit le CSV `id,content` attendu par topic-builder."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "content"])
        writer.writeheader()
        writer.writerows(documents)


def main(
    chemin: Path = DEFAUT,
    garder_pages_ocr: bool = False,
    niveau: str = CONTRIBUTION,
) -> int:
    engine = get_engine()
    check_connection(engine)

    with Session(engine) as session:
        if niveau == DOLEANCE:
            run = run_actif(session, SEGMENTATION)
            doleances = lire_doleances(session)
            documents = construire_documents_doleances(doleances)
            origine = f" (run #{run.id} « {run.label} »)" if run else ""
            lues = f"{len(doleances)} doléance(s) lue(s){origine}"
            vide = (
                "Aucune doléance à exporter. Les cahiers ont-ils été découpés "
                "(uv run python -m segmentation) ?"
            )
        else:
            pages = lire_pages(session, garder_pages_ocr)
            documents = construire_documents(pages)
            lues = f"{len(pages)} page(s) lue(s)"
            vide = (
                "Aucun texte à exporter. La table page_extraction est-elle remplie "
                "(uv run python -m extraction.without_ocr) ?"
            )

    if not documents:
        print(vide, file=sys.stderr)
        return 1

    ecrire_dataset(documents, chemin)
    mots = sum(len(d["content"].split()) for d in documents)
    print(f"{len(documents)} document(s) « {niveau} » · {lues} · {mots} mots -> {chemin}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--output", type=Path, default=DEFAUT, help=f"chemin du CSV de sortie (défaut : {DEFAUT})"
    )
    parser.add_argument(
        "--keep-ocr-pages",
        action="store_true",
        help="inclure aussi les pages manuscrites (needs_ocr), du bruit par défaut écarté",
    )
    parser.add_argument(
        "--niveau",
        choices=NIVEAUX,
        default=CONTRIBUTION,
        help="unité exportée (défaut : contribution ; doleance = texte d'un contributeur)",
    )
    args = parser.parse_args()
    sys.exit(main(args.output, args.keep_ocr_pages, args.niveau))
