import gradio as gr

from gradio_app.data_helpers import (
    get_contribution,
    list_communes,
    list_contributions,
    save_annotation,
)
from gradio_app.source import libelle_page, lien_source


def _cadre(src: str, lien: str, page: str) -> str:
    ouvrir = "Ouvrir le PDF dans un onglet"
    if page:
        ouvrir += f" ({page})"
    return (
        f'<iframe src="{src}" width="100%" height="640px" '
        'style="border:1px solid var(--border-color-primary);border-radius:8px;"></iframe>'
        f'<p style="margin:6px 0 0"><a href="{lien}" target="_blank" '
        f'rel="noopener">{ouvrir}</a></p>'
    )


def pdf_html(pdf_file: str | None, page: int | None = None) -> str:
    """Le cahier, ouvert à la page de la contribution.

    Le PDF vient de S3 (URL présignée) ; on retombe sur le dossier local si le
    bucket est injoignable, pour rester utilisable hors ligne. La visionneuse
    s'ouvrait jusqu'ici en couverture, ce qui obligeait à chercher à la main la
    page qu'on venait de sélectionner.
    """
    if not pdf_file:
        return "<em>PDF à intégrer.</em>"

    url = lien_source(pdf_file, page)
    if url is None:
        return f"<em>PDF introuvable : {pdf_file}</em>"
    return _cadre(url, url, libelle_page(page))

def show(code: str, idx: int):
    """Affiche la contribution n°idx de la commune, désignée par son code INSEE."""
    contribs = list_contributions(code)
    idx = max(0, min(idx, len(contribs) - 1))
    c = get_contribution(code, idx)
    return (
        gr.update(choices=contribs, value=contribs[idx] if contribs else None),
        c["analyse"],
        c["header"],
        c["text"],
        pdf_html(c["pdf_file"], c["page"]),
        c["is_anonymized"],
        c["is_of_interest"],
        idx,
    )

def render():
    """Construit l'onglet 'Par commune' et câble ses événements.

    Retourne (fonction, outputs) pour l'affichage initial : cet événement
    appartient au niveau Blocks, c'est app.py qui le branche (demo.load).
    """
    idx_state = gr.State(0)

    # (libellé, code INSEE) : le libellé se lit, le code identifie. Le
    # sélecteur reposait sur la graphie de l'en-tête, absente d'un tiers des
    # cahiers — 40 % des contributions n'étaient atteignables par aucun chemin.
    communes = list_communes()

    with gr.Row():
        with gr.Column(scale=1):
            commune = gr.Dropdown(
                communes, value=communes[0][1], label="Commune", filterable=True
            )
            contrib = gr.Dropdown(label="Contribution", filterable=True)
            analyse = gr.Markdown()
            with gr.Row():
                prev_btn = gr.Button("Précédente")
                next_btn = gr.Button("Suivante")

        with gr.Column(scale=2):
            header = gr.Markdown()
            text = gr.Textbox(label="Texte de la contribution", lines=18, interactive=False)
            anonymized = gr.Checkbox(label="Anonymisé")
            of_interest = gr.Checkbox(label="Contribution d'intérêt")
            save_btn = gr.Button("Enregistrer", variant="primary")
            status = gr.Markdown()

        with gr.Column(scale=2):
            gr.Markdown("#### PDF source")
            pdf = gr.HTML()

    outputs = [contrib, analyse, header, text, pdf, anonymized, of_interest, idx_state]

    commune.change(lambda c: show(c, 0), commune, outputs)
    contrib.input(
        lambda label, c: show(c, int(label.split("/")[0]) - 1 if "/" in label else 0),
        [contrib, commune],
        outputs,
    )
    prev_btn.click(lambda c, i: show(c, i - 1), [commune, idx_state], outputs)
    next_btn.click(lambda c, i: show(c, i + 1), [commune, idx_state], outputs)
    save_btn.click(save_annotation, [commune, idx_state, anonymized, of_interest], status)

    return lambda: show(communes[0][1], 0), outputs
