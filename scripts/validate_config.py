"""Offline sanity checks for the deployment files (no Docker required).

    python scripts/validate_config.py
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))


def check_compose() -> None:
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    # Compose-specific tags (!reset, !override) are unknown to plain YAML; accept them.
    Loader.add_multi_constructor("!", lambda loader, suffix, node: None)
    for name in ("docker-compose.yml", "docker/docker-compose.prod.yml"):
        doc = yaml.load((ROOT / name).read_text(encoding="utf-8"), Loader=Loader)  # noqa: S506
        services = set(doc["services"])
        print(f"{name}: services = {sorted(services)}")
        if name == "docker-compose.yml":
            assert {"postgres", "redis", "backend", "worker", "frontend"} <= services


def check_env_example() -> None:
    from app.config import Settings

    with tempfile.TemporaryDirectory() as tmp:
        env = Path(tmp) / ".env"
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        env.write_text(
            text.replace("JWT_SECRET=", "JWT_SECRET=" + "j" * 48, 1).replace(
                "ENCRYPTION_KEY=", "ENCRYPTION_KEY=Y7c1kQz4mQWJ3xv0tN9pR2s8uYdHf6bLaEoGiTjKcVw=", 1
            ),
            encoding="utf-8",
        )
        settings = Settings(_env_file=str(env))  # type: ignore[call-arg]
        assert settings.environment == "development", settings.environment
        assert settings.cors_origin_list == ["http://localhost:3000"], settings.cors_origins
        assert settings.allowed_host_list == ["*"]
        assert settings.storage_type == "local"
        print(".env.example parses cleanly with inline comments")


if __name__ == "__main__":
    check_compose()
    check_env_example()
    print("OK")
