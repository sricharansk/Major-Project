"""Timestamp normalisation.  Naive NYC-local timestamps are never silently treated as UTC."""

from __future__ import annotations

import polars as pl

NYC = "America/New_York"


def local_naive_to_utc(col: str, out: str | None = None) -> list[pl.Expr]:
    """Interpret a naive (floating) Socrata timestamp string as America/New_York and convert to UTC.

    DST-ambiguous (fall-back hour) and non-existent (spring-forward hour) local times become null and
    are counted by the caller via ``<out>_tz_unresolved``.
    """
    out = out or f"{col}_utc"
    parsed = pl.col(col).str.strptime(pl.Datetime("us"), strict=False)
    utc = parsed.dt.replace_time_zone(NYC, ambiguous="null", non_existent="null").dt.convert_time_zone("UTC")
    return [
        utc.alias(out),
        (parsed.is_not_null() & utc.is_null()).alias(f"{out}_tz_unresolved"),
    ]


def utc_string_to_utc(col: str, out: str | None = None) -> pl.Expr:
    out = out or f"{col}_utc"
    return pl.col(col).str.strptime(pl.Datetime("us"), strict=False).dt.replace_time_zone("UTC").alias(out)


def right_labelled_bin(col: str, minutes: int, out: str = "bin_utc") -> pl.Expr:
    """Bin label t for observations in [t - minutes, t): label = floor(ts) + minutes.

    At forecast origin t only bins with label <= t are used, i.e. observations strictly before t.
    """
    return (pl.col(col).dt.truncate(f"{minutes}m") + pl.duration(minutes=minutes)).alias(out)
