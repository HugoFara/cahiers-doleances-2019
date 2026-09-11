"""Configuration technique du module OCR (lue depuis `.env`).

La connexion PostgreSQL reste construite par `database/db.py`. Les paramètres
métier de la passe (DPI, modèles par défaut, consigne, tarifs) sont dans
`config.py` : ils vont dans `run.parameters`, pas dans l'environnement.
"""

import logging
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Dossier local contenant les PDFs des cahiers.
    path_to_data: str = ""
    log_level: str = "INFO"

    # Backend mistral : clé de l'API OCR (console.mistral.ai).
    mistral_api_key: str = ""
    mistral_ocr_url: str = "https://api.mistral.ai/v1/ocr"
    # Racine de l'API, pour le mode batch (fichiers et jobs).
    mistral_api_url: str = "https://api.mistral.ai/v1"

    # Backend ollama : serveur d'inférence local.
    ollama_url: str = "http://localhost:11434"


settings = Settings()

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("extraction.with_ocr")
