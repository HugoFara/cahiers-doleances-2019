import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from gradio_app.source import libelle_page, lien_source
from insee.communes import libelle_commune, regrouper

# Constantes
ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")
engine = create_engine(
    URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        database=os.environ["DB_NAME"],
    ),
    pool_pre_ping=True,
)

# Code de remplissage employé à la source quand la commune n'est pas
# renseignée. Ce n'est pas un code INSEE : il sert ici de valeur de sélection
# pour les cahiers qui n'en ont pas, plutôt que de les laisser invisibles.
SANS_COMMUNE = "00000"

#  Plusieurs grilles de thèmes coexistent en base (voir database/runs.py) : sans
#  filtre, l'app les afficherait empilées, et les noms de thèmes — uniques dans
#  une grille, pas dans la table — se confondraient d'une grille à l'autre. On
#  ne sert donc que la grille active, dans **toutes** les vues : la vue commune
#  n'avait pas ce filtre et cumulait les détections de toutes les grilles.
#
#  Écrit en sous-requête plutôt qu'en paramètre Python : quand aucune grille
#  n'est active, la sous-requête vaut NULL, la comparaison n'est jamais vraie et
#  les vues sont vides — exactement ce qu'on veut sur une base pas encore
#  chargée, sans branchement supplémentaire.
GRILLE_SERVIE = "(SELECT id FROM run WHERE kind = 'analyse' AND active)"
DECOUPAGE_SERVI = "(SELECT id FROM run WHERE kind = 'segmentation' AND active)"


def _graphies() -> dict[str, list[str]]:
    """{graphie affichée: toutes les graphies de la même commune}.

    Une même commune est écrite différemment selon les PDF (« AHUILLE » /
    « AHUILLÉ ») : sans ce regroupement la liste en propose deux, dont chacune
    ne montre qu'une partie des contributions.

    Ne sert plus au sélecteur, qui passe par le code INSEE, mais reste la
    meilleure graphie disponible quand le référentiel n'a pas de nom officiel.
    """
    # la commune est parsée du PDF : elle est vide quand l'extraction a échoué.
    q = text("""
        SELECT DISTINCT city FROM contribution
        WHERE city IS NOT NULL AND btrim(city) <> ''
    """)
    return regrouper(pd.read_sql(q, engine)["city"].tolist())


def list_communes() -> list[tuple[str, str]]:
    """(libellé affiché, code INSEE), une entrée par commune du corpus.

    **Le sélecteur repose sur le code, plus sur la graphie de l'en-tête.**
    Celle-ci manque sur un tiers des cahiers : 153 communes n'avaient aucune
    entrée dans la liste et 2 169 contributions sur 5 365 — 40 % — n'étaient
    atteignables par aucun chemin de l'app. Château-Gontier-sur-Mayenne et ses
    cent contributions en faisaient partie.

    Le libellé préfère le nom officiel du Code officiel géographique, retombe
    sur la graphie du corpus, puis sur le code seul — jamais rien.
    """
    q = text("""
        SELECT k.city_code AS code,
               max(v.official_name) AS officiel,
               max(v.name) AS graphie,
               count(*) AS contributions
        FROM contribution k
        LEFT JOIN city v ON v.code = k.city_code
        GROUP BY k.city_code
    """)
    lignes = pd.read_sql(q, engine).to_dict("records")
    communes = []
    for ligne in lignes:
        code = ligne["code"]
        if code is None:
            communes.append((
                f"— commune non renseignée ({ligne['contributions']})",
                SANS_COMMUNE,
            ))
            continue
        communes.append((libelle_commune(ligne["officiel"], ligne["graphie"], code), code))
    # Les cahiers sans commune en dernier : ce sont des exceptions, pas une
    # entrée de navigation.
    return sorted(communes, key=lambda c: (c[1] == SANS_COMMUNE, c[0]))





