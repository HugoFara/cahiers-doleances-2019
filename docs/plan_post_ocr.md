# Plan : et après l'OCR ?

Hypothèse de travail : l'OCR est résolu, tout le corpus est disponible en texte.
Ce document ne décrit pas l'existant (voir les README de chaque module) mais ce
qui reste à faire, et dans quel ordre.

**Constat de départ** : la livraison PoC (`data/analyse_poc_2026-08-11/`) contient
6788 thèmes pour 1380 documents labellisés, dont 4543 au niveau 0 — soit environ un
thème par paragraphe. Et l'unité d'analyse est mal posée : `persist.py` crée *une
contribution par page*, donc `export_dataset.py` envoie *un document = une page*. Or une
page de registre porte souvent plusieurs contributeurs, et une doléance longue court sur
plusieurs pages. Ni la page ni le cahier entier ne sont « ce qu'a écrit une personne ».

## Le principe d'organisation

Choisir des thèmes est déjà une décision. On ne peut pas l'éviter ; on peut la
rendre visible, réversible et non exclusive. D'où la règle qui commande tout le
reste : **les thèmes ne sont pas la structure du corpus, seulement une couche
d'annotation posée dessus.**

Le squelette, c'est la provenance — le principe archivistique de respect des
fonds : on classe selon l'origine, pas selon le contenu. Ici :

```
cote d'archives -> commune (code INSEE) -> cahier -> page -> contribution
```

Chaque maillon porte un identifiant stable qui renvoie à l'image source. Tout le
reste s'y rattache sans jamais le modifier.

**Fait depuis le 2026-09-10.** La table `run` porte chaque couche
interprétative — découpage, grille de thèmes — avec son modèle, son prompt, ses
paramètres, son corpus et son auteur ; `doleance`, `topic` et `instance` s'y
rattachent. Plusieurs grilles coexistent, l'app et les exports servent celle qui
est active. Le `DELETE FROM instance` a disparu.

## Les quatre couches

Chaque couche a son statut épistémique propre ; les séparer explicitement est ce
qui permet d'en retirer une sans casser les autres.

1. **L'image**, conservée intacte.
2. **Les métadonnées factuelles** : commune, date si connue, type de support
   (manuscrit, imprimé, tract ou article collé, lettre jointe, formulaire
   pré-imprimé), type d'auteur (individu, collectif, association, élu). Cette
   dernière distinction compte : une contribution syndicale et un mot manuscrit
   n'ont pas le même poids, et les confondre fausse tous les comptages.
3. **La transcription**, en deux versions. La *diplomatique* conserve
   l'orthographe d'origine — c'est un marqueur social que des chercheurs
   voudront étudier. La *normalisée* ne sert qu'à la recherche.
   État actuel : `clean_page_text` ne touche pas à l'orthographe (elle n'écrase
   que l'espacement), on a donc de fait la diplomatique et pas de normalisée. Le
   piège est devant nous : ne jamais corriger l'orthographe dans la version de
   référence en ajoutant la recherche.
4. **Les annotations interprétatives** : segmentation en doléances, thèmes,
   sentiment, type de revendication. Versionnées, attribuées (humain ou modèle,
   avec quel prompt ou quelle grille), et **plurielles**.

Le découpage en doléances appartient à la couche 4, pas au squelette : c'est une
heuristique qui décide qu'une page porte trois auteurs. Il est versionné comme le
reste depuis le 2026-09-10 (`doleance.run_id`).

**Standards**, pour que le corpus soit réutilisable et pas prisonnier de
l'interface d'un prestataire : IIIF pour les images, PAGE XML ou ALTO pour la
transcription avec coordonnées, EAD pour la description archivistique, TEI
éventuellement pour l'encodage fin.

## Préalable : ne pas se contenter du texte

Demander à l'étape OCR/HTR **le texte ligne par ligne, avec sa bounding box et
son numéro de page** — c'est exactement ce que transportent ALTO et PAGE XML.
Concaténer reste toujours possible, retrouver la géométrie jamais. Elle sert à
trois choses, et la troisième est bloquante :

- découper un registre en contributions distinctes (le blanc vertical et le
  changement d'écriture sont les deux meilleurs séparateurs, et les seuls que le
  texte seul ne donne pas) ;
- renvoyer un verbatim vers son emplacement sur le scan, d'un clic ;
- **occulter les données personnelles sur l'image**, pas seulement dans la
  transcription. Sans coordonnées, c'est impossible.

