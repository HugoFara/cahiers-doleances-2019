"""Onglet de recherche plein texte.

Le corpus ne s'atteignait que commune par commune, ce qui convient à
l'annotation et à personne d'autre : « tout ce qui parle d'éoliennes » n'avait
pas de réponse.

Les extraits sont **caviardés**. La recherche est le premier endroit où le
corpus se lit en vrac, hors du cahier qui lui donnait son contexte : un extrait
rendu à qui interroge n'est pas la même chose qu'un texte lu par un bénévole qui
annote une commune. La vue par commune, elle, montre le texte brut — elle sert à
annoter, pas à diffuser.
"""

import html

import gradio as gr
from data_helpers import chercher_doleances
from source import libelle_page, lien_source

PLACEHOLDER = "éoliennes · \"pouvoir d'achat\" · impôt -taxe"

AIDE = (
    "Les mots s'ajoutent, les guillemets font une expression exacte, "
    "<code>or</code> alterne, un tiret exclut. La recherche porte sur les "
    "<strong>doléances</strong> — ce qu'a écrit une personne — du découpage "
    "actif, et donc sur la seule moitié dactylographiée du corpus."
)


def _reference(r) -> str:
    """« doléance 42 · p. 3 », cliquable vers le scan quand le cahier répond.

    Un extrait de recherche est sorti de son cahier : sans ce lien il est à
    prendre ou à laisser, et rien ne permet d'aller voir ce que le texte dit
    vraiment ni ce que l'extraction a perdu. Quand le PDF est introuvable, la
    référence reste affichée sans lien — un lien mort vaut moins que rien.
    """
    libelle = f"doléance {r.doleance_id}"
    page = libelle_page(r.page_debut, r.page_fin)
    if page:
        libelle += f" · {page}"
    url = lien_source(r.cahier, r.page_debut)
    if url is None:
        return f'<span class="ref">{html.escape(libelle)}</span>'
    return (
        f'<a class="ref" href="{html.escape(url, quote=True)}" target="_blank" '
        f'rel="noopener" title="Ouvrir le cahier à cette page">'
        f"{html.escape(libelle)} ↗</a>"
    )


def _resultat(r) -> str:
    ou = html.escape(r.commune or r.code_commune or "commune inconnue")
    marques = ""
    if r.recopie:
        marques = (
            f'<span class="recopie">↻ même texte dans {r.communes_du_groupe} '
            "communes</span>"
        )
    return (
        '<li class="resultat">'
        f'<div class="ou">{ou} {_reference(r)}'
        f"{marques}</div>"
        f'<p class="extrait">{html.escape(r.extrait)}</p>'
        "</li>"
    )


def chercher(requete: str) -> str:
    """Rend les résultats d'une recherche, en HTML échappé."""
    if not requete or not requete.strip():
        return f'<p class="aide">{AIDE}</p>'

    total, resultats = chercher_doleances(requete)
    if not total:
        return (
            f"<p>Aucune doléance ne répond à « {html.escape(requete)} ».</p>"
            f'<p class="aide">{AIDE}</p>'
        )

    entete = f"<p><strong>{total}</strong> doléance(s) · {len(resultats)} montrée(s)</p>"
    liste = "".join(_resultat(r) for r in resultats)
    note = (
        '<p class="aide">Extraits caviardés : les passages personnels repérés '
        "sont occultés, et un passage non relu l'est aussi. Ce n'est pas une "
        "anonymisation.</p>"
    )
    return f'{entete}<ul class="resultats">{liste}</ul>{note}'


def render():
    """Construit l'onglet et câble ses évènements."""
    with gr.Row():
        requete = gr.Textbox(
            label="Chercher dans les doléances",
            placeholder=PLACEHOLDER,
            scale=4,
            submit_btn=True,
        )
    resultats = gr.HTML(f'<p class="aide">{AIDE}</p>')
    requete.submit(chercher, requete, resultats)
    return resultats