def _rows(code: str) -> pd.DataFrame:
    """Les contributions d'une commune, désignée par son code INSEE."""
    # une seule extraction affichée par contribution : la plus récente
    q = text(f"""
        SELECT k.id, k.city, k.pdf_file, k.start_page, k.end_page, k.is_handwritten,
               e.ocr, e.text, e.num_words, e.num_lines,
               a.is_anonymized, a.is_of_interest,
               (SELECT string_agg(r.name, ', ') FROM instance t
                 JOIN topic r ON r.id = t.topic_id
                 WHERE t.contribution_id = k.id
                   AND t.run_id = {GRILLE_SERVIE}) AS topics,
               (SELECT string_agg(name, ', ') FROM feeling
                 WHERE contribution_id = k.id) AS feelings
        FROM contribution k
        LEFT JOIN extraction e ON e.id = (
            SELECT max(id) FROM extraction WHERE contribution_id = k.id
        )
        LEFT JOIN annotation a ON a.contribution_id = k.id
        WHERE (:code = '' AND k.city_code IS NULL) OR k.city_code = :code
        ORDER BY k.id
    """)
    # Chaîne vide plutôt que NULL en paramètre : `k.city_code = NULL` n'est
    # jamais vrai, la clause aurait silencieusement rendu zéro ligne.
    return pd.read_sql(q, engine, params={"code": "" if code == SANS_COMMUNE else code})

def _topic_instances(contribution_id: int) -> pd.DataFrame:
    """Les instances de thèmes d'une contribution, avec leur page source.

    La page vient de la doléance quand la détection y est rattachée, de la
    contribution sinon : une livraison au niveau page ne sait pas dire mieux que
    la page, et c'est déjà le retour à la source que le plan demande.
    """
    q = text(f"""
        SELECT r.name, t.verbatim, t.summary,
               coalesce(d.start_page, k.start_page) AS page,
               coalesce(d.pdf_name, k.pdf_file) AS cahier
        FROM instance t
        JOIN topic r ON r.id = t.topic_id
        LEFT JOIN doleance d ON d.id = t.doleance_id
        LEFT JOIN contribution k ON k.id = t.contribution_id
        WHERE t.contribution_id = :cid
          AND t.run_id = {GRILLE_SERVIE}
        ORDER BY t.id
    """)
    return pd.read_sql(q, engine, params={"cid": contribution_id})


def _etiquette_source(nom: str, cahier, page) -> str:
    """« **thème** » ou « [**thème**](url#page=N) » selon que le cahier réponde.

    Un lien mort vaut moins qu'un libellé nu : quand le PDF est introuvable, le
    nom reste affiché tel quel.
    """
    if pd.isna(cahier):
        return f"**{nom}**"
    url = lien_source(str(cahier), None if pd.isna(page) else int(page))
    if url is None:
        return f"**{nom}**"
    return f"[**{nom}** ({libelle_page(None if pd.isna(page) else int(page))})]({url})"

def _int(value) -> str:
    """Entier en texte, ou 'N/C' si manquant."""
    return "N/C" if pd.isna(value) else str(int(value))

def _text(value) -> str:
    """Valeur texte, ou 'N/C' si manquante."""
    return "N/C" if pd.isna(value) else str(value)

def _bool(value) -> str:
    """Booléen en texte ('oui'/'non'), ou 'N/C' si manquant."""
    return "N/C" if pd.isna(value) else ("oui" if value else "non")

def _pages(start, end) -> str:
    """'2' ou '4-5', ou 'N/C' si manquant."""
    if pd.isna(start):
        return "N/C"
    if pd.isna(end) or int(end) == int(start):
        return str(int(start))
    return f"{int(start)}-{int(end)}"

def _nature(is_handwritten) -> str:
    if pd.isna(is_handwritten):
        return "N/C"
    return "Manuscrit" if is_handwritten else "Dactylographié"

