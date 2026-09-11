// Le serveur renvoie l'état complet (figure, panneau, groupes, fil d'Ariane) ;
// on l'affiche. Le thème (clair ou sombre) est celui de la page hôte quand la
// vue est intégrée (?theme=), celui du système sinon : c'est ce qui évite le
// passage du sombre au clair entre les onglets et cette vue.

let CONFIG = { apercu: "", grilles: [], grille: null };
let strate = null;
// Grille de thèmes affichée. La base en porte plusieurs à dessein : pouvoir en
// changer ici est ce qui rend le choix de l'une visible et discutable.
let grille = null;

const PARAMS = new URLSearchParams(location.search);
const $ = (id) => document.getElementById(id);
const etat = (texte) => { $("etat").textContent = texte; };

// --- thème ---
function sombre() {
  const voulu = PARAMS.get("theme");
  if (voulu === "dark" || voulu === "light") return voulu === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function appliqueTheme() {
  document.documentElement.classList.toggle("sombre", sombre());
  document.body.classList.toggle("integre", PARAMS.get("integre") === "1");
}

// Les couleurs que la figure ne fixe pas côté serveur : texte, arêtes, contour
// des nœuds, fond de légende. Posées ici pour suivre le thème.
function habille(figure) {
  const d = sombre();
  const encre = d ? "#f3f4f6" : "#1f2937";
  const arete = d ? "#4b5563" : "#d1d5db";
  const fond = d ? "#1f2937" : "#ffffff";
  const bord = d ? "#374151" : "#e5e7eb";
  for (const t of figure.data) {
    if (t.mode === "lines") t.line = { ...(t.line || {}), color: arete };
    if (t.textfont) t.textfont = { ...t.textfont, color: encre };
    if (t.marker && t.marker.line && !t.marker.line.color) {
      t.marker.line = { ...t.marker.line, color: fond };
    }
  }
  figure.layout.font = { ...(figure.layout.font || {}), color: encre };
  figure.layout.legend = {
    ...(figure.layout.legend || {}),
    bgcolor: d ? "rgba(31,41,55,0.8)" : "rgba(255,255,255,0.8)",
    bordercolor: bord,
  };
  return figure;
}

async function poste(route, corps) {
  const r = await fetch(route, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps),
  });
  if (!r.ok) throw new Error(`${route} → HTTP ${r.status}`);
  return r.json();
}

// --- barre d'outils : grille, groupes d'arbres ---
function dessineOutils(strates) {
  const outils = $("outils");
  outils.innerHTML = "";
  if (CONFIG.grilles.length > 1) {
    outils.appendChild(
      champ("Grille de thèmes", CONFIG.grilles, grille, (v) => {
        grille = Number(v);
        chargeApercu(null);
      }),
    );
  }
  // Un seul groupe peuplé : rien à choisir, on ne montre pas le sélecteur.
  const peuples = strates.filter((s) => s.arbres > 0);
  if (peuples.length > 1) {
    const bloc = document.createElement("div");
    bloc.className = "champ";
    const lab = document.createElement("span");
    lab.className = "etiquette";
    lab.textContent = "Groupes d'arbres, par hauteur";
    const seg = document.createElement("div");
    seg.className = "segments";
    seg.setAttribute("role", "tablist");
    for (const s of peuples) {
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", s.value === strate ? "true" : "false");
      b.title = `${s.label} : ${s.hauteur}, ${s.arbres} arbre(s), ${s.part} % des détections`;
      b.innerHTML =
        `<b>${s.label}</b><small>${s.hauteur} · ${s.arbres} arbre(s) · ${s.part} %</small>`;
      b.onclick = () => chargeApercu(s.value);
      seg.appendChild(b);
    }
    bloc.append(lab, seg);
    outils.appendChild(bloc);
  }
}

