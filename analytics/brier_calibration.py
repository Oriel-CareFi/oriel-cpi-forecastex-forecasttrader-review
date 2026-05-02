from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

CALIBRATION_DATA_PATH = Path(__file__).resolve().parents[1] / 'data' / 'calibration' / 'venue_brier_history_sample.csv'
MAX_BINARY_BRIER = 0.25
TARGET_LOG_LOSS = 0.6931  # coin-flip baseline


@dataclass
class CalibrationSummary:
    venue: str
    historical_calibration_score: float
    brier_skill_score: float
    log_loss_skill_score: float
    calibration_bias_score: float
    calibration_sample_size_score: float
    calibration_sample_size: int
    weighted_mean_brier_score: float
    weighted_mean_log_loss: float
    weighted_mean_abs_error_pct: float
    weighted_bias_pct: float
    weighted_hit_rate: float
    matched_rows: int
    contract_family_breakdown: dict
    horizon_bucket_breakdown: dict
    methodology_note: str


def load_calibration_history(path: str | Path | None = None) -> pd.DataFrame:
    target = Path(path) if path is not None else CALIBRATION_DATA_PATH
    df = pd.read_csv(target)
    required = [
        'venue', 'contract_family', 'horizon_bucket', 'horizon_min_days', 'horizon_max_days',
        'n_obs', 'mean_brier_score', 'mean_log_loss', 'mean_abs_error_pct', 'hit_rate', 'bias_pct'
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f'Missing calibration columns in {target}: {missing}')
    return df


def _brier_to_skill_score(mean_brier: float) -> float:
    scaled = 100.0 * (1.0 - (float(mean_brier) / MAX_BINARY_BRIER))
    return max(0.0, min(100.0, scaled))


def _log_loss_to_skill_score(mean_log_loss: float) -> float:
    scaled = 100.0 * (1.0 - (float(mean_log_loss) / TARGET_LOG_LOSS))
    return max(0.0, min(100.0, scaled))


def _bias_to_score(bias_pct: float) -> float:
    penalty = min(50.0, abs(float(bias_pct)) * 10.0)
    return max(0.0, 100.0 - penalty)


def _sample_size_to_score(n_obs: int) -> float:
    if n_obs <= 0:
        return 0.0
    return max(0.0, min(100.0, (np.log1p(n_obs) / np.log1p(250.0)) * 100.0))


def _bucket_label(days: float) -> str:
    days = float(days)
    if days <= 45:
        return '0-45d'
    if days <= 120:
        return '46-120d'
    return '121-220d'


