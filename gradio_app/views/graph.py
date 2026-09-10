"""Vue graphe des thèmes : le dessin et le service.

Sert une page maison (views/static/) qui charge Plotly et écoute plotly_click :
gr.Plot n'expose pas d'évènement de clic.

**Toute la logique de grille est dans `views/grille.py`**, qui ne connaît ni la
base ni Plotly. Ce module n'en garde que deux choses : fabriquer les figures, et
répondre au front. Auparavant, les cinq cents lignes de structure étaient
calculées à l'import sur la grille servie et sur elle seule — la vue ne pouvait
donc ni changer de grille, ni être testée.

Une grille reste lue une fois puis gardée en cache : 6788 topics et 9579
détections tiennent en mémoire, ce qui évite une requête récursive à chaque
interaction. Le cache est indexé par run, plusieurs grilles peuvent donc être
ouvertes tour à tour dans la même session sans redémarrage.
"""

from pathlib import Path

import networkx as nx
import plotly.graph_objects as go

from gradio_app.data_helpers import charger_detections, charger_taxonomie, grilles
from gradio_app.views.grille import (
    APERCU,
    LIBELLE_STRATE,
    PROF_APERCU,
    PROF_COULEUR,
    STRATES,
    Grille,
    role_du_cran,
)

STATIC = Path(__file__).parent / "static"

# Grilles déjà lues, par run. `None` désigne « celle qui est servie » : elle est
# résolue au premier accès puis rangée sous son propre id, pour qu'un choix
# explicite de cette même grille ne la relise pas.
_cache: dict[int | None, Grille] = {}


def grille(run_id: int | None = None) -> Grille:
    """La grille demandée, lue une fois puis gardée.

    Args:
        run_id: le run d'analyse voulu ; ``None`` prend celui qui est servi.

    Returns:
        La `Grille`, éventuellement vide — base migrée mais analyse pas chargée
        est un état normal, pas une erreur.
    """
    if run_id in _cache:
        return _cache[run_id]
    topics = charger_taxonomie(run_id)
    detections = charger_detections(run_id)
    nommee = next(
        (g for g in grilles() if (run_id is None and g["active"]) or g["id"] == run_id),
        None,
    )
    construite = Grille(
        topics.itertuples(),
        detections.itertuples(),
        run_id=nommee["id"] if nommee else run_id,
        label=nommee["label"] if nommee else None,
    )
    _cache[run_id] = construite
    if construite.run_id is not None:
        _cache[construite.run_id] = construite
    return construite


def oublier_les_grilles() -> None:
    """Vide le cache : rechargée en base, une grille sera relue au prochain accès."""
    _cache.clear()


# --- figures -------------------------------------------------------------


def _trace_noeuds(g, noms, pos, seuil, taille, position_texte):
    return go.Scatter(
        x=[pos[n][0] for n in noms], y=[pos[n][1] for n in noms],
        mode="markers+text",
        text=[(n[:24] + "…" if len(n) > 24 else n) if g.rec(n) >= seuil else ""
              for n in noms],
        textposition=position_texte(noms),
        textfont=dict(size=9, color="#334155"),
        customdata=noms,           # récupéré par plotly_click côté front
        hovertext=[f"{n}<br>{g.role(n)} · {g.rec(n)} détections" for n in noms],
        hoverinfo="text", showlegend=False,
        marker=dict(size=[taille(n) for n in noms],
                    color=[g.couleur(n) for n in noms],
                    line=dict(width=1, color="#ffffff")),
    )


def _trace_aretes(paires, pos):
    ex, ey = [], []
    for a, b in paires:
        ex += [pos[a][0], pos[b][0], None]
        ey += [pos[a][1], pos[b][1], None]
    return go.Scatter(x=ex, y=ey, mode="lines", line=dict(width=1, color="#d1d5db"),
                      hoverinfo="none", showlegend=False)


