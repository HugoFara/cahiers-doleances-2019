"""Ce que l'app doit dire avant de montrer un chiffre.

Un site de consultation est un acte éditorial : ce qu'il affiche par défaut, et
surtout ce qu'il tait, décide de la lecture. Le corpus porte trois biais mesurés
et documentés ailleurs dans le dépôt, qui jusqu'ici ne vivaient que dans des
README et des sorties de commande — c'est-à-dire nulle part pour qui utilise
l'app :

- **près de la moitié des pages est écartée**, ce sont les manuscrites, donc la
  contribution ordinaire ;
- **des communes n'ont aucune page lisible** — leur cahier existe, il ne compte
  pour rien ;
- **plusieurs grilles de thèmes coexistent** en base et l'app n'en sert qu'une,
  sans le dire.

S'y ajoute une obligation juridique, pas seulement un scrupule : les données
INSEE et IGN sont sous Licence Ouverte 2.0, dont la troisième condition est de
« ne pas altérer le sens des informations ni induire en erreur quant à leur
interprétation ». Afficher une pondération par population sans son mode d'emploi
tombe exactement là-dedans.

Module sans base de données ni Gradio : il ne met en forme que des compteurs
déjà calculés, et se teste donc directement.
"""

from dataclasses import dataclass

from couverture.mesures import Couverture

# Au-delà, l'avertissement cesse d'être lu. Trois lignes et un repli.
LIGNES_VISIBLES = 3


@dataclass(frozen=True)
class Etat:
    """Ce que l'app sait de ses propres limites, à un instant donné."""

    couverture: Couverture
    # Grille de thèmes servie : ``{"label": ..., "created_at": ...}``. `None`
    # quand aucune n'est active — l'app affiche alors des vues vides, ce qui
    # ressemble à une base vide et n'en est pas une.
    grille: dict | None = None
    # Communes proposées par le sélecteur, et communes réellement dans le
    # corpus. L'écart doit être nul depuis que le sélecteur passe par le code
    # INSEE ; le garder mesuré est ce qui préviendra qu'il se recreuse.
    communes_listees: int = 0
    communes_du_corpus: int = 0


def _pourcent(part: int, total: int) -> str:
    """« 47 % », espace insécable comprise — sinon le rendu HTML coupe la ligne
    entre le nombre et son signe."""
    return f"{part / total * 100:.0f}\u00a0%" if total else "—"


def essentiel(etat: Etat) -> list[str]:
    """Les trois phrases qui doivent accompagner tout comptage."""
    couverture = etat.couverture
    lignes = [
        f"**{_pourcent(couverture.pages.ecartes, couverture.pages.total)} des pages "
        f"sont écartées** ({couverture.pages.ecartes} sur {couverture.pages.total}) : "
        "l'extraction sans OCR ne rend que du bruit sur les pages manuscrites. "
        + (
            f"**{couverture.transcrites} pages manuscrites sont réintégrées** par la "
            "transcription active ; le reste du corpus affiché est sa moitié "
            "dactylographiée — lettres de maires, associations, textes tapés."
            if couverture.transcrites
            else "Le corpus affiché est sa **moitié dactylographiée** — lettres de "
            "maires, associations, textes tapés."
        ),
        f"**{len(couverture.communes_muettes)} communes n'ont aucune page lisible.** "
        "Leur cahier existe et a été numérisé ; il ne compte dans aucun total.",
        "**Les comptages ne sont pas un sondage.** Ce corpus n'est pas un "
        "échantillon représentatif : « x % des contributions parlent de y » "
        "décrit ce qui a été déposé et lu, pas ce que pense une population.",
    ]
    if couverture.habitants is not None:
        lignes[1] += (
            f" Elles pèsent {_pourcent(couverture.habitants.ecartes, couverture.habitants.total)}"
            " des habitants seulement : les communes muettes sont les petites."
        )
    return lignes


def details(etat: Etat) -> list[str]:
    """Ce qui compte mais n'a pas à occuper le haut de l'écran."""
    lignes = []
    if etat.grille:
        depuis = etat.grille.get("created_at")
        date = f", chargée le {str(depuis)[:10]}" if depuis else ""
        lignes.append(
            f"**Grille de thèmes servie** : {etat.grille.get('label') or 'sans nom'}"
            f"{date}. D'autres grilles coexistent en base ; choisir la grille, "
            "c'est déjà interpréter, et cette page n'en montre qu'une."
        )
    else:
        lignes.append(
            "**Aucune grille de thèmes active** : les vues de thèmes sont vides. "
            "Ce n'est pas une base vide, c'est une grille à activer "
            "(`database/runs.py`)."
        )

    manquantes = etat.communes_du_corpus - etat.communes_listees
    if manquantes > 0:
        lignes.append(
            f"**{manquantes} communes du corpus ne sont pas dans la liste** et "
            "leurs contributions ne sont donc atteignables par aucun chemin. "
            "C'est une anomalie : le sélecteur devrait les porter toutes."
        )
    else:
        lignes.append(
            f"Les **{etat.communes_du_corpus} communes** du corpus sont dans la "
            "liste, désignées par leur code INSEE. Le nom affiché est celui du "
            "Code officiel géographique au millésime 2019, celui du dépôt des "
            "cahiers : deux communes avaient déjà fusionné à cette date, et "
            "elles gardent le code sous lequel leur cahier a été remis."
        )

    lignes.append(
        "Sources du référentiel géographique : **Source : Insee** (Code officiel "
        "géographique au 1ᵉʳ janvier 2019, populations légales millésimées 2017) "
        "et **Source : IGN** (ADMIN EXPRESS), sous Licence Ouverte 2.0."
    )
    return lignes


def _gras(ligne: str) -> str:
    """`**x**` en `<strong>x</strong>`, pour la page graphe qui n'est pas du Markdown.

    Les lignes sont écrites dans ce module et nulle part ailleurs : la
    conversion n'a pas à traiter le Markdown en général, seulement celui-là.
    """
    morceaux = ligne.split("**")
    return "".join(
        m if i % 2 == 0 else f"<strong>{m}</strong>" for i, m in enumerate(morceaux)
    )


def liste_markdown(lignes: list[str]) -> str:
    return "\n".join(f"- {ligne}" for ligne in lignes)


def html(etat: Etat) -> str:
    """L'avertissement complet en HTML, pour la vue graphe.

    Cette page-là est servie hors de Gradio, et c'est la plus interprétative des
    deux : elle montre une taxonomie, c'est-à-dire une lecture du corpus. Elle
    n'affichait aucun avertissement.
    """
    essentielles = "".join(f"<li>{_gras(ligne)}</li>" for ligne in essentiel(etat))
    precisions = "".join(f"<li>{_gras(ligne)}</li>" for ligne in details(etat))
    return (
        '<section class="avertissement">'
        "<h2>Ce que ce corpus n\u2019est pas</h2>"
        f"<ul>{essentielles}</ul>"
        "<details><summary>Précisions et sources</summary>"
        f"<ul>{precisions}</ul></details>"
        "</section>"
    )
