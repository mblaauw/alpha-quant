from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from alpha_quant.domain.models import Decision, Fill, Order, Position


class BarsUpdated(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["bars_updated"] = "bars_updated"
    occurred_at: datetime
    symbol: str
    date: date


class OrderSubmitted(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["order_submitted"] = "order_submitted"
    occurred_at: datetime
    order: Order


class OrderFilled(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["order_filled"] = "order_filled"
    occurred_at: datetime
    fill: Fill


class DecisionMade(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["decision_made"] = "decision_made"
    occurred_at: datetime
    decision: Decision


class PositionOpened(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["position_opened"] = "position_opened"
    occurred_at: datetime
    position: Position


class PositionClosed(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["position_closed"] = "position_closed"
    occurred_at: datetime
    symbol: str


class ErrorOccurred(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["error_occurred"] = "error_occurred"
    occurred_at: datetime
    error: str
    context: dict = {}


DomainEvent = Annotated[
    BarsUpdated
    | OrderSubmitted
    | OrderFilled
    | DecisionMade
    | PositionOpened
    | PositionClosed
    | ErrorOccurred,
    Field(discriminator="event_type"),
]
