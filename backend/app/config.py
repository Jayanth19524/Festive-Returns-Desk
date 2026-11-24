"""Settings come from environment variables (.env at the repo root). No secrets in code."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


class Settings:
    sarvam_api_key = os.getenv("SARVAM_API_KEY", "")
    stt_model = os.getenv("SARVAM_STT_MODEL", "saaras:v4")
    llm_model = os.getenv("SARVAM_LLM_MODEL", "sarvam-105b")
    tts_model = os.getenv("SARVAM_TTS_MODEL", "bulbul:v4-flash")


settings = Settings()
