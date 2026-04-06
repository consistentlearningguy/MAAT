"""Export public JSON and CSV for the static dashboard."""

from __future__ import annotations

from backend.core.config import settings
from backend.core.database import SessionLocal, init_db
from backend.services.export_service import ExportService


def main() -> None:
    init_db()
    with SessionLocal() as session:
        service = ExportService(session)
        payload = service.write_public_export(settings.public_export_path)
        csv_output = service.build_csv_export()
        (settings.export_dir / "public-cases.csv").write_text(csv_output, encoding="utf-8")
        print({"json_path": str(settings.public_export_path), "csv_path": str(settings.export_dir / 'public-cases.csv'), "cases": len(payload['cases'])})


if __name__ == "__main__":
    main()
