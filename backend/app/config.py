"""Settings read from environment variables (see .env.example).

Nothing secret is hard-coded here. Every value has a safe local default.
"""

import os
from dataclasses import dataclass, field


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv("REPLAYLAB_DATABASE_URL", "sqlite:///./replaylab.db")
    )
    cors_origins: list[str] = field(
        default_factory=lambda: _split(os.getenv("REPLAYLAB_CORS_ORIGINS", "http://localhost:5173"))
    )
    # Reject request bodies larger than this before parsing them.
    max_request_bytes: int = field(
        default_factory=lambda: int(os.getenv("REPLAYLAB_MAX_REQUEST_BYTES", str(5 * 1024 * 1024)))
    )
    # The "Run scenario" button can be turned off in a public deployment.
    enable_scenario_runner: bool = field(
        default_factory=lambda: os.getenv("REPLAYLAB_ENABLE_SCENARIO_RUNNER", "true").lower() == "true"
    )


def get_settings() -> Settings:
    return Settings()
