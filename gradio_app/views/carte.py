"""Onglet « Carte » : d'où viennent les cahiers, et quelle taille de commune parle.

Un point par commune du corpus, à sa place (coordonnées du COG 2019), dont
la **taille** est la population de la commune en 2019 — l'année où le cahier
a été écrit — et la **couleur**, au choix, ce que la commune a donné : ses
doléances, ses doléances pour mille habitants, ou la part manuscrite de ses
pages. Les communes **muettes** — un cahier, mais aucune page lisible — sont
tracées à part, en croix grise : leur absence de la carte serait un mensonge
de plus.

Le fond de carte est celui de Plotly (contours des pays), pas un fond de
tuiles : rien n'est envoyé à un serveur de cartes, et le contour de la France
suffit à situer trois départements. Les limites départementales n'y sont pas ;
le survol donne le code INSEE, qui les porte.
"""

import html

import gradio as gr
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from gradio_app.data_helpers import communes_pour_carte
from gradio_app.views.lecture import strate

COULEURS = {
    "doléances": ("doleances", "doléances", "Blues"),
    "doléances pour 1 000 habitants": ("pour_mille", "pour 1 000 hab.", "Purples"),
    "part manuscrite des pages": ("part_manuscrite", "% manuscrit", "Oranges"),
}
COULEUR_DEFAUT = "doléances"
TAILLE_MIN, TAILLE_MAX = 5, 34

AIDE = (
    "Un point par commune, <strong>placé</strong> aux coordonnées du Code "
    "officiel géographique 2019 et <strong>dimensionné</strong> par sa "
    "population de 2019, l'année du cahier. Les croix grises sont les communes "
    "<strong>muettes</strong> : un cahier, aucune page lisible à ce jour. "
    "Survoler donne le détail ; la molette zoome, le double-clic recadre."
)


# --- préparation, sans base ni Plotly : testable ---------------------------

def preparer(communes: pd.DataFrame) -> pd.DataFrame:
    """Ajoute ce que la carte trace : taille, indicateurs, strate, survol.

    Args:
        communes: le résultat de `communes_pour_carte`.

    Returns:
        Le même tableau, sans les communes sans coordonnées, avec les colonnes
        ``taille, pour_mille, part_manuscrite, strate, muette, survol``.
    """
    df = communes.dropna(subset=["latitude", "longitude"]).copy()
    pop = df["population"].fillna(0).astype(float)
    # racine carrée : l'aire du point suit la population, pas son rayon —
    # sinon une ville de 40 000 habitants écrase tout le département
    racine = np.sqrt(pop)
    etendue = racine.max() or 1.0
    df["taille"] = TAILLE_MIN + (TAILLE_MAX - TAILLE_MIN) * racine / etendue
    df["pour_mille"] = np.where(pop > 0, 1000 * df["doleances"] / pop.replace(0, np.nan), 0.0)
    df["part_manuscrite"] = np.where(
        df["pages"] > 0, 100 * df["manuscrites"] / df["pages"].replace(0, np.nan), 0.0
    )
    df["strate"] = df["population"].map(strate)
    df["muette"] = df["lisibles"] == 0
    df["survol"] = [_survol(c) for c in df.itertuples()]
    return df


def _survol(c) -> str:
    pop = f"{int(c.population):,}".replace(",", " ") if pd.notna(c.population) else "?"
    transcrites = f", {c.transcrites} transcrite(s)" if c.transcrites else ""
    etat = "<b>muette</b> : aucune page lisible" if c.lisibles == 0 else f"{c.lisibles} page(s) lisible(s)"
    return (
        f"<b>{html.escape(str(c.nom))}</b> ({c.code})<br>"
        f"{pop} habitants en 2019 · {c.strate}<br>"
        f"{c.cahiers} cahier(s), {c.pages} page(s) dont {c.manuscrites} manuscrite(s){transcrites}<br>"
        f"{etat} · {c.doleances} doléance(s)"
    )


# --- rendu -----------------------------------------------------------------

def figure(couleur: str = COULEUR_DEFAUT) -> go.Figure:
    """La carte, colorée par l'indicateur choisi."""
    colonne, legende, palette = COULEURS.get(couleur, COULEURS[COULEUR_DEFAUT])
    df = preparer(communes_pour_carte())
    fig = go.Figure()
    if df.empty:
        fig.update_layout(title="Aucune commune à placer")
        return fig

    parlantes = df[~df["muette"]]
    muettes = df[df["muette"]]
    fig.add_scattergeo(
        lat=parlantes["latitude"], lon=parlantes["longitude"],
        mode="markers", name="communes du corpus",
        marker={
            "size": parlantes["taille"], "color": parlantes[colonne],
            "colorscale": palette, "showscale": True,
            "colorbar": {"title": legende, "thickness": 12},
            "line": {"width": 0.5, "color": "rgba(60,60,60,0.6)"},
            "opacity": 0.85,
        },
        text=parlantes["survol"], hovertemplate="%{text}<extra></extra>",
    )
    if not muettes.empty:
        fig.add_scattergeo(
            lat=muettes["latitude"], lon=muettes["longitude"],
            mode="markers", name="communes muettes (aucune page lisible)",
            marker={"size": muettes["taille"], "symbol": "x", "color": "#9a9a9a", "opacity": 0.9},
            text=muettes["survol"], hovertemplate="%{text}<extra></extra>",
        )
    fig.update_geos(
        scope="europe", fitbounds="locations",
        showcountries=True, countrycolor="#8a8a8a",
        showland=True, landcolor="rgba(128,128,128,0.08)",
        showocean=False, showlakes=False, showframe=False,
        projection_type="mercator",
    )
    fig.update_layout(
        title=f"{len(df)} communes · taille = population 2019 · couleur = {couleur}",
        height=720,
        margin={"l": 0, "r": 0, "t": 60, "b": 0},
        legend={"orientation": "h", "y": -0.02},
        paper_bgcolor="rgba(0,0,0,0)",
        geo={"bgcolor": "rgba(0,0,0,0)"},
        font={"color": "#8a8a8a"},
    )
    return fig


def render():
    """Construit l'onglet et câble ses évènements."""
    gr.HTML(f'<p class="aide">{AIDE}</p>')
    couleur = gr.Radio(
        choices=list(COULEURS), value=COULEUR_DEFAUT, label="Couleur", interactive=True
    )
    carte = gr.Plot(figure(COULEUR_DEFAUT), label="Communes du corpus")
    couleur.change(figure, couleur, carte)
    return carte
