"""Mesure de ce que le corpus analysé laisse dehors.

Le pipeline écarte les pages `needs_ocr` — celles dont le texte extrait sans OCR
est du bruit, en pratique les pages manuscrites. C'est une décision technique
subie, consignée au [journal](../docs/journal_des_decisions.md), et elle a une
conséquence qui n'est pas technique : **le corpus analysé n'est que sa partie
dactylographiée**. Lettres de maires, contributions d'associations, textes tapés.
L'écriture ordinaire — celle de la personne qui passe à la mairie et écrit trois
lignes dans le registre — n'y est pas.

Tant que ce n'est pas chiffré, toute statistique tirée du corpus se lit comme si
elle portait sur l'ensemble. Ce module produit le chiffre, à afficher à côté de
tout comptage.

Les fonctions ne prennent que des lignes déjà lues : elles se testent sans
PostgreSQL, et elles ne manipulent jamais le texte des cahiers — seulement des
compteurs.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from database.pages import est_commentaire_page_vide, est_derive
from insee.codes import departement
from insee.communes import cle_commune


@dataclass(frozen=True)
class Part:
    """Une population et la portion qui en est écartée."""

    total: int
    ecartes: int

    @property
    def retenus(self) -> int:
        return self.total - self.ecartes

    @property
    def taux(self) -> float:
        """Portion écartée, entre 0 et 1. 0.0 si la population est vide."""
        return self.ecartes / self.total if self.total else 0.0

    def resume(self, nom: str) -> str:
        return f"{nom} : {self.ecartes}/{self.total} écarté(s) ({self.taux:.0%})"


@dataclass
class Couverture:
    """Ce que l'analyse voit du corpus, et ce qu'elle n'en voit pas."""

    pages: Part
    cahiers: Part
    communes: Part
    # Cahiers dont *toutes* les pages sont écartées : ces communes n'ont aucune
    # voix dans l'analyse, ce qui est autre chose qu'être partiellement lue.
    cahiers_muets: list[str] = field(default_factory=list)
    communes_muettes: list[str] = field(default_factory=list)
    # Population des communes du corpus, et celle des communes muettes. Compter
    # les communes met une commune de 90 habitants au même rang qu'une de
    # 16 000 : la part en habitants dit tout autre chose, et les deux ensemble
    # disent où penche le manque.
    habitants: Part | None = None
    # Pages manuscrites que la transcription active a rendues lisibles : la
    # part écartée ci-dessus les compte déjà comme lues.
    transcrites: int = 0

    def resume(self) -> list[str]:
        lignes = [
            self.pages.resume("pages"),
            f"pages manuscrites réintégrées par transcription : {self.transcrites}",
            self.cahiers.resume("cahiers"),
            self.communes.resume("communes"),
            f"cahiers entièrement écartés : {len(self.cahiers_muets)}",
            f"communes sans aucune page lisible : {len(self.communes_muettes)}",
        ]
        if self.habitants is not None:
            lignes.append(
                self.habitants.resume("habitants des communes muettes")
            )
        return lignes


def _ecartee(page, transcrites: frozenset[int] = frozenset()) -> bool:
    """Une page est écartée si elle est `needs_ocr` et sans transcription.

    `is True` et non la valeur brute : la colonne est nullable, et une page
    insérée par une autre voie ne doit pas être comptée comme manuscrite au
    prétexte que le flag est absent — c'est la même logique ternaire que
    `database/pages.py`. Une page manuscrite transcrite par le run
    `transcription` actif a un texte de lecture : elle n'est plus écartée.
    """
    return page.needs_ocr is True and page.id not in transcrites


