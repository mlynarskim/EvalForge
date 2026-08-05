from __future__ import annotations

import csv
import hashlib
import json
import uuid
from html import escape
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import Experiment, ExperimentModel, ExperimentRun, Report
from app.services.metrics_service import metrics_service
from app.services.recommendation_service import recommendation_service


class ReportService:
    """Generate portable experiment reports in HTML, PDF, CSV and JSON."""

    def payload(self, db: Session, experiment_id: uuid.UUID) -> dict[str, Any]:
        experiment = db.scalar(
            select(Experiment)
            .options(
                selectinload(Experiment.runs).selectinload(ExperimentRun.evaluations),
                selectinload(Experiment.models).selectinload(ExperimentModel.model),
            )
            .where(Experiment.id == experiment_id)
        )
        if not experiment:
            raise ValueError("Experiment not found")
        metrics = metrics_service.aggregate(experiment.runs)
        recommendation = recommendation_service.recommend(
            metrics, experiment.recommendation_weights or {}
        )
        names = {str(item.model_id): item.model.display_name for item in experiment.models}
        recommended_id = str(recommendation.get("recommended_model_id") or "")
        fallback_id = str(recommendation.get("fallback_model_id") or "")
        recommendation = {
            **recommendation,
            "recommended_model_name": names.get(recommended_id),
            "fallback_model_name": names.get(fallback_id),
        }
        return {
            "experiment": {
                "id": str(experiment.id),
                "name": experiment.name,
                "description": experiment.description,
                "status": experiment.status.value,
                "created_at": experiment.created_at.isoformat(),
                "completed_at": experiment.completed_at.isoformat()
                if experiment.completed_at
                else None,
                "currency": experiment.currency,
                "total_cost": experiment.total_cost,
                "parameters": experiment.parameters,
                "evaluator_config": experiment.evaluator_config,
            },
            "models": [
                {"id": model_id, "name": names.get(model_id, model_id), **values}
                for model_id, values in metrics.items()
            ],
            "recommendation": recommendation,
            "limitations": [
                "Results are limited to the selected dataset and evaluator configuration.",
                "Automated model judge results require independent human review.",
                "Pricing reflects the snapshot stored when the experiment was created.",
            ],
            "runs": [
                {
                    "id": str(run.id),
                    "model": names.get(str(run.model_id), str(run.model_id)),
                    "test_case_id": str(run.test_case_id),
                    "status": run.status,
                    "latency_ms": run.latency_ms,
                    "input_tokens": run.input_tokens,
                    "output_tokens": run.output_tokens,
                    "cost": run.total_cost,
                    "error": run.error_message,
                    "response": run.raw_response,
                    "evaluations": [
                        {
                            "evaluator": item.evaluator,
                            "score": item.score,
                            "passed": item.passed,
                            "details": item.details,
                        }
                        for item in run.evaluations
                    ],
                }
                for run in experiment.runs
            ],
        }

    def generate(
        self,
        db: Session,
        experiment_id: uuid.UUID,
        user_id: uuid.UUID,
        format: str,
        currency: str,
    ) -> Report:
        if format not in {"html", "pdf", "csv", "json"}:
            raise ValueError("Unsupported report format")
        payload = self.payload(db, experiment_id)
        settings.report_directory.mkdir(parents=True, exist_ok=True)
        path = settings.report_directory / f"{experiment_id}.{format}"
        if format == "json":
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        elif format == "csv":
            self._write_csv(path, payload)
        elif format == "html":
            path.write_text(self._html(payload), encoding="utf-8")
        else:
            self._write_pdf(path, payload)
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        report = Report(
            experiment_id=experiment_id,
            generated_by_id=user_id,
            format=format,
            currency=currency,
            file_path=str(path.resolve()),
            checksum=checksum,
        )
        db.add(report)
        db.commit()
        return report

    def _write_csv(self, path: Path, payload: dict[str, Any]) -> None:
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=[
                    "id",
                    "model",
                    "test_case_id",
                    "status",
                    "latency_ms",
                    "input_tokens",
                    "output_tokens",
                    "cost",
                    "error",
                    "response",
                ],
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(payload["runs"])

    def _html(self, payload: dict[str, Any]) -> str:
        experiment = payload["experiment"]
        model_rows = "".join(
            "<tr>"
            f"<td>{escape(model['name'])}</td>"
            f"<td>{model['quality']:.1%}</td>"
            f"<td>{model['pass_rate']:.1%}</td>"
            f"<td>{model['mean_latency_ms']:.0f} ms</td>"
            f"<td>{model['total_cost']:.4f} {escape(experiment['currency'])}</td>"
            f"<td>{model['error_rate']:.1%}</td>"
            "</tr>"
            for model in payload["models"]
        )
        recommended = payload["recommendation"].get("recommended_model_name")
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>EvalForge report</title><style>
body{{font:15px Inter,Arial,sans-serif;color:#172033;margin:40px;max-width:1100px}}
h1{{font-size:30px;margin-bottom:4px}} .muted{{color:#667085}} .cards{{display:flex;gap:16px;margin:24px 0}}
.card{{border:1px solid #e4e7ec;border-radius:12px;padding:16px;min-width:160px}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:12px;border-bottom:1px solid #e4e7ec;text-align:left}}
th{{background:#f8fafc}} .brand{{color:#635bff;font-weight:700}} footer{{margin-top:40px;color:#98a2b3}}
</style></head><body><div class="brand">EvalForge</div><h1>{escape(experiment["name"])}</h1>
<p class="muted">Experiment report generated from an immutable result snapshot.</p>
<div class="cards"><div class="card"><strong>Status</strong><br>{escape(experiment["status"])}</div>
<div class="card"><strong>Total cost</strong><br>{experiment["total_cost"]:.4f} {escape(experiment["currency"])}</div>
<div class="card"><strong>Runs</strong><br>{len(payload["runs"])}</div></div>
<h2>Model comparison</h2><table><thead><tr><th>Model</th><th>Quality</th><th>Pass rate</th>
<th>Mean latency</th><th>Total cost</th><th>Error rate</th></tr></thead><tbody>{model_rows}</tbody></table>
<h2>Recommendation</h2><p>Recommended model ID: <strong>{escape(str(recommended or "None"))}</strong></p>
<p>{escape(payload["recommendation"]["reason"])}</p><h2>Limitations</h2><ul>
{"".join(f"<li>{escape(item)}</li>" for item in payload["limitations"])}</ul>
<footer>Generated by EvalForge</footer></body></html>"""

    def _write_pdf(self, path: Path, payload: dict[str, Any]) -> None:
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="Brand",
                parent=styles["Heading2"],
                textColor=colors.HexColor("#635BFF"),
                spaceAfter=8,
            )
        )
        document = SimpleDocTemplate(
            str(path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm
        )
        experiment = payload["experiment"]
        story = [
            Paragraph("EvalForge", styles["Brand"]),
            Paragraph(escape(experiment["name"]), styles["Title"]),
            Paragraph("Experiment evaluation report", styles["Normal"]),
            Spacer(1, 8 * mm),
        ]
        summary = Table(
            [
                ["Status", "Total cost", "Runs"],
                [
                    experiment["status"],
                    f"{experiment['total_cost']:.4f} {experiment['currency']}",
                    str(len(payload["runs"])),
                ],
            ],
            colWidths=[55 * mm] * 3,
        )
        summary.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F4F7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#475467")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
                    ("PADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.extend(
            [summary, Spacer(1, 8 * mm), Paragraph("Model comparison", styles["Heading2"])]
        )
        rows = [["Model", "Quality", "Pass", "P95", "Cost", "Errors"]]
        rows.extend(
            [
                model["name"],
                f"{model['quality']:.1%}",
                f"{model['pass_rate']:.1%}",
                f"{model['p95_latency_ms']:.0f} ms",
                f"{model['total_cost']:.4f}",
                f"{model['error_rate']:.1%}",
            ]
            for model in payload["models"]
        )
        table = Table(
            rows, repeatRows=1, colWidths=[42 * mm, 22 * mm, 20 * mm, 24 * mm, 24 * mm, 22 * mm]
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172033")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D0D5DD")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.extend([table, Spacer(1, 8 * mm), Paragraph("Recommendation", styles["Heading2"])])
        story.append(Paragraph(escape(payload["recommendation"]["reason"]), styles["BodyText"]))
        story.extend([Spacer(1, 6 * mm), Paragraph("Limitations", styles["Heading2"])])
        story.extend(
            Paragraph(f"• {escape(item)}", styles["BodyText"]) for item in payload["limitations"]
        )
        document.build(story)


report_service = ReportService()
