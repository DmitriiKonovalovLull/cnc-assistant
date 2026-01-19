def classify_sample(delta: float, physics_valid: bool):
    if not physics_valid:
        return "trash"

    if abs(delta) < 0.25:
        return "good"

    if abs(delta) < 0.6:
        return "questionable"

    return "edge"
