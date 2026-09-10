"""Qui a produit un run — une obligation, plus un rappel.

Chaque couche interprétative du corpus est attribuée : c'est la contrepartie de
sa réversibilité. Une grille de thèmes qu'on ne peut rattacher à personne ne se
discute pas, elle se subit. Le journal des décisions dit qui a tranché quoi ;
la table `run` doit dire qui a produit quoi.

Jusqu'ici l'auteur était **réclamé** : chaque commande acceptait un `--auteur`
facultatif et se contentait d'imprimer « run sans auteur : renseigner --auteur
avant publication » quand il manquait. Un avertissement qu'on lit une fois puis
plus jamais ne tient pas lieu de contrainte, et la base porte encore des runs
anonymes pour le prouver.

L'auteur est donc **résolu d'office** et la colonne est `NOT NULL`. L'ordre des
sources va du plus explicite au plus implicite :

1. l'argument passé à la commande (`--auteur`) ;
2. la variable d'environnement ``CAHIER_DOLEANCES_AUTEUR``, pour une machine de
   traitement ou un travail par lots ;
3. l'identité git du dépôt — `user.name` / `user.email` s'ils sont configurés,
   sinon celle que git déduit lui-même (`git var GIT_AUTHOR_IDENT`). C'est la
   personne qui lance la passe, et déjà l'identité sous laquelle elle en
   commettra le résultat ;
4. le compte système, en dernier ressort.

Aucune de ces sources ne quitte la machine : l'auteur est écrit dans la base
locale, au même titre que la date du run.
"""

import getpass
import os
import subprocess
from pathlib import Path

VARIABLE = "CAHIER_DOLEANCES_AUTEUR"
RACINE = Path(__file__).resolve().parent.parent


class AuteurInconnu(RuntimeError):
    """Aucune source ne nomme l'auteur : le run ne peut pas être créé."""


def _lancer_git(*arguments: str) -> str | None:
    """Sortie d'une commande git dans le dépôt, ou ``None``.

    Les erreurs sont avalées à dessein : git peut être absent, le dossier peut
    ne pas être un dépôt, la clé peut ne pas être configurée. Aucun de ces cas
    n'est une anomalie, ce sont juste des sources qui ne répondent pas.
    """
    try:
        acheve = subprocess.run(
            ["git", *arguments],
            cwd=RACINE,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    valeur = acheve.stdout.strip()
    return valeur or None


def _git(cle: str) -> str | None:
    """Une valeur de la configuration git du dépôt, ou ``None``."""
    return _lancer_git("config", "--get", cle)


def _git_var(nom: str) -> str | None:
    """Une variable calculée par git (`git var`), ou ``None``."""
    return _lancer_git("var", nom)


def _git_ident_effectif() -> str | None:
    """L'identité sous laquelle git commettrait ici, configurée ou déduite.

    `git var GIT_AUTHOR_IDENT` répond « Nom <courriel> horodatage fuseau » même
    quand `user.name` et `user.email` ne sont pas configurés — git déduit alors
    l'identité du compte et du nom de machine. C'est exactement ce que porteront
    les commits du dépôt, donc la bonne réponse à « qui a lancé cette passe ».
    """
    brut = _git_var("GIT_AUTHOR_IDENT")
    if not brut:
        return None
    ferme = brut.rfind(">")
    return brut[: ferme + 1] if ferme != -1 else None


def _git_identite() -> str | None:
    """« Prénom Nom <courriel> », ou l'un des deux, ou ``None``."""
    nom, courriel = _git("user.name"), _git("user.email")
    if nom and courriel:
        return f"{nom} <{courriel}>"
    return nom or courriel or _git_ident_effectif()


def _compte_systeme() -> str | None:
    """Le compte sous lequel tourne la passe, en dernier ressort."""
    try:
        return getpass.getuser() or None
    except (OSError, KeyError):
        return None


def par_defaut() -> str | None:
    """L'auteur que la machine sait nommer sans qu'on le lui dise.

    Returns:
        L'identité trouvée, ou ``None`` si aucune source ne répond.
    """
    depuis_env = os.environ.get(VARIABLE, "").strip()
    return depuis_env or _git_identite() or _compte_systeme()


def resoudre(auteur: str | None = None) -> str:
    """L'auteur à écrire dans le run.

    Args:
        auteur: ce que la commande a reçu, s'il y a lieu.

    Returns:
        L'identité retenue, jamais vide.

    Raises:
        AuteurInconnu: si aucune source ne nomme personne. Le message dit quoi
            faire ; c'est le seul cas où une passe s'arrête pour cette raison.
    """
    explicite = (auteur or "").strip()
    if explicite:
        return explicite
    trouve = par_defaut()
    if trouve:
        return trouve
    raise AuteurInconnu(
        "Aucun auteur : passer --auteur, ou définir "
        f"{VARIABLE}, ou configurer git (git config user.email). "
        "Un run non attribué ne se discute pas."
    )
