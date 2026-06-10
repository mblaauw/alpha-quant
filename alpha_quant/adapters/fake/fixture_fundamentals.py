from alpha_quant.domain.models import EarningsEntry, FundamentalsSnapshot
from alpha_quant.ports.fundamentals import Fundamentals


class FixtureFundamentals(Fundamentals):
    def __init__(
        self,
        snapshots: dict[str, FundamentalsSnapshot] | None = None,
    ) -> None:
        self._snapshots: dict[str, FundamentalsSnapshot] = snapshots or {}
        self._earnings: list[EarningsEntry] = []

    def seed_snapshot(self, symbol: str, data: FundamentalsSnapshot) -> None:
        self._snapshots[symbol] = data

    def seed_earnings_calendar(self, entries: list[EarningsEntry]) -> None:
        self._earnings = entries

    async def snapshot(self, symbol: str) -> FundamentalsSnapshot:
        if symbol not in self._snapshots:
            msg = f"No fixture fundamentals for symbol: {symbol}"
            raise ValueError(msg)
        return self._snapshots[symbol]

    async def earnings_calendar(self, start: str, end: str) -> list[EarningsEntry]:
        return [e for e in self._earnings if start <= e.date.isoformat() <= end]