// --- fil d'Ariane : vue d'ensemble › racine › niveau 1 › … › descendre ---
function dessineFil(niveaux) {
  const fil = $("fil");
  fil.innerHTML = "";
  if (!niveaux.length) return;

  const chevron = () => {
    const c = document.createElement("span");
    c.className = "chevron";
    c.textContent = "›";
    return c;
  };
  const chip = (texte, actif, action) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip" + (actif ? " actif" : "");
    b.textContent = texte;
    b.title = texte;
    if (action) b.onclick = action;
    else b.disabled = true;
    return b;
  };

  const racine = niveaux[0];
  const surApercu = !racine.value || racine.value === CONFIG.apercu;
  fil.appendChild(chip("Vue d'ensemble", surApercu, () => chargeApercu(strate)));

  // La racine reste un sélecteur : sur une grande grille, c'est le moyen de
  // sauter d'un arbre à l'autre sans repasser par la vue d'ensemble.
  fil.appendChild(chevron());
  fil.appendChild(
    selecteur(racine.options, surApercu ? null : racine.value, racine.label, (v) => {
      if (!v || v === CONFIG.apercu) chargeApercu(strate);
      else chargeNoeud(v);
    }),
  );

  for (const niveau of niveaux.slice(1)) {
    fil.appendChild(chevron());
    if (niveau.value) {
      fil.appendChild(chip(niveau.value, niveau === niveaux[niveaux.length - 1], () => chargeNoeud(niveau.value)));
    } else {
      fil.appendChild(selecteur(niveau.options, null, niveau.label, (v) => v && chargeNoeud(v)));
    }
  }
}

// un <select> compact, avec une option vide quand rien n'est choisi
function selecteur(options, valeur, invite, surChangement) {
  const sel = document.createElement("select");
  sel.className = "fil-select";
  sel.title = invite;
  if (valeur === null) {
    const vide = document.createElement("option");
    vide.value = "";
    vide.textContent = invite;
    sel.appendChild(vide);
  }
  for (const o of options) {
    if (o.value === CONFIG.apercu) continue; // la vue d'ensemble a sa puce
    const opt = document.createElement("option");
    opt.value = o.value;
    opt.textContent = o.label;
    opt.title = o.label;
    if (opt.value === String(valeur)) opt.selected = true;
    sel.appendChild(opt);
  }
  sel.onchange = (e) => surChangement(e.target.value);
  return sel;
}

// options : [{value, label}]
function champ(label, options, valeur, surChangement) {
  const bloc = document.createElement("div");
  bloc.className = "champ";
  const lab = document.createElement("label");
  lab.className = "etiquette";
  lab.textContent = label;
  const sel = document.createElement("select");
  for (const o of options) {
    const opt = document.createElement("option");
    opt.value = o.value;
    opt.textContent = o.label;
    opt.title = o.label;
    if (opt.value === String(valeur)) opt.selected = true;
    sel.appendChild(opt);
  }
  sel.onchange = (e) => surChangement(e.target.value);
  bloc.append(lab, sel);
  return bloc;
}

// --- graphe ---
function dessineGraphe(figure) {
  const gd = $("graphe");
  habille(figure);
  Plotly.react(gd, figure.data, figure.layout, {
    responsive: true,
    displaylogo: false,
  });
  // Plotly.react garde les écouteurs : on purge avant de rebrancher
  if (gd.removeAllListeners) gd.removeAllListeners("plotly_click");
  gd.on("plotly_click", (ev) => {
    const nom = ev.points[0].customdata;
    if (nom) chargeNoeud(nom);
  });
}

// --- rendu ---
function applique(reponse) {
  if (reponse.erreur) {
    etat(reponse.erreur);
    return;
  }
  strate = reponse.strate;
  grille = reponse.grille;
  dessineGraphe(reponse.figure);
  dessineOutils(reponse.strates || []);
  dessineFil(reponse.niveaux);
  $("panneau").innerHTML = reponse.description + reponse.occurrences;
}

async function chargeApercu(cle) {
  etat("Cliquer un nœud pour entrer dans un thème.");
  applique(await poste("/graphe/api/apercu", { strate: cle, grille }));
}

async function chargeNoeud(nom) {
  etat(`Sélection : ${nom}`);
  applique(await poste("/graphe/api/noeud", { nom, grille }));
}

// ?grille=<run>&noeud=<nom> : un lien vers une grille, ou un thème dedans.
async function demarre() {
  appliqueTheme();
  CONFIG = await (await fetch("/graphe/api/config")).json();
  grille = Number(PARAMS.get("grille")) || CONFIG.grille;
  const noeud = PARAMS.get("noeud");
  if (noeud) await chargeNoeud(noeud);
  else await chargeApercu(null);
}

demarre().catch((e) => etat(`Erreur : ${e.message}`));
