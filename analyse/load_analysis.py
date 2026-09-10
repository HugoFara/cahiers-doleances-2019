"""Charge une livraison de l'équipe analyse — une grille de thèmes et ses détections.

Une livraison, c'est un dossier avec `taxonomy.json` (les thèmes, leur parenté,
leur description) et `instances.json` (par document, les thèmes détectés et
leurs extraits). Elle devient un run de genre `analyse` : la grille est une
lecture du corpus, datée, attribuée, et plusieurs coexistent.

Le rattachement des détections aux textes passe par l'identifiant de document
(`identifiants.py`) et se vérifie par les verbatims : en dessous de
`SEUIL_CORRESPONDANCE`, la livraison ne décrit pas ce corpus et n'y est pas
rattachée.

Utilisation :
    uv run python -m analyse.load_analysis <dossier>
    uv run python -m analyse.load_analysis <dossier> --nouveau-run --label "v5"
"""

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from analyse.identifiants import CONTRIBUTION, DOLEANCE, lire_id_document
from database.db import check_connection, get_engine
from database.models import Contribution, Doleance, Instance, PageExtraction, Run, Topic
from database.runs import ANALYSE, activer_run, creer_run, run_par_source


def _propre(valeur):
    """Retire les caractères NUL : PostgreSQL les refuse en text.

    La livraison en contient dans les noms, descriptions, extraits et
    justifications. On nettoie AUSSI le nom côté label, sinon il ne
    correspondrait plus au nom nettoyé du topic et la jointure casserait.
    """
    return valeur.replace("\x00", "") if isinstance(valeur, str) else valeur


def charger_topics(session: Session, topics: list[dict], run_id: int) -> dict[str, int]:
    """Upsert des topics de ce run par external_id. Renvoie {external_id: topic.id}.

    Le filtre sur le run est ce qui autorise deux grilles concurrentes : hors de
    lui, l'UUID d'une livraison écraserait le thème homonyme d'une autre.
    """
    connus = {
        t.external_id: t
        for t in session.query(Topic).filter(Topic.run_id == run_id).all()
        if t.external_id
    }
    for t in topics:
        ligne = connus.get(t["id"])
        if ligne is None:
            ligne = Topic(run_id=run_id, external_id=t["id"])
            session.add(ligne)
            connus[t["id"]] = ligne
        ligne.name = _propre(t["name"])
        ligne.description = _propre(t["description"])
        ligne.level = t["level"]
        ligne.validated = t["validated"]
    session.flush()  # attribue les id auto-incrémentés
    return {ext: ligne.id for ext, ligne in connus.items()}


def rattacher_parents(
    session: Session, topics: list[dict], ids: dict[str, int], run_id: int
) -> int:
    """Deuxième passe : `parent` est un UUID, il faut que tous les topics existent."""
    orphelins = 0
    par_ext = {
        t.external_id: t
        for t in session.query(Topic).filter(Topic.run_id == run_id).all()
        if t.external_id
    }
    for t in topics:
        parent_ext = t.get("parent")
        cible = ids.get(parent_ext) if parent_ext else None
        if parent_ext and cible is None:
            orphelins += 1  # parent absent de la livraison
        par_ext[t["id"]].parent_id = cible
    session.flush()
    return orphelins


@dataclass(frozen=True)
class Cibles:
    """Les documents que la base sait reconnaître dans une livraison.

    Une livraison porte soit sur des contributions, soit sur des doléances,
    selon le `--niveau` avec lequel `export_dataset.py` a produit son entrée.
    Les deux tables ont des id qui se recouvrent, d'où le préfixe des ids de
    doléance (`analyse/identifiants.py`).
    """

    contributions: set[int]
    # doleance.id -> contribution.id de sa page d'ouverture (parfois NULL)
    doleances: dict[int, int | None]

    @classmethod
    def depuis(cls, session: Session) -> "Cibles":
        """Lit en base les contributions et les doléances rattachables."""
        return cls(
            contributions={c.id for c in session.query(Contribution.id).all()},
            doleances=dict(
                session.execute(select(Doleance.id, Doleance.contribution_id)).all()
            ),
        )


