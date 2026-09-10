"""Remplit la table `city` et rattache les contributions à leur commune.

Le rattachement se fait depuis le **nom du fichier**, seule source toujours
disponible en base : les pages d'en-tête ne sont pas persistées par l'extraction
(`SKIP_FIRST_N_PAGES`), leur code n'est donc lisible qu'en rouvrant les PDF.
C'est ce que fait la commande `auditer`, séparément — le rattachement ne doit pas
dépendre de la présence des fichiers d'origine.

Le nom de la commune reste la graphie la plus riche rencontrée dans le corpus,
et non le nom officiel : celui-ci demande le Code officiel géographique, qui
apportera aussi population et coordonnées.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import City, Contribution
from insee.codes import code_du_nom_de_fichier, departement
from insee.communes import cle_commune, regrouper


@dataclass
class Rapport:
    """Ce qu'a donné un rattachement."""

    contributions: int = 0
    rattachees: int = 0
    communes: int = 0
    communes_nommees: int = 0
    cahiers_sans_code: list[str] = field(default_factory=list)

    def resume(self) -> list[str]:
        sans = len(self.cahiers_sans_code)
        return [
            f"contributions rattachées : {self.rattachees}/{self.contributions}",
            f"communes : {self.communes} ({self.communes_nommees} avec une graphie)",
            f"cahiers sans code INSEE : {sans}",
        ]


def graphie_retenue(graphies: list[str]) -> str | None:
    """La graphie la plus riche rencontrée pour une commune.

    Délègue à `insee.communes.regrouper`, qui applique déjà ce critère à la
    liste déroulante de l'app : on affiche « TORCÉ-VIVIERS-EN-CHARNIE » plutôt
    que « TORCE VIVIERS EN CHARNIE ». Réimplémenter le critère ici le ferait
    diverger de l'app à la première retouche.

    Plusieurs groupes sous un même code signalent deux communes différentes
    derrière un seul code INSEE — anomalie de données. On retient alors le
    groupe le plus attesté, sans masquer que le reste existe.

    Args:
        graphies: toutes les graphies rencontrées pour ce code.

    Returns:
        La graphie à afficher, ou ``None`` si aucune n'est exploitable.
    """
    propres = [g.strip() for g in graphies if g and g.strip()]
    if not propres:
        return None
    # `regrouper` dédoublonne les variantes : compter l'attestation demande de
    # regrouper soi-même, puis de lui laisser le choix de la graphie affichée.
    par_commune: dict[str, list[str]] = defaultdict(list)
    for graphie in propres:
        par_commune[cle_commune(graphie)].append(graphie)
    dominante = max(par_commune.values(), key=len)
    return next(iter(regrouper(dominante)))


def rattacher(session: Session) -> Rapport:
    """Rattache chaque contribution au code INSEE de son cahier.

    Idempotent : relancer recalcule les mêmes rattachements et met à jour les
    graphies. Les contributions dont le cahier ne porte pas de code gardent
    `city_code` à NULL — deux cahiers du corpus sont dans ce cas, sans commune à
    la source.

    Args:
        session: session ouverte sur la base (le commit reste à l'appelant).

    Returns:
        Le rapport du rattachement.
    """
    contributions = list(session.scalars(select(Contribution)))
    rapport = Rapport(contributions=len(contributions))

    # Premier passage : lire les codes sans rien écrire. La commune doit exister
    # avant qu'une contribution la désigne, sinon la clé étrangère est violée —
    # et l'autoflush de SQLAlchemy écrirait les contributions en premier.
    codes: dict[int, str | None] = {}
    graphies: dict[str, list[str]] = defaultdict(list)
    sans_code: set[str] = set()
    for contribution in contributions:
        code = code_du_nom_de_fichier(contribution.pdf_file or "")
        codes[id(contribution)] = code
        if code is None:
            if contribution.pdf_file:
                sans_code.add(contribution.pdf_file)
            continue
        if contribution.city:
            graphies[code].append(contribution.city)

    # Deuxième passage : les communes, puis un flush qui les rend référençables.
    connues = {c.code: c for c in session.scalars(select(City))}
    for code in sorted({c for c in codes.values() if c}):
        ville = connues.get(code)
        if ville is None:
            ville = City(code=code)
            session.add(ville)
            connues[code] = ville
        ville.department = departement(code)
        nom = graphie_retenue(graphies.get(code, []))
        if nom:  # ne pas effacer une graphie déjà connue si ce lot n'en a pas
            ville.name = nom
    session.flush()

    # Troisième passage : le rattachement lui-même.
    for contribution in contributions:
        contribution.city_code = codes[id(contribution)]
        rapport.rattachees += contribution.city_code is not None

    rapport.cahiers_sans_code = sorted(sans_code)
    rapport.communes = len(connues)
    rapport.communes_nommees = sum(1 for v in connues.values() if v.name)
    return rapport


def couverture_par_departement(session: Session) -> dict[str, tuple[int, int]]:
    """(communes, contributions) par département.

    C'est l'échelle des Archives départementales, et celle à laquelle la
    question « qu'est-ce qui manque » se pose.
    """
    lignes = session.execute(
        select(City.department, City.code, Contribution.id)
        .join(Contribution, Contribution.city_code == City.code, isouter=True)
    ).all()
    communes: dict[str, set[str]] = defaultdict(set)
    contributions: dict[str, int] = defaultdict(int)
    for departement_code, code, contribution_id in lignes:
        if departement_code is None:
            continue
        communes[departement_code].add(code)
        contributions[departement_code] += contribution_id is not None
    return {
        d: (len(communes[d]), contributions[d]) for d in sorted(communes)
    }
