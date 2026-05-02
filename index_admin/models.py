from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class IndexDefinition:
    index_id: str
    index_name: str
    methodology_version: str
    description: str
    domain: str
    currency: str
    timezone: str
    publication_cadence: str
    refresh_cadence_seconds: int
    effective_date: str
    status: str


@dataclass(frozen=True)
class InputObservation:
    as_of: str
    venue: str
    instrument_id: str
    target_month: str
    bid: float
    ask: float
    mid: float
    last: float
    depth: float
    open_interest: float
    spread_bps: float
    age_seconds: int
    source_timestamp: str
    is_eligible: bool
    exclusion_reason: Optional[str] = None
    weight: float = 0.0
    implied_value: float = 0.0
    fallback_flag: bool = False


@dataclass(frozen=True)
class BucketQuality:
    target_month: str
    coverage_score: float
    freshness_score: float
    depth_score: float
    spread_score: float
    oi_score: float
    balance_score: float
    quality_score: float
    timestamp_integrity_score: float
    source_diversity_score: float
    fallback_penalty_adjusted_score: float
    continuity_score: float
    publishability_score: float
    publication_decision: str


@dataclass(frozen=True)
class BlendedBucketOutput:
    target_month: str
    observed_market_implied: float
    blended_reference: float
    fair_value: float
    fallback_used: bool
    fallback_level: Optional[str]
    confidence_score: float
    publishability_score: float
    reason_codes: list[str] = field(default_factory=list)
    top_weighted_source: Optional[str] = None


@dataclass(frozen=True)
class PublicationRecord:
    run_id: str
    index_id: str
    methodology_version: str
    as_of: str
    publication_status: str
    published_buckets: list[str]
    held_buckets: list[str]
    override_applied: bool
    override_note: Optional[str]
    created_at: str
