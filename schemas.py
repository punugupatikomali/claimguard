"""Validated structured data used by ClaimGuard."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class BillItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str = Field(min_length=1, max_length=240)
    service_date: str | None = None
    quantity: float = Field(default=1, ge=0)
    unit_price: float = Field(default=0, ge=0)
    total: float = Field(ge=0)
    category: str = "other"
    page: int | None = Field(default=None, ge=1)


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="ignore")
    rule_type: Literal["room_daily_limit", "excluded_service", "not_covered", "other"]
    description: str = Field(min_length=1, max_length=500)
    amount_limit: float | None = Field(default=None, ge=0)
    target_keywords: list[str] = Field(default_factory=list)
    page: int | None = Field(default=None, ge=1)
    quote: str = Field(default="", max_length=1200)
    confidence: Literal["high", "medium", "low"] = "medium"


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    bill_items: list[BillItem] = Field(default_factory=list)
    policy_rules: list[PolicyRule] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
