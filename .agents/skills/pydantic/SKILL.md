---
name: pydantic
description: Pydantic v2 patterns used in Alpha-Quant — frozen BaseModel, discriminated unions for events, JSON schema generation, and validation conventions.
---

# Pydantic v2 for Alpha-Quant

All data models use `pydantic.BaseModel` with `frozen=True`.

## Convention

```python
from pydantic import BaseModel


class MyModel(BaseModel, frozen=True):
    field: str
    count: int = 0
```

## Domain Events

Events use discriminated unions with `Annotated` and `Discriminator`:

```python
from typing import Annotated, Literal
from pydantic import BaseModel, Field, Discriminator


class OrderPlaced(BaseModel, frozen=True):
    event_type: Literal["order_placed"] = "order_placed"
    symbol: str
    shares: int


class FillExecuted(BaseModel, frozen=True):
    event_type: Literal["fill_executed"] = "fill_executed"
    symbol: str
    shares: int
    price: float


TradingEvent = Annotated[
    OrderPlaced | FillExecuted,
    Field(discriminator="event_type"),
]
```

## Validation

- Use `field_validator` for cross-field validation
- Use `model_validator` for whole-model invariants
- Prefer `field_validator` with `@classmethod` and `mode="before"` for coercion

## JSON Schema

```bash
uv run python -c "
import json
from domain.models import PortfolioSnapshot
print(json.dumps(PortfolioSnapshot.model_json_schema(), indent=2))
"
```

## Key Domain Models

Located in `src/domain/models.py`:
- `Bar`, `Quote` — Market data
- `Position`, `Order`, `Fill` — Trading state
- `Decision`, `Candidate` — Decision engine output
- `IndicatorState` — Technical indicator state
- `PortfolioSnapshot` — Daily portfolio summary
