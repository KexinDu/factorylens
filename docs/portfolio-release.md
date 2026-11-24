# FactoryLens portfolio release draft

## Repository metadata

**Suggested repository:** `factorylens`

**Description:** Educational industrial AI prototype that connects hydraulic
sensor scores, evidence-backed diagnosis, human-reviewed work orders, and
auditable Markdown reports.

**Topics:** `predictive-maintenance`, `industrial-ai`, `rag`,
`tool-calling`, `fastapi`, `react`, `sqlite`, `scikit-learn`,
`anomaly-detection`, `portfolio-project`.

## Draft release notes · v0.1.0

FactoryLens adds a maintenance workflow to MachineGuard AI's hydraulic
test-rig dashboard and predictive models.

- Search educational maintenance documents and upload local TXT or Markdown references.
- Inspect the recorded sensor readings, upstream model findings and citations
  in the Diagnostic Copilot. Use optional OpenAI-compatible tool calling
  or retrieval-only mode.
- Confirm a work order, record maintenance notes and export Markdown reports.
- Reproduce the offline retrieval and saved-record evaluation.

Local acceptance passed 54 pytest and 16 Vitest tests, along with Ruff,
ESLint and the production build. One saved OpenLux run completed two
Responses calls and verified structured output, tool calls and references.
The retrieval development set passed seven of eight cases. The manufacturer
torque query retrieved generic evidence despite the missing specification.
The project owner completed a ChatGPT-assisted review of the saved cloud
diagnosis on 2026-11-24. Two of four findings were supported and two were
partially supported, with zero rated unsupported. Both hypotheses need
clearer operating-condition prerequisites. This version is an educational
prototype using recorded UCI test-rig cycles. Industrial validity remains
unverified.

## Résumé facts

- Extended an attributed open-source FastAPI/React application with a
  maintenance workflow spanning TF-IDF retrieval, strict LLM outputs,
  SQLite history, work orders and Markdown export.
- Added **55 net automated tests** over the verified upstream baseline,
  reaching **54 backend/ML tests and 16 frontend tests**.
- Verified one real Responses API tool-calling workflow from a public
  UCI cycle through a persisted, cited diagnosis. Two completed requests
  took **25.863 s** and used **5,619 tokens**. This is a single observed run.
- Built an eight-case retrieval development evaluation. It passed **7/8**,
  with **6/6** positive Hit@3 and **1/2** correct rejections.

## One-minute demo outline

1. Start with the problem. Maintenance review needs a traceable connection
   between sensor readings, model risk, evidence and a human decision.
2. Open HYD-0001 and explain that it is a UCI rig cycle. The original
   classifier and Isolation Forest come from MachineGuard AI.
3. Open the saved OpenLux diagnosis. Show what came from the measured
   record, which tools the model requested and which excerpts it cited.
4. Show the human review and status flow, then open the Markdown report.
5. Close with the validation numbers, the torque-query miss and the
   single-case semantic review, including the two partially supported hypotheses.

## Release sequence after approval

1. Use the completed [groundedness record](groundedness-review.md) and the
   [commit plan](commit-plan.md) to review the local release history,
   attribution and safety scan before authorizing publication.
2. Choose a GitHub account or organization and create an empty `factorylens`
   repository there. The existing `origin` targets the upstream MachineGuard
   repository. To preserve it, use a separate, explicitly verified
   `portfolio` remote for any approved push. Start privately if review is
   still in progress. [GitHub repository setup](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)
3. Confirm the remote owner and repository, push the approved branch to
   `portfolio` without force, and inspect the first Actions run. Confirm
   the tracked README screenshots render and repeat the staged secret and
   size checks.
4. With public release approval, set visibility and add description/topics.
   Tag the reviewed commit as `v0.1.0` and publish the approved release
   notes. Keep API credentials, DBs, logs and downloadable QA reports local.

Repository creation, remote changes, push, tag and release await separate approval.
