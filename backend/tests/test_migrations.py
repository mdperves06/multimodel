import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def _alembic(db_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_migrations_apply_and_match_models(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'm.db'}"
    up = _alembic(url, "upgrade", "head")
    assert up.returncode == 0, up.stderr
    check = _alembic(url, "check")  # fails if models drifted from migrations
    assert check.returncode == 0, check.stdout + check.stderr
    down = _alembic(url, "downgrade", "base")
    assert down.returncode == 0, down.stderr
