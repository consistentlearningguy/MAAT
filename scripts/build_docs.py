"""Build the docs data bundle for static hosting."""

from __future__ import annotations

import json

from backend.core.config import settings
from backend.core.database import SessionLocal, init_db
from backend.services.export_service import ExportService


def main() -> None:
    init_db()
    with SessionLocal() as session:
        payload = ExportService(session).write_public_export(settings.public_export_path)
    reference_layers = {
        "airports": json.loads((settings.reference_dir / "airports.json").read_text(encoding="utf-8-sig")),
        "borderCrossings": json.loads((settings.reference_dir / "border_crossings.json").read_text(encoding="utf-8-sig")),
        "highways": json.loads((settings.reference_dir / "highways.json").read_text(encoding="utf-8-sig")),
        "youthServices": json.loads((settings.reference_dir / "youth_services.json").read_text(encoding="utf-8-sig")),
    }
    (settings.docs_data_dir / "reference-layers.json").write_text(json.dumps(reference_layers, indent=2), encoding="utf-8-sig")
    print({"docs_json": str(settings.public_export_path), "docs_reference": str(settings.docs_data_dir / 'reference-layers.json'), "cases": len(payload['cases'])})


if __name__ == "__main__":
    main()

