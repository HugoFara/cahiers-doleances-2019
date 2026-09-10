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

## Ce que coûte l'OCR

**Chiffré le 2026-09-10.** L'équipe initiale avait estimé l'OCR du corpus à
environ **1 500 €** (chiffre rapporté, non retrouvé dans le repo). Aux prix
2026 des modèles de documents, ce chiffre est dépassé d'un facteur 50 à 100,
et c'est un argument décisif pour reprendre le manuscrit :

- **Mistral OCR 4.1** (`mistral-ocr-latest`, entreprise française) facture à la
  page : **4 $ / 1 000 pages** en mode OCR, 5 $ / 1 000 pages en mode Document
  AI (sortie structurée), **−50 % en batch**, +10 % pour l'endpoint régional
  UE. Le corpus entier — 516 cahiers, 5 365 pages de contenu (~6 400 avec les
  pages de métadonnées), dont 2 510 manuscrites — passe pour **22 à 26 $ en
  standard, moitié en batch**. Les seules pages manuscrites : 10 $, 5 $ en
  batch. Vitesse annoncée : 2 000 pages/min — le corpus en quelques minutes.
  Autrement dit, plusieurs passes complètes — comparer des modèles, rejouer
  après correctif — sont envisageables pour un coût négligeable.
- **Alternative locale, 0 €** : `glm-ocr` (0,9B, 2,2 Go) ou `qwen3-vl`
  (30b/32b) sur Ollama. Poids ouverts, aucune donnée ne quitte la machine, le
  corpus tient sur un GPU standard ; seule la vitesse d'inférence diffère.

Repères de qualité : Mistral OCR v1 (2503) annonçait 94,89 en overall sur son
bench interne (GPT-4o : 89,77) et **99,20 sur le français** ; glm-ocr 94,62 sur
OmniDocBench V1.5. Les deux benchmarks ne sont pas comparables entre eux, et
**aucun ne publie de score sur écriture manuscrite** — pour les 2 510 pages
`needs_ocr`, le seul juge valable reste l'échantillon de référence
(`reference/`). C'est lui qu'il faut passer d'abord : une passe API sur
l'échantillon se compte en centimes.

**Essai du 2026-09-10.** Mistral OCR 4.1 passé sur 31 pages — une page seule,
puis deux lots de 15 pages typées et 15 manuscrites tirées au sort
(`data/ocr_essai_2026-09-10/`) : **0,12 $, zéro échec.**

- **Manuscrit** : le score wordfreq — la métrique du projet — passe de
  **0,13 ± 0,06 (garbage) à 0,90 ± 0,05**, plancher à 0,776. Les 15 pages
  passent au-dessus du seuil `needs_ocr` de 0,3 : l'API lit le manuscrit.
  C'est le déblocage des 47 % écartées, pour ~10 $ (batch : ~5 $).
- **Dactylographié** : 2,9 s ± 0,8 s/page ; wordfreq 0,86 → 0,93. WER médian
  contre la référence : 8,4 %. Mais ce WER surestime l'erreur de Mistral — sur
  la page testée en détail, chaque écart était une *correction* de la
  référence (`F£V` → `FEV`, `saint lcxjp du dorât` → `SAINT LOUP DU DORAT`,
  `Ton` → `l'on`) : la couche texte des archives est elle-même corrompue,
  notamment sur les en-têtes — là même où `find_city` lit la commune pour le
  rattachement INSEE. Une repasse OCR améliorerait aussi `insee/`.
- **Le seuil fuit** : 2 des 15 pages « typées » sont en réalité des
  formulaires pré-imprimés remplis à la main — pymupdf n'y lit que les
  pointillés, le wordfreq reste au-dessus de 0,3 (0,44) et la page entre dans
  le corpus analysé avec du garbage. Les 47 % sont un *plancher* de la part
  manuscrite.
