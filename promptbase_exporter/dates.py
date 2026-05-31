from __future__ import annotations

from datetime import date, datetime, time, timezone


def parse_datetime_ms(value: str, *, end_of_day: bool) -> int:
    """Parse a date or ISO datetime into a UTC epoch-milliseconds integer.

    A bare ``YYYY-MM-DD`` date is interpreted in UTC, at the start of the day
    unless ``end_of_day`` is set. Naive datetimes are assumed UTC; aware ones
    are converted to UTC.
    """
    raw = value.strip()
    if not raw:
        raise ValueError("date value cannot be empty")
    try:
        if re_full_date(raw):
            parsed_date = date.fromisoformat(raw)
            parsed_datetime = datetime.combine(
                parsed_date,
                time.max if end_of_day else time.min,
                tzinfo=timezone.utc,
            )
        else:
            parsed_datetime = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed_datetime.tzinfo is None:
                parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)
            else:
                parsed_datetime = parsed_datetime.astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError(
            f"invalid date/datetime '{value}'. Use YYYY-MM-DD or ISO datetime."
        ) from exc
    return int(parsed_datetime.timestamp() * 1000)


def re_full_date(value: str) -> bool:
    return len(value) == 10 and value[4] == "-" and value[7] == "-"
