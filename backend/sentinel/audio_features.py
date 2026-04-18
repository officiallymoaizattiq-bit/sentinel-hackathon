from __future__ import annotations

import opensmile

from sentinel.models import AudioFeatures, RecommendedAction, Score

_smile = opensmile.Smile(
    feature_set=opensmile.FeatureSet.eGeMAPSv02,
    feature_level=opensmile.FeatureLevel.Functionals,
)


def _val(row, *names: str) -> float:
    for n in names:
        if n in row.index:
            return float(row[n])
    return 0.0


def extract_features(wav_path: str) -> AudioFeatures:
    df = _smile.process_file(wav_path)
    row = df.iloc[0]
    return AudioFeatures(
        f0_mean=_val(row, "F0semitoneFrom27.5Hz_sma3nz_amean"),
        jitter=_val(row, "jitterLocal_sma3nz_amean"),
        shimmer=_val(row, "shimmerLocaldB_sma3nz_amean"),
        hnr=_val(row, "HNRdBACF_sma3nz_amean"),
        speech_rate=_val(row, "VoicedSegmentsPerSec"),
        pause_ratio=_val(row, "MeanUnvoicedSegmentLength"),
        breaths_per_min=_val(row, "loudness_sma3_amean") * 20.0,
    )


def zscore_drift(
    *,
    current: AudioFeatures,
    baseline: AudioFeatures,
    stdev: dict[str, float] | None,
) -> dict[str, float]:
    cur = current.model_dump()
    base = baseline.model_dump()
    sd = stdev or {k: 1.0 for k in cur}
    return {
        k: (cur[k] - base[k]) / (sd.get(k, 1.0) or 1.0)
        for k in cur
    }


def rules_only_score(
    *, features: AudioFeatures, drift: dict[str, float]
) -> Score:
    red: list[str] = []
    det = 0.0
    if features.breaths_per_min >= 22:
        red.append("tachypnea")
        det += 0.35
    if features.pause_ratio > 0.4 or drift.get("speech_rate", 0.0) < -2.0:
        red.append("slow_speech_or_pauses")
        det += 0.25
    if features.hnr < 8:
        red.append("low_hnr")
        det += 0.2
    if features.shimmer > 0.2 or features.jitter > 0.05:
        red.append("voice_instability")
        det += 0.1
    det = min(det, 0.99)

    qsofa = 1 if features.breaths_per_min >= 22 else 0
    news2 = 5 if det > 0.5 else (3 if det > 0.3 else 1)

    if det >= 0.8:
        action = RecommendedAction.SUGGEST_911
    elif det >= 0.55:
        action = RecommendedAction.NURSE_ALERT
    elif det >= 0.35:
        action = RecommendedAction.CAREGIVER_ALERT
    elif red:
        action = RecommendedAction.PATIENT_CHECK
    else:
        action = RecommendedAction.NONE

    return Score(
        deterioration=det,
        qsofa=qsofa,
        news2=news2,
        red_flags=red,
        summary="rules-only: " + ", ".join(red) if red else "rules-only: nominal",
        recommended_action=action,
    )
