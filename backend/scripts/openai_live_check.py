"""Opt-in live check against the real OpenAI API.

Nothing else in this repository calls OpenAI without a user-supplied key. Run this once to
confirm your key and network path work:

    OPENAI_API_KEY=sk-... python backend/scripts/openai_live_check.py  # free
    OPENAI_API_KEY=sk-... python backend/scripts/openai_live_check.py --generate  # billed
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("JWT_SECRET", "x" * 40)
os.environ.setdefault("ENCRYPTION_KEY", "Y7c1kQz4mQWJ3xv0tN9pR2s8uYdHf6bLaEoGiTjKcVw=")

from app.providers.base import ImageRequest, ProviderError  # noqa: E402
from app.providers.openai import OpenAIAdapter  # noqa: E402


def main() -> int:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        print("Set OPENAI_API_KEY in your environment first.")
        return 2
    adapter = OpenAIAdapter(base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    creds = {"api_key": key}

    result = adapter.validate_credentials(creds)
    print("credentials valid:", result.valid, result.error or "")
    if result.limits:
        print("rate limits reported:", result.limits)
    if not result.valid:
        return 1

    if "--generate" in sys.argv:
        try:
            out = adapter.generate_image(
                creds, ImageRequest("a small red circle on white", 1, "dall-e-2", "256x256")
            )
        except ProviderError as exc:
            print("generation failed:", exc.message)
            return 1
        path = Path("openai_live_check.png")
        path.write_bytes(out.images[0].data)
        print(f"generated {len(out.images[0].data)} bytes -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
