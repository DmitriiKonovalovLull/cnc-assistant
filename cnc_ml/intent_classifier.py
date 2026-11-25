"""TF-IDF/SVM baseline consolidated from cnc_ai_ecosystem."""

from pathlib import Path

from .label_mapping import build_label_mappings, validate_intent_training_data


class IntentClassifier:
    def __init__(self, pipeline, id_to_label):
        self.pipeline = pipeline
        self.id_to_label = id_to_label

    @classmethod
    def train(cls, queries, intents, *, validation_split=0.25, seed=42):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.svm import LinearSVC

        queries, intents = validate_intent_training_data(queries, intents, validation_split)
        normalized = [" ".join(text.casefold().split()) for text in queries]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate queries must be resolved before splitting the dataset")
        label_to_id, id_to_label = build_label_mappings(intents)
        labels = [label_to_id[label] for label in intents]
        train_x, valid_x, train_y, valid_y = train_test_split(
            queries, labels, test_size=validation_split, random_state=seed, stratify=labels
        )
        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(max_features=1000, ngram_range=(1, 2))),
            ("classifier", LinearSVC(C=1.0, class_weight="balanced", max_iter=1000, random_state=seed)),
        ])
        pipeline.fit(train_x, train_y)
        predicted = pipeline.predict(valid_x)
        class_ids = list(range(len(label_to_id)))
        report = {
            "seed": seed,
            "train_samples": len(train_y),
            "validation_samples": len(valid_y),
            "accuracy": float(accuracy_score(valid_y, predicted)),
            "macro_f1": float(f1_score(valid_y, predicted, average="macro", zero_division=0)),
            "class_labels": list(label_to_id),
            "confusion_matrix": confusion_matrix(valid_y, predicted, labels=class_ids).tolist(),
            "per_class": classification_report(
                valid_y, predicted, labels=class_ids, target_names=list(label_to_id),
                output_dict=True, zero_division=0,
            ),
        }
        return cls(pipeline, id_to_label), report

    def predict(self, text):
        from .label_mapping import resolve_intent_label

        if not isinstance(text, str) or not text.strip():
            raise ValueError("Query must be a non-empty string")
        class_id = self.pipeline.predict([text])[0]
        # SVM margins are not calibrated probabilities; return a label only.
        return resolve_intent_label(class_id, self.id_to_label)

    def save(self, directory):
        import joblib

        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "schema_version": 1,
            "pipeline": self.pipeline,
            "id_to_label": self.id_to_label,
        }, directory / "intent.joblib")

    @classmethod
    def load(cls, directory):
        """Load only artifacts produced by a trusted local training process."""
        import joblib

        payload = joblib.load(Path(directory) / "intent.joblib")
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Unsupported intent model artifact schema")
        mapping = payload.get("id_to_label")
        if not isinstance(mapping, dict) or not mapping:
            raise ValueError("Artifact has no label mapping")
        pipeline = payload.get("pipeline")
        try:
            classes = pipeline.named_steps["classifier"].classes_
        except (AttributeError, KeyError) as exc:
            raise ValueError("Artifact has no trained classifier") from exc
        if set(mapping) != {str(int(class_id)) for class_id in classes}:
            raise ValueError("Artifact label mapping does not match the classifier")
        if any(not isinstance(label, str) or not label.strip() for label in mapping.values()):
            raise ValueError("Artifact contains invalid labels")
        return cls(pipeline, mapping)
