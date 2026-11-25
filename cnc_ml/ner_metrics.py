"""Exact entity-span evaluation with document boundaries retained."""


def evaluate_entities(predictions, references):
    if len(predictions) != len(references):
        raise ValueError("Predictions and references must have the same document count")

    def spans(documents):
        result = set()
        for document_id, entities in enumerate(documents):
            for entity in entities:
                start, end, label = entity["start"], entity["end"], entity["type"]
                if (type(start) is not int or type(end) is not int
                        or start < 0 or end <= start or not isinstance(label, str) or not label.strip()):
                    raise ValueError("Each entity needs a type and valid half-open integer offsets")
                result.add((document_id, label, start, end))
        return result

    predicted, expected = spans(predictions), spans(references)
    true_positive = len(predicted & expected)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "true_positives": true_positive,
        "false_positives": len(predicted - expected),
        "false_negatives": len(expected - predicted),
        "documents": len(references),
    }