## Priorité 1 — faire du squelette un squelette

- ~~**Runs et versions.**~~ Fait. L'app annonce la grille servie sur ses deux
  pages (2026-09-10), et la vue commune la filtre enfin — elle cumulait toutes
  les grilles. Reste à imposer l'auteur d'un run plutôt que de le réclamer, et à
  permettre d'**en changer** depuis l'app : cela demande de sortir la taxonomie
  de l'état de module de `views/graph.py`, un refactoring et non un câblage.
- **Commune → code INSEE.** Fait le 2026-09-10 (`insee/`) : le code se lit dans
  le nom du fichier, la table `city` le porte, `contribution.city_code` y
  renvoie. **459 communes au lieu de 307** — le parsing d'en-tête en manquait un
  tiers. Population, nom officiel et coordonnées ajoutés le 2026-09-10 depuis le
  **Code officiel géographique au millésime 2019**, versionné dans
  `insee/referentiel/` : le code des cahiers est une clé datée, et deux d'entre
  eux désignaient déjà une commune absorbée au moment du dépôt. La pondération
  par population est donc en place — et elle dit que **les communes absentes du
  corpus sont les petites** (53 % des communes de l'Ain, 72 % de ses habitants).
- **Types de support et d'auteur** (couche 2). À poser dès maintenant, même
  renseignés à la main sur un échantillon : ils conditionnent l'interprétation de
  tout comptage.
- **Déduplication.** Fait le 2026-09-10 (`doublons/`) : MinHash + LSH au niveau
  doléance, groupes conservés avec le nombre de communes touchées. **13 groupes,
  33 doléances sur 1 002 (3 %).** Le plus gros n'est pas un tract citoyen mais la
  lettre présidentielle qui ouvre les registres, encore présente dans onze
  doléances — à écarter avant tout comptage de thèmes.
- **Reprendre le manuscrit.** `export_dataset.py` et `segmentation/` écartent les
  pages `needs_ocr` : le corpus analysé est *la partie dactylographiée
  seulement*. **Chiffré le 2026-09-10 : 47 % des pages écartées, 37 communes sans
  aucune page lisible** (`couverture/`) — soit 4 % des habitants seulement, les
  communes muettes étant les petites. Les 2 855 pages retenues sont exactement
  les 2 855 documents analysés jusqu'ici. C'est le biais le plus lourd du projet,
  il porte sur la population que ces cahiers devaient faire entendre, et il ne se
  lève qu'avec l'HTR. D'ici là, le taux doit accompagner tout comptage.

## Priorité 2 — les annotations comme couche plurielle

- **Plusieurs grilles doivent coexister.** Au moins deux, dès le départ, pour que
  la comparaison soit possible : une grille émergente (découverte LLM, celle de
  `topic-builder`) et une grille reprenant les thèmes du Grand Débat 2019 —
  étiquetée comme telle, « cadrage gouvernemental 2019 », précisément pour que ce
  cadrage soit visible et discutable au lieu d'être la référence implicite.
  Aucune des deux n'est neutre : la grille émergente déplace simplement la
  décision vers le nombre de clusters, le modèle d'embedding, la formulation du
  prompt et le niveau de granularité.
- **Une catégorie « hors grille » visible, avec son volume.** C'est la seule
  façon de voir ce que la grille ne capte pas. À afficher à côté de tout
  comptage.
- **Mesurer la taxonomie au lieu de la régénérer.** Les 32 passes successives de
  `factorize`/`structure` de `RECIPE.md` traitent un symptôme à la main.
  Instruments : distributions thèmes/document et documents/thème, stabilité entre
  deux runs sur la même entrée, part hors grille, et un **jeu de référence** de
  200-300 doléances annotées à la main. Sans lui on ne peut pas dire si la v5 vaut
  mieux que la v4 — ni ce que vaut le découpage en doléances. L'outillage existe
  depuis le 2026-09-10 (`reference/`) : tirage stratifié reproductible, étalon
  versionnable sans le texte, précision/rappel et WindowDiff. **Il reste à
  annoter** — c'est du travail humain, personne ne peut le produire à la place.
- **Coût et passage à l'échelle.** Embeddings d'abord (une passe, peu chère),
  clustering, appel LLM sur les représentants ; ou distillation d'un petit
  classifieur. Les mêmes vecteurs servent à la recherche sémantique et aux
  quasi-doublons. `pgvector` dans le Postgres déjà en place. Attention au lieu
  d'hébergement (voir P3).

## Priorité 3 — données personnelles

Le point dur, et le seul qui puisse bloquer toute publication.

**Cadre juridique** (à faire valider par un DPO, le service juridique des
Archives, voire la CNIL — les références ci-dessous sont rapportées, non
vérifiées ici) : l'arrêté d'avril 2025 ouvre la *communication* — consultation et
reproduction — pas la publication en ligne. Pour la mise en ligne de documents
administratifs, le CRPA (art. L.312-1-2) pose l'anonymisation en principe. Et un
nom associé à une opinion politique relève des catégories particulières de
l'article 9 du RGPD : c'est très exactement le contenu de ces cahiers.

**Rappel avant précision.** Un nom manqué est une fuite ; un faux positif ne
coûte presque rien. Mesurer le *rappel* de la NER sur un échantillon annoté à la
main, pas un taux global.

**Occulter l'image, pas seulement le texte.** À partir des coordonnées de l'HTR :
noms, adresses, signatures, visages sur les photos. Beaucoup de projets ne
caviardent que la transcription et publient le scan en clair.

**Réidentification contextuelle.** « Je suis la seule infirmière du village, mon
mari est au chômage depuis la fermeture de l'usine », dans une commune de 150
habitants, identifie la personne sans aucun nom. Pseudonymiser n'est pas
anonymiser. Pour les très petites communes il faudra peut-être arbitrer entre
précision géographique et protection — agrégation au canton. Décision à consigner.

**Tiers et personnalités publiques.** Pas lieu d'occulter un ministre cité dans
son rôle. Le voisin, le maire nommément accusé, l'employeur cité, si.

**Hébergement du traitement.** Envoyer des scans bruts porteurs d'opinions
politiques nominatives à une API de LLM hors UE pose un problème de transfert.
Faire la passe d'anonymisation en local (eScriptorium/Kraken pour l'HTR, un NER
français type CamemBERT, ou un LLM hébergé en interne) ou chez un sous-traitant
européen sous contrat. Les modèles externes n'interviennent qu'ensuite, sur du
texte déjà nettoyé.

