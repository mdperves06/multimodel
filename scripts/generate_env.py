"""Create a .env from .env.example with freshly generated secrets.

    python scripts/generate_env.py            # refuses to overwrite an existing .env
    python scripts/generate_env.py --force    # overwrite

Requires the `cryptography` package (installed with the backend requirements).
"""

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    target = ROOT / ".env"
    if target.exists() and "--force" not in sys.argv:
        print(f"{target} already exists. Use --force to overwrite it.")
        return 1
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        print("Install the backend requirements first: pip install -r backend/requirements.txt")
        return 1

    values = {
        "JWT_SECRET": secrets.token_urlsafe(48),
        "ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
    }
    lines = []
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        key = line.split("=", 1)[0]
        if key in values and "=" in line:
            line = f"{key}={values[key]}"
        lines.append(line)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {target} with new secrets. Back up ENCRYPTION_KEY: losing it makes stored")
    print("provider credentials unreadable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
