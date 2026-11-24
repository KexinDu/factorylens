import re
from datetime import datetime, timezone
from html import escape

from fastapi import Response

from .diagnostic_schemas import Diagnosis
from .work_orders import WorkOrder

MEASUREMENTS = (
    ("System pressure", "pressure_bar", "bar"),
    ("Oil temperature", "oil_temperature_c", "°C"),
    ("Motor power", "motor_power_w", "W"),
    ("Volume flow", "volume_flow_lpm", "L/min"),
    ("Vibration", "vibration_mms", "mm/s"),
)
PROVIDERS = {"openai": "OpenAI direct", "openlux": "OpenLux"}
PUNCTUATION = re.compile(r"[\\`*_[\]~|]")


def inline(value: str | None) -> str:
    if not value:
        return "Unavailable"
    single_line = " ".join(value.splitlines())
    escaped = PUNCTUATION.sub(lambda match: "\\" + match[0], single_line)
    return escape(escaped, quote=False)


def literal_block(value: str | None) -> str:
    if not value:
        return "None recorded."
    # A delimiter longer than every backtick run keeps the original evidence literal.
    longest_run = max((len(run) for run in re.findall(r"`+", value)), default=0)
    fence = "`" * max(3, longest_run + 1)
    return f"{fence}text\n{value}\n{fence}"


def render_report(
    diagnosis: Diagnosis, *, order: WorkOrder | None = None, generated_at: datetime
) -> str:
    model = diagnosis.model_findings
    mode = (
        "Cloud diagnostic assistance" if diagnosis.mode == "openai" else "Retrieval-only fallback"
    )
    lines = [
        "# FactoryLens Maintenance Report", "",
        "FactoryLens extends MachineGuard AI for educational maintenance workflows.", "",
        f"- Generated at (UTC): {generated_at.astimezone(timezone.utc).isoformat()}",
        f"- Diagnosis ID: {inline(diagnosis.diagnosis_id)}",
        f"- Equipment ID: {inline(diagnosis.device_id)}",
        f"- Data source: {inline(diagnosis.source)}", "",
        "## Diagnostic question", "", literal_block(diagnosis.question), "",
        "## Recorded sensor measurements", "",
        "| Measurement | Value | Unit |", "| --- | ---: | --- |",
    ]
    for label, field, unit in MEASUREMENTS:
        lines.append(f"| {label} | {getattr(diagnosis.observed_signals, field)} | {unit} |")
    lines += [
        "", "## Machine learning findings", "",
        f"- Supervised risk level: {inline(model.risk_level)}",
        f"- Predicted failure probability: {model.failure_probability:.4%}",
        f"- Classifier positive prediction: {'Yes' if model.failure_prediction else 'No'}",
        f"- Isolation Forest anomaly detected: {'Yes' if model.anomaly else 'No'}",
        f"- Isolation Forest anomaly score: {model.anomaly_score}",
        "", literal_block(model.interpretation),
        "", "## Diagnostic result", "", f"- Mode: {mode}",
    ]
    provider = PROVIDERS[diagnosis.llm_provider]
    if diagnosis.mode == "openai":
        lines += [
            f"- Provider: {provider}", f"- Model: {inline(diagnosis.openai_model)}",
            "", "### Summary", "", literal_block(diagnosis.summary),
        ]
        for heading, findings in (
            ("Possible causes to verify", diagnosis.possible_causes),
            ("Recommended checks for qualified personnel", diagnosis.recommended_checks),
        ):
            lines += ["", f"### {heading}", ""]
            for finding in findings:
                citations = ", ".join(inline(ref) for ref in finding.references) or "None recorded"
                lines.append(f"- {inline(finding.text)} (References: {citations})")
            if not findings:
                lines.append("None recorded.")
    else:
        lines += [
            f"- Selected provider: {provider}",
            "- Model: No completed cloud generation",
            "", "Generative AI diagnosis did not complete. The report contains stored "
            "measurements, model findings and local retrieval evidence.",
            "", literal_block(diagnosis.summary),
        ]
    lines += ["", "### Uncertainty", "", literal_block(diagnosis.uncertainty)]

    lines += ["", "## Evidence excerpts", ""]
    if not diagnosis.evidence_references:
        lines.append("No relevant evidence was recorded.")
    for item in diagnosis.evidence_references:
        lines += [
            f"### {inline(item.filename)} · Chunk {item.position}", "",
            f"- Reference ID: {inline(item.reference_id)}",
            f"- Source: {inline(item.source)}",
            *([f"- Section: {inline(item.heading)}"] if item.heading else []),
            "", literal_block(item.text), "",
        ]

    if order is not None:
        lines += [
            "", "## Maintenance work order", "",
            f"- Work order ID: {inline(order.work_order_id)}",
            f"- Title: {inline(order.title)}",
            f"- Priority: {inline(order.priority)}",
            f"- Status: {inline(order.status.replace('_', ' ').title())}",
            "", "### Issue description", "", literal_block(order.issue_description),
            "", "### Maintenance notes", "", literal_block(order.maintenance_notes),
        ]
    lines += [
        "", "## Scope and limitations", "",
        "- Industrial education prototype. Qualified personnel must verify possible causes "
        "and decide on inspections or maintenance.",
        "- UCI Condition Monitoring of Hydraulic Systems (DOI 10.24432/C5CW21, CC BY 4.0) "
        "contains hydraulic test-rig measurements. A cycle ID represents a benchmark record.",
        "- Manual entries may contain demonstration or operator-supplied values. "
        "Use the recorded source above when interpreting measurements.",
        *[f"- {inline(limit)}" for limit in diagnosis.limitations],
    ]
    return "\n".join(lines) + "\n"


def report_download(diagnosis: Diagnosis, order: WorkOrder | None = None) -> Response:
    record_id = order.work_order_id if order else diagnosis.diagnosis_id
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "-", record_id)[:64] or "record"
    kind = "work-order" if order else "diagnosis"
    filename = f"factorylens-{kind}-{safe_id}.md"
    return Response(
        render_report(diagnosis, order=order, generated_at=datetime.now(timezone.utc)),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