def resoudre_document(external_doc_id: str, cibles: Cibles) -> tuple[str, int] | None:
    """Rapproche l'id de document de la livraison d'une ligne existante.

    `analyse/export_dataset.py` produit le dataset d'entrée de l'analyse avec
    la clé primaire de la ligne exportée comme id de document : la livraison
    nous la renvoie telle quelle et le rapprochement est immédiat.

    Attention : ce rapprochement ne prouve rien à lui seul. Les livraisons
    antérieures numérotent les documents par leur position dans le CSV (0, 1,
    2…), et ces entiers tombent dans la plage des `contribution.id` existants :
    le dump du POC d'août va de 0 à 1523, tous « reconnus » ici alors qu'ils
    désignent un tout autre corpus. C'est `mesurer_correspondance` qui tranche,
    en vérifiant que les verbatims sont bien dans le texte des lignes visées.

    Args:
        external_doc_id: l'id du document dans la livraison.
        cibles: ce que la base connaît.

    Returns:
        Le couple (niveau, id) désigné, ou ``None`` si rien ne correspond.
    """
    lu = lire_id_document(external_doc_id)
    if lu is None:
        return None
    niveau, identifiant = lu
    if niveau == DOLEANCE:
        return lu if identifiant in cibles.doleances else None
    return lu if identifiant in cibles.contributions else None


def rattachements(cle: tuple[str, int], cibles: Cibles) -> tuple[int | None, int | None]:
    """Traduit une cible résolue en (contribution_id, doleance_id).

    Une instance rattachée à une doléance reçoit *aussi* la contribution de
    celle-ci : les vues de l'app joignent sur `contribution_id`, elles
    continuent de fonctionner sans connaître le nouveau niveau.
    """
    niveau, identifiant = cle
    if niveau == DOLEANCE:
        return cibles.doleances.get(identifiant), identifiant
    return identifiant, None


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


def textes_des_cibles(
    session: Session, cles: list[tuple[str, int]]
) -> dict[tuple[str, int], str]:
    """Texte source de chaque cible, pour y chercher les verbatims.

    Args:
        session: session ouverte sur la base.
        cles: couples (niveau, id) à lire.

    Returns:
        ``{(niveau, id): texte}``, les cibles absentes en moins.
    """
    contributions = [i for niveau, i in cles if niveau == CONTRIBUTION]
    doleances = [i for niveau, i in cles if niveau == DOLEANCE]
    textes: dict[tuple[str, int], str] = {}

    if contributions:
        # Une contribution peut porter plusieurs pages : les recoller, sinon le
        # verbatim d'une page tardive serait déclaré absent.
        pages: dict[int, list[str]] = defaultdict(list)
        for contribution_id, texte in session.execute(
            select(PageExtraction.contribution_id, PageExtraction.text).where(
                PageExtraction.contribution_id.in_(contributions)
            )
        ).all():
            if texte:
                pages[contribution_id].append(texte)
        textes.update(
            {(CONTRIBUTION, cid): "\n".join(t) for cid, t in pages.items()}
        )

    if doleances:
        for doleance_id, texte in session.execute(
            select(Doleance.id, Doleance.text).where(Doleance.id.in_(doleances))
        ).all():
            textes[(DOLEANCE, doleance_id)] = texte or ""

    return textes


def mesurer_correspondance(
    session: Session, documents: list[dict], cibles: Cibles
) -> tuple[float, int]:
    """Vérifie sur un échantillon que la livraison parle bien de notre corpus.

    Returns:
        (taux de correspondance, nombre de paires testées).
    """
    candidats: list[tuple[tuple[str, int], str]] = []
    for doc in documents:
        cle = resoudre_document(str(doc["id"]), cibles)
        if cle is None:
            continue
        for lab in doc["labels"]:
            extrait = lab.get("extract")
            if extrait:
                candidats.append((cle, extrait))
                break
        if len(candidats) >= TAILLE_ECHANTILLON:
            break
    if not candidats:
        return 0.0, 0

    textes = textes_des_cibles(session, [cle for cle, _ in candidats])
    paires = [(v, textes.get(cle, "")) for cle, v in candidats]
    return taux_correspondance(paires), len(paires)


def charger_instances(
    session: Session,
    documents: list[dict],
    ids_par_nom: dict[str, int],
    cibles: Cibles,
    run_id: int,
    rattacher: bool = True,
) -> tuple[int, int]:
    """Remplace les instances **de ce run** par celles de la livraison.

    Recharger une livraison ne touche plus aux autres grilles : c'est la
    différence entre versionner une couche et l'écraser.

    Renvoie (labels sans topic ignorés, instances rattachées à un document).
    """
    session.execute(
        text("DELETE FROM instance WHERE run_id = :run_id"), {"run_id": run_id}
    )
    inconnus = 0
    rattachees = 0
    for doc in documents:
        cle = resoudre_document(str(doc["id"]), cibles) if rattacher else None
        contribution_id, doleance_id = (
            rattachements(cle, cibles) if cle is not None else (None, None)
        )
        for lab in doc["labels"]:
            topic_id = ids_par_nom.get(_propre(lab["name"]))
            if topic_id is None:
                inconnus += 1
                continue
            rattachees += cle is not None
            session.add(Instance(
                run_id=run_id,
                contribution_id=contribution_id,
                doleance_id=doleance_id,
                external_doc_id=str(doc["id"]),
                topic_id=topic_id,
                verbatim=_propre(lab["extract"]),
                summary=_propre(lab["rationale"]),
            ))
    return inconnus, rattachees


