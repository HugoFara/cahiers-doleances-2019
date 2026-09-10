"""Une grille de thèmes, et tout ce qu'on en déduit — sans base ni dessin.

Cette logique vivait dans l'état de module de `views/graph.py` : cinq cents
lignes calculées à l'import, sur la grille servie et sur elle seule. Deux
conséquences, et la seconde était la vraie :

- **on ne pouvait pas changer de grille depuis l'app**, alors que toute la base
  est faite pour que plusieurs coexistent. Annoncer laquelle est servie sans
  permettre d'en essayer une autre, c'est rendre la pluralité théorique ;
- **rien n'était testable.** Un état construit à l'import depuis une connexion
  PostgreSQL ne se monte pas dans un test, et cette vue était la seule du dépôt
  sans aucun test.

D'où cette classe : elle reçoit des lignes, elle calcule, elle ne connaît ni
SQLAlchemy ni Plotly. `views/graph.py` garde le dessin et le service, et tient
un cache de `Grille` par run.

Les lignes attendues sont n'importe quel objet portant les bons attributs — un
`itertuples()` de pandas comme un tuple nommé écrit à la main dans un test.
"""

import math
from collections import Counter, defaultdict, deque

RADIUS = 2           # profondeur du voisinage affiché autour du focus
CAP = 45             # plafond de nœuds dans le voisinage
APERCU_CAP = 260     # plafond de nœuds dans la vue d'ensemble
APERCU_ARBRES = 20   # plafond d'arbres dans la vue d'ensemble

# strates de forêt : elles se définissent par la hauteur, comme notre critère
STRATES = [
    # clé, libellé, test sur la hauteur, part du cercle allouée
    ("A", "Canopée", lambda h: h >= 5, 0.62),
    ("B", "Sous-bois", lambda h: 3 <= h <= 4, 0.26),
    ("C", "Semis", lambda h: h <= 2, 0.12),
]
LIBELLE_STRATE = {cle: lib for cle, lib, _, _ in STRATES}
PROF_APERCU = {"A": 2, "B": 3, "C": 3}   # crans dépliés dans l'aperçu, par strate
APERCU = "— Vue d'ensemble —"            # sentinelle du 1er sélecteur

# ordre validé : deux crans voisins restent distinguables, daltonisme inclus
PROF_COULEUR = ["#2a78d6",  # 0 bleu — racine
                "#eb6834",  # 1 orange
                "#1baf7a",  # 2 aqua
                "#eda100",  # 3 jaune
                "#e87ba4",  # 4 magenta
                "#008300",  # 5 vert
                "#4a3aa7",  # 6 violet
                "#e34948"]  # 7 rouge


def role_du_cran(cran: int) -> str:
    return "racine" if cran == 0 else f"niveau {cran}"