def mesurer(
    pages: list,
    communes: dict[int, str] | None = None,
    populations: dict[str, int] | None = None,
    noms: dict[str, str] | None = None,
    transcrites: set[int] | None = None,
) -> Couverture:
    """Calcule ce que l'exclusion des pages manuscrites retire du corpus.

    **L'identification des communes change tout au troisième chiffre.** Sans
    `communes`, on retombe sur la graphie parsée de l'en-tête — qui manque sur
    un tiers des cahiers, si bien que ces communes ne sont pas comptées *du
    tout*, ni au numérateur ni au dénominateur. Mesuré sur le corpus : 307
    communes par graphie contre 459 par code INSEE. Passer `communes` donne le
    vrai dénominateur.

    Args:
        pages: lignes `page_extraction`, avec `pdf_name`, `city` et `needs_ocr`.
        communes: ``{contribution_id: code INSEE}`` (`python -m insee
            rattacher`). À défaut, regroupement par graphie, moins fiable.
        populations: ``{code INSEE: population municipale}`` (`python -m insee
            cog`), **déjà purgé des doubles comptes** — une commune déléguée
            dont la parente est là doit y valoir 0, faute de quoi ses habitants
            sont comptés deux fois. `insee.cog.populations_sans_double_compte`
            produit ce dictionnaire ; ce module ne connaît pas la règle.
        noms: ``{code INSEE: nom officiel}``, pour la liste des communes
            muettes. Sans lui, une commune dont l'en-tête était illisible
            s'affiche par son code — et c'est précisément le cas de 14 des 37
            communes muettes du corpus, celles que le rattachement INSEE avait
            justement rendues visibles.
        transcrites: ids des pages que le run `transcription` actif a
            transcrites (`database.pages.transcriptions_actives`). Une page
            manuscrite transcrite n'est plus écartée. Sans lui, la mesure est
            celle du squelette seul.

    Returns:
        La couverture, aux trois échelles qui comptent : la page (le volume de
        texte), le cahier (les registres touchés), la commune (les voix).
    """
    par_cahier: dict[str, list] = defaultdict(list)
    par_commune: dict[str, list] = defaultdict(list)
    ville_affichee: dict[str, str] = {}
    lues = frozenset(transcrites or ())

    def ecartee(page) -> bool:
        return _ecartee(page, lues)

    for page in pages:
        par_cahier[page.pdf_name or "(sans cahier)"].append(page)
        cle = (communes or {}).get(page.contribution_id) if communes else None
        if cle is None and not communes and page.city:
            cle = cle_commune(page.city)
        if cle is None:
            continue
        par_commune[cle].append(page)
        # Le nom officiel l'emporte sur la graphie du cahier : cette liste est
        # faite pour être publiée, et « Vald'Yerre » s'y lit mieux que
        # « COMMUNE NOUVELLE D ARROU ». Reste le code, si on n'a ni l'un ni
        # l'autre — jamais rien.
        ville_affichee.setdefault(cle, (noms or {}).get(cle) or page.city or cle)

    cahiers_muets = sorted(
        nom for nom, p in par_cahier.items() if all(ecartee(x) for x in p)
    )
    communes_muettes = sorted(
        ville_affichee[cle]
        for cle, p in par_commune.items()
        if all(ecartee(x) for x in p)
    )

    habitants = None
    if populations:
        habitants = Part(
            sum(populations.get(cle, 0) for cle in par_commune),
            sum(
                populations.get(cle, 0)
                for cle, p in par_commune.items()
                if all(ecartee(x) for x in p)
            ),
        )

    return Couverture(
        pages=Part(len(pages), sum(1 for p in pages if ecartee(p))),
        cahiers=Part(
            len(par_cahier),
            sum(1 for p in par_cahier.values() if any(ecartee(x) for x in p)),
        ),
        communes=Part(
            len(par_commune),
            sum(1 for p in par_commune.values() if any(ecartee(x) for x in p)),
        ),
        cahiers_muets=cahiers_muets,
        communes_muettes=communes_muettes,
        habitants=habitants,
        transcrites=sum(1 for p in pages if p.needs_ocr is True and p.id in lues),
    )


@dataclass(frozen=True)
class LigneCommune:
    """Ce qu'on lit des pages d'une commune.

    Une page a du texte natif (sa couche texte est lisible), ou n'en a pas
    (`needs_ocr` : en pratique un manuscrit, parfois un scan sans couche
    texte). Les secondes se répartissent selon ce que la transcription active
    en a fait : lues, vides (le modèle dit la page blanche), en échec (le
    modèle a dérivé), ou pas encore traitées.
    """

    code: str
    nom: str
    cahiers: int
    pages: int
    natives: int
    transcrites: int = 0
    vides: int = 0
    echecs: int = 0

    @property
    def sans_texte(self) -> int:
        return self.pages - self.natives

    @property
    def non_traitees(self) -> int:
        return self.sans_texte - self.transcrites - self.vides - self.echecs

    @property
    def departement(self) -> str:
        return departement(self.code) or ""

    @property
    def taux_natif(self) -> float:
        """Part des pages lisibles sans aucune transcription."""
        return self.natives / self.pages if self.pages else 0.0

    @property
    def taux_exploitable(self) -> float:
        """Part des pages dont on lit un texte, transcription comprise.

        Les pages vides restent au dénominateur : une page blanche est une page
        du cahier, et la retirer ferait monter le taux des registres les plus
        creux.
        """
        return (self.natives + self.transcrites) / self.pages if self.pages else 0.0


