from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class City(Base):
    """Une commune, identifiée par son code INSEE.

    `contribution.city` est une graphie parsée de l'en-tête du PDF : la même
    commune n'y est pas écrite pareil d'un cahier à l'autre, et le parsing
    échoue sur un tiers du corpus. Le code INSEE est la clé qui manquait —
    stable, officielle, et elle porte le département.

    Deux noms, et la distinction compte : `name` est la graphie la plus riche
    rencontrée **dans le corpus** — ce qu'a écrit l'en-tête du cahier — quand
    `official_name` est celui du Code officiel géographique. Le premier est un
    fait de provenance, le second un référentiel ; écraser l'un par l'autre
    perdrait de l'information dans les deux sens.

    **Le millésime pivot est 2019**, celui du dépôt des cahiers. `code` ne bouge
    jamais : `current_code` porte le code actuel comme une annotation, et non
    comme une correction. Voir `insee/referentiel/SOURCES.md`.
    """

    __tablename__ = "city"

    code = Column(String(5), primary_key=True)  # INSEE 2019 ; 2A/2B pour la Corse
    name = Column(String)  # graphie rencontrée dans le corpus
    official_name = Column(String)  # libellé du COG au millésime pivot
    # Indexé : la couverture se lit par département, échelle des Archives.
    department = Column(String, index=True)  # dérivé du code, Corse et outre-mer compris
    # COM (plein exercice), COMD (déléguée), COMA (associée) au millésime pivot.
    # Deux cahiers du corpus portent le code d'une commune déjà absorbée.
    cog_type = Column(String(4))
    parent_code = Column(String(5))  # commune absorbante, si cog_type != COM
    current_code = Column(String(5))  # millésime courant, via la table de passage
    # Population municipale (PMUN). Celle d'une commune déléguée est **incluse**
    # dans celle de sa commune parente : les sommer compte deux fois.
    population = Column(Integer)
    latitude = Column(Float)
    longitude = Column(Float)


class Embedding(Base):
    """La représentation vectorielle d'une doléance, pour une passe donnée.

    Table à part et non colonne sur `doleance` : un vecteur dépend d'un modèle,
    de sa version et du découpage du texte qu'on lui a donné. C'est une lecture
    du corpus, pas une propriété de la doléance — même raisonnement que pour
    `duplicate_member` et `pii_span`, et deux passes doivent pouvoir coexister
    pour être comparées.

    **La colonne `vector` n'a pas de dimension déclarée**, et ce n'est pas un
    oubli : la dimension dépend du modèle, qui n'est pas choisi. pgvector accepte
    un vecteur non contraint, mais **refuse de l'indexer** — une recherche
    vectorielle passera donc par un parcours complet tant que la dimension n'est
    pas fixée. Sur mille doléances c'est sans conséquence ; le jour où le modèle
    est choisi, une migration fixe la dimension et pose l'index HNSW.
    """

    __tablename__ = "embedding"
    __table_args__ = (
        UniqueConstraint("run_id", "doleance_id", name="uq_embedding_run_doleance"),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("run.id"))
    # Indexé : « le vecteur de cette doléance » est la question la plus posée.
    doleance_id = Column(Integer, ForeignKey("doleance.id"), index=True)
    vector = Column(Vector())


class Contribution(Base):
    __tablename__ = "contribution"

    id = Column(Integer, primary_key=True)
    city = Column(String)  # graphie parsée de l'en-tête ; city_code fait foi
    # Rempli par `python -m insee rattacher`, depuis le code porté par le nom du
    # fichier. NULL quand le cahier n'en porte pas (deux cas dans le corpus).
    city_code = Column(String(5), ForeignKey("city.code"))
    pdf_file = Column(
        String
    )  # nom du fichier du cahier ; TODO ajuster en fonction de l'adaptation S3
    start_page = Column(Integer)
    end_page = Column(Integer)
    is_handwritten = Column(Boolean)


class Extraction(Base):
    __tablename__ = "extraction"

    id = Column(Integer, primary_key=True)
    contribution_id = Column(Integer, ForeignKey("contribution.id"))
    ocr = Column(String)
    text = Column(Text)
    num_words = Column(Integer)
    num_lines = Column(Integer)