class Grille:
    """Une grille de thèmes prête à être parcourue.

    Args:
        topics: lignes portant `name`, `parent_nom`, `description`.
        detections: lignes portant `topic`, `external_doc_id`, `summary`,
            `verbatim`.
        run_id: le run dont vient cette grille, pour le cache et l'affichage.
        label: son nom lisible.

    Une grille vide est un état normal — base migrée, analyse pas encore
    chargée — et doit se construire sans lever : toutes les collections sont
    alors vides et les vues rendent du vide.
    """

    def __init__(self, topics=(), detections=(), run_id=None, label=None):
        self.run_id = run_id
        self.label = label

        self.par_nom = {ligne.name: ligne for ligne in topics}
        self.parent_nom = {
            nom: (ligne.parent_nom or None) for nom, ligne in self.par_nom.items()
        }

        self.occurrences = defaultdict(list)
        for ligne in detections:
            self.occurrences[ligne.topic].append(
                (ligne.external_doc_id, ligne.summary, ligne.verbatim)
            )
        self.propres = {nom: len(v) for nom, v in self.occurrences.items()}
        self.total_detections = sum(self.propres.values())

        self._structurer()
        self._mesurer_profondeur()
        self._stratifier()

    # --- structure -------------------------------------------------------

    def _structurer(self) -> None:
        """Écarte les isolés et les cycles, puis construit la hiérarchie.

        Un thème sans parent et sans enfant n'est pas un arbre ; un cycle de
        parenté — la livraison en contient — ferait boucler tous les parcours.
        Les deux sont mis de côté plutôt que corrigés : ce sont des faits de la
        grille, pas des erreurs à réparer ici.
        """
        est_parent = {p for p in self.parent_nom.values() if p}
        isoles = {
            nom
            for nom in self.par_nom
            if not self.parent_nom[nom] and nom not in est_parent
        }
        cycliques = {nom for nom in self.par_nom if self._cyclique(nom)}
        self.propre = set(self.par_nom) - isoles - cycliques

        self.parent_de = {
            nom: self.parent_nom[nom]
            for nom in self.propre
            if self.parent_nom[nom] in self.propre
        }
        self.enfants = defaultdict(list)
        for nom, parent in self.parent_de.items():
            self.enfants[parent].append(nom)

        self._memo_rec = {}
        self.racines = self._racines()

    def _cyclique(self, nom, vus=None) -> bool:
        vus = vus or set()
        if nom in vus:
            return True
        vus.add(nom)
        parent = self.parent_nom.get(nom)
        return self._cyclique(parent, vus) if parent and parent in self.par_nom else False

    def _racines(self) -> list[str]:
        """Une racine par composante connexe, les plus fournies d'abord.

        Les arbres sans aucune détection sont écartés : ils encombrent le
        sélecteur sans rien montrer.
        """
        adjacence = defaultdict(set)
        for nom in self.propre:
            adjacence[nom]
            if nom in self.parent_de:
                adjacence[nom].add(self.parent_de[nom])
                adjacence[self.parent_de[nom]].add(nom)

        vus, composantes = set(), []
        for depart in adjacence:
            if depart in vus:
                continue
            pile, composante = [depart], []
            while pile:
                courant = pile.pop()
                if courant in vus:
                    continue
                vus.add(courant)
                composante.append(courant)
                pile.extend(adjacence[courant] - vus)
            composantes.append(composante)

        racines = []
        poids = lambda c: sum(self.propres.get(n, 0) for n in c)  # noqa: E731
        for composante in sorted(composantes, key=lambda c: -poids(c)):
            if poids(composante) == 0:
                continue
            racines.append(
                next(
                    (n for n in composante if n not in self.parent_de), composante[0]
                )
            )
        return racines

    # --- profondeur et strates -------------------------------------------

    def _mesurer_profondeur(self) -> None:
        self.profondeur = {}
        for racine in (n for n in self.propre if n not in self.parent_de):
            self.profondeur[racine] = 0
            file = deque([racine])
            while file:
                courant = file.popleft()
                for enfant in self.enfants[courant]:
                    self.profondeur[enfant] = self.profondeur[courant] + 1
                    file.append(enfant)
        # `default=0` : sans thème en base, `max()` lèverait ValueError et
        # ferait échouer le démarrage de l'app entière, pas seulement cette vue.
        self.prof_max = max(self.profondeur.values(), default=0)

    def _stratifier(self) -> None:
        self.hauteur = {r: self._hauteur_arbre(r) for r in self.racines}
        self.strate_de = {
            r: cle
            for r in self.racines
            for cle, _, test, _ in STRATES
            if test(self.hauteur[r])
        }
        self.racines_strate = {
            cle: [r for r in self.racines if self.strate_de[r] == cle]
            for cle, _, _, _ in STRATES
        }

    def _hauteur_arbre(self, racine: str) -> int:
        crans, file, maximum = {racine: 0}, deque([racine]), 0
        while file:
            courant = file.popleft()
            for enfant in self.enfants[courant]:
                crans[enfant] = crans[courant] + 1
                maximum = max(maximum, crans[enfant])
                file.append(enfant)
        return maximum

    # --- lectures --------------------------------------------------------

    def __len__(self) -> int:
        return len(self.par_nom)

    @property
    def vide(self) -> bool:
        """Aucun arbre à montrer — base migrée mais analyse pas chargée."""
        return not self.racines

    def rec(self, nom: str) -> int:
        """Détections agrégées sur le sous-arbre."""
        if nom not in self._memo_rec:
            self._memo_rec[nom] = self.propres.get(nom, 0) + sum(
                self.rec(enfant) for enfant in self.enfants[nom]
            )
        return self._memo_rec[nom]

    def sous_arbre(self, racine: str) -> set[str]:
        vus, file = set(), deque([racine])
        while file:
            courant = file.popleft()
            if courant in vus:
                continue
            vus.add(courant)
            file.extend(self.enfants[courant])
        return vus

    def kids(self, nom: str) -> list[str]:
        return sorted(self.enfants[nom], key=self.rec, reverse=True)

    def prof(self, nom: str) -> int:
        return self.profondeur[nom]

    def role(self, nom: str) -> str:
        return role_du_cran(self.prof(nom))

    def couleur(self, nom: str) -> str:
        return PROF_COULEUR[self.prof(nom) % len(PROF_COULEUR)]

    def chemin(self, nom: str) -> list[str]:
        """Ancêtres de `nom`, de la racine jusqu'à lui."""
        suite, courant = [], nom
        while courant is not None:
            suite.append(courant)
            courant = self.parent_de.get(courant)
        return list(reversed(suite))

    def bornes_hauteur(self, strate: str) -> str:
        """« 2–5 », « 3 », ou « — » quand la strate ne porte aucun arbre.

        Le « — » n'est pas cosmétique : la version précédente indexait la liste
        triée des hauteurs sans la tester, ce qui levait `IndexError` dès qu'une
        strate était vide. Le cas ne se voyait pas sur la grille livrée, dont les
        trois strates sont peuplées ; il apparaît sur toute grille plus petite.
        """
        hauteurs = sorted({self.hauteur[r] for r in self.racines_strate[strate]})
        if not hauteurs:
            return "—"
        if hauteurs[0] == hauteurs[-1]:
            return str(hauteurs[0])
        return f"{hauteurs[0]}–{hauteurs[-1]}"

    def detections_strate(self, strate: str) -> int:
        return sum(self.rec(r) for r in self.racines_strate[strate])

    def detections_totales(self) -> int:
        """Détections portées par les arbres, apercevables donc comptables."""
        return sum(self.rec(r) for r in self.racines)

    def racines_apercu(self, strate: str) -> list[str]:
        """Les arbres montrés dans l'aperçu : les plus gros d'abord.

        Au-delà d'une vingtaine, le layout radial devient un anneau illisible ;
        le reste de la strate reste accessible par le sélecteur.
        """
        return self.racines_strate[strate][:APERCU_ARBRES]

    # --- squelette et disposition ----------------------------------------

    def squelette(self, prof_max: int, racines: list[str]):
        """Les `prof_max` premiers crans sous la racine, plafonné à APERCU_CAP."""
        portee = (
            set().union(*(self.sous_arbre(r) for r in racines)) if racines else set()
        )
        garde = {n for n in portee if self.prof(n) <= prof_max}
        if len(garde) > APERCU_CAP:
            garde = set(sorted(garde, key=self.rec, reverse=True)[:APERCU_CAP]) | set(
                racines
            )
        lien = {}
        for nom in garde:
            parent = self.parent_de.get(nom)
            while parent is not None and parent not in garde:
                parent = self.parent_de.get(parent)
            lien[nom] = parent
        return garde, lien

    def _budgets(self, racines, poids):
        """Part du cercle par arbre : budget fixe par strate, puis au prorata dedans.

        `poids` = feuilles affichées, pas le sous-arbre complet, sinon le secteur
        est calibré sur des milliers de feuilles alors qu'on en dessine
        quelques dizaines.
        """
        presents = [
            (cle, part)
            for cle, _, _, part in STRATES
            if any(self.strate_de[r] == cle for r in racines)
        ]
        somme_parts = sum(p for _, p in presents) or 1
        budgets = {}
        for cle, part in presents:
            groupe = [r for r in racines if self.strate_de[r] == cle]
            somme = sum(max(1, poids.get(r, 1)) for r in groupe)
            for racine in groupe:
                budgets[racine] = (
                    (part / somme_parts) * max(1, poids.get(racine, 1)) / somme
                )
        return budgets

    def layout_foret(self, garde, lien):
        """Un secteur angulaire par arbre, la profondeur donne le rayon."""
        enfants = defaultdict(list)
        for nom, parent in lien.items():
            if parent is not None:
                enfants[parent].append(nom)
        for parent in enfants:
            enfants[parent].sort(key=self.rec, reverse=True)
        racines = sorted(
            (n for n in garde if lien[n] is None), key=self.rec, reverse=True
        )

        largeur = {}

        def compte(nom):
            if nom not in largeur:
                largeur[nom] = (
                    1 if not enfants[nom] else sum(compte(c) for c in enfants[nom])
                )
            return largeur[nom]

        for racine in racines:
            compte(racine)

        budgets = self._budgets([r for r in racines if r in self.strate_de], largeur)

        crans = {}

        def marque(nom, cran):
            crans[nom] = cran
            for enfant in enfants[nom]:
                marque(enfant, cran + 1)

        for racine in racines:
            marque(racine, 1)

        # rayon : assez d'écart pour que deux nœuds d'un même anneau ne se touchent pas
        rayon = max(
            1.4,
            max(
                (compte * 0.9) / (2 * math.pi * cran)
                for cran, compte in Counter(crans.values()).items()
            ),
        )
        positions = {}

        def place(nom, angle0, angle1):
            angle = (angle0 + angle1) / 2
            positions[nom] = (
                rayon * crans[nom] * math.cos(angle),
                rayon * crans[nom] * math.sin(angle),
            )
            courant = angle0
            for enfant in enfants[nom]:
                part = (angle1 - angle0) * largeur[enfant] / largeur[nom]
                place(enfant, courant, courant + part)
                courant += part

        # strate par strate : les arbres d'une même strate restent voisins à l'écran
        ordre = {cle: i for i, (cle, _, _, _) in enumerate(STRATES)}
        racines = sorted(
            racines,
            key=lambda r: (ordre.get(self.strate_de.get(r), 9), -self.rec(r)),
        )
        courant = 0.0
        for racine in racines:
            part = 2 * math.pi * budgets.get(racine, 1 / len(racines))
            place(racine, courant, courant + part)
            courant += part
        return positions

    def voisinage(self, focus: str) -> dict[str, int]:
        """Parcours en largeur autour du focus, plafonné à CAP nœuds.

        À distance égale, les thèmes les plus fournis passent devant.
        """
        distance = {focus: 0}
        file = deque([focus])
        while file:
            nom = file.popleft()
            if distance[nom] >= RADIUS:
                continue
            voisins = ([self.parent_de[nom]] if nom in self.parent_de else []) + (
                self.enfants[nom]
            )
            for voisin in sorted(voisins, key=self.rec, reverse=True):
                if voisin not in distance:
                    distance[voisin] = distance[nom] + 1
                    file.append(voisin)
        if len(distance) <= CAP:
            return distance
        garde = sorted(distance, key=lambda n: (distance[n], -self.rec(n)))[:CAP]
        return {n: distance[n] for n in garde}
