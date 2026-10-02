"""Write the API's OpenAPI schema to a file, without starting a server.

The frontend's TypeScript types are generated from this, so the two sides of the API can't
drift apart: rename a field in Python and the frontend stops compiling.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def main() -> None:
    app = create_app(Settings(serve_frontend=False, scheduler_enabled=False, demo_mode=False))
    schema = app.openapi()
    OUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(OUT.parents[2])}: {len(schema['paths'])} paths, "
          f"{len(schema['components']['schemas'])} schemas")


if __name__ == "__main__":
    main()
