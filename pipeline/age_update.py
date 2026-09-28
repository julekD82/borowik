import math


def _parse_year(a_year) -> int | None:
    """`a_year` arrives from WFS as a plain int/str most of the time, but can
    be missing (None) or a float NaN (pandas' usual stand-in for a missing
    numeric cell) -- both mean "rok stanu opisu nieznany"."""
    if a_year is None:
        return None
    if isinstance(a_year, float) and math.isnan(a_year):
        return None
    try:
        return int(a_year)
    except (TypeError, ValueError):
        return None


def update_age(spec_age: float | None, a_year, analysis_year: int, enabled: bool) -> tuple[float | None, str]:
    """Plan wdrozenia 1.6.2: wiek z opisu taksacyjnego (`spec_age`, as of
    `a_year`) shifted forward to `analysis_year` -- `wiek_obecny =
    wiek_z_opisu + (rok_analizy - rok_stanu_opisu)`. Gated by
    `profile["age"]["update_to_analysis_year"]` (`enabled`), default True.

    Returns (age_to_use, status), status in:
    - "wylaczona": `enabled` is False -- pre-1.6.2 behaviour, `spec_age`
      returned unchanged (an intentional config choice, not a data gap).
    - "brak_roku_stanu": `enabled` is True but `a_year` is missing/
      unparseable -- no correction applied (spec: "bez korekty i flaga w
      diagnostyce"), `spec_age` returned unchanged.
    - "skorygowano": correction applied (a no-op shift of 0 when
      `analysis_year == a_year` still counts as applied). A bare `spec_age
      is None` also lands here when `a_year` is known -- there is nothing to
      shift, but the rok-stanu lookup itself did not fail."""
    if not enabled:
        return spec_age, "wylaczona"
    year = _parse_year(a_year)
    if year is None:
        return spec_age, "brak_roku_stanu"
    if spec_age is None:
        return None, "skorygowano"
    return spec_age + (analysis_year - year), "skorygowano"
