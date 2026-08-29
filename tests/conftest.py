from pathlib import Path

from cinis.config.dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
