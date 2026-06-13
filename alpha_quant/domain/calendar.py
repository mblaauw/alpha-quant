from datetime import date, timedelta


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    last = date(year, month + 1, 1) - timedelta(days=1)
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


def _known_holidays(year: int) -> list[date]:
    raw: list[date] = [
        date(year, 1, 1),
        _nth_weekday_of_month(year, 1, 0, 3),
        _nth_weekday_of_month(year, 2, 0, 3),
        _last_weekday_of_month(year, 5, 0),
        date(year, 6, 19),
        date(year, 7, 4),
        _nth_weekday_of_month(year, 9, 0, 1),
        _nth_weekday_of_month(year, 11, 3, 4),
        date(year, 12, 25),
    ]
    observed: list[date] = []
    for h in raw:
        if h.weekday() == 5:
            observed.append(h - timedelta(days=1))
        elif h.weekday() == 6:
            observed.append(h + timedelta(days=1))
        else:
            observed.append(h)
    return observed


_holiday_cache: dict[int, list[date]] = {}


def is_market_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    year = d.year
    if year not in _holiday_cache:
        _holiday_cache[year] = _known_holidays(year)
    return d not in _holiday_cache[year]


def prev_market_day(d: date) -> date:
    d -= timedelta(days=1)
    while not is_market_day(d):
        d -= timedelta(days=1)
    return d


def next_market_day(d: date) -> date:
    d += timedelta(days=1)
    while not is_market_day(d):
        d += timedelta(days=1)
    return d
