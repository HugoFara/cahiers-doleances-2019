import os
from pathlib import Path

import pandas as pd
from communes import regrouper
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# Constantes
ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "raw" / "pdfs"

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

def _graphies() -> dict[str, list[str]]:
    """{graphie affichée: toutes les graphies de la même commune}.

    Une même commune est écrite différemment selon les PDF (« AHUILLE » /
    « AHUILLÉ ») : sans ce regroupement la liste en propose deux, dont chacune
    ne montre qu'une partie des contributions.
    """
    # la commune est parsée du PDF : elle est vide quand l'extraction a échoué.
    q = text("""
        SELECT DISTINCT city FROM contribution
        WHERE city IS NOT NULL AND btrim(city) <> ''
    """)
    return regrouper(pd.read_sql(q, engine)["city"].tolist())


def list_communes() -> list[str]:
    return list(_graphies())





def _rows(commune: str) -> pd.DataFrame:
    """Les contributions d'une commune."""
    # une seule extraction affichée par contribution : la plus récente
    q = text("""
        SELECT k.id, k.city, k.pdf_file, k.start_page, k.end_page, k.is_handwritten,
               e.ocr, e.text, e.num_words, e.num_lines,
               a.is_anonymized, a.is_of_interest,
               (SELECT string_agg(r.name, ', ') FROM instance t
                 JOIN topic r ON r.id = t.topic_id
                 WHERE t.contribution_id = k.id) AS topics,
               (SELECT string_agg(name, ', ') FROM feeling
                 WHERE contribution_id = k.id) AS feelings
        FROM contribution k
        LEFT JOIN extraction e ON e.id = (
            SELECT max(id) FROM extraction WHERE contribution_id = k.id
        )
        LEFT JOIN annotation a ON a.contribution_id = k.id
        WHERE k.city = ANY(:graphies)
        ORDER BY k.id
    """)
    # toutes les graphies de la commune, pas seulement celle affichée
    graphies = _graphies().get(commune, [commune])
    return pd.read_sql(q, engine, params={"graphies": graphies})

def _topic_instances(contribution_id: int) -> pd.DataFrame:
    """Les instances de thèmes d'une contribution avec verbatim et résumé."""
    q = text("""
        SELECT r.name, t.verbatim, t.summary
        FROM instance t JOIN topic r ON r.id = t.topic_id
        WHERE t.contribution_id = :cid
        ORDER BY t.id
    """)
    return pd.read_sql(q, engine, params={"cid": contribution_id})

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

def list_contributions(commune: str) -> list[str]:
    rows = _rows(commune)
    return [f"{i + 1}/{len(rows)} | {_nature(h)}" for i, h in enumerate(rows["is_handwritten"])]

def get_contribution(commune: str, idx: int) -> dict:
    rows = _rows(commune)
    r = rows.iloc[idx]
    # le détail (verbatim + résumé) ne s'affiche que si l'analyse existe
    inst = _topic_instances(int(r["id"]))
    details = "".join(
        f"\n  - **{i.name}** — « {i.verbatim} » : *{i.summary}*"
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
        # état d'annotation existant (le tien ou celui d'un autre bénévole)
        "is_anonymized": bool(r["is_anonymized"]) if pd.notna(r["is_anonymized"]) else False,
        "is_of_interest": bool(r["is_of_interest"]) if pd.notna(r["is_of_interest"]) else False,
    }

def save_annotation(commune: str, idx: int, is_anonymized: bool, is_of_interest: bool) -> str:
    contribution_id = int(_rows(commune).iloc[idx]["id"])
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


#  vue graphe : la taxonomie et ses détections, lues une fois au démarrage
#
#  Plusieurs grilles de thèmes coexistent en base (voir database/runs.py) : sans
#  filtre, l'app les afficherait empilées, et les noms de thèmes — uniques dans
#  une grille, pas dans la table — se confondraient d'une grille à l'autre. On
#  ne sert donc que la grille active.
#
#  Écrit en sous-requête plutôt qu'en paramètre Python : quand aucune grille
#  n'est active, la sous-requête vaut NULL, la comparaison n'est jamais vraie et
#  les vues sont vides — exactement ce qu'on veut sur une base pas encore
#  chargée, sans branchement supplémentaire.
GRILLE_SERVIE = "(SELECT id FROM run WHERE kind = 'analyse' AND active)"


def grille_servie() -> dict | None:
    """La grille de thèmes actuellement affichée, pour l'annoncer à l'écran."""
    q = text("SELECT id, label, created_at FROM run WHERE kind = 'analyse' AND active")
    lignes = pd.read_sql(q, engine).to_dict("records")
    return lignes[0] if lignes else None


def charger_taxonomie() -> pd.DataFrame:
    """Les topics de la grille servie, parent résolu par nom.

    Les noms sont uniques **dans une grille**, ce qui suffit au graphe puisqu'il
    n'en affiche qu'une.
    """
    q = text(f"""
        SELECT t.id, t.external_id, t.name, t.description, t.level, p.name AS parent_nom
        FROM topic t
        LEFT JOIN topic p ON p.id = t.parent_id AND p.run_id = t.run_id
        WHERE t.run_id = {GRILLE_SERVIE}
    """)
    return pd.read_sql(q, engine)


def charger_detections() -> pd.DataFrame:
    """Les instances de la grille servie, rattachées au nom de leur topic.

    `external_doc_id` est l'identifiant du document dans la livraison analyse :
    le rapprochement avec `contribution` n'est pas résolu, on affiche cet id tel quel.
    """
    q = text(f"""
        SELECT t.name AS topic, i.verbatim, i.summary, i.external_doc_id
        FROM instance i
        JOIN topic t ON t.id = i.topic_id
        WHERE i.run_id = {GRILLE_SERVIE}
        ORDER BY i.id
    """)
    return pd.read_sql(q, engine)
