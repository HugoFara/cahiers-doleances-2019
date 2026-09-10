"""Réglages de la recherche plein texte."""

# Configuration de recherche PostgreSQL, posée par la migration
# `b1c5f8e34a72`. Qualifiée : le SQL des requêtes dépend sinon du search_path.
CONFIGURATION = "public.francais_sans_accent"

LIMITE_DEFAUT = 20
LIMITE_MAX = 200

# Largeur de l'extrait rendu autour du terme trouvé, en caractères.
FENETRE = 260

# On cherche le terme de la requête dans le texte en raccourcissant le mot
# jusqu'à ce préfixe : PostgreSQL radicalise (« éoliennes » et « éolien »
# donnent le même lexème), Python non. Descendre plus bas ferait surligner
# n'importe quoi.
PREFIXE_MIN = 4

# Distance maximale parcourue pour recaler une coupe sur une frontière de mot.
# L'OCR produit des blocs de centaines de caractères sans espace : sans borne,
# la recherche d'une frontière y remonterait jusqu'au début du texte.
MARGE_BORD = 40
