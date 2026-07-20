import json

from backend.app.services.evaluation import score


BASELINES = ["no-memory", "vector-memory", "todo-ledger", "mementovm"]


def main() -> None:
    report = {name: score(name) for name in BASELINES}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