def _legende(g, fig, noeuds):
    """Une entrée par cran présent, de la racine vers les feuilles."""
    feuilles_par_prof = {p: all(not g.enfants[n] for n in noeuds if g.prof(n) == p)
                         for p in {g.prof(n) for n in noeuds}}
    for p in sorted(feuilles_par_prof):
        etiq = " · feuilles" if p and feuilles_par_prof[p] else ""
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", name=f"{role_du_cran(p)}{etiq}",
            marker=dict(size=11, color=PROF_COULEUR[p % len(PROF_COULEUR)]),
            showlegend=True))


def _mise_en_page(fig, hauteur, egaliser):
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="v", xanchor="right", x=1, yanchor="bottom", y=0,
                    bgcolor="rgba(255,255,255,0.75)", bordercolor="#e5e7eb", borderwidth=1),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, **({"scaleanchor": "x", "scaleratio": 1} if egaliser else {})),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10), height=hauteur,
    )
    return fig


def figure_apercu(g, strate):
    keep, lien = g.squelette(PROF_APERCU[strate], g.racines_apercu(strate))
    pos = g.layout_foret(keep, lien)
    noms = list(keep)
    seuil = sorted((g.rec(n) for n in noms), reverse=True)[:22][-1] if len(noms) > 22 else 0
    paires = [(n, p) for n, p in lien.items() if p is not None and p in pos]
    fig = go.Figure([
        _trace_aretes(paires, pos),
        _trace_noeuds(g, noms, pos, seuil,
                      lambda n: 8 + min(round(g.rec(n) ** 0.5) * 2, 30),
                      lambda ns: ["middle left" if pos[n][0] < 0 else "middle right"
                                  for n in ns]),
    ])
    _legende(g, fig, noms)
    return _mise_en_page(fig, hauteur=620, egaliser=True)


def figure_noeud(g, nom):
    """Focus au centre, voisinage à rayon 2 (Fruchterman-Reingold)."""
    dist = g.voisinage(nom)
    graphe = nx.Graph()
    graphe.add_nodes_from(dist)
    for n in dist:
        if n in g.parent_de and g.parent_de[n] in dist:
            graphe.add_edge(n, g.parent_de[n])
    pos = nx.spring_layout(graphe, k=2.2 / (len(graphe) ** 0.5), seed=42,
                           pos={nom: (0, 0)}, fixed=[nom], iterations=200)
    noms = list(dist)
    seuil = sorted((g.rec(n) for n in noms), reverse=True)[:18][-1] if len(noms) > 18 else 0
    fig = go.Figure([
        _trace_aretes(list(graphe.edges()), pos),
        _trace_noeuds(g, noms, pos, seuil,
                      lambda n: 12 + min(g.rec(n), 24),
                      lambda ns: ["top center"] * len(ns)),
    ])
    fig.add_trace(go.Scatter(                       # anneau « vous êtes ici »
        x=[pos[nom][0]], y=[pos[nom][1]], mode="markers", name="sélection",
        marker=dict(size=20 + min(g.rec(nom), 24), color="rgba(0,0,0,0)",
                    line=dict(width=3, color="#ef4444")), hoverinfo="skip"))
    _legende(g, fig, noms)
    return _mise_en_page(fig, hauteur=560, egaliser=False)


# --- panneau et cascade ---------------------------------------------------


def _html_description(g, nom):
    ligne = g.par_nom[nom]
    kids = g.enfants[nom]
    sous = f"{len(kids)} sous-thèmes" if kids else "aucun sous-thème (feuille)"
    return (
        f"<h3>{nom}</h3>"
        f"<p class='meta'><b>{g.role(nom).capitalize()}</b> ({g.prof(nom)} cran(s) sous la racine) "
        f"· <b>Parent</b> : {g.parent_de.get(nom, '— (racine)')} · {sous}</p>"
        f"<p class='meta'><b>Détections</b> : {g.rec(nom)} au total · "
        f"{g.propres.get(nom, 0)} sur ce topic</p>"
        f"<p>{ligne.description or ''}</p>"
    )


