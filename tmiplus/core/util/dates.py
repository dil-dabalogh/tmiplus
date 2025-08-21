from __future__ import annotations
from datetime import date, timedelta
import dateparser

def parse_date(s: str) -> date:
    d = dateparser.parse(s)
    if not d:
        raise ValueError(f"Could not parse date: {s}")
    return d.date()

def iso_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

def date_to_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")

def iter_weeks(from_date: date, to_date: date):
    cur = iso_monday(from_date)
    end = iso_monday(to_date)
    while cur <= end:
        yield cur
        cur += timedelta(days=7)

def week_end_from_start_str(week_start: str) -> str:
    """Given a week start (Monday) string YYYY-MM-DD, return the week end (Sunday) string.

    This is helpful for normalizing assignment week ranges when only a start is provided.
    """
    start = parse_date(week_start)
    return date_to_str(start + timedelta(days=6))
