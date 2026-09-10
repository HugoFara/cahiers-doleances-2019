"""L'échange avec l'analyse : le corpus qui sort, la grille de thèmes qui revient.

Un run de genre `analyse` est une grille de thèmes posée sur le corpus. Ce
paquet en gère l'aller (`export_dataset.py`, le CSV que lit `topic-builder`) et
le retour (`load_analysis.py`, la livraison chargée en `topic` et `instance`),
avec le format d'identifiant qui permet de rattacher l'un à l'autre
(`identifiants.py`). `taxonomie/` mesure ensuite ce que vaut une grille.
"""
