# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""
SPT Calculator — Substantial Presence Test arithmetic.

Implements the IRS Substantial Presence Test (IRC §7701(b)(3)) to
determine whether a nonresident alien meets the day-count threshold
for tax residency. This is pure math — no LLM reasoning.

Key rules implemented:
    1. The 5-Year Exempt Individual rule for F-1/J-1/M-1/Q-1 students
       (IRC §7701(b)(5)(A)–(D)).
    2. The SPT weighted day-count formula
       (current×1 + prior_1×⌊1/3⌋ + prior_2×⌊1/6⌋).
    3. The two-prong residency determination
       (≥31 current-year days AND ≥183 weighted days).

Reference:
    https://www.irs.gov/individuals/international-taxpayers/substantial-presence-test
"""

from __future__ import annotations

from datetime import date
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Visa categories that qualify as "Exempt Individuals" under §7701(b)(5)
# ---------------------------------------------------------------------------
# F-1, J-1 student, M-1, Q-1 students are exempt for up to 5 calendar years.
# J-1 teachers/researchers have a tighter 2-of-6-prior-calendar-years rule.
_EXEMPT_STUDENT_VISAS = frozenset({"F-1", "J-1", "M-1", "Q-1"})

# Maximum calendar years an exempt student can skip SPT day counting.
_MAX_EXEMPT_YEARS = 5

# J-1 teacher/researcher window: exempt for any part of 2 calendar years
# out of the preceding 6 (IRC §7701(b)(5)(E)).
_MAX_J1_TEACHER_RESEARCHER_YEARS = 2
_J1_TR_LOOKBACK_YEARS = 6


class SubstantialPresenceCalculator:
    """Performs the IRS Substantial Presence Test and exempt-individual check.

    This is the single entry-point class for Layer 1 deterministic logic.
    The orchestrator (or the L1 Residency Agent) calls ``evaluate_residency``
    with pre-collected day-count figures and receives back a dictionary that
    maps directly onto the ``ResidencyState`` Pydantic model.

    All arithmetic uses **integer division** (``//``) for the SPT fractions,
    matching IRS guidance that fractional days are dropped — not rounded.
    """

    # ── Public API ─────────────────────────────────────────────────────

    def evaluate_residency(
        self,
        tax_year: int,
        visa_type: str,
        first_us_arrival_year: int,
        days_present_current_year: int,
        days_present_minus_1: int,
        days_present_minus_2: int,
        visa_subtype: str = "student",
    ) -> Dict[str, object]:
        """Run the full SPT evaluation pipeline and return a residency result.

        This is the **main method** consumed by the orchestrator. It
        encapsulates three sequential checks:

            1. **Exempt-Individual Check** — Is the student still within the
               5-calendar-year exempt window for their visa type?
            2. **31-Day Minimum** — Were they present ≥ 31 days in the
               current tax year? (Needed before the weighted formula.)
            3. **SPT Weighted Formula** — Does the three-year weighted
               total reach ≥ 183 days?

        Args:
            tax_year: The calendar year being filed (e.g. 2024).
            visa_type: The individual's visa category (e.g. "F-1", "H-1B").
            first_us_arrival_year: The first calendar year the individual
                was present in the US on any visa.
            days_present_current_year: Days physically present in the US
                during ``tax_year``.
            days_present_minus_1: Days present in ``tax_year - 1``.
            days_present_minus_2: Days present in ``tax_year - 2``.
            visa_subtype: Distinguishes a J-1 "teacher_researcher" (2-year
                exempt window) from a J-1 "student" (5-year window, the
                default). No effect for F-1/M-1/Q-1, which always use the
                5-year window regardless of this value. This is a
                continuous-presence approximation of the real 2-of-6-prior-
                calendar-years rule (IRC §7701(b)(5)(E)) — it does not model
                gaps in US presence, matching the same simplifying
                assumption the 5-year student rule already makes.

        Returns:
            A dictionary compatible with the ``ResidencyState`` model::

                {
                    "status": "nonresident_alien" | "resident_alien",
                    "spt_days_current_year": int,
                    "is_exempt_individual": bool,
                    "exempt_visa_type": str | None,
                    "years_in_exempt_status": int,
                }
        """
        # Step 0: Compute how many calendar years the individual has been
        # present (arrival year counts as year 1).
        calendar_years_present = self._calendar_years_present(
            tax_year, first_us_arrival_year
        )

        # Step 1: Exempt-Individual check
        is_exempt = self._is_exempt_individual(
            visa_type, calendar_years_present, visa_subtype
        )

        # If exempt, days count as zero → automatic nonresident_alien
        if is_exempt:
            return {
                "status": "nonresident_alien",
                "spt_days_current_year": days_present_current_year,
                "is_exempt_individual": True,
                "exempt_visa_type": visa_type,
                "years_in_exempt_status": calendar_years_present,
            }

        # Step 2 & 3: SPT formula (only reached for non-exempt individuals)
        total_spt_days = self._compute_spt_days(
            days_present_current_year,
            days_present_minus_1,
            days_present_minus_2,
        )

        status = self._determine_status(
            days_present_current_year, total_spt_days
        )

        return {
            "status": status,
            "spt_days_current_year": days_present_current_year,
            "is_exempt_individual": False,
            "exempt_visa_type": None,
            "years_in_exempt_status": calendar_years_present,
        }

    # ── Internal helpers (pure functions) ──────────────────────────────

    @staticmethod
    def _calendar_years_present(tax_year: int, first_us_arrival_year: int) -> int:
        """Calculate the number of calendar years present in the US.

        The arrival year itself counts as year 1.

        Examples:
            - Arrived 2020, filing 2024 → (2024 - 2020) + 1 = 5
            - Arrived 2024, filing 2024 → (2024 - 2024) + 1 = 1

        Args:
            tax_year: The tax year being filed.
            first_us_arrival_year: Year of first US arrival.

        Returns:
            Number of calendar years present (always ≥ 1).
        """
        return (tax_year - first_us_arrival_year) + 1

    @staticmethod
    def _is_exempt_individual(
        visa_type: str, calendar_years_present: int, visa_subtype: str = "student"
    ) -> bool:
        """Determine if the individual is an Exempt Individual under §7701(b)(5).

        An individual on an F-1, J-1, M-1, or Q-1 student visa is exempt
        from the SPT for up to 5 calendar years from their first US arrival.
        A J-1 teacher/researcher instead gets a tighter 2-calendar-year
        window (IRC §7701(b)(5)(E)) — visa_type alone ("J-1") cannot
        distinguish the two, hence visa_subtype. Once the filer exceeds
        their applicable window, they are no longer exempt and must pass
        the SPT like any other alien.

        Args:
            visa_type: The visa category string (e.g. "F-1").
            calendar_years_present: Years since first arrival (inclusive).
            visa_subtype: "teacher_researcher" selects the 2-year J-1 window;
                anything else (including the default "student") uses the
                5-year window.

        Returns:
            True if the individual qualifies as exempt.
        """
        if visa_type not in _EXEMPT_STUDENT_VISAS:
            return False
        max_years = (
            _MAX_J1_TEACHER_RESEARCHER_YEARS
            if visa_type == "J-1" and visa_subtype == "teacher_researcher"
            else _MAX_EXEMPT_YEARS
        )
        return calendar_years_present <= max_years

    @staticmethod
    def _compute_spt_days(
        days_current: int,
        days_minus_1: int,
        days_minus_2: int,
    ) -> int:
        """Apply the IRS SPT weighted day-count formula.

        Formula (IRC §7701(b)(3)(A)):
            total = days_current × 1
                  + days_minus_1 × (1/3)   ← integer division, drop fraction
                  + days_minus_2 × (1/6)   ← integer division, drop fraction

        The IRS explicitly drops fractional days (they do NOT round).

        Args:
            days_current: Days present in the current tax year.
            days_minus_1: Days present in the first prior year.
            days_minus_2: Days present in the second prior year.

        Returns:
            Total weighted SPT days as an integer.
        """
        return days_current + (days_minus_1 // 3) + (days_minus_2 // 6)

    @staticmethod
    def _determine_status(days_current: int, total_spt_days: int) -> str:
        """Apply the two-prong SPT residency determination.

        Prong 1: The individual must be present ≥ 31 days in the current year.
        Prong 2: The weighted SPT total must be ≥ 183 days.

        Both prongs must be satisfied to classify as resident_alien.

        Args:
            days_current: Days present in the current tax year.
            total_spt_days: Weighted total from ``_compute_spt_days``.

        Returns:
            "resident_alien" if both prongs pass, else "nonresident_alien".
        """
        if days_current < 31:
            return "nonresident_alien"
        if total_spt_days >= 183:
            return "resident_alien"
        return "nonresident_alien"

    # ── Dual-status detection ────────────────────────────────────────────

    def evaluate_residency_with_status_change(
        self,
        tax_year: int,
        visa_type: str,
        first_us_arrival_year: int,
        days_present_current_year: int,
        days_present_minus_1: int,
        days_present_minus_2: int,
        first_day_in_us_current_year: Optional[date] = None,
        last_day_in_us_current_year: Optional[date] = None,
        prior_visa_was_resident: bool = False,
        visa_subtype: str = "student",
    ) -> Dict[str, object]:
        """Detect dual-status (mid-year transition between NRA and RA).

        Three triggers under IRC §7701(b)(2):

        1. **Arrival year** — NRA for part of the year then meets SPT later.
        2. **Departure year** — RA for part of the year then leaves.
        3. **First-year choice** — §7701(b)(4) election (out of scope for v1).

        Args:
            tax_year: Calendar year being filed.
            visa_type: Current visa.
            first_us_arrival_year: First calendar year the filer was in the US.
            days_present_current_year: Days present in ``tax_year``.
            days_present_minus_1: Days present in ``tax_year - 1``.
            days_present_minus_2: Days present in ``tax_year - 2``.
            first_day_in_us_current_year: First date physically present in the
                US during the current year, if known.
            last_day_in_us_current_year: Last date physically present, if known.
            prior_visa_was_resident: True if the filer was an RA in the prior
                year (informs the departure-year path).

        Returns:
            Dict mirroring :meth:`evaluate_residency` plus ``residency_start_date``,
            ``residency_end_date``, and ``is_dual_status``.
        """
        base = self.evaluate_residency(
            tax_year=tax_year,
            visa_type=visa_type,
            first_us_arrival_year=first_us_arrival_year,
            days_present_current_year=days_present_current_year,
            days_present_minus_1=days_present_minus_1,
            days_present_minus_2=days_present_minus_2,
            visa_subtype=visa_subtype,
        )

        result: Dict[str, object] = dict(base)
        result.update(
            {
                "is_dual_status": False,
                "residency_start_date": None,
                "residency_end_date": None,
                "dual_status_reason": None,
            }
        )

        # Exempt individuals are NRA all year — no dual-status from exempt visa.
        if base["is_exempt_individual"]:
            return result

        # Arrival-year dual-status: filer was not an RA last year, became one
        # this year, and first US presence is partway through the calendar year.
        if (
            base["status"] == "resident_alien"
            and not prior_visa_was_resident
            and first_day_in_us_current_year is not None
            and first_day_in_us_current_year > date(tax_year, 1, 1)
        ):
            result["status"] = "dual_status"
            result["is_dual_status"] = True
            result["residency_start_date"] = first_day_in_us_current_year.isoformat()
            result["dual_status_reason"] = (
                "Arrival-year dual status: NRA from Jan 1 to residency_start_date, "
                "resident alien thereafter (IRC §7701(b)(2)(A))."
            )
            return result

        # Departure-year dual-status: filer was an RA last year, leaves the US
        # partway through this year, and is NRA after departure.
        if (
            prior_visa_was_resident
            and last_day_in_us_current_year is not None
            and last_day_in_us_current_year < date(tax_year, 12, 31)
        ):
            result["status"] = "dual_status"
            result["is_dual_status"] = True
            result["residency_end_date"] = last_day_in_us_current_year.isoformat()
            result["dual_status_reason"] = (
                "Departure-year dual status: resident alien through "
                "residency_end_date, NRA thereafter (IRC §7701(b)(2)(B))."
            )
            return result

        return result