def resoudre_run(
    session: Session,
    dossier: Path,
    *,
    label: str | None,
    nouveau: bool,
    auteur: str | None,
    modele: str | None,
    version_prompt: str | None,
    nb_topics: int,
    nb_documents: int,
) -> "Run":
    """Le run de cette livraison : le sien s'il existe déjà, un neuf sinon.

    Recharger la même livraison la met à jour ; `nouveau` force une grille de
    plus, pour comparer deux passages du même corpus.
    """
    source = str(dossier)
    existant = None if nouveau else run_par_source(session, ANALYSE, source)
    if existant is not None:
        activer_run(session, existant)
        print(f"run d'analyse repris : #{existant.id} « {existant.label} »")
        return existant

    run = creer_run(
        session,
        ANALYSE,
        label=label or dossier.name,
        source=source,
        model=modele,
        prompt_version=version_prompt,
        parameters={"topics": nb_topics, "documents": nb_documents},
        corpus=f"{nb_documents} document(s) labellisé(s)",
        author=auteur,
    )
    print(f"run d'analyse créé : #{run.id} « {run.label} »")
    return run


def main(
    dossier: Path,
    *,
    label: str | None = None,
    nouveau_run: bool = False,
    auteur: str | None = None,
    modele: str | None = None,
    version_prompt: str | None = None,
) -> None:
    topics = json.loads((dossier / "taxonomy.json").read_text())["topics"]
    documents = json.loads((dossier / "instances.json").read_text())["documents"]
    print(f"livraison : {len(topics)} topics · {len(documents)} documents")

    engine = get_engine()
    check_connection(engine)

    with Session(engine) as session:
        run = resoudre_run(
            session,
            dossier,
            label=label,
            nouveau=nouveau_run,
            auteur=auteur,
            modele=modele,
            version_prompt=version_prompt,
            nb_topics=len(topics),
            nb_documents=len(documents),
        )
        run_id = run.id
        run_auteur = run.author

        ids = charger_topics(session, topics, run_id)
        print(f"  topics synchronisés : {len(ids)}")

        orphelins = rattacher_parents(session, topics, ids, run_id)
        print(f"  parents rattachés ({orphelins} parent(s) introuvable(s) -> NULL)")

        # Noms scopés au run : deux grilles peuvent nommer un thème pareil.
        ids_par_nom = {
            t.name: t.id
            for t in session.query(Topic).filter(Topic.run_id == run_id).all()
        }
        cibles = Cibles.depuis(session)

        taux, testes = mesurer_correspondance(session, documents, cibles)
        rattacher = testes > 0 and taux >= SEUIL_CORRESPONDANCE
        if testes == 0:
            print("  aucun id de document ne correspond à notre corpus")
        else:
            print(f"  correspondance vérifiée : {taux:.0%} sur {testes} verbatim(s)")
        if testes > 0 and not rattacher:
            print(
                "  -> rattachement ABANDONNÉ : les identifiants de la livraison "
                "tombent dans la plage des contribution.id mais désignent un "
                "autre corpus. Les instances sont chargées sans contribution_id."
            )

        inconnus, rattachees = charger_instances(
            session, documents, ids_par_nom, cibles, run_id, rattacher
        )
        print(f"  instances chargées ({inconnus} label(s) sans topic -> ignoré(s))")
        print(f"  instances rattachées à un document : {rattachees}")

        session.commit()

        for modele_orm in (Topic, Instance):
            total = session.query(modele_orm).count()
            dans_le_run = (
                session.query(modele_orm).filter(modele_orm.run_id == run_id).count()
            )
            print(f"{modele_orm.__tablename__}: {dans_le_run} lignes dans ce run "
                  f"· {total} au total (toutes grilles)")

    print(f"run attribué à : {run_auteur}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Charge une livraison de l'équipe analyse.")
    parser.add_argument(
        "dossier", type=Path, help="dossier contenant taxonomy.json et instances.json"
    )
    parser.add_argument("--label", help="nom lisible de la grille (défaut : nom du dossier)")
    parser.add_argument(
        "--nouveau-run", action="store_true",
        help="charger en une grille de plus au lieu de mettre à jour celle de ce dossier",
    )
    parser.add_argument(
        "--auteur",
        help="qui a produit la livraison (défaut : la configuration git du dépôt)",
    )
    parser.add_argument("--modele", help="modèle LLM ayant produit la grille")
    parser.add_argument("--version-prompt", help="version du prompt employé")
    args = parser.parse_args()
    main(
        args.dossier,
        label=args.label,
        nouveau_run=args.nouveau_run,
        auteur=args.auteur,
        modele=args.modele,
        version_prompt=args.version_prompt,
    )