def compute_calibration_summary(
    calibration_df: pd.DataFrame,
    venue: str,
    constituents: pd.DataFrame,
) -> CalibrationSummary:
    if constituents.empty:
        return CalibrationSummary(
            venue=venue,
            historical_calibration_score=50.0,
            brier_skill_score=50.0,
            log_loss_skill_score=50.0,
            calibration_bias_score=50.0,
            calibration_sample_size_score=0.0,
            calibration_sample_size=0,
            weighted_mean_brier_score=0.25,
            weighted_mean_log_loss=TARGET_LOG_LOSS,
            weighted_mean_abs_error_pct=0.0,
            weighted_bias_pct=0.0,
            weighted_hit_rate=0.5,
            matched_rows=0,
            contract_family_breakdown={},
            horizon_bucket_breakdown={},
            methodology_note='No constituents available; calibration score set to neutral fallback.',
        )

    work = constituents.copy()
    work['contract_family'] = work['contract_family'].fillna('unknown').astype(str)
    work['horizon_bucket'] = work['days_from_valuation'].map(_bucket_label)

    venue_hist = calibration_df[calibration_df['venue'].str.lower() == venue.lower()].copy()
    merged = work.merge(
        venue_hist,
        on=['contract_family', 'horizon_bucket'],
        how='left',
        suffixes=('', '_hist'),
    )

    # fallback to venue-level averages when exact row missing
    venue_defaults = {
        'mean_brier_score': float(venue_hist['mean_brier_score'].mean()) if not venue_hist.empty else 0.18,
        'mean_log_loss': float(venue_hist['mean_log_loss'].mean()) if not venue_hist.empty else 0.60,
        'mean_abs_error_pct': float(venue_hist['mean_abs_error_pct'].mean()) if not venue_hist.empty else 0.35,
        'hit_rate': float(venue_hist['hit_rate'].mean()) if not venue_hist.empty else 0.60,
        'bias_pct': float(venue_hist['bias_pct'].mean()) if not venue_hist.empty else 0.0,
        'n_obs': int(round(venue_hist['n_obs'].mean())) if not venue_hist.empty else 0,
    }
    for col, default in venue_defaults.items():
        merged[col] = merged[col].fillna(default)

    weights = merged['weight'].astype(float).clip(lower=0.0)
    if weights.sum() <= 0:
        weights = pd.Series(np.ones(len(merged)), index=merged.index, dtype=float)
    weights = weights / weights.sum()

    weighted_brier = float(np.average(merged['mean_brier_score'].astype(float), weights=weights))
    weighted_log = float(np.average(merged['mean_log_loss'].astype(float), weights=weights))
    weighted_mae = float(np.average(merged['mean_abs_error_pct'].astype(float), weights=weights))
    weighted_hit_rate = float(np.average(merged['hit_rate'].astype(float), weights=weights))
    weighted_bias = float(np.average(merged['bias_pct'].astype(float), weights=weights))
    sample_size = int(round(float(np.average(merged['n_obs'].astype(float), weights=weights))))

    brier_skill = _brier_to_skill_score(weighted_brier)
    log_skill = _log_loss_to_skill_score(weighted_log)
    bias_score = _bias_to_score(weighted_bias)
    sample_score = _sample_size_to_score(sample_size)

    historical_score = round(
        0.45 * brier_skill +
        0.20 * log_skill +
        0.15 * bias_score +
        0.20 * sample_score,
        2,
    )

    fam_breakdown = {}
    for fam, grp in merged.groupby('contract_family'):
        w = grp['weight'].astype(float)
        w = w / w.sum() if w.sum() > 0 else pd.Series(np.ones(len(grp)) / len(grp), index=grp.index)
        fam_breakdown[str(fam)] = {
            'share': round(float(weights.loc[grp.index].sum()), 4),
            'mean_brier_score': round(float(np.average(grp['mean_brier_score'], weights=w)), 4),
            'score': round(float(np.average([_brier_to_skill_score(v) for v in grp['mean_brier_score']], weights=w)), 2),
        }

    bucket_breakdown = {}
    for bucket, grp in merged.groupby('horizon_bucket'):
        w = grp['weight'].astype(float)
        w = w / w.sum() if w.sum() > 0 else pd.Series(np.ones(len(grp)) / len(grp), index=grp.index)
        bucket_breakdown[str(bucket)] = {
            'share': round(float(weights.loc[grp.index].sum()), 4),
            'mean_brier_score': round(float(np.average(grp['mean_brier_score'], weights=w)), 4),
            'score': round(float(np.average([_brier_to_skill_score(v) for v in grp['mean_brier_score']], weights=w)), 2),
        }

    return CalibrationSummary(
        venue=venue,
        historical_calibration_score=historical_score,
        brier_skill_score=round(brier_skill, 2),
        log_loss_skill_score=round(log_skill, 2),
        calibration_bias_score=round(bias_score, 2),
        calibration_sample_size_score=round(sample_score, 2),
        calibration_sample_size=sample_size,
        weighted_mean_brier_score=round(weighted_brier, 4),
        weighted_mean_log_loss=round(weighted_log, 4),
        weighted_mean_abs_error_pct=round(weighted_mae, 4),
        weighted_bias_pct=round(weighted_bias, 4),
        weighted_hit_rate=round(weighted_hit_rate, 4),
        matched_rows=int(merged[['contract_family', 'horizon_bucket']].drop_duplicates().shape[0]),
        contract_family_breakdown=fam_breakdown,
        horizon_bucket_breakdown=bucket_breakdown,
        methodology_note='Brier/log-loss calibration is matched by venue × contract family × horizon bucket and blended using constituent weights.',
    )
