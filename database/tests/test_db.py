"""Tests des helpers de connexion à la base."""

import pytest
from sqlalchemy import create_engine

from database.db import check_connection


def test_check_connection_passe_sur_une_base_joignable():
    check_connection(create_engine("sqlite://"))


def test_check_connection_abandonne_avec_un_message_lisible():
    """Le README promet un échec immédiat nommant l'hôte, le port et la base."""
    engine = create_engine("postgresql+psycopg2://u:p@127.0.0.1:1/base_absente")
    with pytest.raises(SystemExit) as abandon:
        check_connection(engine)

    message = str(abandon.value)
    assert "127.0.0.1" in message
    assert "port=1" in message
    assert "base_absente" in message
