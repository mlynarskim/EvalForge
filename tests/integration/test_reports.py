from pathlib import Path

from sqlalchemy import func, select

from app.config import settings
from app.models import Experiment, Report, User
from app.services.demo_service import seed_demo
from app.services.report_service import report_service


def test_reports_are_generated_with_checksums(db, tmp_path: Path) -> None:
    seed_demo(db)
    experiment = db.scalar(select(Experiment))
    user = db.scalar(select(User))
    assert experiment and user
    original_directory = settings.report_directory
    settings.report_directory = tmp_path
    try:
        for format in ("json", "csv", "html", "pdf"):
            report = report_service.generate(db, experiment.id, user.id, format, "PLN")
            assert Path(report.file_path).is_file()
            assert len(report.checksum) == 64
        assert db.scalar(select(func.count()).select_from(Report)) == 4
    finally:
        settings.report_directory = original_directory