def list_contributions(code: str) -> list[str]:
    rows = _rows(code)
    return [f"{i + 1}/{len(rows)} | {_nature(h)}" for i, h in enumerate(rows["is_handwritten"])]

def get_contribution(code: str, idx: int) -> dict:
    rows = _rows(code)
    r = rows.iloc[idx]
    # le détail (verbatim + résumé) ne s'affiche que si l'analyse existe
    inst = _topic_instances(int(r["id"]))
    details = "".join(
        f"\n  - {_etiquette_source(i.name, i.cahier, i.page)}"
        f" — « {i.verbatim} » : *{i.summary}*"
        for i in inst.itertuples() if pd.notna(i.verbatim)
    )
    return {
        # bloc affiché à gauche, sous le select Contribution
        "analyse": (
            f"#### Analyse textuelle\n"
            f"- **Thèmes détectés** : {_text(r['topics'])}{details}\n"
            f"- **Sentiment** : {_text(r['feelings'])}\n"
            f"- **Anonymisé** : {_bool(r['is_anonymized'])}\n"
            f"- **Contribution d'intérêt** : {_bool(r['is_of_interest'])}"
        ),
        # provenance technique, au-dessus du résultat OCR
        # (la nature Manuscrit/Dactylographié est déjà dans le libellé du dropdown)
        "header": (
            f"| Pages | Lignes | Mots | Extraction |\n"
            f"|---|---|---|---|\n"
            f"| {_pages(r['start_page'], r['end_page'])} | {_int(r['num_lines'])} "
            f"| {_int(r['num_words'])} | {_text(r['ocr'])} |"
        ),
        "text": r["text"] if pd.notna(r["text"]) else "N/C (pas encore extraite)",
        "pdf_file": r["pdf_file"],
        # page d'ouverture : le PDF s'ouvre dessus plutôt qu'en couverture
        "page": None if pd.isna(r["start_page"]) else int(r["start_page"]),
        # état d'annotation existant (le tien ou celui d'un autre bénévole)
        "is_anonymized": bool(r["is_anonymized"]) if pd.notna(r["is_anonymized"]) else False,
        "is_of_interest": bool(r["is_of_interest"]) if pd.notna(r["is_of_interest"]) else False,
    }

def save_annotation(code: str, idx: int, is_anonymized: bool, is_of_interest: bool) -> str:
    contribution_id = int(_rows(code).iloc[idx]["id"])
    with engine.begin() as conn: # begin = transaction, commit automatique
        if not is_anonymized and not is_of_interest:
            # plus rien d'activé : on supprime la ligne (contribution redevient vierge)
            conn.execute(
                text("DELETE FROM annotation WHERE contribution_id = :cid"),
                {"cid": contribution_id},
            )
            return f"Annotation effacée (contribution {idx + 1})."
        # UPSERT : insère, ou met à jour l'annotation existante
        conn.execute(
            text("""
                INSERT INTO annotation (contribution_id, is_anonymized, is_of_interest)
                VALUES (:cid, :anonymized, :of_interest)
                ON CONFLICT (contribution_id) DO UPDATE
                   SET is_anonymized = EXCLUDED.is_anonymized,
                       is_of_interest = EXCLUDED.is_of_interest
            """),
            {"cid": contribution_id, "anonymized": is_anonymized,
             "of_interest": is_of_interest},
        )
    return f"Enregistré (contribution {idx + 1})."




def grille_servie() -> dict | None:
    """La grille de thèmes servie par défaut, pour l'annoncer à l'écran."""
    q = text("SELECT id, label, created_at FROM run WHERE kind = 'analyse' AND active")
    lignes = pd.read_sql(q, engine).to_dict("records")
    return lignes[0] if lignes else None


