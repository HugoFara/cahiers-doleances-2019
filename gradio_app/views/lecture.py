"""Onglet « Lecture » : ce qu'une grille fait voir du corpus, et ce qu'elle rate.

La vue thèmes montre la *grille* — comment son auteur a rangé ses catégories.
Sur une grille plate, neuf rubriques sans parent, elle n'a rien à montrer que
neuf points ; et même sur une grille profonde, elle répond à « comment la
grille est organisée », pas à « de quoi parlent les doléances ». Cette vue
répond à la seconde question, avec trois choses que l'arbre n'a pas :

- la part des doléances par thème, et la barre **hors grille** à côté : sans
  elle, « 34 % parlent de fiscalité » ne dit pas sur quelle part du corpus il
  porte ;
- la même part en **rubrique dominante** (une par doléance, celle qui a le
  plus de détections), la seule comparable à une source où chaque
  proposition n'avait qu'une rubrique ;
- la **distribution de référence** de la grille quand elle en a une (le Vrai
  Débat publie la sienne), en grisé à côté.

Et sous le graphique, les doléances que la grille ne voit pas, les plus
longues d'abord, caviardées : ce qu'aucune rubrique n'avait prévu.

Tout repose sur les détections du run choisi. Pour les runs « mots-clés »,
c'est un détecteur de vocabulaire, et le titre le dit.
"""

import html

import gradio as gr
import pandas as pd
import plotly.graph_objects as go

from gradio_app.data_helpers import (
    detections_par_doleance,
    doleances_sans_detection,
    grilles,
    grilles_lisant_les_doleances,
    nombre_de_doleances,
)
from gradio_app.views.recherche import resultat_html

HORS_GRILLE = "hors grille"
LIMITE_HORS_GRILLE = 30
# Au-delà, la grille est une livraison à milliers de thèmes : on montre les
# plus fournis et on le dit, plutôt qu'un graphique illisible.
MAX_BARRES = 25

AIDE = (
    "Une doléance compte dans un thème dès qu'elle y a une détection "
    "(plusieurs thèmes possibles), et une seule fois en <strong>rubrique "
    "dominante</strong> : celle où elle a le plus de détections (pour les "
    "mots-clés, le plus de termes qui ont mordu ; à égalité, la première de "
    "la grille). La barre "
    "<strong>hors grille</strong> est la part des doléances qu'aucun thème ne "
    "voit. Les runs « mots-clés » détectent du vocabulaire, pas un propos : "
    "c'est l'étalon bas d'un futur modèle, pas une lecture."
)


# --- calcul, sans base : testable sur un DataFrame ------------------------

def repartition(detections: pd.DataFrame, total: int, ordre: list[str] | None = None) -> pd.DataFrame:
    """Par thème : doléances rattachées, doléances où il domine, en nombre et en part.

    Args:
        detections: lignes ``topic_id, external_id, topic, doleance_id, n``.
        total: nombre de doléances du découpage — le dénominateur.
        ordre: identifiants externes des thèmes, dans l'ordre voulu ; les
            thèmes absents des détections y figurent à zéro.

    Returns:
        Une ligne par thème, plus une ligne « hors grille » en dernier, colonnes
        ``external_id, topic, doleances, dominantes, part, part_dominante``.
    """
    if detections.empty:
        rattachees = pd.DataFrame(columns=["external_id", "topic", "doleances"])
        dominantes = pd.Series(dtype=int)
        vues = 0
    else:
        rattachees = (
            detections.groupby(["external_id", "topic"], sort=False)["doleance_id"]
            .nunique()
            .rename("doleances")
            .reset_index()
        )
        # la dominante : le thème le plus détecté dans la doléance ; à égalité,
        # le premier dans l'ordre de la grille (topic_id croissant)
        premiere = (
            detections.sort_values(["doleance_id", "n", "topic_id"], ascending=[True, False, True])
            .drop_duplicates("doleance_id")
        )
        dominantes = premiere.groupby("external_id")["doleance_id"].nunique()
        vues = detections["doleance_id"].nunique()

    lignes = rattachees.set_index("external_id")
    if ordre:
        noms = dict(zip(rattachees["external_id"], rattachees["topic"]))
        lignes = lignes.reindex(ordre)
        lignes["topic"] = [noms.get(i, i) for i in lignes.index]
        lignes["doleances"] = lignes["doleances"].fillna(0).astype(int)
    lignes["dominantes"] = dominantes.reindex(lignes.index).fillna(0).astype(int)
    lignes = lignes.reset_index()

    hors = pd.DataFrame(
        [{"external_id": HORS_GRILLE, "topic": HORS_GRILLE,
          "doleances": max(total - vues, 0), "dominantes": max(total - vues, 0)}]
    )
    table = pd.concat([lignes, hors], ignore_index=True)
    diviseur = total or 1
    table["part"] = 100 * table["doleances"] / diviseur
    table["part_dominante"] = 100 * table["dominantes"] / diviseur
    return table


def _reference(run: dict | None) -> dict | None:
    params = (run or {}).get("parameters") or {}
    ref = params.get("reference")
    return ref if ref and ref.get("parts") else None


# --- rendu -----------------------------------------------------------------

def _run(run_id: int | None) -> dict | None:
    return next((g for g in grilles() if g["id"] == run_id), None)


