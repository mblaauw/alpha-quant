from __future__ import annotations

from datetime import date, timedelta

from alpha_quant.domain.models import UniverseMember
from alpha_quant.ports.fundamentals import Fundamentals
from alpha_quant.ports.market_data import MarketData


def select(
    dt: date,
    all_symbols: list[str],
    market_data: MarketData,
    fundamentals: Fundamentals,
    *,
    sec_map: dict[str, object] | None = None,
    quarantined: set[str] | None = None,
    min_price: float = 5.0,
    min_adv: float = 5_000_000,
) -> list[UniverseMember]:
    quarantined = quarantined or set()
    results: list[UniverseMember] = []
    adv_days = 20

    for symbol in all_symbols:
        if symbol in quarantined:
            results.append(
                UniverseMember(symbol=symbol, passes_m1=False, fail_reason="Quarantined")
            )
            continue

        if sec_map is not None and symbol not in sec_map:
            results.append(
                UniverseMember(symbol=symbol, passes_m1=False, fail_reason="No SEC CIK mapping")
            )
            continue

        start = dt - timedelta(days=adv_days * 2)
        try:
            bars = market_data.daily_bars(symbol, start, dt)
        except Exception:
            results.append(
                UniverseMember(symbol=symbol, passes_m1=False, fail_reason="Price data unavailable")
            )
            continue

        if not bars:
            results.append(
                UniverseMember(symbol=symbol, passes_m1=False, fail_reason="No recent bars")
            )
            continue

        recent_bars = [b for b in bars if b.date <= dt][-adv_days:]
        if not recent_bars:
            results.append(
                UniverseMember(symbol=symbol, passes_m1=False, fail_reason="No bars in window")
            )
            continue

        latest = recent_bars[-1]
        price = latest.close

        if price < min_price:
            results.append(
                UniverseMember(
                    symbol=symbol,
                    price=price,
                    passes_m1=False,
                    fail_reason=f"Price ${price:.2f} below ${min_price:.2f}",
                )
            )
            continue

        dollar_volumes = [b.close * b.volume for b in recent_bars]
        sorted_dv = sorted(dollar_volumes)
        adv = sorted_dv[len(sorted_dv) // 2]

        if adv < min_adv:
            results.append(
                UniverseMember(
                    symbol=symbol,
                    price=price,
                    volume_adv=adv,
                    passes_m1=False,
                    fail_reason=f"ADV ${adv:,.0f} below ${min_adv:,.0f}",
                )
            )
            continue

        try:
            snap = fundamentals.snapshot(symbol)
            market_cap = snap.market_cap
            sector = snap.sector
        except Exception:
            market_cap = None
            sector = None

        results.append(
            UniverseMember(
                symbol=symbol,
                price=price,
                volume_adv=adv,
                market_cap=market_cap,
                sector=sector,
                passes_m1=True,
            )
        )

    return results
