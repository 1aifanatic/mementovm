# PM-Mini v1 evaluation report

Run date: July 20, 2026  
Dataset: PM-Mini v1  
Scenarios: 60  
Execution: deterministic local runner

| System | Precision | Recall | PM F1 | False alarms | Misses | Duplicate actions |
|---|---:|---:|---:|---:|---:|---:|
| No memory | 0.000 | 0.000 | 0.000 | 0 | 25 | 0 |
| Vector memory | 0.364 | 0.800 | 0.500 | 35 | 5 | 35 |
| Todo ledger | 0.500 | 0.800 | 0.615 | 20 | 5 | 0 |
| MementoVM | 1.000 | 1.000 | 1.000 | 0 | 0 | 0 |

These values are calculated by the checked-in runner and verified by the test
suite. They describe this synthetic release dataset only. Exact event/entity
matching, explicit validity and inhibitors, cancellation-aware retrieval, and
absence rules explain MementoVM's advantage over the intentionally simpler
baselines.

Reproduce with `python -m evaluation.runner`. Failed scenarios are included in
each run's `failures` field and can be replayed through the dashboard.