def _titre(run: dict | None, total: int) -> str:
    label = (run or {}).get("label") or "grille"
    modele = (run or {}).get("model")
    nature = " · détecteur de vocabulaire, étalon bas" if modele == "mots-clés" else ""
    return f"{label}{nature} · {total} doléances du découpage servi"


def figure(run_id: int | None) -> go.Figure:
    """Barres horizontales : part rattachée, part dominante, référence."""
    fig = go.Figure()
    run = _run(run_id)
    total = nombre_de_doleances()
    if run is None or not total:
        fig.update_layout(title="Aucune grille à lire")
        return fig

    detections = detections_par_doleance(run["id"])
    reference = _reference(run)
    ordre = list(reference["parts"]) if reference else None
    table = repartition(detections, total, ordre)

    if detections.empty:
        fig.update_layout(
            title=_titre(run, total) + " · aucune détection sur ces doléances "
            "(les identifiants de cette grille désignent un autre corpus ?)"
        )
        return fig

    corps = table[table["external_id"] != HORS_GRILLE]
    tronque = ""
    if len(corps) > MAX_BARRES:
        corps = corps.nlargest(MAX_BARRES, "doleances")
        tronque = f" · {MAX_BARRES} thèmes les plus fournis sur {len(table) - 1}"
    if not ordre:
        corps = corps.sort_values("doleances", ascending=True)
    else:
        corps = corps.iloc[::-1]  # l'ordre de la référence, de haut en bas
    hors = table[table["external_id"] == HORS_GRILLE]
    corps = pd.concat([hors, corps])  # hors grille tout en bas

    noms = [
        f"<b>{html.escape(t)}</b>" if e == HORS_GRILLE else html.escape(t)
        for e, t in zip(corps["external_id"], corps["topic"])
    ]
    fig.add_bar(
        y=noms, x=corps["part"], orientation="h", name="doléances rattachées (plusieurs thèmes possibles)",
        marker_color="#4c78a8",
        customdata=corps["doleances"],
        hovertemplate="%{y}<br>%{x:.1f} % · %{customdata} doléances<extra></extra>",
    )
    fig.add_bar(
        y=noms, x=corps["part_dominante"], orientation="h", name="rubrique dominante (une par doléance)",
        marker_color="#f58518",
        customdata=corps["dominantes"],
        hovertemplate="%{y}<br>%{x:.1f} % · %{customdata} doléances<extra></extra>",
    )
    if reference:
        parts = reference["parts"]
        fig.add_bar(
            y=noms,
            x=[parts.get(e, 0) if e != HORS_GRILLE else 0 for e in corps["external_id"]],
            orientation="h", name=f"référence : {reference['titre']}",
            marker_color="#b0b0b0",
            hovertemplate="%{y}<br>%{x:.1f} % (référence)<extra></extra>",
        )
    fig.update_layout(
        title=_titre(run, total) + tronque,
        barmode="group",
        xaxis_title="% des doléances",
        height=max(420, 40 * len(corps) + 160),
        margin={"l": 10, "r": 10, "t": 70, "b": 40},
        legend={"orientation": "h", "y": -0.12},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#8a8a8a"},
    )
    fig.update_xaxes(gridcolor="rgba(128,128,128,0.25)")
    return fig


def hors_grille(run_id: int | None) -> str:
    """Les doléances que la grille ne voit pas, rendues comme des résultats de recherche."""
    run = _run(run_id)
    if run is None:
        return '<p class="aide">Aucune grille choisie.</p>'
    total, resultats = doleances_sans_detection(run["id"], LIMITE_HORS_GRILLE)
    if not total:
        return "<p>Cette grille rattache toutes les doléances à au moins un thème.</p>"
    entete = (
        f"<p><strong>{total}</strong> doléance(s) hors grille · "
        f"{len(resultats)} montrée(s), les plus longues d'abord</p>"
    )
    liste = "".join(resultat_html(r) for r in resultats)
    note = (
        '<p class="aide">Ce que ni cette grille ni son détecteur ne voient. '
        "Extraits caviardés : les passages personnels repérés sont occultés. "
        "Ce n'est pas une anonymisation.</p>"
    )
    return f'{entete}<ul class="resultats">{liste}</ul>{note}'


def _choix() -> tuple[list[tuple[str, int]], int | None]:
    """Les grilles qui ont des détections, la servie d'abord ; et celle à ouvrir.

    On ouvre sur la première qui lit vraiment les doléances du découpage servi :
    la grille servie peut être une livraison dont les identifiants désignent un
    autre corpus, et l'ouvrir sur un graphique vide n'aiderait personne.
    """
    lisibles = grilles_lisant_les_doleances()
    options = [
        (f"{g['label']}{' · servie' if g['active'] else ''} · {g['detections']} détections", g["id"])
        for g in grilles()
        if g["detections"]
    ]
    defaut = next((i for _, i in options if i in lisibles), options[0][1] if options else None)
    return options, defaut


def render():
    """Construit l'onglet et câble ses évènements."""
    options, defaut = _choix()
    choix = gr.Dropdown(choices=options, value=defaut, label="Grille lue", interactive=True)
    gr.HTML(f'<p class="aide">{AIDE}</p>')
    trace = gr.Plot(figure(defaut), label="Part des doléances par thème")
    gr.Markdown("### Ce que la grille ne voit pas")
    liste = gr.HTML(hors_grille(defaut))
    choix.change(figure, choix, trace)
    choix.change(hors_grille, choix, liste)
    return trace, liste
