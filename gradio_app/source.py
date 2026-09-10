"""Le chemin du retour à la source : d'une étiquette à la page du cahier.

Le plan le demande depuis le début — « renvoyer un verbatim vers son emplacement
sur le scan, d'un clic ». Sans ce chemin, une étiquette de thème, un extrait de
recherche ou une valeur de typologie sont à prendre ou à laisser : rien ne permet
d'aller vérifier ce que le texte dit vraiment, ni de voir ce que l'extraction a
perdu. C'est le minimum qu'un corpus d'archives doive à qui le lit.

Ce qu'on sait faire aujourd'hui s'arrête à la **page**. Les visionneuses PDF
comprennent l'ancre `#page=N`, et `doleance.start_page` porte le numéro de page
réel dans le cahier. Aller plus loin — encadrer le passage sur l'image — demande
la géométrie des lignes, que l'extraction actuelle ne produit pas ; c'est la même
chose qui manque pour occulter les données personnelles sur les scans.

L'URL vient de S3 quand le bucket répond, du dossier local sinon, et vaut `None`
quand le cahier est introuvable — auquel cas l'appelant affiche du texte sans
lien plutôt qu'un lien mort.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "data" / "raw" / "pdfs"

# Ancre comprise par les visionneuses PDF des navigateurs. Ce n'est pas un
# standard du format mais une convention respectée partout, y compris par le
# lecteur intégré de Chrome et de Firefox.
ANCRE_PAGE = "#page="


def avec_page(url: str, page: int | None) -> str:
    """Ajoute l'ancre de page à une URL de PDF.

    Args:
        url: l'URL du cahier, présignée ou locale.
        page: le numéro de page, tel qu'il est en base (1 = première page du
            PDF). ``None`` ou une valeur non entière laisse l'URL intacte.

    Returns:
        L'URL, suffixée de l'ancre quand la page est connue.
    """
    if page is None:
        return url
    try:
        numero = int(page)
    except (TypeError, ValueError):
        return url
    if numero < 1:
        return url
    return f"{url}{ANCRE_PAGE}{numero}"


def _url_presignee(cahier: str) -> str | None:
    """L'URL S3 du cahier, en passant par le nom que l'import sait résoudre.

    Les modules de `gradio_app/` s'importent à plat quand Gradio sert l'app
    depuis ce dossier, et en paquet quand pytest part de la racine. Cette
    indirection porte les deux cas — et donne aux tests un seul point à
    remplacer pour couper S3.
    """
    try:
        from s3_helpers import url_pdf
    except ModuleNotFoundError:  # pytest, depuis la racine du dépôt
        from gradio_app.s3_helpers import url_pdf
    return url_pdf(cahier)


def lien_source(cahier: str | None, page: int | None = None) -> str | None:
    """URL cliquable vers la page d'un cahier, ou ``None`` s'il est introuvable.

    Args:
        cahier: nom du fichier PDF (`doleance.pdf_name`, `contribution.pdf_file`).
        page: page à ouvrir, si on la connaît.

    Returns:
        L'URL, ou ``None`` — l'appelant doit alors afficher le libellé sans lien.
    """
    if not cahier:
        return None

    url = _url_presignee(cahier)
    if url:
        return avec_page(url, page)

    chemin = (PDF_DIR / cahier).resolve()
    if chemin.exists():
        return avec_page(f"/gradio_api/file={chemin}", page)
    return None


def libelle_page(debut: int | None, fin: int | None = None) -> str:
    """« p. 3 » ou « p. 3-15 », vide si la page n'est pas connue."""
    if debut is None:
        return ""
    if fin is None or int(fin) == int(debut):
        return f"p. {int(debut)}"
    return f"p. {int(debut)}-{int(fin)}"