class PageExtraction(Base):
    """Page-by-page extracted text with quality scoring and an OCR flag.

    One row per persisted PDF page. Metadata pages (first two) are not inserted
    here; they are only used to extract ``city``.
    """

    __tablename__ = "page_extraction"

    id = Column(Integer, primary_key=True)
    contribution_id = Column(Integer, ForeignKey("contribution.id"))
    pdf_name = Column(String)
    page_number = Column(Integer)
    text = Column(Text)  # texte extrait et nettoyé
    quality_score = Column(Float)  # 0.0 (garbage) à 1.0 (texte propre)
    needs_ocr = Column(Boolean)  # page manuscrite suspectée
    city = Column(String)  # ville extraite
    # Catégorie du versement, lue dans le préfixe du nom de fichier : CC
    # (cahiers citoyens), CO (courriers), CR / IL (comptes rendus). NULL hors
    # de la convention de nommage. Les lectures du corpus filtrent dessus :
    # les quatre ne se mélangent pas.
    categorie = Column(String(2), index=True)


class PageTranscription(Base):
    """La transcription OCR d'une page, pour une passe donnée.

    Couche 3 du plan : la transcription dépend d'un modèle, de sa version, du
    rendu (DPI) et d'une consigne — c'est une lecture de l'image, pas une
    propriété de la page. Comme `embedding`, `typologie` ou `pii_span`, elle
    vit dans une table à part, versionnée par un run ; deux passes coexistent
    pour être comparées, et le squelette (`page_extraction.text`) n'est jamais
    écrasé.

    `layout` conserve la géométrie ligne à ligne quand le backend la donne
    (Mistral OCR renvoie texte et polygones) : concaténer reste toujours
    possible, retrouver les coordonnées jamais. C'est le préalable du plan —
    découpage sur le blanc vertical, verbatim lié au scan, occultation sur
    l'image. NULL pour les backends qui ne rendent que du texte.

    `text` est la version diplomatique : l'orthographe d'origine n'est pas
    touchée, seulement la syntaxe markdown du backend retirée. La version
    normalisée ne sert qu'à la recherche et se produit à la lecture.
    """

    __tablename__ = "page_transcription"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "page_extraction_id", name="uq_page_transcription_run_page"
        ),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("run.id"))
    # Indexé : « la transcription de cette page » est la question la plus
    # posée, et la passe se relit page par page.
    page_extraction_id = Column(
        Integer, ForeignKey("page_extraction.id"), index=True
    )
    # Indexé : la relecture et le rejeu se font cahier par cahier, comme
    # `doleance`.
    pdf_name = Column(String, index=True)
    page_number = Column(Integer)
    text = Column(Text)  # transcription normalisée, orthographe d'origine
    layout = Column(JSON)  # lignes et coordonnées, si le backend les donne
    quality_score = Column(Float)  # wordfreq de la transcription


class Run(Base):
    """Une production de couche interprétative : un découpage, une livraison d'analyse.

    Les thèmes ne sont pas la structure du corpus, seulement une couche posée
    dessus — et une couche doit pouvoir être versionnée, attribuée, comparée à
    une autre, et retirée. Avant cette table, `load_analysis` faisait
    `DELETE FROM instance` à chaque livraison : une seule grille pouvait exister
    à la fois, et rien ne disait de quel modèle ni de quel prompt elle venait.

    `active` désigne le run servi par défaut pour son genre — un index unique
    partiel garantit qu'il n'y en a qu'un. Les autres restent en base, lisibles
    et comparables.
    """

    __tablename__ = "run"
    __table_args__ = (
        Index(
            "uq_run_actif_par_genre",
            "kind",
            unique=True,
            sqlite_where=text("active"),
            postgresql_where=text("active"),
        ),
    )

    id = Column(Integer, primary_key=True)
    kind = Column(String)  # "segmentation" | "analyse" (database/runs.py)
    label = Column(String)  # nom court lisible : « grille émergente v4 »
    source = Column(String)  # dossier de livraison, ou module producteur
    model = Column(String)  # modèle LLM ou OCR utilisé, s'il y en a un
    prompt_version = Column(String)
    parameters = Column(JSON)  # seuils et config, tels qu'appliqués
    corpus = Column(String)  # ce sur quoi le run a tourné
    # NOT NULL : une couche interprétative anonyme ne se discute pas. L'auteur
    # est résolu d'office par `creer_run` (voir `database/auteur.py`), il n'est
    # plus réclamé après coup.
    author = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    active = Column(Boolean)  # run servi par défaut pour ce genre
    notes = Column(Text)


