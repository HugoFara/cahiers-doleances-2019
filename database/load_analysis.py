import json
import sys
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from database.db import check_connection, get_engine
from database.models import Contribution, Instance, PageExtraction, Topic

DEFAUT = Path(__file__).resolve().parent.parent / "analyse" / "analysis_v4"


def _propre(valeur):
    """Retire les caractères NUL : PostgreSQL les refuse en text.

    La livraison en contient dans les noms, descriptions, extraits et
    justifications. On nettoie AUSSI le nom côté label, sinon il ne
    correspondrait plus au nom nettoyé du topic et la jointure casserait.
    """
    return valeur.replace("\x00", "") if isinstance(valeur, str) else valeur


def charger_topics(session: Session, topics: list[dict]) -> dict[str, int]:
    """Upsert des topics par external_id. Renvoie {external_id: topic.id}."""
    connus = {t.external_id: t for t in session.query(Topic).all() if t.external_id}
    for t in topics:
        ligne = connus.get(t["id"])
        if ligne is None:
            ligne = Topic(external_id=t["id"])
            session.add(ligne)
            connus[t["id"]] = ligne
        ligne.name = _propre(t["name"])
        ligne.description = _propre(t["description"])
        ligne.level = t["level"]
        ligne.validated = t["validated"]
    session.flush()  # attribue les id auto-incrémentés
    return {ext: ligne.id for ext, ligne in connus.items()}


def rattacher_parents(session: Session, topics: list[dict], ids: dict[str, int]) -> int:
    """Deuxième passe : `parent` est un UUID, il faut que tous les topics existent."""
    orphelins = 0
    par_ext = {t.external_id: t for t in session.query(Topic).all() if t.external_id}
    for t in topics:
        parent_ext = t.get("parent")
        cible = ids.get(parent_ext) if parent_ext else None
        if parent_ext and cible is None:
            orphelins += 1  # parent absent de la livraison
        par_ext[t["id"]].parent_id = cible
    session.flush()
    return orphelins


def resoudre_contribution(external_doc_id: str, contributions_connues: set[int]) -> int | None:
    """Rapproche l'id de document de la livraison d'une contribution existante.

    `database/export_dataset.py` produit le dataset d'entrée de l'analyse avec
    `contribution.id` comme id de document : la livraison nous le renvoie tel
    quel et le rapprochement est immédiat.

    Attention : ce rapprochement ne prouve rien à lui seul. Les livraisons
    antérieures numérotent les documents par leur position dans le CSV (0, 1,
    2…), et ces entiers tombent dans la plage des `contribution.id` existants :
    le dump du POC d'août va de 0 à 1523, tous « reconnus » ici alors qu'ils
    désignent un tout autre corpus. C'est `mesurer_correspondance` qui tranche,
    en vérifiant que les verbatims sont bien dans le texte des contributions
    visées.
    """
    try:
        contribution_id = int(external_doc_id)
    except (TypeError, ValueError):
        return None
    return contribution_id if contribution_id in contributions_connues else None


# En dessous de ce taux, les identifiants de la livraison ne désignent pas nos
# contributions : on préfère ne rien rattacher plutôt que rattacher au hasard.
SEUIL_CORRESPONDANCE = 0.3
# Les verbatims sont parfois reformulés par le modèle : on compare des débuts
# de phrase, et seulement sur un échantillon, la vérification étant indicative.
LONGUEUR_COMPAREE = 40
TAILLE_ECHANTILLON = 50


def _normaliser(valeur: str) -> str:
    """Minuscules et espaces normalisés, pour comparer verbatim et texte source."""
    return " ".join(valeur.replace("\u2212", "-").replace("\u2019", "'").split()).lower()


def taux_correspondance(paires: list[tuple[str, str]]) -> float:
    """Proportion de verbatims réellement présents dans le texte visé.

    Args:
        paires: couples (verbatim, texte de la contribution rapprochée).

    Returns:
        Un ratio entre 0 et 1, ou 0.0 si aucune paire n'est fournie.
    """
    if not paires:
        return 0.0
    trouves = sum(
        1
        for verbatim, texte in paires
        if _normaliser(verbatim)[:LONGUEUR_COMPAREE] in _normaliser(texte)
    )
    return trouves / len(paires)


