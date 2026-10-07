"""User-selected editing profiles for deterministic, explainable scoring."""
from dataclasses import replace
from detection.highlight_scorer import HighlightScoringConfig, ScoreWeights

def config_for_style(style, base=None):
    base = base or HighlightScoringConfig()
    key = str(style or "").strip().lower()
    profiles = {
        "fast montage": (ScoreWeights(.20,.30,.30,.10,.05,.05), 8.0, 18.0, 1.5),
        "cinematic": (ScoreWeights(.20,.15,.25,.15,.10,.15), 10.0, 24.0, 18.0),
        "funny": (ScoreWeights(.35,.20,.15,.10,.05,.15), 8.0, 24.0, 14.0),
        "clutch": (ScoreWeights(.25,.25,.25,.10,.05,.10), 10.0, 26.0, 18.0),
        "kill montage": (ScoreWeights(.15,.30,.35,.10,.05,.05), 6.0, 18.0, 10.0),
    }
    weights, minimum, maximum, ideal = profiles.get(key, (base.weights, base.min_highlight_duration, base.max_highlight_duration, base.ideal_duration))
    return replace(base, weights=weights, min_highlight_duration=minimum, max_highlight_duration=maximum, ideal_duration=ideal)
