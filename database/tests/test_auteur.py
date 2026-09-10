"""Tests de l'attribution des runs : imposée, plus réclamée."""

import pytest

from database import auteur


def test_l_argument_explicite_l_emporte_sur_tout(monkeypatch):
    monkeypatch.setenv(auteur.VARIABLE, "la variable")
    assert auteur.resoudre("  Camille Dupont  ") == "Camille Dupont"


def test_un_argument_vide_ne_compte_pas_pour_un_auteur(monkeypatch):
    """`--auteur ""` ne doit pas ouvrir la porte à un run anonyme."""
    monkeypatch.setenv(auteur.VARIABLE, "la variable")
    assert auteur.resoudre("   ") == "la variable"


def test_la_variable_d_environnement_sert_aux_traitements_par_lots(monkeypatch):
    monkeypatch.setenv(auteur.VARIABLE, "chaîne de traitement nocturne")
    assert auteur.resoudre() == "chaîne de traitement nocturne"


def test_a_defaut_la_configuration_git_du_depot(monkeypatch):
    monkeypatch.delenv(auteur.VARIABLE, raising=False)
    monkeypatch.setattr(auteur, "_git_identite", lambda: "Camille <c@example.org>")
    assert auteur.resoudre() == "Camille <c@example.org>"


def test_puis_le_compte_systeme(monkeypatch):
    monkeypatch.delenv(auteur.VARIABLE, raising=False)
    monkeypatch.setattr(auteur, "_git_identite", lambda: None)
    monkeypatch.setattr(auteur, "_compte_systeme", lambda: "camille")
    assert auteur.resoudre() == "camille"


def test_sans_aucune_source_la_passe_s_arrete(monkeypatch):
    """Le seul cas où l'absence d'auteur bloque : plus aucun run anonyme."""
    monkeypatch.delenv(auteur.VARIABLE, raising=False)
    monkeypatch.setattr(auteur, "_git_identite", lambda: None)
    monkeypatch.setattr(auteur, "_compte_systeme", lambda: None)
    with pytest.raises(auteur.AuteurInconnu):
        auteur.resoudre()


def test_git_absent_ou_hors_depot_ne_leve_rien(monkeypatch):
    """git manquant est une source qui ne répond pas, pas une anomalie."""

    def explose(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(auteur.subprocess, "run", explose)
    assert auteur._git("user.email") is None
    assert auteur._git_identite() is None


def test_sans_user_name_ni_user_email_on_prend_l_identite_deduite_par_git(monkeypatch):
    """Un dépôt non configuré commet quand même sous une identité : c'est elle."""
    monkeypatch.setattr(auteur, "_git", lambda cle: None)
    monkeypatch.setattr(
        auteur, "_git_var", lambda nom: "Camille <camille@poste.local> 1757520000 +0200"
    )
    assert auteur._git_identite() == "Camille <camille@poste.local>"
