"""La recherche elle-même : une requête, des doléances, des extraits.

Le corpus ne s'atteignait jusqu'ici que commune par commune, ce qui convient à
l'annotation et à personne d'autre. « Tout ce qui parle d'éoliennes » n'avait pas
de réponse.

Trois choses que cette recherche fait et qui ne vont pas de soi :

- **elle porte sur les doléances**, l'unité d'analyse du corpus — ce qu'a écrit
  une personne — et non sur la page ni sur le cahier entier ;
- **elle ne sert qu'un découpage**, celui du run actif, comme les vues de thèmes
  ne servent qu'une grille : sans ce filtre deux découpages concurrents
  rendraient chaque doléance deux fois ;
- **elle caviarde ce qu'elle montre.** Un extrait sorti de son cahier, rendu à
  qui interroge, est le premier endroit où le corpus se lit en vrac. Les
  passages personnels repérés y sont occultés, et un passage non relu l'est
  aussi.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from anonymisation.rendu import PassageRendu, caviarder
from recherche.config import CONFIGURATION, LIMITE_DEFAUT, LIMITE_MAX
from recherche.extraits import fenetre, termes

DECOUPAGE_SERVI = "(SELECT id FROM run WHERE kind = 'segmentation' AND active)"
ANONYMISATION_SERVIE = "(SELECT id FROM run WHERE kind = 'anonymisation' AND active)"
DOUBLONS_SERVIS = "(SELECT id FROM run WHERE kind = 'doublons' AND active)"


class RequeteVide(ValueError):
    """Une recherche sans terme rendrait le corpus entier, ce qui n'est pas une recherche."""


@dataclass(frozen=True)
class Resultat:
    """Une doléance trouvée, telle qu'on peut la montrer."""

    doleance_id: int
    cahier: str | None
    commune: str | None
    code_commune: str | None
    rang: float
    mots: int | None
    extrait: str
    caviarde: bool
    # Nombre de communes où ce même texte se retrouve, si la déduplication a
    # tourné. Une liste de résultats où les trois premiers sont le même tract
    # recopié se lit tout autrement selon qu'on le sait ou non.
    communes_du_groupe: int | None = None
    # Pages du cahier où la doléance commence et finit. C'est le seul chemin de
    # retour à la source que le corpus permette aujourd'hui : l'ancre `#page=`
    # d'une visionneuse PDF. Encadrer le passage sur l'image demanderait la
    # géométrie des lignes, que l'extraction ne produit pas.
    page_debut: int | None = None
    page_fin: int | None = None

    @property
    def recopie(self) -> bool:
        """Vrai si ce texte se retrouve dans plusieurs communes."""
        return bool(self.communes_du_groupe and self.communes_du_groupe > 1)

    def resume(self) -> str:
        ou = self.commune or self.code_commune or "commune inconnue"
        page = f" p. {self.page_debut}" if self.page_debut else ""
        marques = []
        if self.recopie:
            marques.append(f"↻ même texte dans {self.communes_du_groupe} communes")
        if not self.caviarde:
            marques.append("⚠ non caviardé")
        suffixe = ("  " + " · ".join(marques)) if marques else ""
        return f"[{self.rang:.4f}] {ou} · doléance {self.doleance_id}{page}{suffixe}"


_SQL = f"""
    SELECT d.id, d.pdf_name, d.text, d.num_words, d.start_page, d.end_page,
           k.city_code, v.official_name, v.name,
           dg.cities,
           ts_rank_cd(to_tsvector('{CONFIGURATION}', coalesce(d.text, '')), q.query) AS rang
    FROM doleance d
    CROSS JOIN websearch_to_tsquery('{CONFIGURATION}', :requete) AS q(query)
    LEFT JOIN contribution k ON k.id = d.contribution_id
    LEFT JOIN city v ON v.code = k.city_code
    LEFT JOIN duplicate_member dm ON dm.doleance_id = d.id
    LEFT JOIN duplicate_group dg
           ON dg.id = dm.group_id AND dg.run_id = {DOUBLONS_SERVIS}
    WHERE d.run_id = {DECOUPAGE_SERVI}
      AND to_tsvector('{CONFIGURATION}', coalesce(d.text, '')) @@ q.query
    ORDER BY rang DESC, d.id
    LIMIT :limite
"""

