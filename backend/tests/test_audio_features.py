import numpy as np
import soundfile as sf

from sentinel.audio_features import (
    extract_features,
    zscore_drift,
    rules_only_score,
)
from sentinel.models import AudioFeatures, RecommendedAction


def _write_wav(path, duration_s=10, sr=16000):
    t = np.linspace(0, duration_s, duration_s * sr, endpoint=False)
    y = 0.2 * np.sin(2 * np.pi * 200 * t)
    sf.write(path, y, sr, subtype="PCM_16")


def test_extract_features_returns_populated(tmp_path):
    p = tmp_path / "tone.wav"
    _write_wav(p)
    feats = extract_features(str(p))
    assert isinstance(feats, AudioFeatures)
    assert feats.f0_mean > 0


def test_zscore_drift_zero_on_baseline():
    f = AudioFeatures(f0_mean=100, jitter=0.02, shimmer=0.1, speech_rate=4.0,
                      pause_ratio=0.2, breaths_per_min=14, hnr=12)
    drift = zscore_drift(current=f, baseline=f, stdev=None)
    assert all(abs(v) < 1e-6 for v in drift.values())


def test_rules_only_red_when_tachypnea_and_pauses():
    f = AudioFeatures(breaths_per_min=26, pause_ratio=0.55, speech_rate=2.0,
                      f0_mean=180, jitter=0.08, shimmer=0.25, hnr=6)
    score = rules_only_score(features=f, drift={"speech_rate": -3.0})
    assert score.recommended_action in (
        RecommendedAction.NURSE_ALERT, RecommendedAction.SUGGEST_911
    )
    assert "tachypnea" in score.red_flags
