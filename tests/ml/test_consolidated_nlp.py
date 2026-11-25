"""Synthetic fixtures verify implementation, not CNC model quality."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from cnc_ml.intent_classifier import IntentClassifier
from cnc_ml.label_mapping import build_label_mappings, validate_intent_training_data
from cnc_ml.ner_metrics import evaluate_entities


QUERIES = [
    "standard thread reference alpha", "standard tolerance reference beta",
    "standard designation reference gamma", "standard pitch reference delta",
    "standard fit reference epsilon", "standard geometry reference zeta",
    "tool cutter selection eta", "tool drill selection theta",
    "tool insert selection iota", "tool mill selection kappa",
    "tool holder selection lambda", "tool reamer selection sigma",
]
INTENTS = ["standard"] * 6 + ["tool"] * 6


class ClassifierTests(unittest.TestCase):
    def test_train_save_load_preserves_labels_and_predictions(self):
        model, report = IntentClassifier.train(QUERIES, INTENTS, validation_split=1 / 3)
        with tempfile.TemporaryDirectory() as directory:
            model.save(directory)
            restored = IntentClassifier.load(directory)
            self.assertEqual(restored.id_to_label, model.id_to_label)
            self.assertEqual(restored.predict("tool cutter selection"), model.predict("tool cutter selection"))
            self.assertEqual(restored.predict("standard thread reference"), "standard")
        self.assertEqual(report["train_samples"], 8)
        self.assertEqual(report["validation_samples"], 4)
        self.assertEqual(sum(map(sum, report["confusion_matrix"])), 4)
        self.assertEqual(report["class_labels"], ["standard", "tool"])

    def test_vectorizer_does_not_fit_validation_text(self):
        from sklearn.model_selection import train_test_split
        train, validation, _, _ = train_test_split(
            QUERIES, INTENTS, test_size=1 / 3, random_state=42, stratify=INTENTS
        )
        model, _ = IntentClassifier.train(QUERIES, INTENTS, validation_split=1 / 3)
        vocabulary = model.pipeline.named_steps["tfidf"].vocabulary_
        train_words = set(" ".join(train).split())
        validation_only = set(" ".join(validation).split()) - train_words
        self.assertTrue(validation_only)
        self.assertFalse(validation_only & set(vocabulary))

    def test_duplicate_text_is_rejected_before_split(self):
        queries = QUERIES.copy()
        queries[1] = "  STANDARD   THREAD reference ALPHA "
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            IntentClassifier.train(queries, INTENTS)

    def test_seed_reproduces_split_and_metrics(self):
        _, first = IntentClassifier.train(QUERIES, INTENTS, seed=10)
        _, second = IntentClassifier.train(QUERIES, INTENTS, seed=10)
        self.assertEqual(first, second)

    def test_empty_prediction_is_rejected(self):
        model, _ = IntentClassifier.train(QUERIES, INTENTS)
        with self.assertRaises(ValueError):
            model.predict(" ")

    def test_artifact_with_mismatched_labels_is_rejected(self):
        import joblib
        model, _ = IntentClassifier.train(QUERIES, INTENTS)
        with tempfile.TemporaryDirectory() as directory:
            model.save(directory)
            path = Path(directory) / "intent.joblib"
            artifact = joblib.load(path)
            artifact["id_to_label"] = {"50": "wrong"}
            joblib.dump(artifact, path)
            with self.assertRaisesRegex(ValueError, "does not match"):
                IntentClassifier.load(directory)

    def test_cli_train_and_predict(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "dataset.json"
            output = Path(directory) / "model"
            dataset.write_text(json.dumps({"queries": QUERIES, "intents": INTENTS}), encoding="utf-8")
            trained = subprocess.run([
                sys.executable, "-m", "cnc_ml", "train", str(dataset),
                "--output", str(output),
            ], capture_output=True, text=True, check=True)
            report = json.loads(trained.stdout)
            self.assertEqual(report["train_samples"] + report["validation_samples"], len(QUERIES))
            self.assertTrue((output / "validation.json").is_file())
            prediction = subprocess.check_output([
                sys.executable, "-m", "cnc_ml", "predict", str(output), "tool cutter selection",
            ], text=True)
            self.assertEqual(prediction.strip(), "tool")


class DataContractTests(unittest.TestCase):
    def test_labels_are_stable_when_input_order_changes(self):
        self.assertEqual(build_label_mappings(["zeta", "alpha"]), build_label_mappings(["alpha", "zeta"]))

    def test_non_string_label_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_intent_training_data(["a", "b"], [None, 2], 0.5)

    def test_misaligned_data_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "same number"):
            validate_intent_training_data(QUERIES, INTENTS[:-1], 0.25)

    def test_singleton_class_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least two samples"):
            validate_intent_training_data(["first", "second", "third"], ["a", "a", "b"], 0.5)

    def test_split_must_have_space_for_each_class(self):
        with self.assertRaisesRegex(ValueError, "at least one sample"):
            validate_intent_training_data(QUERIES[:4], ["a", "a", "b", "b"], 0.1)


class EntityMetricTests(unittest.TestCase):
    def test_same_span_in_different_documents_is_not_a_match(self):
        entity = {"type": "TOOL", "start": 0, "end": 5}
        metrics = evaluate_entities([[entity], []], [[], [entity]])
        self.assertEqual(metrics["true_positives"], 0)
        self.assertEqual(metrics["false_positives"], 1)
        self.assertEqual(metrics["false_negatives"], 1)

    def test_end_boundary_must_match(self):
        metrics = evaluate_entities(
            [[{"type": "TOOL", "start": 0, "end": 4}]],
            [[{"type": "TOOL", "start": 0, "end": 5}]],
        )
        self.assertEqual(metrics["f1"], 0.0)

    def test_exact_span_and_type_matches(self):
        entity = {"type": "MATERIAL", "start": 4, "end": 9}
        self.assertEqual(evaluate_entities([[entity]], [[entity]])["f1"], 1.0)

    def test_empty_inputs_and_invalid_boundaries(self):
        self.assertEqual(evaluate_entities([], [])["f1"], 0.0)
        with self.assertRaises(ValueError):
            evaluate_entities([[]], [])
        with self.assertRaises(ValueError):
            evaluate_entities([[{"type": "TOOL", "start": 3, "end": 1}]], [[]])


if __name__ == "__main__":
    unittest.main()
