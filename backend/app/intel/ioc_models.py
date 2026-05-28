"""Stage 3K-Q2 local IOC registry models (deterministic, air-gappable)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IocType(StrEnum):
    IP = "ip"
    DOMAIN = "domain"
    URL = "url"
    HASH_MD5 = "hash_md5"
    HASH_SHA1 = "hash_sha1"
    HASH_SHA256 = "hash_sha256"


class StalenessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"


ConfidenceLevel = Literal["low", "medium", "high"]
SourceKind = Literal["internal_curated", "vendor_offline_feed", "analyst_added"]
UpdateMode = Literal["air_gapped_bundle", "analyst_added"]


class IocSourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_kind: SourceKind
    air_gapped: bool = True
    max_staleness_hours: int = Field(ge=1)
    update_process_notes: str = ""
    last_refreshed: datetime
    lookup_name: str
    source_owner: str
    provenance: str
    update_mode: UpdateMode = "air_gapped_bundle"
    airgap_approved: bool = True

    @field_validator("last_refreshed", mode="before")
    @classmethod
    def _parse_last_refreshed(cls, value: object) -> object:
        if isinstance(value, str):
            return value.replace("Z", "+00:00")
        return value


class IocRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    ioc_type: IocType
    source_id: str
    confidence: ConfidenceLevel
    tlp: str
    first_seen: datetime
    last_seen: datetime
    expiry: datetime | None = None
    lookup_name: str | None = None
    provenance: str | None = None
    update_mode: UpdateMode | None = None
    airgap_approved: bool | None = None

    @field_validator("first_seen", "last_seen", "expiry", mode="before")
    @classmethod
    def _parse_datetimes(cls, value: object) -> object:
        if isinstance(value, str):
            return value.replace("Z", "+00:00")
        return value


class IocRegistryDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coe_synthetic_fixture: bool = True
    captured_live_run: bool = False
    production_execution: bool = False
    sources: list[IocSourceRecord]
    iocs: list[IocRecord]


class IocLookupResult(BaseModel):
    match: bool
    confidence: ConfidenceLevel | None = None
    staleness_status: StalenessStatus | None = None
    tlp: str | None = None
    redacted_provenance: str | None = None
    lookup_name: str | None = None
    ioc_type: IocType | None = None
    normalized_value: str | None = None
    source_id: str | None = None
    blocking_reason: str | None = None
