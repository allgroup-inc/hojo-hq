"""日付ユーティリティ：6ヶ月境界の判定を1か所に集約する。"""
from __future__ import annotations
import calendar
from datetime import date


def add_months(d: date, n: int) -> date:
    """d の n ヶ月後。月末は対象月の末日にクランプする（1/31 + 1ヶ月 = 2/28）。"""
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def has_reached_months(start: date, as_of: date, months: int) -> bool:
    """start から months ヶ月が経過したか（境界当日を含む）。"""
    return as_of >= add_months(start, months)


def is_within_months(start: date, end: date, months: int) -> bool:
    """end が start から months ヶ月以内か（境界当日を含む）。"""
    return end <= add_months(start, months)
