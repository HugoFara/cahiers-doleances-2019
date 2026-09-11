from pathlib import Path

import gradio as gr
import plotly.offline
from fastapi import Body
from fastapi.responses import FileResponse, HTMLResponse, Response

from gradio_app.avertissements import details, essentiel, liste_markdown
from gradio_app.avertissements import html as avertissement_html
from gradio_app.data_helpers import etat_du_corpus
from gradio_app.source import PDF_DIR
from gradio_app.views import commune, graph, recherche

STYLE = Path(__file__).parent / "views" / "style.css"


# La vue thèmes est une page à part (Plotly et son évènement de clic, que
# gr.Plot n'expose pas). Elle est intégrée dans un onglet plutôt que reliée par
# un lien : trois onglets, un en-tête, un avertissement, un thème — passer du
# sombre de Gradio au clair d'une autre page cassait le fil. Le cadre reçoit
# le thème de l'hôte par l'URL, posée au chargement (voir plus bas).
CADRE_GRAPHE = (
    '<iframe id="cadre-graphe" src="/graphe?integre=1" title="Thèmes" '
    'style="width:100%;height:960px;border:0;display:block"></iframe>'
)
# Le thème de Gradio est celui du système, ou celui forcé par ?__theme= ; la
# page intégrée ne le connaît pas, on le lui passe.
JS_THEME_CADRE = """
() => {
  const cadre = document.getElementById("cadre-graphe");
  if (!cadre) return;
  const sombre = document.body.classList.contains("dark")
    || !!document.querySelector(".gradio-container.dark")
    || (new URLSearchParams(location.search).get("__theme") !== "light"
        && window.matchMedia("(prefers-color-scheme: dark)").matches);
  cadre.src = "/graphe?integre=1&theme=" + (sombre ? "dark" : "light");
}
"""

with gr.Blocks(title="Cahiers de doléances") as demo:
    gr.HTML('<div class="nav"><h1>Cahiers de doléances</h1></div>')

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

    with gr.Tab("Thèmes"):
        gr.HTML(CADRE_GRAPHE)

    demo.load(load_fn, None, load_outputs)
    demo.load(None, None, None, js=JS_THEME_CADRE)


# VUE GRAPH DE TOPIC
app = gr.Server()
# no-store : recharger la page reprend les fichiers static/ à jour
_NO_STORE = {"Cache-Control": "no-store"}

@app.get("/graphe/api/config")
def graphe_config():
    return graph.config()


@app.post("/graphe/api/apercu")
def graphe_apercu(strate: str | None = Body(None), grille: int | None = Body(None)):
    return graph.apercu(strate, grille)


@app.post("/graphe/api/noeud")
def graphe_noeud(nom: str = Body(...), grille: int | None = Body(None)):
    return graph.noeud(nom, grille)


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
    # police système des deux côtés : la page thèmes n'a pas la Montserrat de
    # Gradio, et deux polices pour une app se voient tout de suite
    theme=gr.themes.Soft(font=["ui-sans-serif", "system-ui", "sans-serif"]),
    css_paths=[STYLE]
)


if __name__ == "__main__":
    app.launch()