def grilles() -> list[dict]:
    """Toutes les grilles de thèmes en base, la servie d'abord.

    La base est faite pour que plusieurs coexistent — c'est ce qui rend le choix
    de l'une visible et discutable. Les lister est le premier pas pour pouvoir
    en changer sans redémarrer l'app.
    """
    q = text("""
        SELECT r.id, r.label, r.active, r.created_at, r.model, r.author, r.parameters,
               (SELECT count(*) FROM topic WHERE run_id = r.id) AS topics,
               (SELECT count(*) FROM instance WHERE run_id = r.id) AS detections
        FROM run r
        WHERE r.kind = 'analyse'
        ORDER BY r.active DESC, r.id DESC
    """)
    return pd.read_sql(q, engine).to_dict("records")


def _clause_grille(run_id: int | None) -> tuple[str, dict]:
    """La grille demandée, ou la servie quand aucune n'est nommée.

    Écrit en sous-requête pour le cas par défaut : sans grille active, la
    comparaison n'est jamais vraie et la vue est vide — l'état normal d'une base
    migrée mais pas encore chargée, sans branchement supplémentaire.
    """
    if run_id is None:
        return GRILLE_SERVIE, {}
    return ":run_id", {"run_id": int(run_id)}


def charger_taxonomie(run_id: int | None = None) -> pd.DataFrame:
    """Les topics d'une grille, parent résolu par nom.

    Les noms sont uniques **dans une grille**, ce qui suffit au graphe puisqu'il
    n'en affiche qu'une à la fois.

    Args:
        run_id: la grille à lire ; ``None`` prend celle qui est servie.
    """
    cible, params = _clause_grille(run_id)
    q = text(f"""
        SELECT t.id, t.external_id, t.name, t.description, t.level, p.name AS parent_nom
        FROM topic t
        LEFT JOIN topic p ON p.id = t.parent_id AND p.run_id = t.run_id
        WHERE t.run_id = {cible}
    """)
    return pd.read_sql(q, engine, params=params)


def charger_detections(run_id: int | None = None) -> pd.DataFrame:
    """Les instances d'une grille, rattachées au nom de leur topic.

    `external_doc_id` est l'identifiant du document dans la livraison analyse :
    le rapprochement avec `contribution` n'est pas résolu pour la livraison
    d'août, on affiche cet id tel quel.

    Args:
        run_id: la grille à lire ; ``None`` prend celle qui est servie.
    """
    cible, params = _clause_grille(run_id)
    q = text(f"""
        SELECT t.name AS topic, i.verbatim, i.summary, i.external_doc_id
        FROM instance i
        JOIN topic t ON t.id = i.topic_id
        WHERE i.run_id = {cible}
        ORDER BY i.id
    """)
    return pd.read_sql(q, engine, params=params)


def detections_par_doleance(run_id: int) -> pd.DataFrame:
    """Une ligne par (thème, doléance) rattachés, avec le nombre de détections.

    Seules les doléances du découpage servi comptent : une livraison dont les
    identifiants désignent un autre corpus n'en rattache aucune, et la vue le
    dit plutôt que de compter des documents qu'on ne peut pas relire.

    `n` mesure l'intensité du rattachement, pour choisir un thème dominant :
    le nombre d'instances, sauf pour les runs « mots-clés », qui n'en font
    qu'une par thème et par doléance — là, c'est le nombre de termes qui ont
    mordu, que l'instance liste dans son résumé.

    Args:
        run_id: le run de genre `analyse` à lire.
    """
    q = text(f"""
        SELECT t.id AS topic_id, t.external_id, t.name AS topic,
               i.doleance_id,
               sum(CASE WHEN i.summary LIKE 'mots-clés :%'
                        THEN array_length(string_to_array(i.summary, ','), 1)
                        ELSE 1 END) AS n
        FROM instance i
        JOIN topic t ON t.id = i.topic_id
        WHERE i.run_id = :run_id
          AND i.doleance_id IN (SELECT id FROM doleance WHERE run_id = {DECOUPAGE_SERVI})
        GROUP BY t.id, t.external_id, t.name, i.doleance_id
        ORDER BY t.id, i.doleance_id
    """)
    return pd.read_sql(q, engine, params={"run_id": int(run_id)})


