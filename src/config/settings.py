import os
import yaml
from pathlib import Path
from pydantic import Field, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base layout
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "src" / "config" / "config.yaml"
ENV_PATH = PROJECT_ROOT / ".env"

class LLMSettings(BaseModel):
    model_name: str = "llama3.2"
    base_url: str = "http://localhost:11434"
    timeout_seconds: int = 120

class ProcessingSettings(BaseModel):
    chunk_size: int = 700
    chunk_overlap: int = 100
    max_chunks: int = 8
    max_file_size_mb: int = 200

class LoggingSettings(BaseModel):
    level: str = "INFO"
    log_dir: str = "logs"

class AppSettings(BaseSettings):
    """
    Configuration Model.
    Precedence: System Environment > .env file > config.yaml > default values.
    """
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding='utf-8',
        env_nested_delimiter="__", # Allows overriding nested yaml like OLLAMA__MODEL_NAME
        extra='ignore'
    )

    llm: LLMSettings = Field(default_factory=LLMSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    @classmethod
    def load(cls) -> "AppSettings":
        """Load from YAML first, then let BaseSettings override with ENV vars."""
        yaml_config = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                try:
                    yaml_config = yaml.safe_load(f) or {}
                except Exception as e:
                    from src.utils.logger import get_logger
                    get_logger("settings").error(f"Failed to load config.yaml: {e}")
        
        # Pydantic BaseSettings automatically applies .env over kwargs
        return cls(**yaml_config)

# Global singleton
config = AppSettings.load()

# Convenience exports
OLLAMA_MODEL = config.llm.model_name
OLLAMA_BASE_URL = config.llm.base_url
CHUNK_SIZE = config.processing.chunk_size
CHUNK_OVERLAP = config.processing.chunk_overlap
MAX_CHUNKS = config.processing.max_chunks
MAX_FILE_SIZE = config.processing.max_file_size_mb * 1024 * 1024
