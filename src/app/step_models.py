from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from domain.events import DomainEvent
from domain.invariants import InvariantViolation
from domain.models import Bar, Decision, Fill, IndicatorState, Position
from domain.validate import ValidationResult


class LoadBarsResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    all_bars: dict[str, list[Bar]]
    prices: dict[str, float]
    events: list[DomainEvent] = Field(default_factory=list)


class ValidateResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    violations: list[ValidationResult] = Field(default_factory=list)
    halted: bool = False
    events: list[DomainEvent] = Field(default_factory=list)


class DeriveResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    indicator_states: dict[str, IndicatorState]
    events: list[DomainEvent] = Field(default_factory=list)


class RiskExitResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    positions: dict[str, Position]
    fills: list[Fill] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    cash_adjust: float = 0.0
    events: list[DomainEvent] = Field(default_factory=list)


class DecideResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    decisions: list[Decision] = Field(default_factory=list)
    fills: list[Fill] = Field(default_factory=list)
    events: list[DomainEvent] = Field(default_factory=list)
    entry_cost: float = 0.0


class ShadowBookResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    fills: list[Fill] = Field(default_factory=list)
    events: list[DomainEvent] = Field(default_factory=list)
    violations: list[InvariantViolation] = Field(default_factory=list)