class Doleance(Base):
    """Le texte d'un contributeur : l'unité d'analyse réelle du corpus.

    Une page de registre porte souvent plusieurs contributeurs, et une doléance
    longue court sur plusieurs pages : ni ``page_extraction`` ni ``contribution``
    ne délimitent « ce qu'a écrit une personne ». Cette table le fait, en
    découpant le texte d'un cahier (``pdf_name``) sur les signaux de rupture
    visibles dans le texte (voir ``segmentation/``).

    Le découpage est heuristique et assumé comme tel : ``signal`` conserve la
    règle qui a ouvert la doléance, pour pouvoir mesurer la qualité du découpage
    et rejouer le corpus quand l'OCR fournira la géométrie des lignes.
    """

    __tablename__ = "doleance"
    __table_args__ = (
        # Index d'expression, pas colonne générée : une colonne `tsvector` sur
        # le modèle casserait les tests, qui montent le schéma sur SQLite.
        # `ddl_if` réserve sa création à PostgreSQL tout en le laissant dans les
        # métadonnées, ce qui garde `alembic check` d'accord avec la base.
        Index(
            "ix_doleance_recherche",
            text("to_tsvector('public.francais_sans_accent', coalesce(text, \'\'))"),
            postgresql_using="gin",
        ).ddl_if(dialect="postgresql"),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("run.id"))  # découpage qui l'a produite
    # Contribution de la page où la doléance commence : garde le lien vers la
    # commune et les annotations existantes. NULL si la page était orpheline.
    contribution_id = Column(Integer, ForeignKey("contribution.id"))
    # Indexé : le découpage se relit et se rejoue cahier par cahier.
    pdf_name = Column(String, index=True)
    city = Column(String)
    position = Column(Integer)  # rang dans le cahier, à partir de 0
    start_page = Column(Integer)
    end_page = Column(Integer)
    text = Column(Text)
    signal = Column(String)  # règle de découpage ayant ouvert la doléance
    num_words = Column(Integer)


class DuplicateGroup(Base):
    """Un ensemble de doléances au texte quasi identique.

    Les registres contiennent des tracts collés, des lettres-types diffusées par
    des associations, des pétitions, et parfois le même cahier scanné deux fois.
    Comptées comme autant de contributions distinctes, elles gonflent les
    fréquences de thèmes : « 34 % des contributions parlent de fiscalité » peut
    ne mesurer que le nombre de fois qu'un tract a été recopié.

    On ne les écrase pas pour autant. « Ce texte apparaît dans 47 communes » est
    un résultat en soi — une campagne organisée, ce qui est autre chose qu'une
    écriture individuelle. `cities` porte cette information.

    Le regroupement est une couche interprétative comme les autres : il dépend
    d'un seuil de similarité, il a donc un `run`.
    """

    __tablename__ = "duplicate_group"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("run.id"))
    size = Column(Integer)  # nombre de doléances du groupe
    cities = Column(Integer)  # communes distinctes touchées
    similarity_min = Column(Float)  # plus faible similarité retenue dans le groupe


class DuplicateMember(Base):
    """L'appartenance d'une doléance à un groupe de doublons.

    Table de liaison plutôt qu'une colonne sur `doleance` : le regroupement est
    une lecture du corpus, pas une propriété de la doléance, et deux runs de
    déduplication doivent pouvoir coexister sans se marcher dessus.
    """

    __tablename__ = "duplicate_member"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("duplicate_group.id"))
    # Indexé : « à quel groupe appartient cette doléance » est la question
    # posée par toute lecture qui veut pondérer un comptage.
    doleance_id = Column(Integer, ForeignKey("doleance.id"), index=True)


class PiiSpan(Base):
    """Un passage d'une doléance susceptible d'identifier une personne.

    **Des offsets, pas une copie caviardée du texte.** Le texte d'origine reste
    intact et fait foi ; le caviardage est un rendu, produit à la lecture. C'est
    ce qui permet de corriger une détection, d'en ajouter une, ou de changer la
    politique de caviardage sans avoir abîmé la source.

    `confirmed` est la file de relecture : NULL tant qu'aucun humain n'a tranché,
    vrai pour une donnée personnelle réelle, faux pour un faux positif. Un faux
    positif ne coûte presque rien, un nom manqué est une fuite : c'est le rappel
    qu'il faut mesurer, pas la précision.
    """

    __tablename__ = "pii_span"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("run.id"))
    doleance_id = Column(Integer, ForeignKey("doleance.id"), index=True)
    start = Column(Integer)  # offset de caractère dans doleance.text
    end = Column(Integer)
    kind = Column(String)  # email, telephone, iban, url, adresse, nom, role_public
    detector = Column(String)  # règle qui l'a produit, pour auditer sa qualité
    confirmed = Column(Boolean)  # relecture humaine ; NULL = non relu


