from backend.app.services.evaluation import dataset, score


def test_pm_mini_is_sixty_reproducible_scenarios():
    rows = dataset()
    assert len(rows) == 60
    assert len({row["id"] for row in rows}) == 60
    assert {row["kind"] for row in rows} == {
        "exact_cue", "entity_lure", "stale", "inhibitor", "absence", "cancelled"
    }


def test_mementovm_meets_release_targets():
    metrics = score("mementovm")
    assert metrics["prospective_memory_f1"] >= 0.80
    assert metrics["false_alarm_rate"] <= 0.08
    assert metrics["missed_cue_rate"] <= 0.15
    assert metrics["duplicate_actions"] == 0


def test_baselines_are_measured_not_constant():
    scores = {name: score(name) for name in ["no-memory", "vector-memory", "todo-ledger", "mementovm"]}
    assert scores["no-memory"]["prospective_memory_f1"] < scores["mementovm"]["prospective_memory_f1"]
    assert scores["vector-memory"]["false_positives"] > scores["mementovm"]["false_positives"]