_SQL_PASSAGES = f"""
    SELECT doleance_id, start, "end", kind, confirmed
    FROM pii_span
    WHERE run_id = {ANONYMISATION_SERVIE}
      AND doleance_id = ANY(:ids)
"""

_SQL_COMPTE = f"""
    SELECT count(*)
    FROM doleance d
    CROSS JOIN websearch_to_tsquery('{CONFIGURATION}', :requete) AS q(query)
    WHERE d.run_id = {DECOUPAGE_SERVI}
      AND to_tsvector('{CONFIGURATION}', coalesce(d.text, '')) @@ q.query
"""


def compter(session: Session, requete: str) -> int:
    """Combien de doléances répondent, sans en rapporter aucune.

    Le total compte : un extrait sur vingt ne dit pas si le terme est rare ou
    partout, et c'est cette différence qui décide de la suite d'une recherche.
    """
    if not requete or not requete.strip():
        raise RequeteVide("Aucun terme de recherche.")
    return session.execute(text(_SQL_COMPTE), {"requete": requete}).scalar() or 0


def _passages(session: Session, ids: list[int]) -> dict[int, list[PassageRendu]]:
    """Les passages personnels des doléances rendues, groupés par doléance."""
    if not ids:
        return {}
    par_doleance: dict[int, list[PassageRendu]] = {}
    for ligne in session.execute(text(_SQL_PASSAGES), {"ids": ids}):
        par_doleance.setdefault(ligne.doleance_id, []).append(
            PassageRendu(
                debut=ligne.start,
                fin=ligne.end,
                genre=ligne.kind,
                confirme=ligne.confirmed,
            )
        )
    return par_doleance


def chercher(
    session: Session,
    requete: str,
    limite: int = LIMITE_DEFAUT,
    *,
    caviardage: bool = True,
) -> list[Resultat]:
    """Les doléances qui répondent à la requête, du plus pertinent au moins.

    La requête suit la syntaxe de `websearch_to_tsquery` : les mots s'ajoutent,
    les guillemets font une expression exacte, `or` alterne, un tiret exclut.
    C'est la syntaxe que les gens connaissent des moteurs de recherche, et elle
    ne lève jamais d'erreur de syntaxe — un opérateur mal placé devient un mot.

    Args:
        session: session ouverte sur la base.
        requete: les termes cherchés.
        limite: nombre maximum de résultats, plafonné par `LIMITE_MAX`.
        caviardage: occulter les passages personnels dans les extraits. Ne le
            désactiver que pour un usage interne, jamais pour un rendu servi.

    Returns:
        Les résultats, extraits compris.

    Raises:
        RequeteVide: si la requête ne porte aucun terme.
    """
    if not requete or not requete.strip():
        raise RequeteVide("Aucun terme de recherche.")

    lignes = session.execute(
        text(_SQL),
        {"requete": requete, "limite": min(max(1, limite), LIMITE_MAX)},
    ).all()

    passages = _passages(session, [ligne.id for ligne in lignes]) if caviardage else {}
    mots = termes(requete)

    resultats = []
    for ligne in lignes:
        brut = ligne.text or ""
        texte = caviarder(brut, passages.get(ligne.id, [])) if caviardage else brut
        resultats.append(
            Resultat(
                doleance_id=ligne.id,
                cahier=ligne.pdf_name,
                commune=ligne.official_name or ligne.name,
                code_commune=ligne.city_code,
                rang=float(ligne.rang or 0.0),
                mots=ligne.num_words,
                extrait=fenetre(texte, mots),
                caviarde=caviardage,
                communes_du_groupe=ligne.cities,
                page_debut=ligne.start_page,
                page_fin=ligne.end_page,
            )
        )
    return resultats