class Typologie(Base):
    """Ce qu'est une doléance — genre de document, genre d'auteur.

    C'est la couche 2 du plan : les métadonnées qui conditionnent
    l'interprétation de tout comptage. « 34 % des contributions demandent X » ne
    veut rien dire si les 34 % mêlent un mot manuscrit d'habitant, une motion de
    conseil municipal et le courrier par lequel la mairie transmet le cahier.

    **Deux axes, une ligne chacun** (`axis` = `support` ou `auteur`), plutôt
    qu'une colonne par axe : les deux questions sont indépendantes, se relisent
    séparément, et un axe de plus — type de revendication, ton — s'ajoutera sans
    migration de colonne. `uq_typologie_run_doleance_axe` interdit qu'un axe soit
    tranché deux fois dans un même run.

    Table à part et non colonnes sur `doleance`, pour la même raison que
    `pii_span` et `duplicate_member` : c'est une **lecture** du corpus, produite
    par des règles de forme faillibles, pas une propriété du texte. Elle est
    versionnée par un run et se retire sans toucher au squelette.

    `confirmed` est la file de relecture : NULL tant qu'aucun humain n'a tranché.
    Aucune de ces valeurs n'est vérifiée — les règles n'ont ni précision ni
    rappel mesurés, faute d'échantillon annoté.
    """

    __tablename__ = "typologie"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "doleance_id", "axis", name="uq_typologie_run_doleance_axe"
        ),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("run.id"))
    # Indexé : « qu'est-ce que cette doléance » est posé par toute lecture qui
    # veut pondérer ou filtrer un comptage.
    doleance_id = Column(Integer, ForeignKey("doleance.id"), index=True)
    axis = Column(String)  # "support" | "auteur" (typologie/classement.py)
    value = Column(String)  # y compris "indetermine", qui est un résultat
    detector = Column(String)  # signaux ayant tranché, joints par "+"
    confirmed = Column(Boolean)  # relecture humaine ; NULL = non relu


# Référentiel des thèmes, alimenté depuis la livraison de l'équipe analyse.
class Topic(Base):
    __tablename__ = "topic"
    # Deux grilles concurrentes peuvent réutiliser le même UUID de livraison :
    # l'unicité vaut dans un run, pas dans la table.
    __table_args__ = (UniqueConstraint("run_id", "external_id", name="uq_topic_run_external_id"),)

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("run.id"))  # grille à laquelle il appartient
    # UUID de la livraison : clé de rapprochement pour recharger sans dupliquer
    external_id = Column(String)
    name = Column(String)
    description = Column(Text)
    level = Column(Integer)  # rang d'abstraction fourni par l'équipe analyse
    validated = Column(Boolean)  # relecture humaine du thème
    parent_id = Column(Integer, ForeignKey("topic.id"))  # hiérarchie
    parent = Column(Text)  # ancien parent par nom, remplacé par parent_id


class Instance(Base):
    __tablename__ = "instance"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("run.id"))  # livraison qui l'a produite
    contribution_id = Column(Integer, ForeignKey("contribution.id"))
    # id du document dans la livraison analyse ; le rapprochement avec
    # contribution reste à faire, on conserve la clé source en attendant
    external_doc_id = Column(String)
    # Renseigné quand la livraison porte sur des doléances (ids « d<id> » de
    # export_dataset --niveau doleance) ; contribution_id reste renseigné aussi,
    # repris de la doléance, pour ne pas casser les vues qui joignent dessus.
    doleance_id = Column(Integer, ForeignKey("doleance.id"))
    topic_id = Column(Integer, ForeignKey("topic.id"))
    verbatim = Column(Text)
    summary = Column(Text)


class Feeling(Base):
    __tablename__ = "feeling"

    id = Column(Integer, primary_key=True)
    contribution_id = Column(Integer, ForeignKey("contribution.id"))
    name = Column(String)


class Annotation(Base):
    __tablename__ = "annotation"

    contribution_id = Column(Integer, ForeignKey("contribution.id"), primary_key=True)
    is_anonymized = Column(Boolean)
    is_of_interest = Column(Boolean)
