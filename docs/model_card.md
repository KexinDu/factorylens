# MachineGuard AI model card

## Intended use

Portfolio demonstration of risk triage for AI4I-compatible sensor snapshots. It is not appropriate for autonomous maintenance control or safety decisions.

## Data and target

UCI AI4I 2020, 10,000 rows. Target: Machine failure. Direct failure-mode flags are excluded as leakage. Product IDs and row IDs are also excluded because they do not describe operating state.

## Evaluation

Stratified 60/20/20 split, seed 42. Model selection and threshold tuning use validation data; the test split is reserved for one final report. PR-AUC and failure recall are emphasized because accuracy obscures rare failures.

## Explainability

Global impurity-based importance is shown for model orientation. Local signed TreeSHAP values are returned by the API. Explanations describe the model, not physical causality.

## Risks

The source data is synthetic, rare modes may be underrepresented, one-row inference ignores time dependence, and deployment populations may drift. Site-specific thresholds, calibration, prospective testing, monitoring, and qualified engineering oversight are required.

