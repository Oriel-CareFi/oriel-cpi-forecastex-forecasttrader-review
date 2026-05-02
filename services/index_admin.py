from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

from index_admin.models import (
    BlendedBucketOutput,
    BucketQuality,
    IndexDefinition,
    InputObservation,
    PublicationRecord,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / 'data'


def _bounded_score(value: float | None, low: float, high: float) -> float:
    if value is None:
        return 0.0
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return float((value - low) / (high - low))


def _inverse_score(value: float | None, low: float, high: float) -> float:
    if value is None:
        return 0.0
    if value <= low:
        return 1.0
    if value >= high:
        return 0.0
    return float(1.0 - ((value - low) / (high - low)))


def _freshness_score(age_seconds: int, max_staleness_seconds: int = 180) -> float:
    return max(0.0, 1.0 - (age_seconds / max_staleness_seconds))


def _publication_decision(score: float) -> str:
    if score >= 0.80:
        return 'publish'
    if score >= 0.65:
        return 'restricted'
    return 'hold'


def _load_index_admin_bundle_impl() -> dict:
    definition = IndexDefinition(
        index_id='oriel.cpi.blended.1m6m',
        index_name='Oriel CPI Blended Reference Curve',
        methodology_version='1.0.0',
        description='Governed blended reference built from eligible CPI market observations and Oriel reference logic.',
        domain='macro_inflation',
        currency='USD',
        timezone='America/New_York',
        publication_cadence='intraday',
        refresh_cadence_seconds=60,
        effective_date='2026-04-13',
        status='active',
    )

    oriel_curve = pd.read_csv(DATA_DIR / 'oriel_curve_current.csv', parse_dates=['target_month'])
    kalshi = pd.read_csv(DATA_DIR / 'kalshi_constituents_current.csv', parse_dates=['target_month'])
    forecastex = pd.read_csv(DATA_DIR / 'forecastex_constituents_current.csv', parse_dates=['target_month'])

    as_of = datetime(2026, 4, 13, 10, 31, tzinfo=timezone.utc)
    observations: list[InputObservation] = []
    outputs: list[BlendedBucketOutput] = []
    qualities: list[BucketQuality] = []
    fallback_rows: list[dict] = []

    # Aggregate to one blended value per month using the constituent weights
    def _weighted_avg(df: pd.DataFrame) -> pd.Series:
        w = df['weight'].values
        v = df['expected_yoy_pct'].values
        total = w.sum() or 1.0
        return pd.Series({'expected_yoy_pct': float((w * v).sum() / total)})

    kalshi_agg = kalshi.groupby('target_month', sort=True).apply(_weighted_avg).reset_index()
    forecastex_agg = forecastex.groupby('target_month', sort=True).apply(_weighted_avg).reset_index()
    kalshi_slim = kalshi_agg.rename(columns={'expected_yoy_pct': 'expected_yoy_pct_kalshi'})
    forecastex_slim = forecastex_agg.rename(columns={'expected_yoy_pct': 'expected_yoy_pct_fx'})
    merged = (
        oriel_curve[['target_month', 'expected_yoy_pct']]
        .merge(kalshi_slim, on='target_month')
        .merge(forecastex_slim, on='target_month')
        .sort_values('target_month')
        .reset_index(drop=True)
    )

    prev_blended = None
    for idx, row in merged.iterrows():
        month = row['target_month']
        month_label = month.strftime('%Y-%m')
        base_age = 36 + idx * 22
        # force final bucket into restricted/hold territory for realism
        ages = {'kalshi': base_age, 'forecastex': base_age + (20 if idx >= 4 else 8)}
        depths = {'kalshi': 26000 - idx * 2200, 'forecastex': 22000 - idx * 2600}
        oi = {'kalshi': 90000 - idx * 6000, 'forecastex': 72000 - idx * 5200}
        mids = {'kalshi': float(row['expected_yoy_pct_kalshi']), 'forecastex': float(row['expected_yoy_pct_fx'])}
        spreads = {'kalshi': 46 + idx * 9, 'forecastex': 58 + idx * 11}
        venue_quality = {}

        venue_obs: list[InputObservation] = []
        for venue in ['kalshi', 'forecastex']:
            freshness = _freshness_score(ages[venue])
            spread_score = _inverse_score(spreads[venue], 25, 150)
            depth_score = _bounded_score(depths[venue], 1000, 25000)
            oi_score = _bounded_score(oi[venue], 1000, 90000)
            raw_weight = (freshness ** 1.0) * (spread_score ** 1.2) * (depth_score ** 0.8) * (oi_score ** 0.6)
            venue_quality[venue] = raw_weight
            is_eligible = ages[venue] <= 180 and spreads[venue] <= 150 and depths[venue] >= 1000 and oi[venue] >= 1000
            exclusion_reason = None if is_eligible else 'STALE_QUOTE'
            source_timestamp = (as_of - timedelta(seconds=ages[venue])).isoformat()
            bid = mids[venue] - (spreads[venue] / 20000.0)
            ask = mids[venue] + (spreads[venue] / 20000.0)
            venue_obs.append(InputObservation(
                as_of=as_of.isoformat(),
                venue=venue,
                instrument_id=f"{venue.upper()}_{month.strftime('%Y%m')}",
                target_month=month_label,
                bid=round(bid, 4),
                ask=round(ask, 4),
                mid=round(mids[venue], 4),
                last=round(mids[venue], 4),
                depth=float(depths[venue]),
                open_interest=float(oi[venue]),
                spread_bps=float(spreads[venue]),
                age_seconds=int(ages[venue]),
                source_timestamp=source_timestamp,
                is_eligible=is_eligible,
                exclusion_reason=exclusion_reason,
                implied_value=round(mids[venue], 4),
            ))

        total_weight = sum(venue_quality.values()) or 1.0
        normalized_weights = {k: min(v / total_weight, 0.70) for k, v in venue_quality.items()}
        weight_total = sum(normalized_weights.values()) or 1.0
        normalized_weights = {k: v / weight_total for k, v in normalized_weights.items()}

        weighted_obs = []
        for obs in venue_obs:
            weight = normalized_weights[obs.venue] if obs.is_eligible else 0.0
            weighted_obs.append(obs)
            observations.append(InputObservation(**{**asdict(obs), 'weight': round(weight, 4)}))

        observed_market_implied = sum(o.mid * normalized_weights[o.venue] for o in venue_obs if o.is_eligible)
        fair_value = float(row['expected_yoy_pct'])
        fallback_used = idx >= 4
        fallback_level = 'single-source fallback' if idx == 4 else ('fair-value-assisted holdover' if idx == 5 else None)
        fallback_penalty = 0.70 if fallback_used else 1.0
        blended_reference = observed_market_implied * (0.85 if idx == 5 else 0.97) + fair_value * (0.15 if idx == 5 else 0.03)

        coverage_score = 1.0
        freshness_score = sum(_freshness_score(o.age_seconds) for o in venue_obs) / len(venue_obs)
        depth_score = sum(_bounded_score(o.depth, 1000, 25000) for o in venue_obs) / len(venue_obs)
        spread_score = sum(_inverse_score(o.spread_bps, 25, 150) for o in venue_obs) / len(venue_obs)
        oi_score = sum(_bounded_score(o.open_interest, 1000, 90000) for o in venue_obs) / len(venue_obs)
        balance_score = 1.0 - abs(normalized_weights['kalshi'] - normalized_weights['forecastex'])
        quality_score = (
            0.20 * coverage_score + 0.20 * freshness_score + 0.15 * spread_score +
            0.15 * depth_score + 0.10 * oi_score + 0.20 * balance_score
        )
        timestamp_integrity_score = freshness_score * (0.9 if idx < 5 else 0.72)
        source_diversity_score = 1.0 - max(normalized_weights.values()) * 0.35
        continuity_score = 1.0
        if prev_blended is not None:
            continuity_score = max(0.0, 1.0 - min(abs(blended_reference - prev_blended) / 0.35, 1.0))
        publishability_score = (
            0.30 * quality_score +
            0.20 * timestamp_integrity_score +
            0.20 * source_diversity_score +
            0.15 * fallback_penalty +
            0.15 * continuity_score
        )
        decision = _publication_decision(publishability_score)
        reason_codes = []
        if fallback_used:
            reason_codes.append('SINGLE_SOURCE_FALLBACK' if idx == 4 else 'FAIR_VALUE_ASSISTED')
        if decision != 'publish':
            reason_codes.append('TIMESTAMP_MISMATCH' if idx == 5 else 'LOW_SOURCE_DIVERSITY')

        outputs.append(BlendedBucketOutput(
            target_month=month_label,
            observed_market_implied=round(observed_market_implied, 4),
            blended_reference=round(blended_reference, 4),
            fair_value=round(fair_value, 4),
            fallback_used=fallback_used,
            fallback_level=fallback_level,
            confidence_score=round((quality_score + publishability_score) / 2.0, 4),
            publishability_score=round(publishability_score, 4),
            reason_codes=reason_codes,
            top_weighted_source=max(normalized_weights, key=normalized_weights.get),
        ))
        qualities.append(BucketQuality(
            target_month=month_label,
            coverage_score=round(coverage_score, 4),
            freshness_score=round(freshness_score, 4),
            depth_score=round(depth_score, 4),
            spread_score=round(spread_score, 4),
            oi_score=round(oi_score, 4),
            balance_score=round(balance_score, 4),
            quality_score=round(quality_score, 4),
            timestamp_integrity_score=round(timestamp_integrity_score, 4),
            source_diversity_score=round(source_diversity_score, 4),
            fallback_penalty_adjusted_score=round(fallback_penalty, 4),
            continuity_score=round(continuity_score, 4),
            publishability_score=round(publishability_score, 4),
            publication_decision=decision,
        ))
        fallback_rows.append({
            'target_month': month_label,
            'fallback_used': fallback_used,
            'fallback_level': fallback_level or 'multi-source eligible market blend',
            'fallback_reason': ', '.join(reason_codes) if reason_codes else 'none',
        })
        prev_blended = blended_reference

    published = [q.target_month for q in qualities if q.publication_decision == 'publish']
    held = [q.target_month for q in qualities if q.publication_decision == 'hold']
    restricted = [q.target_month for q in qualities if q.publication_decision == 'restricted']
    record = PublicationRecord(
        run_id='run_20260413_103100_v1',
        index_id=definition.index_id,
        methodology_version=definition.methodology_version,
        as_of=as_of.isoformat(),
        publication_status='published with controls' if held or restricted else 'published',
        published_buckets=published,
        held_buckets=held,
        override_applied=False,
        override_note=None,
        created_at=(as_of + timedelta(seconds=4)).isoformat(),
    )

    runs = pd.DataFrame([
        {
            'run_id': 'run_20260413_103100_v1',
            'as_of': as_of.isoformat(),
            'methodology_version': '1.0.0',
            'published_buckets': len(published),
            'held_buckets': len(held),
            'restricted_buckets': len(restricted),
            'overrides': 'No',
            'fallback_count': sum(1 for o in outputs if o.fallback_used),
        },
        {
            'run_id': 'run_20260413_093100_v1',
            'as_of': (as_of - timedelta(hours=1)).isoformat(),
            'methodology_version': '1.0.0',
            'published_buckets': max(len(published)-1, 0),
            'held_buckets': len(held) + 1,
            'restricted_buckets': len(restricted),
            'overrides': 'No',
            'fallback_count': max(sum(1 for o in outputs if o.fallback_used)-1, 0),
        },
    ])

    return {
        'definition': definition,
        'observations_df': pd.DataFrame([asdict(o) for o in observations]),
        'quality_df': pd.DataFrame([asdict(q) for q in qualities]),
        'outputs_df': pd.DataFrame([asdict(o) for o in outputs]),
        'publication_record': record,
        'runs_df': runs,
        'fallback_df': pd.DataFrame(fallback_rows),
    }


if st is not None:
    load_index_admin_bundle = st.cache_data(show_spinner=False)(_load_index_admin_bundle_impl)
else:  # pragma: no cover
    load_index_admin_bundle = _load_index_admin_bundle_impl
