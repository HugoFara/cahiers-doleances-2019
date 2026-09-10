from pathlib import Path

import gradio as gr
import plotly.offline
from avertissements import details, essentiel, liste_markdown
from avertissements import html as avertissement_html
from data_helpers import etat_du_corpus
from fastapi import Body
from fastapi.responses import FileResponse, HTMLResponse, Response
from source import PDF_DIR
from views import commune, graph, recherche

STYLE = Path(__file__).parent / "views" / "style.css"


# VUE COMMUNES
with gr.Blocks(title="Cahiers de doléances") as demo:
    # barre de navigation : la vue graphe est une page à part (voir le docstring),
    # on y accède par un lien plutôt que par un onglet
    gr.HTML(
        '<div class="nav">'
        '<h1>Visualisation des contributions</h1>'
        '<a class="nav-lien" href="/graphe">Vue graphe des thèmes →</a>'
        "</div>"
    )

    # L'avertissement est au-dessus des onglets, pas dans l'un d'eux : ce qu'un
    # site affiche par défaut décide de la lecture, et ces trois phrases valent
    # pour tout ce que la page montre ensuite. Elles sont visibles sans clic —
    # un avertissement qu'il faut déplier n'est pas un avertissement.
    _etat = etat_du_corpus()
    gr.Markdown(
        "### Ce que ce corpus n'est pas\n\n" + liste_markdown(essentiel(_etat)),
        elem_classes="avertissement",
    )
    with gr.Accordion("Précisions et sources", open=False):
        gr.Markdown(liste_markdown(details(_etat)))

    with gr.Tab("Par commune"):
        load_fn, load_outputs = commune.render()

    with gr.Tab("Recherche"):
        recherche.render()

    demo.load(load_fn, None, load_outputs)


# VUE GRAPH DE TOPIC
app = gr.Server()
# no-store : recharger la page reprend les fichiers static/ à jour
_NO_STORE = {"Cache-Control": "no-store"}

@app.get("/graphe/api/config")
def graphe_config():
    return graph.config()


@app.post("/graphe/api/apercu")
def graphe_apercu(strate: str = Body(..., embed=True)):
    return graph.apercu(strate)


@app.post("/graphe/api/noeud")
def graphe_noeud(nom: str = Body(..., embed=True)):
    return graph.noeud(nom)


@app.get("/graphe/plotly.js")
def graphe_plotly_js():
    return Response(
        plotly.offline.get_plotlyjs(),
        media_type="text/javascript"
    )


@app.get("/graphe/app.js")
def graphe_app_js():
    return FileResponse(
        graph.STATIC / "app.js",
        media_type="text/javascript",
        headers=_NO_STORE
    )


@app.get("/graphe/style.css")
def graphe_style_css():
    return FileResponse(
        graph.STATIC / "style.css",
        media_type="text/css",
        headers=_NO_STORE
    )


@app.get("/graphe")
def graphe_index():
    # L'avertissement est injecté au service plutôt qu'écrit dans le HTML : ses
    # chiffres viennent de la base et doivent suivre le corpus.
    page = (graph.STATIC / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(
        page.replace("<!--avertissement-->", avertissement_html(etat_du_corpus())),
        headers=_NO_STORE
    )


# le Blocks est monté en dernier : sa route "/" ne doit pas masquer /graphe
gr.mount_gradio_app(
    app,
    demo,
    path="/",
    allowed_paths=[str(PDF_DIR)],
    theme=gr.themes.Soft(),
    css_paths=[STYLE]
)


if __name__ == "__main__":
    app.launch()
