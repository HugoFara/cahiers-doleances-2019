# Analyse : le corpus qui sort, la grille de thèmes qui revient

Une grille de thèmes est une *lecture* du corpus, pas une propriété du texte :
elle dépend du modèle, du prompt, du nombre de clusters, ou de la main qui l'a
écrite. Elle est donc chargée comme un run de genre `analyse`, daté et attribué,
et plusieurs coexistent — c'est ce qui rend le choix de l'une visible et
discutable, au lieu d'en faire la référence implicite. `taxonomie/` mesure
ensuite ce qu'une grille vaut ; l'app en sert une et permet d'en changer.

Ce paquet gère l'aller et le retour :

| Fichier | Rôle |
|---|---|
| `export_dataset.py` | le corpus vers le CSV `id,content` que lit `topic-builder` |
| `load_analysis.py` | la livraison (`taxonomy.json`, `instances.json`) vers `topic` et `instance` |
| `identifiants.py` | le format d'identifiant de document, partagé par les deux |

## Exporter le corpus pour l'analyse

`analyse/export_dataset.py` écrit le CSV `id,content` attendu par
`topic-builder`, à deux niveaux (`--niveau`) :

- `contribution` (défaut) : lit `page_extraction`, une ligne par contribution,
  pages concaténées dans l'ordre. Les pages `needs_ocr` (manuscrites, texte
  illisible) sont écartées par défaut ; `--keep-ocr-pages` les réintègre pour
  inspecter le corpus complet. **Une contribution, c'est une page** : plusieurs
  contributeurs peuvent s'y côtoyer, et une doléance longue y est coupée en deux.
- `doleance` : lit `doleance`, une ligne par contributeur, telle que
  `segmentation/` l'a découpée. C'est la bonne unité d'analyse.

**L'`id` du document est la clé primaire de la ligne exportée** — `42` pour une
contribution, `d42` pour une doléance. La livraison de l'analyse renvoie ses
labels indexés par cet id, ce qui rend le rapprochement immédiat au retour (voir
plus bas). Le préfixe n'est pas cosmétique : les deux tables ont des id
auto-incrémentés qui se recouvrent, sans marquage une livraison sur les doléances
serait rechargée en désignant des contributions au hasard. Le format est dans
`analyse/identifiants.py`, partagé par l'export et le chargement.

## Charger la livraison de l'équipe analyse

`analyse/load_analysis.py` lit un dossier de livraison (`taxonomy.json` +
`instances.json`) et remplit `topic` et `instance` sous un run de genre
`analyse`. Chaque chargement est une grille de plus, ou la mise à jour de celle
que ce dossier a déjà produite.

`instance.contribution_id` est résolu quand l'id de document de la livraison
correspond à une contribution existante — c'est le cas des livraisons produites
depuis `export_dataset.py`. Sinon (livraisons antérieures, numérotées `doc 73` par
l'équipe analyse) il reste NULL et l'instance n'est rattachée que par
`external_doc_id`, comme avant. Le script affiche le nombre d'instances rattachées.

Quand la livraison porte sur des doléances (ids `d42`), `instance.doleance_id` est
résolu **et** `contribution_id` est repris de la doléance : les vues de l'app
joignent sur `contribution_id`, elles continuent de fonctionner sans connaître le
nouveau niveau.

**La livraison d'août ne décrit pas ce corpus.** `load_analysis.py` vérifie que
les verbatims d'une livraison se retrouvent bien dans le texte visé, et refuse le
rattachement en dessous de 30 % : c'est ce garde-fou qui laisse
`instance.contribution_id` à NULL. Mesuré le 10 septembre 2026, la raison est
plus profonde qu'un décalage d'identifiants — sur les 9 579 extraits de cette
livraison, **3,8 % seulement** se retrouvent dans les 6,4 millions de caractères
de `page_extraction`, et **24 % de son vocabulaire y est absent**. Elle porte sur
une autre extraction, ou un autre périmètre. Aucun rattachement par verbatim ne
la sauvera : il faut refaire l'analyse sur le corpus actuel.

## Commandes

```bash
uv run python -m analyse.export_dataset --output data/dataset.csv                    # corpus -> CSV topic-builder
uv run python -m analyse.export_dataset --niveau doleance --output data/dataset.csv  # au niveau doléance
uv run python -m analyse.load_analysis <dossier>                                     # charger une livraison (met à jour sa grille)
uv run python -m analyse.load_analysis <dossier> --nouveau-run --label "v5"          # charger en grille de plus
```
