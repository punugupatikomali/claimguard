"""Validated structured data used by ClaimGuard."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class BillItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str = Field(min_length=1, max_length=240)
    service_date: Optional[str] = None
    quantity: float = Field(default=1, ge=0)
    unit_price: float = Field(default=0, ge=0)
    total: float = Field(ge=0)
    category: str = "other"
    page: Optional[int] = Field(default=None, ge=1)


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rule_type: Literal["room_daily_limit", "excluded_service", "not_covered", "other"]
    description: str = Field(min_length=1, max_length=500)
    amount_limit: Optional[float] = Field(default=None, ge=0)
    target_keywords: list[str] = Field(default_factory=list)
    page: Optional[int] = Field(default=None, ge=1)
    quote: str = Field(default="", max_length=1200)
    confidence: Literal["high", "medium", "low"] = "medium"


class ClaimInfo(BaseModel):
    """Non-personal claim header fields. Patient identifiers are deliberately not extracted."""
    model_config = ConfigDict(extra="ignore")
    invoice_number: Optional[str] = None
    provider: Optional[str] = None
    bill_date: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    stated_total: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = None


class AIObservation(BaseModel):
    """Something unusual Claude noticed that the deterministic checks do not cover. Never priced."""
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=160)
    detail: str = Field(default="", max_length=800)
    severity: Literal["high", "medium", "low"] = "low"
    related_item: Optional[str] = None


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    claim_info: ClaimInfo = Field(default_factory=ClaimInfo)
    bill_items: list[BillItem] = Field(default_factory=list)
    policy_rules: list[PolicyRule] = Field(default_factory=list)
    observations: list[AIObservation] = Field(default_factory=list)
    reviewer_summary: str = Field(default="", max_length=1500)
    notes: list[str] = Field(default_factory=list)
