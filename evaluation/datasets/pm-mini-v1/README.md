# PM-Mini v1

PM-Mini v1 is a deterministic 60-scenario synthetic benchmark for the
prospective-memory mechanics in the hackathon release. The generator is
`backend/app/services/evaluation.py::dataset`; every row receives a stable ID.

| Family | Count | What it tests |
|---|---:|---|
| Exact cues | 20 | Correct future event and hard entity constraints |
| Entity lures | 15 | Similar language with a mismatched deal or contract |
| Stale cues | 10 | Superseded or invalid document state |
| Inhibitors | 5 | A true trigger blocked by current state |
| Absence cues | 5 | Expected events missing after a deadline |
| Cancellations | 5 | A later event against retired memory |

The benchmark is intentionally small and domain-focused. It supports release
regression checks; it is not evidence of general-world or causal learning.

