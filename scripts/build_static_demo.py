"""Build a self-contained HTML snapshot of the dashboard in dist/.

The snapshot embeds the API responses for the sample export so the page can be
viewed without running the service.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from ro_aging.api import STATIC_DIR, app
from ro_aging.config import settings

AS_OF = "2026-10-21"
OUTPUT = Path(__file__).resolve().parents[1] / "dist" / "ro-aging-snapshot.html"


def main() -> None:
    client = TestClient(app)
    headers = {"X-API-Key": settings.api_key}

    def get(path: str, **params: str):
        response = client.get(f"/api/v1{path}", params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    snapshot = {
        "as_of": AS_OF,
        "branches": get("/branches"),
        "summary": get("/ro-aging", as_of=AS_OF)["rows"],
        "detail": get("/ro-aging/detail", as_of=AS_OF),
        "exceptions": get("/data-exceptions"),
        "reconciliation": get("/reconciliation", as_of=AS_OF),
    }

    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    payload = json.dumps(snapshot).replace("</", "<\\/")

    def inline_font(match: re.Match[str]) -> str:
        data = (STATIC_DIR / "fonts" / match.group(1)).read_bytes()
        return f'url("data:font/woff2;base64,{base64.b64encode(data).decode()}")'

    css = re.sub(r'url\("fonts/([^"]+)"\)', inline_font, css)

    html = html.replace(
        '<link rel="stylesheet" href="/static/styles.css">', f"<style>\n{css}</style>"
    )
    html = html.replace(
        '<script id="snapshot" type="application/json"></script>',
        f'<script id="snapshot" type="application/json">{payload}</script>',
    )
    html = html.replace('<script src="/static/app.js"></script>', f"<script>\n{js}</script>")

    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(OUTPUT.parents[1])}")


if __name__ == "__main__":
    main()
