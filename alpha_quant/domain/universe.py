from __future__ import annotations

from datetime import date

from alpha_quant.domain.models import Bar, FundamentalsSnapshot, UniverseMember


def select(
    dt: date,
    all_symbols: list[str],
    bars_by_symbol: dict[str, list[Bar]],
    fundamentals_by_symbol: dict[str, FundamentalsSnapshot | None],
    *,
    sec_map: dict[str, object] | None = None,
    quarantined: set[str] | None = None,
    min_price: float = 5.0,
    min_adv: float = 5_000_000,
    adv_days: int = 20,
) -> list[UniverseMember]:
    quarantined = quarantined or set()
    results: list[UniverseMember] = []

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

        bars = bars_by_symbol.get(symbol)
        if not bars:
            results.append(
                UniverseMember(symbol=symbol, passes_m1=False, fail_reason="No bars data")
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

        snap = fundamentals_by_symbol.get(symbol)
        market_cap = snap.market_cap if snap else None
        sector = snap.sector if snap else None

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