def par_commune(
    pages: list,
    communes: dict[int, str],
    noms: dict[str, str] | None = None,
    transcriptions: dict[int, str] | None = None,
) -> tuple[list[LigneCommune], int]:
    """Le taux de pages exploitables, commune par commune.

    **Seul le code INSEE fait la commune.** Le repli sur la graphie de
    `mesurer` n'a pas sa place dans une table publiée par commune : il
    ferait deux lignes d'une même commune, et aucune de celles dont l'en-tête
    est illisible. Les pages sans code sont comptées à part.

    Args:
        pages: lignes `page_extraction`, avec `id`, `pdf_name`,
            `contribution_id` et `needs_ocr`.
        communes: ``{contribution_id: code INSEE}``.
        noms: ``{code INSEE: nom}`` ; à défaut, la ligne porte le code.
        transcriptions: ``{id de page: texte}`` du run `transcription` actif.
            Le texte n'est lu que pour classer la page (lue, vide, dérive) ;
            il ne sort pas d'ici.

    Returns:
        Les lignes triées par code, et le nombre de pages sans commune.
    """
    transcriptions = transcriptions or {}
    pages_de: dict[str, list] = defaultdict(list)
    sans_commune = 0
    for page in pages:
        code = communes.get(page.contribution_id)
        if code is None:
            sans_commune += 1
        else:
            pages_de[code].append(page)

    lignes = []
    for code in sorted(pages_de):
        natives = transcrites = vides = echecs = 0
        for page in pages_de[code]:
            if page.needs_ocr is not True:
                natives += 1
                continue
            texte = transcriptions.get(page.id)
            if texte is None:
                continue
            if est_derive(texte):
                echecs += 1
            elif est_commentaire_page_vide(texte) or not texte.strip():
                vides += 1
            else:
                transcrites += 1
        lignes.append(
            LigneCommune(
                code=code,
                nom=(noms or {}).get(code) or code,
                cahiers=len({p.pdf_name for p in pages_de[code]}),
                pages=len(pages_de[code]),
                natives=natives,
                transcrites=transcrites,
                vides=vides,
                echecs=echecs,
            )
        )
    return lignes, sans_commune


def distribution_qualite(pages: list, pas: float = 0.1) -> dict[str, int]:
    """Répartition des scores de qualité, par tranche.

    Le seuil `needs_ocr` est fixé à 0,3 : savoir si les pages s'agglutinent aux
    extrêmes ou s'étalent autour du seuil dit si ce seuil sépare vraiment deux
    populations ou s'il coupe au milieu d'un continuum — auquel cas la part
    écartée dépend surtout de l'endroit où on a mis la barre.

    Args:
        pages: lignes `page_extraction` avec `quality_score`.
        pas: largeur des tranches.

    Returns:
        ``{"0.0-0.1": n, ...}``, tranches vides comprises.
    """
    tranches = {}
    nb = round(1 / pas)
    for i in range(nb):
        tranches[f"{i * pas:.1f}-{(i + 1) * pas:.1f}"] = 0
    for page in pages:
        score = page.quality_score
        if score is None:
            continue
        indice = min(int(score / pas), nb - 1)
        tranches[f"{indice * pas:.1f}-{(indice + 1) * pas:.1f}"] += 1
    return tranches


def sensibilite_seuil(pages: list, seuils: list[float]) -> dict[float, Part]:
    """Part écartée selon l'endroit où on place la barre `needs_ocr`.

    Le seuil de 0,3 est un choix. S'il tombe au milieu d'un continuum, la part
    écartée en dépend directement et le chiffre n'est qu'un artefact de ce
    réglage ; s'il tombe dans un creux entre deux populations, le chiffre tient.
    Cette fonction permet de trancher.

    Args:
        pages: lignes `page_extraction` avec `quality_score`.
        seuils: valeurs à tester.

    Returns:
        ``{seuil: part écartée}``.
    """
    notees = [p for p in pages if p.quality_score is not None]
    return {
        seuil: Part(len(notees), sum(1 for p in notees if p.quality_score < seuil))
        for seuil in seuils
    }
