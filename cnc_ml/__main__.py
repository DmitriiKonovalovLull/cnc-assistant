"""Run local baseline training or inference without starting application services."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="CNC intent classifier baseline")
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train")
    train.add_argument("dataset", type=Path, help="JSON with queries and intents lists")
    train.add_argument("--output", type=Path, default=Path("artifacts/intent-model"))
    train.add_argument("--validation-split", type=float, default=0.25)
    train.add_argument("--seed", type=int, default=42)
    predict = commands.add_parser("predict")
    predict.add_argument("model", type=Path, help="Directory of a trusted local artifact")
    predict.add_argument("text")
    args = parser.parse_args()
    from .intent_classifier import IntentClassifier

    if args.command == "train":
        payload = json.loads(args.dataset.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("Dataset must be a JSON object")
        model, report = IntentClassifier.train(
            payload.get("queries", []), payload.get("intents", []),
            validation_split=args.validation_split, seed=args.seed,
        )
        model.save(args.output)
        (args.output / "validation.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(IntentClassifier.load(args.model).predict(args.text))


if __name__ == "__main__":
    main()