def grilles_lisant_les_doleances() -> set[int]:
    """Les runs d'analyse dont au moins une détection vise une doléance du découpage servi."""
    q = text(f"""
        SELECT DISTINCT i.run_id
        FROM instance i
        WHERE i.doleance_id IN (SELECT id FROM doleance WHERE run_id = {DECOUPAGE_SERVI})
    """)
    with engine.connect() as conn:
        return {int(r[0]) for r in conn.execute(q)}


def nombre_de_doleances() -> int:
    """Les doléances du découpage servi : le dénominateur de toute part."""
    q = text(f"SELECT count(*) FROM doleance WHERE run_id = {DECOUPAGE_SERVI}")
    with engine.connect() as conn:
        return int(conn.execute(q).scalar() or 0)


def doleances_sans_detection(run_id: int, limite: int = 30):
    """(total, résultats) : ce que la grille ne voit pas, les plus longues d'abord."""
    from sqlalchemy.orm import Session

    from recherche.requetes import compter_sans_detection, sans_detection

    with Session(engine) as session:
        return (
            compter_sans_detection(session, int(run_id)),
            sans_detection(session, int(run_id), limite),
        )


#  avertissements : ce que l'app doit dire avant de montrer un chiffre
#
#  Les mesures viennent de `couverture.mesures` et `insee.cog`, pas d'un calcul
#  refait ici : deux implémentations de la même règle divergent, et celle qui
#  s'affiche à l'écran serait la dernière à être corrigée. Le coût est de lire
#  les pages une fois au démarrage, ce que fait déjà `python -m couverture`.

def _pages_pour_couverture() -> list:
    """Les colonnes que `couverture.mesures.mesurer` lit, et rien d'autre.

    Les `Row` de SQLAlchemy donnent l'accès par attribut : elles passent telles
    quelles là où le module attend des lignes `page_extraction`.
    """
    q = text("""
        SELECT p.pdf_name, p.city, p.needs_ocr, p.contribution_id
        FROM page_extraction p
    """)
    with engine.connect() as conn:
        return list(conn.execute(q))


def _codes_par_contribution() -> dict[int, str]:
    q = text("""
        SELECT id, city_code FROM contribution WHERE city_code IS NOT NULL
    """)
    with engine.connect() as conn:
        return dict(conn.execute(q).all())


def etat_du_corpus():
    """Ce que l'app sait de ses propres limites.

    Dégrade plutôt que d'échouer : sans référentiel INSEE lisible, la
    pondération par population et les noms officiels disparaissent de
    l'avertissement, le reste tient.
    """
    from couverture.mesures import mesurer
    from gradio_app.avertissements import Etat

    codes = _codes_par_contribution()
    try:
        from insee.cog import lire, populations_sans_double_compte

        referentiel = lire()
        habitants = populations_sans_double_compte(set(codes.values()), referentiel)
        noms = {c: referentiel[c].nom for c in set(codes.values()) if c in referentiel}
    except (OSError, KeyError):
        habitants, noms = {}, {}

    return Etat(
        couverture=mesurer(_pages_pour_couverture(), codes, habitants, noms),
        grille=grille_servie(),
        communes_listees=len([c for c in list_communes() if c[1] != SANS_COMMUNE]),
        communes_du_corpus=len(set(codes.values())),
    )


def chercher_doleances(requete: str, limite: int = 20):
    """(total, résultats) pour une requête plein texte.

    Ouvre une session ORM le temps de la requête : `recherche.requetes` prend
    une `Session`, quand le reste de ce module travaille en SQL brut via pandas.
    """
    from sqlalchemy.orm import Session

    from recherche.requetes import RequeteVide, chercher, compter

    with Session(engine) as session:
        try:
            return compter(session, requete), chercher(session, requete, limite)
        except RequeteVide:
            return 0, []