def _html_occurrences(g, nom):
    blocs = []
    for doc_id, rationale, extrait in g.occurrences.get(nom, [])[:6]:
        blocs.append(f"<blockquote>« {(extrait or '').strip()} »"
                     f"<footer>— doc {doc_id} · {rationale or ''}</footer></blockquote>")
    if not blocs:
        vide = ("Ce thème regroupe des sous-thèmes ; les occurrences sont sur les feuilles."
                if g.enfants[nom] else "Aucune occurrence sur ce topic.")
        blocs = [f"<p class='meta'><i>{vide}</i></p>"]
    return "<h4>Occurrences dans les textes</h4>" + "".join(blocs)


def _tableau_strates(g, strate, total) -> str:
    lignes = []
    for cle, lib, _test, _part in STRATES:
        groupe = g.racines_strate[cle]
        part = round(100 * g.detections_strate(cle) / total) if total else 0
        courant = " class='ici'" if cle == strate else ""
        lignes.append(f"<tr{courant}><td>{cle} · {lib}</td>"
                      f"<td>{g.bornes_hauteur(cle)}</td><td>{len(groupe)}</td>"
                      f"<td>{part} %</td></tr>")
    return (
        "<table><thead><tr><th>Strate</th><th>Hauteur</th><th>Arbres</th>"
        "<th>Signal</th></tr></thead><tbody>" + "".join(lignes) + "</tbody></table>"
    )


def _html_strate_vide(g, strate):
    """Aucune racine dans cette strate — fréquent sur une petite grille.

    Le tableau reste affiché : il dit où sont les arbres, ce qui est
    précisément l'information qui manque quand l'écran est vide.
    """
    total = g.detections_totales()
    peuplees = [cle for cle, _, _, _ in STRATES if g.racines_strate[cle]]
    ou = (
        "Les arbres de cette grille sont en strate "
        + ", ".join(peuplees)
        + "."
        if peuplees
        else "Cette grille ne porte aucun arbre."
    )
    return (
        f"<h3>Strate {strate} · {LIBELLE_STRATE[strate]} — aucun arbre</h3>"
        f"<p class='meta'>{ou} La strate se définit par la hauteur des arbres, "
        "et une grille peu profonde n'en peuple qu'une.</p>"
        + _tableau_strates(g, strate, total)
    )


def _html_apercu(g, strate):
    rs = g.racines_strate[strate]
    total = g.detections_totales()
    dets = g.detections_strate(strate)
    montres = g.racines_apercu(strate)
    keep, _ = g.squelette(PROF_APERCU[strate], montres)
    part = round(100 * dets / total) if total else 0

    return (
        f"<h3>Strate {strate} · {LIBELLE_STRATE[strate]}</h3>"
        f"<p><b>{len(rs)} arbres · {dets} détections</b> "
        f"({part} % du signal) · hauteur {g.bornes_hauteur(strate)}</p>"
        f"<p class='meta'>Aperçu : les <b>{len(montres)} arbres les plus gros</b> sur {len(rs)}, "
        f"jusqu'au cran {PROF_APERCU[strate]} sous la racine ({len(keep)} nœuds). "
        f"Les autres restent accessibles par le sélecteur.</p>"
        + _tableau_strates(g, strate, total)
        + "<p class='meta'><b>Taille</b> = détections. <b>Couleur</b> = distance à la racine : "
        "toute racine porte la même couleur, quelle que soit la hauteur de son arbre.</p>"
    )


def _html_grille_vide(g):
    """Ce qu'on affiche quand la grille choisie ne porte aucun arbre.

    Une grille chargée sans détection rattachable, ou une base pas encore
    remplie : dire lequel des deux vaut mieux qu'un écran blanc.
    """
    quoi = f"« {g.label} »" if g.label else "celle-ci"
    return (
        f"<h3>Grille {quoi} — rien à montrer</h3>"
        f"<p class='meta'>{len(g)} thème(s) en base, {g.total_detections} détection(s), "
        "et aucun arbre : les thèmes sont isolés, cycliques, ou sans détection. "
        "Charger une livraison (<code>analyse/load_analysis.py</code>) ou choisir "
        "une autre grille ci-dessus.</p>"
    )


