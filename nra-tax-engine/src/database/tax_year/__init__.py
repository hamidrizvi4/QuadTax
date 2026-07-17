"""Year-keyed tax data loader.

Each tax year has its own directory (e.g. ``database/tax_year/2025/``) holding
the bracket tables, standard deductions, FICA limits, AMT parameters, and
Schedule NEC rates for that year. This module exposes :func:`load_year`
which validates the data through Pydantic models and returns an immutable
``LoadedYear`` view for the calculation modules to consume.

Design notes:
    - Money values stay as plain numbers in JSON for readability; callers
      should wrap in ``decimal.Decimal`` at the point of use when correctness
      matters (Phase 2 will migrate the calculators).
    - The loader does NOT cache by default. Callers may cache the
      ``LoadedYear`` instance once at process start.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

FilingStatus = Literal["single", "mfs", "mfj", "qss", "hoh"]
NRA_ALLOWED_FILING_STATUSES = frozenset({"single", "mfs", "qss"})


class Bracket(BaseModel):
    """One row of a graduated tax bracket table."""

    rate: float = Field(ge=0.0, le=1.0)
    min: float = Field(ge=0.0)
    up_to: Optional[float] = Field(default=None, description="Inclusive upper bound. None for top bracket.")
    base_tax: float = Field(ge=0.0, description="Pre-computed cumulative tax at the bottom of this bracket.")


class StandardDeduction(BaseModel):
    """Standard deduction amounts and NRA-specific rules."""

    amounts: Dict[str, float]
    nra_rules: Dict[str, object]
    additional_amounts: Dict[str, float] = Field(default_factory=dict)

    def for_status(self, status: FilingStatus, india_treaty: bool = False) -> float:
        """Return the deduction amount for ``status``, honoring the India treaty exception."""
        if india_treaty:
            india_map = self.nra_rules.get("nra_india_treaty_amount_by_status", {})
            if isinstance(india_map, dict) and status in india_map:
                return float(india_map[status])
            return float(self.amounts.get(status, 0.0))
        nra_default = self.nra_rules.get("nra_default", 0)
        return float(nra_default)

    def for_dependent(
        self, status: FilingStatus, earned_income: float, india_treaty: bool = False
    ) -> float:
        """IRC §63(c)(5): a filer who can be claimed as another taxpayer's
        dependent has their standard deduction capped at the greater of a
        fixed minimum or (earned income + a small addon), never exceeding
        the regular amount for their status.
        """
        regular_amount = self.for_status(status, india_treaty=india_treaty)
        minimum = float(self.nra_rules.get("dependent_minimum", 0))
        addon = float(self.nra_rules.get("dependent_earned_income_addon", 0))
        dependent_amount = max(minimum, float(earned_income) + addon)
        return min(regular_amount, dependent_amount)


class FICALimits(BaseModel):
    """Social Security and Medicare wage bases and rates."""

    social_security: Dict[str, float]
    medicare: Dict[str, object]
    fica_exempt_visas: List[str]
    fica_exempt_cite: str


class AMTParams(BaseModel):
    """Alternative Minimum Tax parameters."""

    exemption: Dict[str, float]
    phaseout_threshold: Dict[str, float]
    rate_kink: Dict[str, float]
    rates: Dict[str, float]


class SchNECRates(BaseModel):
    """Schedule NEC statutory FDAP rates by category."""

    default_rate: float
    category_rates: Dict[str, float]
    long_term_capital_gain_us_source_non_real_property: Dict[str, float]


class LoadedYear(BaseModel):
    """Immutable view of one tax year's parameter set."""

    tax_year: int
    brackets: Dict[FilingStatus, List[Bracket]]
    standard_deduction: StandardDeduction
    fica: FICALimits
    amt: AMTParams
    sch_nec: SchNECRates
    ny: Optional[Dict[str, object]] = None

    model_config = {"frozen": True}


def _data_dir(tax_year: int) -> Path:
    return Path(__file__).parent / str(tax_year)


def supported_years() -> List[int]:
    """Return every tax year currently vendored under ``database/tax_year/``.

    Scans for direct subdirectories whose name is a 4-digit year (skips
    ``__pycache__`` and any other non-year directory). Used to build
    helpful "unsupported year" error messages instead of a bare
    ``FileNotFoundError`` — see :func:`load_year` and
    :class:`src.orchestrator.engine.UnsupportedTaxYearError`.
    """
    root = Path(__file__).parent
    years = [
        int(child.name)
        for child in root.iterdir()
        if child.is_dir() and child.name.isdigit() and len(child.name) == 4
    ]
    return sorted(years)


def _strip_meta(value):
    """Recursively drop keys whose name begins with ``_`` (documentation/meta)."""
    if isinstance(value, dict):
        return {k: _strip_meta(v) for k, v in value.items() if not k.startswith("_")}
    if isinstance(value, list):
        return [_strip_meta(v) for v in value]
    return value


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return _strip_meta(raw)


def _load_brackets(tax_year: int, status: FilingStatus) -> List[Bracket]:
    raw = _load_json(_data_dir(tax_year) / f"brackets_{status}.json")
    return [Bracket(**row) for row in raw["brackets"]]


@lru_cache(maxsize=8)
def load_year(tax_year: int) -> LoadedYear:
    """Load and validate all parameter files for ``tax_year``.

    Args:
        tax_year: Calendar year of the return being filed (e.g. 2025).

    Returns:
        A :class:`LoadedYear` with bracket tables and lookup parameters.

    Raises:
        FileNotFoundError: If the year directory or any required file is missing.
        pydantic.ValidationError: If a data file does not match the schema.
    """
    base = _data_dir(tax_year)
    if not base.is_dir():
        raise FileNotFoundError(
            f"Tax year directory not found: {base}. Add database/tax_year/{tax_year}/ first."
        )

    brackets: Dict[FilingStatus, List[Bracket]] = {}
    for status in ("single", "mfs", "qss"):
        path = base / f"brackets_{status}.json"
        if path.exists():
            brackets[status] = _load_brackets(tax_year, status)  # type: ignore[arg-type]

    standard_deduction = StandardDeduction(**_load_json(base / "standard_deduction.json"))
    fica = FICALimits(**_load_json(base / "fica_limits.json"))
    amt = AMTParams(**_load_json(base / "amt.json"))
    sch_nec = SchNECRates(**_load_json(base / "sch_nec_rates.json"))

    ny_path = base / "ny.json"
    ny = _load_json(ny_path) if ny_path.exists() else None

    return LoadedYear(
        tax_year=tax_year,
        brackets=brackets,
        standard_deduction=standard_deduction,
        fica=fica,
        amt=amt,
        sch_nec=sch_nec,
        ny=ny,
    )
