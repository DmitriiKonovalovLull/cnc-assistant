def experience_score(profile: dict) -> float:
    if not profile or profile["samples"] < 5:
        return 0.1

    stability = 1 - abs(profile["avg_delta"])
    physics = profile["physics_valid_ratio"]

    score = stability * physics
    return round(max(0.0, min(score, 1.0)), 3)