def _opt(g, nom, avec_topics=False):
    """`value` = le nom brut attendu par l'API, `label` = ce qui s'affiche."""
    detail = f"{len(g.sous_arbre(nom))} topics · " if avec_topics else ""
    return {"value": nom, "label": f"{nom} · {detail}{g.rec(nom)} détections"}


def _options_racines(g, strate):
    return ([{"value": APERCU, "label": APERCU}]
            + [_opt(g, r, avec_topics=True) for r in g.racines_strate[strate]])


def _cascade(g, chemin, strate):
    """Toute la ligne de sélecteurs pour un chemin donné."""
    racines = _options_racines(g, strate)
    niveaux = []
    for i, node in enumerate(chemin):
        options = racines if i == 0 else [_opt(g, k) for k in g.kids(chemin[i - 1])]
        niveaux.append({"label": "Racine · arbre" if i == 0 else g.role(node).capitalize(),
                        "options": options, "value": node})
    if chemin:
        kids = g.kids(chemin[-1])
        if kids:
            niveaux.append({"label": f"Descendre · {g.role(kids[0])} ({len(kids)})",
                            "options": [_opt(g, k) for k in kids], "value": None})
    else:
        niveaux.append({"label": "Racine · arbre", "options": racines, "value": APERCU})
    return niveaux


# --- réponses servies au front -------------------------------------------


def _libelle_grille(ligne: dict) -> str:
    marque = " · servie" if ligne["active"] else ""
    return f"{ligne['label']}{marque} · {ligne['detections']} détections"


def config():
    """Ce que le front a besoin de savoir avant sa première requête."""
    servie = next((g for g in grilles() if g["active"]), None)
    return {
        "apercu": APERCU,
        "strates": [{"value": cle, "label": f"{cle} · {LIBELLE_STRATE[cle]}"}
                    for cle in PROF_APERCU],
        "grilles": [{"value": g["id"], "label": _libelle_grille(g)} for g in grilles()],
        "grille": servie["id"] if servie else None,
    }


def _reponse(g, strate, chemin):
    """Le socle commun aux deux vues : grille courante, strate, sélecteurs."""
    return {
        "grille": g.run_id,
        "strate": strate,
        "niveaux": _cascade(g, chemin, strate) if not g.vide else [],
    }


def apercu(strate, run_id=None):
    g = grille(run_id)
    if g.vide:
        return {**_reponse(g, strate, []),
                "figure": {"data": [], "layout": {}},
                "description": _html_grille_vide(g),
                "occurrences": ""}
    if strate not in g.racines_strate:
        return {"erreur": f"strate inconnue : {strate}"}
    # Une strate sans racine n'a rien à dessiner, et le layout radial ne sait
    # pas diviser un cercle en zéro part. Le cas ne se voyait pas sur la grille
    # livrée, dont les trois strates sont peuplées ; il apparaît dès qu'on en
    # charge une plus petite, ce que l'app permet maintenant.
    if not g.racines_strate[strate]:
        return {**_reponse(g, strate, []),
                "figure": {"data": [], "layout": {}},
                "description": _html_strate_vide(g, strate),
                "occurrences": ""}
    return {
        **_reponse(g, strate, []),
        "figure": figure_apercu(g, strate).to_plotly_json(),
        "description": _html_apercu(g, strate),
        "occurrences": "",
    }


def noeud(nom, run_id=None):
    """Sert le clic comme le menu : on reçoit un nom, on recalcule tout le reste."""
    g = grille(run_id)
    if nom not in g.propre:
        return {"erreur": f"topic inconnu : {nom}"}
    chemin = g.chemin(nom)
    strate = g.strate_de.get(chemin[0], "A")
    return {
        **_reponse(g, strate, chemin),
        "figure": figure_noeud(g, nom).to_plotly_json(),
        "description": _html_description(g, nom),
        "occurrences": _html_occurrences(g, nom),
    }
