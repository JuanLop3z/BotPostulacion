"""Opt-in live read-only smoke test. Never submits applications or prints job contents.

Run after installing the backend: python scripts/smoke_greenhouse.py --board stripe
The default automated pytest suite uses MockTransport and does not call providers.
"""

import argparse
import json
from datetime import UTC, datetime

from app.integrations import SourceError
from app.integrations.greenhouse import GreenhouseAdapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Comprobar lectura real de un portal público Greenhouse.")
    parser.add_argument("--board", default="stripe", help="Token público del portal de la empresa")
    args = parser.parse_args()
    adapter = GreenhouseAdapter()
    report = {
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "source": adapter.name,
        "board": args.board,
        "method": "GET",
        "submit_capability": adapter.capabilities.submit,
        "real_applications_sent": 0,
    }
    try:
        jobs = adapter.search(board=args.board)
    except SourceError as exc:
        report.update(status="unavailable", error=str(exc))
        print(json.dumps(report, ensure_ascii=False))
        return 2
    report.update(status="ok", jobs=len(jobs), sample_id=jobs[0].external_id if jobs else None)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
