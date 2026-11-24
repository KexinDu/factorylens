# Proposed Git commits

Phase 8.1 approves these three local commits only. The groups include the completed project-owner groundedness review and its summary across the release documentation. The four upstream commits remain intact. Use actual commit times and review each staged diff before committing.

## 1. Implement FactoryLens industrial AI MVP

- `.dockerignore`
- `.env.example`
- `.gitignore`
- `backend/app/config.py`
- `backend/app/diagnostic_agent.py`
- `backend/app/diagnostic_api.py`
- `backend/app/diagnostic_history.py`
- `backend/app/diagnostic_schemas.py`
- `backend/app/knowledge.py`
- `backend/app/knowledge_api.py`
- `backend/app/knowledge_examples/hydraulic-overview.md`
- `backend/app/knowledge_examples/pressure-and-flow.md`
- `backend/app/knowledge_examples/temperature-power-vibration.md`
- `backend/app/main.py`
- `backend/app/maintenance_reports.py`
- `backend/app/service.py`
- `backend/app/work_orders.py`
- `backend/app/work_orders_api.py`
- `backend/tests/test_diagnostics.py`
- `backend/tests/test_knowledge.py`
- `backend/tests/test_maintenance_reports.py`
- `backend/tests/test_work_orders.py`
- `frontend/src/App.tsx`
- `frontend/src/DiagnosticCopilot.tsx`
- `frontend/src/KnowledgeBase.tsx`
- `frontend/src/ReportDownload.tsx`
- `frontend/src/WorkOrderForm.tsx`
- `frontend/src/WorkOrders.tsx`
- `frontend/src/diagnostic.css`
- `frontend/src/knowledge.css`
- `frontend/src/services/api.ts`
- `frontend/src/test/DiagnosticCopilot.test.tsx`
- `frontend/src/test/KnowledgeBase.test.tsx`
- `frontend/src/test/ReportDownload.test.tsx`
- `frontend/src/types.ts`
- `frontend/src/work-orders.css`
- `pyproject.toml`
- `requirements-deploy.txt`

## 2. Add evaluation and final acceptance documentation

- `docs/diagnostic-copilot.md`
- `docs/final-acceptance.md`
- `docs/groundedness-review.md`
- `docs/knowledge-base.md`
- `docs/maintenance-evaluation.md`
- `docs/maintenance-work-orders.md`
- `scripts/evaluate_maintenance.py`
- `scripts/maintenance_eval_cases.json`

## 3. Prepare portfolio documentation and CI workflow

- `.github/workflows/ci.yml`
- `README.md`
- `docs/architecture.md`
- `docs/commit-plan.md`
- `docs/images/README.md`
- `docs/images/dashboard.jpg`
- `docs/images/diagnostic-copilot.jpg`
- `docs/images/knowledge-base.jpg`
- `docs/images/openlux-diagnosis.jpg`
- `docs/images/resolved-work-order.jpg`
- `docs/images/tools-and-evidence.jpg`
- `docs/images/work-orders.jpg`
- `docs/portfolio-release.md`

Review the [release draft](portfolio-release.md) separately before changing remotes, pushing, tagging or publishing.