def mesurer_correspondance(
    session: Session, documents: list[dict], contributions_connues: set[int]
) -> tuple[float, int]:
    """Vérifie sur un échantillon que la livraison parle bien de nos contributions.

    Returns:
        (taux de correspondance, nombre de paires testées).
    """
    candidats = []
    for doc in documents:
        contribution_id = resoudre_contribution(str(doc["id"]), contributions_connues)
        if contribution_id is None:
            continue
        for lab in doc["labels"]:
            extrait = lab.get("extract")
            if extrait:
                candidats.append((contribution_id, extrait))
                break
        if len(candidats) >= TAILLE_ECHANTILLON:
            break
    if not candidats:
        return 0.0, 0

    textes = dict(
        session.execute(
            select(PageExtraction.contribution_id, PageExtraction.text).where(
                PageExtraction.contribution_id.in_([c for c, _ in candidats])
            )
        ).all()
    )
    paires = [(v, textes.get(c, "")) for c, v in candidats]
    return taux_correspondance(paires), len(paires)


def charger_instances(
    session: Session,
    documents: list[dict],
    ids_par_nom: dict[str, int],
    contributions_connues: set[int],
    rattacher: bool = True,
) -> tuple[int, int]:
    """Remplace toutes les instances par celles de la livraison.

    Renvoie (labels sans topic ignorés, instances rattachées à une contribution).
    """
    session.execute(text("DELETE FROM instance"))
    inconnus = 0
    rattachees = 0
    for doc in documents:
        contribution_id = (
            resoudre_contribution(str(doc["id"]), contributions_connues)
            if rattacher
            else None
        )
        for lab in doc["labels"]:
            topic_id = ids_par_nom.get(_propre(lab["name"]))
            if topic_id is None:
                inconnus += 1
                continue
            rattachees += contribution_id is not None
            session.add(Instance(
                contribution_id=contribution_id,
                external_doc_id=str(doc["id"]),
                topic_id=topic_id,
                verbatim=_propre(lab["extract"]),
                summary=_propre(lab["rationale"]),
            ))
    return inconnus, rattachees


def main(dossier: Path = DEFAUT) -> None:
    topics = json.loads((dossier / "taxonomy.json").read_text())["topics"]
    documents = json.loads((dossier / "instances.json").read_text())["documents"]
    print(f"livraison : {len(topics)} topics · {len(documents)} documents")

    engine = get_engine()
    check_connection(engine)

    with Session(engine) as session:
        ids = charger_topics(session, topics)
        print(f"  topics synchronisés : {len(ids)}")

        orphelins = rattacher_parents(session, topics, ids)
        print(f"  parents rattachés ({orphelins} parent(s) introuvable(s) -> NULL)")

        ids_par_nom = {t.name: t.id for t in session.query(Topic).all()}
        contributions_connues = {c.id for c in session.query(Contribution.id).all()}

        taux, testes = mesurer_correspondance(session, documents, contributions_connues)
        rattacher = testes > 0 and taux >= SEUIL_CORRESPONDANCE
        if testes == 0:
            print("  aucun id de document ne correspond à une contribution")
        else:
            print(f"  correspondance vérifiée : {taux:.0%} sur {testes} verbatim(s)")
        if testes > 0 and not rattacher:
            print(
                "  -> rattachement ABANDONNÉ : les identifiants de la livraison "
                "tombent dans la plage des contribution.id mais désignent un "
                "autre corpus. Les instances sont chargées sans contribution_id."
            )

        inconnus, rattachees = charger_instances(
            session, documents, ids_par_nom, contributions_connues, rattacher
        )
        print(f"  instances chargées ({inconnus} label(s) sans topic -> ignoré(s))")
        print(f"  instances rattachées à une contribution : {rattachees}")

        session.commit()

        for modele in (Topic, Instance):
            print(f"{modele.__tablename__}: {session.query(modele).count()} lignes")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAUT)