- **Réserves** : wordfreq mesure la proportion de mots français connus, pas la
  fidélité — une hallucination fluide scorerait bien ; l'étalon annoté reste
  le seul juge. La sortie est du markdown (`#`, liens d'images) — à normaliser
  avant comparaison ou stockage. L'essai a envoyé des scans bruts porteurs de
  données personnelles à l'API : à cadrer P3 avant toute passe en production.
- **ornith-1.5:9b (Ollama, CPU)** pour comparaison : 207 s/page (contre 4,4),
  chaîne de pensée fuite dans la réponse, en-tête omis, corps du texte juste.
  À retester avec un GPU.

Extrapolation corpus entier : ~6 h en séquentiel, 22 à 26 $.

Le coût ne décide pas seul : envoyer les scans bruts à une API retombe sur la
question de la P3 (hébergement, transfert). Mistral est européen, propose un
endpoint UE (+10 %) et du self-host sélectif ; les modèles locaux tranchent la
question d'office. Une clé `MISTRAL_API_KEY` est en place dans `.env` pour
essayer l'API sur l'échantillon de référence.

## Priorité 1 — faire du squelette un squelette

- ~~**Runs et versions.**~~ Fait. L'app annonce la grille servie sur ses deux
  pages (2026-09-10), et la vue commune la filtre enfin — elle cumulait toutes
  les grilles. L'auteur n'est plus réclamé mais **imposé** depuis le 2026-09-10 :
  `run.author` est `NOT NULL` et `creer_run` le résout d'office
  (`database/auteur.py`). Et l'app sait **en changer** depuis le 2026-09-10 : la
  logique de grille est sortie de l'état de module de `views/graph.py` dans une
  classe `Grille` qui ne connaît ni la base ni Plotly, et que l'on peut donc
  enfin tester — le premier essai sur une petite grille a fait tomber une erreur
  que la grille livrée masquait.
- **Commune → code INSEE.** Fait le 2026-09-10 (`insee/`) : le code se lit dans
  le nom du fichier, la table `city` le porte, `contribution.city_code` y
  renvoie. **459 communes au lieu de 307** — le parsing d'en-tête en manquait un
  tiers. Population, nom officiel et coordonnées ajoutés le 2026-09-10 depuis le
  **Code officiel géographique au millésime 2019**, versionné dans
  `insee/referentiel/` : le code des cahiers est une clé datée, et deux d'entre
  eux désignaient déjà une commune absorbée au moment du dépôt. La pondération
  par population est donc en place — et elle dit que **les communes absentes du
  corpus sont les petites** (53 % des communes de l'Ain, 72 % de ses habitants).
- **Types de support et d'auteur** (couche 2). Fait le 2026-09-10
  (`typologie/`) : deux axes posés sur chaque doléance par des règles de forme,
  versionnés par un run. Le résultat déplace le corpus — **une doléance sur cinq
  n'est pas une contribution** (181 `illisible`, 24 `apparat` : couvertures,
  en-têtes, tampons, manuscrits passés à travers `needs_ocr`, et les mots de
  transmission d'une mairie au préfet). La première personne ne marque que 24 %
  des doléances mais 48 % des mots ; huit pétitions pèsent 4 % du corpus. Ni la
  précision ni le rappel de ces règles ne sont mesurés : cela retombe sur
  l'étalon annoté.
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
  lève qu'avec l'HTR. D'ici là, le taux doit accompagner tout comptage. Le coût
  n'est plus l'obstacle : l'OCR complet du corpus se chiffre en dizaines de
  dollars en API, ou zéro en local — voir « Ce que coûte l'OCR » ci-dessus.

## Priorité 2 — les annotations comme couche plurielle

- **Plusieurs grilles doivent coexister.** Au moins deux, dès le départ, pour que
  la comparaison soit possible : une grille émergente (découverte LLM, celle de
  `topic-builder`) et une grille reprenant les thèmes du Grand Débat 2019 —
  étiquetée comme telle, « cadrage gouvernemental 2019 », précisément pour que ce
  cadrage soit visible et discutable au lieu d'être la référence implicite.
  Aucune des deux n'est neutre : la grille émergente déplace simplement la
  décision vers le nombre de clusters, le modèle d'embedding, la formulation du
  prompt et le niveau de granularité. **La grille gouvernementale existe depuis
  le 2026-09-10** (`analyse/grilles/cadrage_gouvernemental_2019.json`) : les
  quatre thèmes et les vingt questions de la Lettre aux Français, reproduits mot
  pour mot, chargés en run non actif. Il lui manque ses détections, qui
  demandent un modèle — donc la P3.
  **Une troisième depuis le 2026-09-11**, `vrai_debat_2019.json` : les neuf
  rubriques de la plateforme des gilets jaunes, à plat, avec leur distribution
  de référence (économie 31 %, démocratie 20 %, écologie 16 %, santé 10 %).
  Les deux grilles de cadrage ont leurs détections par mots-clés, étalon bas
  d'un futur modèle ; trois lectures chiffrées du même corpus, c'est ce qu'il
  faut apporter à l'atelier de grille avec l'association.
- **Une catégorie « hors grille » visible, avec son volume.** C'est la seule
  façon de voir ce que la grille ne capte pas. À afficher à côté de tout
  comptage.
- **Mesurer la taxonomie au lieu de la régénérer.** Fait le 2026-09-10
  (`taxonomie/`). Sur la grille livrée : **76 % des thèmes attestés le sont par un
  seul document**, 35 % de la grille n'a aucune détection, et les parents produits
  par `structure` ne portent aucune détection propre (99,6 % inutilisés). La
  grille ne généralise pas, elle réécrit le corpus — ce que les 32 passes de
  factorisation ne pouvaient pas montrer, faute d'instrument. La **couverture**
  (« hors grille ») fonctionne dès qu'une livraison est produite par
  `export_dataset.py` ; elle n'est pas mesurable sur la livraison d'août.
  **Mesuré le 2026-09-10 : cette livraison ne décrit pas le corpus qui est en
  base.** Ce n'est pas seulement que ses identifiants sont des rangs de CSV
  (0 à 1523) — sur ses 9 579 extraits, **3,8 % seulement** se retrouvent dans les
  6,4 millions de caractères de `page_extraction`, et **24 % de son vocabulaire y
  est absent**. Elle ne peut donc pas être rerattachée, même en cherchant ses
  verbatims : il faut refaire l'analyse sur le corpus actuel, ce qui suppose un
  LLM et donc la décision d'hébergement de la P3.
- **Le jeu de référence** de 200-300 doléances annotées à la main reste le
  chaînon manquant : les métriques comparent deux grilles entre elles, seul un
  étalon dit laquelle est juste. L'outillage existe (`reference/`) — tirage
  stratifié reproductible, étalon versionnable sans le texte, précision/rappel et
  WindowDiff. **Il reste à annoter**, et c'est du travail humain.
- **Coût et passage à l'échelle.** `pgvector` est posé et la table `embedding`
  attend (2026-09-10) ; le modèle reste à choisir. Embeddings d'abord (une passe, peu chère),
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

Côté outillage : la **recherche plein texte** est faite depuis le 2026-09-10
(`recherche/`), avec une configuration indifférente aux accents — « impot » sans
accent trouvait 22 doléances sur 309. Chaque étiquette renvoie à sa page source
depuis le 2026-09-10 — thèmes, résultats de recherche et visionneuse PDF ouvrent
le cahier à la bonne page (`gradio_app/source.py`). Restent les annotations
désactivables. La recherche vectorielle a sa
base — `pgvector` installé, table `embedding` versionnée par run — et attend le
choix d'un modèle, qui relève de P3 : ces textes sont des opinions politiques
nominatives, la passe doit tourner en UE. Les trois avertissements — part écartée, communes muettes,
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

Côté code, plus rien n'est entièrement faisable sans décision préalable : la
recherche plein texte, dernier chantier de cette catégorie, est faite. `pgvector` est installé
depuis le 2026-09-10 et la table `embedding` attend ; ce qui manque est le choix
d'un modèle, la même décision d'hébergement que pour la NER. Le reste attend du
travail humain ou un alignement.
Le millésime du Code officiel géographique a été tranché le
2026-09-10 — pivot 2019, table de passage vers le millésime courant, extraits
versionnés — et reste révisable d'une commande si l'alignement national impose
autre chose. Tout le reste attend soit du travail humain (annotation de
l'étalon), soit une décision d'alignement (modèle de NER hébergé en UE, formats
IIIF / ALTO / EAD).

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
| Reprendre le manuscrit (HTR) | à faire — **prochain** ; essai Mistral OCR concluant le 2026-09-10 (manuscrit : wordfreq 0,13 → 0,90 sur 15 pages, corpus ~25 $) ; restent l'étalon de qualité et la P3 |
| Commune -> INSEE | fait — 459 communes contre 307 par graphie |
| Population et coordonnées (Code officiel géographique) | fait — `insee/referentiel/`, millésime pivot 2019 |
| Types de support et d'auteur | fait — `typologie/` ; 20 % des doléances ne sont pas des contributions |
| Déduplication | fait — 3 % des doléances, `doublons/` |
| Anonymisation : passe de formes | fait — `anonymisation/` ; 88 % des doléances touchées |
| Anonymisation : NER | fait le 2026-09-11 — `anonymisation/ner.py`, CamemBERT-NER en local sur CPU ; noms 1 309 -> 3 582 sur le découpage servi |
| Anonymisation : rappel mesuré, occultation image | à faire — **le point dur** ; le rappel attend l'étalon annoté, l'image attend la géométrie |
| Métriques de taxonomie, catégorie « hors grille » | fait — `taxonomie/` ; 76 % de singletons |
| Recherche plein texte | fait — `recherche/`, configuration sans accent |
| Recherche vectorielle | base prête (`pgvector`, table `embedding`) — reste le choix du modèle |
| Couverture et représentativité | fait — pondérée par population, `insee/` et `couverture/` |
| Standards IIIF / ALTO / EAD, export en masse | à faire |
| Avertissements et couverture affichés dans l'app | fait — les deux vues, `gradio_app/avertissements.py` |
| Changer de grille depuis l'app | fait — `views/grille.py`, cache par run |
| Grille « cadrage gouvernemental 2019 » | définie — `analyse/grilles/`, 4 thèmes, 20 questions ; détections **par mots-clés** depuis le 2026-09-11 (`analyse/mots_cles.py`, run à part : 65 % des doléances, 7,4 questions chacune — étalon bas) ; un modèle attend la P3 |

**Ce que le découpage donne aujourd'hui** : sur les 2 855 pages de
`topic-builder/data/cahiers/dataset.csv`, **1 002 doléances** dans 469 cahiers,
soit 2,1 par cahier et 753 mots de moyenne — 622 d'entre elles courent sur
plusieurs pages. (Une mesure antérieure annonçait 3 243 doléances et 11 % de
pages à plusieurs contributeurs : elle découpait chaque page isolément, alors que
le pipeline regroupe par cahier. Les 11 % restent vrais des pages prises seules.)
C'est un plancher assumé : les
règles ne lisent que le texte, elles ne voient ni le blanc vertical ni le
changement d'écriture. Le chiffre à surveiller après le passage à l'OCR complet
est celui-là ; s'il ne monte pas franchement, c'est que la géométrie manque
toujours.
