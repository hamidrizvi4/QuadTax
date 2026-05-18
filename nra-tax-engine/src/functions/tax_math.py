# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""Tax math — graduated brackets for ECI, flat rate for FDAP.

This module is the deterministic core of federal tax liability computation.
It reads year-keyed bracket tables from ``src/database/tax_year/<year>/`` via
:func:`src.database.tax_year.load_year` and applies them in sequence.

Backward compatibility:
    Callers that omit ``tax_year`` and ``filing_status`` will get TY2025 single
    filer brackets — the same data the year-keyed JSON files now hold. Phase 2
    of the production-readiness plan migrates monetary values to
    :class:`decimal.Decimal`; for now float-with-explicit-round matches IRS
    rounding ("nearest whole dollar").
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

from src.database.tax_year import (
    NRA_ALLOWED_FILING_STATUSES,
    FilingStatus,
    load_year,
)

DEFAULT_TAX_YEAR = 2025
DEFAULT_FILING_STATUS: FilingStatus = "single"


class TaxCalculator:
    """Computes ECI tax via graduated brackets and FDAP tax at a flat rate.

    Args:
        tax_year: Calendar year of the return (default: 2025).
        filing_status: One of ``single`` / ``mfs`` / ``qss``. NRAs cannot
            file MFJ except via §6013(g) election; ``hoh`` is not permitted.
        db_path: Legacy escape hatch — when provided, loads a raw bracket
            list from a single JSON file (the pre-Phase-0 format). Kept so
            existing unit tests that construct ``TaxCalculator()`` with no
            arguments continue to work against the new year-keyed data.
    """

    def __init__(
        self,
        tax_year: int = DEFAULT_TAX_YEAR,
        filing_status: FilingStatus = DEFAULT_FILING_STATUS,
        db_path: Union[str, Path, None] = None,
    ) -> None:
        if filing_status not in NRA_ALLOWED_FILING_STATUSES and filing_status != "mfj":
            raise ValueError(
                f"Invalid filing_status '{filing_status}'. "
                f"NRA filers may use: {sorted(NRA_ALLOWED_FILING_STATUSES)}."
            )

        self.tax_year = tax_year
        self.filing_status: FilingStatus = filing_status

        if db_path is not None:
            with open(db_path, "r", encoding="utf-8") as f:
                self.brackets: List[Dict[str, Optional[float]]] = json.load(f)
        else:
            year = load_year(tax_year)
            try:
                rows = year.brackets[filing_status]
            except KeyError as e:
                raise ValueError(
                    f"No brackets available for filing_status '{filing_status}' in TY{tax_year}."
                ) from e
            self.brackets = [
                {"rate": b.rate, "up_to": b.up_to, "min": b.min, "base_tax": b.base_tax}
                for b in rows
            ]

    def calculate_tax_liability(
        self,
        eci_taxable_income: float,
        fdap_taxable_income: float,
        fdap_rate: float,
    ) -> Dict[str, float]:
        """Apply graduated brackets to ECI and a flat rate to FDAP.

        Args:
            eci_taxable_income: Net ECI after deductions and treaty exemptions.
            fdap_taxable_income: Net FDAP after treaty exemptions (no deductions).
            fdap_rate: Statutory or treaty-overridden flat rate (e.g. 0.30, 0.14, 0.0).

        Returns:
            Dictionary with keys ``eci_tax_liability``, ``fdap_tax_liability``,
            and ``total_tax_liability``, each rounded to the nearest whole
            dollar per IRS practice.
        """
        fdap_tax = fdap_taxable_income * fdap_rate

        eci_tax = 0.0
        remaining_income = float(eci_taxable_income)
        previous_bracket_up_to = 0.0

        for bracket in self.brackets:
            if remaining_income <= 0:
                break

            up_to = bracket.get("up_to")
            rate = float(bracket["rate"])

            if up_to is not None:
                bracket_size = float(up_to) - previous_bracket_up_to
                chunk = min(remaining_income, bracket_size)
            else:
                chunk = remaining_income

            eci_tax += chunk * rate
            remaining_income -= chunk

            if up_to is not None:
                previous_bracket_up_to = float(up_to)

        eci_tax_rounded = float(round(eci_tax))
        fdap_tax_rounded = float(round(fdap_tax))

        return {
            "eci_tax_liability": eci_tax_rounded,
            "fdap_tax_liability": fdap_tax_rounded,
            "total_tax_liability": eci_tax_rounded + fdap_tax_rounded,
        }
