"""Write the agents-api OpenAPI spec to packages/contracts/openapi/agents.json."""

import json
import sys
from pathlib import Path

from joby_agents.agents_api.app import app

DEFAULT_OUT = Path(__file__).resolve().parents[4] / "packages/contracts/openapi/agents.json"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
