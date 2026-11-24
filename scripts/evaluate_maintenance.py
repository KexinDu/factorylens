"""Evaluate bundled retrieval cases and optionally verify one archived public UCI diagnosis."""

import argparse
import gc
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.app.config import Settings
from backend.app.diagnostic_schemas import Diagnosis, GeneratedDiagnosis
from backend.app.knowledge import KnowledgeLibrary
from backend.app.schemas import MachineLookupResult
from backend.app.service import PredictionService

CASES = Path(__file__).with_name("maintenance_eval_cases.json")
TOP_K = 3


def evaluate_retrieval(library: KnowledgeLibrary) -> dict:
    results = []
    for case in json.loads(CASES.read_text(encoding="utf-8")):
        matches = library.search(case["question"], TOP_K)
        rank = next((
            number for number, match in enumerate(matches, 1)
            if match["filename"] == case.get("expected_document")
            and match["heading"] == case.get("expected_heading")
        ), None)
        expects_empty = case["expect_empty"]
        results.append({
            "id": case["id"], "question": case["question"],
            "expected_document": case.get("expected_document"),
            "expected_heading": case.get("expected_heading"),
            "expect_empty": expects_empty, "rank": rank,
            "passed": not matches if expects_empty else rank is not None,
            "matches": [
                {key: match[key] for key in ("filename", "heading", "score")} for match in matches
            ],
        })
    positive = [item for item in results if not item["expect_empty"]]
    empty = [item for item in results if item["expect_empty"]]
    return {
        "dataset": "hand-authored development cases; no independent test split",
        "top_k": TOP_K,
        "case_count": len(results),
        "passed": sum(item["passed"] for item in results),
        "failed": [item["id"] for item in results if not item["passed"]],
        "hit_at_k": sum(item["passed"] for item in positive) / len(positive),
        "mrr_at_k": sum(1 / item["rank"] for item in positive if item["rank"]) / len(positive),
        "empty_expected_passed": sum(item["passed"] for item in empty),
        "empty_expected_count": len(empty),
        "cases": results,
    }


def verify_snapshot(
    archive: Path, diagnosis_id: str, config: Settings, library: KnowledgeLibrary
) -> dict:
    with closing(sqlite3.connect(archive.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        row = db.execute(
            "SELECT snapshot_json FROM diagnostic_history WHERE diagnosis_id = ?", (diagnosis_id,),
        ).fetchone()
    if row is None:
        raise ValueError("Diagnosis not found in the archive.")
    diagnosis = Diagnosis.model_validate_json(row[0])
    if diagnosis.source != "UCI hydraulic test rig" or diagnosis.mode != "openai":
        raise ValueError("Select one saved cloud diagnosis for a public UCI test-rig record.")

    findings = [*diagnosis.possible_causes, *diagnosis.recommended_checks]
    # Validate the archived cloud fields against the saved output schema independently.
    GeneratedDiagnosis.model_validate(
        diagnosis.model_dump(include=set(GeneratedDiagnosis.model_fields))
    )
    baseline = MachineLookupResult.model_validate(PredictionService(config).lookup(
        diagnosis.device_id
    ))
    evidence = {item.reference_id: item for item in diagnosis.evidence_references}
    examples = {row["filename"]: row["document_id"] for row in library.list_documents()}
    cited = {ref for finding in findings for ref in finding.references}
    text_matches = True
    for item in evidence.values():
        document = library.get_document(examples.get(item.filename, ""))
        chunk = next((chunk for chunk in (document or {}).get("chunks", [])
                      if chunk["position"] == item.position), None)
        text_matches &= bool(
            chunk and item.text and chunk["text"][:900] == item.text
            and chunk["heading"] == item.heading and document["source"] == item.source
        )
    scores = {
        "failure_probability", "risk_level", "failure_prediction", "anomaly", "anomaly_score",
    }
    checks = {
        "schema_valid": True,
        "device_and_readings_match": diagnosis.observed_signals == baseline.machine,
        "ml_scores_match": diagnosis.model_findings.model_dump(include=scores)
        == baseline.assessment.model_dump(include=scores),
        "citation_ids_valid": bool(cited) and cited <= evidence.keys()
        and all(bool(finding.references) for finding in findings)
        and len(evidence) == len(diagnosis.evidence_references)
        and all(ref == f"KB-{item.chunk_id}" for ref, item in evidence.items()),
        "evidence_text_matches_bundled_corpus": bool(evidence) and text_matches,
        "trace_consistent": [event.order for event in diagnosis.trace]
        == list(range(1, len(diagnosis.trace) + 1))
        and all(event.elapsed_ms >= 0 for event in diagnosis.trace)
        and {"analyze_equipment", "search_knowledge"} <= {
            event.tool for event in diagnosis.trace
            if event.origin == "model" and event.status == "ok"
        },
    }
    return {
        "diagnosis_id": diagnosis.diagnosis_id, "device_id": diagnosis.device_id,
        "provider": diagnosis.llm_provider, "model": diagnosis.openai_model,
        "evidence_count": len(evidence), "distinct_citations": len(cited),
        "checks": checks, "passed": all(checks.values()),
        "trace": [
            {"order": event.order, "tool": event.tool, "origin": event.origin,
             "status": event.status, "elapsed_ms": event.elapsed_ms}
            for event in diagnosis.trace
        ],
        "provider_usage": "Not part of the diagnosis snapshot; consult the archived run log.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-db", type=Path)
    parser.add_argument("--diagnosis-id")
    args = parser.parse_args()
    if bool(args.snapshot_db) != bool(args.diagnosis_id):
        parser.error("--snapshot-db and --diagnosis-id must be provided together")
    os.environ.setdefault("MPLCONFIGDIR", str(Path.cwd() / ".matplotlib"))
    with TemporaryDirectory() as temp:
        database = Path(temp) / "evaluation.db"
        config = Settings(_env_file=None, database_path=database)
        library = KnowledgeLibrary(database, config.knowledge_chunk_length,
                                   config.knowledge_chunk_overlap)
        library.initialize()
        results = {"retrieval": evaluate_retrieval(library)}
        if args.snapshot_db:
            try:
                results["diagnostic_snapshot"] = verify_snapshot(
                    args.snapshot_db, args.diagnosis_id, config, library,
                )
            finally:
                # The upstream service's SQLite context commits but does not close its connection.
                # Release unreachable connections before Windows deletes the temporary database.
                gc.collect()
        print(json.dumps(results, indent=2, ensure_ascii=True))
        return int(bool(args.snapshot_db and not results["diagnostic_snapshot"]["passed"]))


if __name__ == "__main__":
    raise SystemExit(main())