**Droits d'auteur.** Les articles de presse et tracts collés dans les cahiers
restent protégés : occultation, ou publication de la seule référence.

Techniquement : une table `pii_span` d'offsets et de boîtes — pas une copie
caviardée du texte — une file de relecture humaine, et deux rendus (brut en
interne, caviardé en public). **Fait le 2026-09-10** pour la partie « formes »
(`anonymisation/`) : courriels, téléphones, IBAN, adresses, noms marqués par une
civilité ou posés en signature, et distinction des fonctions publiques et des
adresses institutionnelles, qui n'ont pas à être occultées. **88 % des doléances
contiennent au moins un passage repéré.**

Ce qui reste est le plus dur, et aucune partie n'est une question de code seule :
la reconnaissance d'entités nommées (choix d'un modèle hébergé en UE), la mesure
du rappel (échantillon annoté à la main), l'occultation sur l'image (demande la
géométrie de l'OCR), et la réidentification contextuelle, à laquelle aucune règle
de forme n'accède.

## Priorité 4 — diffusion, et ce qu'elle décide

Un site de consultation est un acte éditorial. Page d'accueil, citations mises en
avant, nuage de mots, tableau « les 10 préoccupations des Français », parcours
scénarisé : c'est la synthèse officielle de 2019 sous une autre forme. Même
l'absence de thèmes est un choix — un site en plein texte seul favorise ceux qui
savent déjà quoi chercher.

Questions à poser au prestataire, et à trancher pour notre propre app :

1. Qui choisit les contenus mis en avant, selon quels critères, et est-ce signé ?
2. Les vues par défaut sont-elles descriptives (carte, commune, chronologie,
   plein texte) ou interprétatives (thèmes, classements) ?
3. Les comptages portent-ils l'avertissement qu'il ne s'agit pas d'un échantillon
   représentatif ? « 34 % des contributions parlent de fiscalité » sera lu comme
   un sondage. Couverture à calculer et à publier : part des communes, pondérée
   par la population, par département.
4. Le corpus et les annotations sont-ils téléchargeables en masse (dump, API,
   IIIF) ? **C'est le point décisif.** Si tout ne passe que par l'interface du
   prestataire, son interprétation est un monopole, quelle que soit la qualité du
   site.

Côté outillage : recherche plein texte (`tsvector`, configuration `french`) et
vectorielle ; annotations désactivables ; chaque étiquette renvoyant à sa page
source en un clic. Les trois avertissements — part écartée, communes muettes,
grille servie — sont affichés depuis le 2026-09-10, et le sélecteur de commune
est passé au code INSEE : il en manquait 153, soit 40 % des contributions hors
d'atteinte.

## Le journal des décisions

Chaque choix — segmentation, grille, règles d'anonymisation, normalisation,
périmètre — est daté, justifié et attribué dans
[`docs/journal_des_decisions.md`](journal_des_decisions.md), publié avec le
corpus. C'est ce qui rend les décisions visibles et donc contestables.

## Décisions à prendre en amont

- **Le livrable** : site d'exploration public, jeu de données ouvert, ou rapport
  de synthèse ? L'anonymisation est existentielle pour les deux premiers,
  secondaire pour le troisième ; la qualité du découpage compte surtout pour le
  troisième.
- **L'alignement national** : le Campus Condorcet pilote la mise en ligne du
  corpus national (à confirmer). Aligner règles d'anonymisation et formats sur
  les leurs évite deux versions incompatibles des mêmes cahiers, l'une plus
  occultée que l'autre. À vérifier avant de figer quoi que ce soit.

**Par où continuer** : faire annoter l'échantillon de référence — l'outillage
attend, le travail humain non, et le découpage sous-coupe visiblement (753 mots
par doléance en moyenne) sans qu'on puisse encore chiffrer de combien.

Côté code, le millésime du Code officiel géographique a été tranché le
2026-09-10 — pivot 2019, table de passage vers le millésime courant, extraits
versionnés — et reste révisable d'une commande si l'alignement national impose
autre chose. Restent entièrement faisables sans décision préalable : les
métriques de taxonomie et la catégorie « hors grille », la **recherche plein
texte** (`tsvector`, configuration `french`) et vectorielle. Tout le reste
attend soit du travail humain (annotation de l'étalon), soit une décision d'alignement (modèle de NER hébergé
en UE, formats IIIF / ALTO / EAD).

---

## Suivi

| Étape | État |
|---|---|
| Table `doleance` + découpage par signaux de texte | fait — `segmentation/` |
| Export et chargement au niveau doléance | fait — `--niveau doleance`, `instance.doleance_id` |
| Journal des décisions | ouvert — `docs/journal_des_decisions.md` |
| Runs et versions (grilles concurrentes, `doleance` versionnée) | fait — `database/runs.py`, table `run` |
| Jeu de référence annoté (200-300 doléances) | outillage fait — `reference/` ; **reste à annoter** |
| Chiffrer la part manuscrite écartée | fait — 47 % des pages, `couverture/` |
| Reprendre le manuscrit (HTR) | à faire — **prochain**, bloqué sur l'OCR |
| Commune -> INSEE | fait — 459 communes contre 307 par graphie |
| Population et coordonnées (Code officiel géographique) | fait — `insee/referentiel/`, millésime pivot 2019 |
| Types de support et d'auteur | à faire |
| Déduplication | fait — 3 % des doléances, `doublons/` |
| Anonymisation : passe de formes | fait — `anonymisation/` ; 88 % des doléances touchées |
| Anonymisation : NER, rappel mesuré, occultation image | à faire — **le point dur** |
| Métriques de taxonomie, catégorie « hors grille » | à faire |
| Recherche plein texte et vectorielle | à faire — **le seul item encore entièrement faisable côté code** |
| Couverture et représentativité | fait — pondérée par population, `insee/` et `couverture/` |
| Standards IIIF / ALTO / EAD, export en masse | à faire |
| Avertissements et couverture affichés dans l'app | fait — les deux vues, `gradio_app/avertissements.py` |
| Changer de grille depuis l'app | à faire — demande de paramétrer `views/graph.py` par run |

**Ce que le découpage donne aujourd'hui** : sur les 2 855 pages de
`topic-builder/data/cahiers/dataset.csv`, 3 243 doléances — 11 % des pages
contiennent plus d'un contributeur repérable. C'est un plancher assumé : les
règles ne lisent que le texte, elles ne voient ni le blanc vertical ni le
changement d'écriture. Le chiffre à surveiller après le passage à l'OCR complet
est celui-là ; s'il ne monte pas franchement, c'est que la géométrie manque
toujours.
