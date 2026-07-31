"""
Centralized config: env vars + shared clients.
Same pattern as ai-consulting-lab/config.py - one place to look, not scattered
os.environ.get() calls across the codebase.
"""
import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

# --- Env vars ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")
APP_SECRET_KEY = os.environ.get("APP_SECRET_KEY")  # checked against the X-API-Key header

# Port 5000 is taken by macOS AirPlay. Port 5001 is already used by the
# ai-consulting-lab HVAC project. Default this project to 5002 so both can
# run at the same time without a conflict.
PORT = int(os.environ.get("PORT", 5002))

# Bump this string any time the classifier prompt changes meaningfully.
# Every logged decision and every eval run records which version produced it,
# so accuracy can be tracked prompt-version over prompt-version.
PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "v1")

MODEL_NAME = "claude-sonnet-5"

# --- Shared clients ---
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None


def require_config():
    """Fail loudly and early if required env vars are missing, instead of a
    confusing error deep inside a request handler."""
    missing = [
        name
        for name, val in [
            ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
            ("DATABASE_URL", DATABASE_URL),
            ("APP_SECRET_KEY", APP_SECRET_KEY),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Check your .env file against .env.example."
        )
