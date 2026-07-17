"""Form IT-203-B — Nonresident and Part-Year Resident Income Allocation.

Schedule A: allocation of wage and salary income to NY State (lines 1a-1p
on the vendored 2025 PDF). This engine tracks one aggregate job (total
wages + NY/total work days), so only the first Schedule A block (page 1)
is populated; the page-3 continuation blocks for a 2nd/3rd job are left
blank.

Line semantics (verified against the real form, not assumed):
    1a  Total calendar days at this job = 365 (constant).
    1b-1f  Nonworking-day breakdown (Sat/Sun, holidays, sick, vacation,
           other): not tracked at this granularity — left blank.
    1g  Total nonworking days: derived as 1a - 1h (not summed from 1b-1f,
        since that breakdown isn't tracked) so the 1g-1h-1i-1k-1l chain
        stays internally consistent even though 1b-1f are blank.
    1h  Total days worked in year at this job = total_work_days.
    1i  Days (of 1h) worked outside NY = total_work_days - ny_work_days.
    1j  Days worked at home (of 1i): not tracked — 0.
    1k  = 1i - 1j = 1i.
    1l  Days worked in NY = 1h - 1k = ny_work_days.
    1m  = 1h (repeated per form instructions).
    1n  = 1l / 1m = ny_work_days / total_work_days — the WAGE allocation
         ratio ``ny_source_allocator.allocate()`` actually used to compute
         ``ny.ny_source_wages`` (line 1p). This is deliberately NOT the
         same as ``ny.ny_income_percentage`` (the blended AGI-level ratio
         used on IT-203 line 45), which also folds in 1042-S/FDAP
         allocation and can differ from the pure wage-day ratio.
         Reproduces all three of ``allocate()``'s apportionment branches
         (not just the day-ratio one) using ``ny.employer_in_ny``: when
         the Schedule A employer isn't NY-based, ``allocate()`` zeroes out
         NY-source wages regardless of the day ratio, so 1n must show 0
         too or 1n × 1o would silently disagree with the real 1p amount.
    1o  Wages to be allocated = total_w2_wages.
    1p  NY-allocated wages, taken directly from ``ny.ny_source_wages``
        (independently computed by ``ny_source_allocator``) rather than
        recomputed as 1n × 1o here, to avoid rounding drift against the
        number that actually drives the tax calculation.

Schedule B: living quarters maintained in NY. The address block is gated
on ``abode_months_in_year > 0`` (months an NY abode — dorm or otherwise —
was maintained), NOT ``days_in_ny`` (mere physical-presence day count,
which is also nonzero for e.g. a filer who took a short NYC trip but
never maintained living quarters there and would wrongly get an address
row). Column E ("living quarters still maintained") has no dedicated
intake field distinguishing "still maintains this specific NY address"
from general US presence, so it is approximated with
``residency.is_still_in_us`` (documented limitation — see
``compute_field_map``). Schedule C (college tuition itemized deduction)
has no backing intake data and is left entirely blank.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    ny = state.ny

    total_days = 365
    days_worked = int(ny.total_work_days)
    days_outside_ny = max(0, days_worked - int(ny.ny_work_days))
    nonworking_days = max(0, total_days - days_worked)
    # Matches ny_source_allocator.allocate()'s exact formula (all three
    # branches, including the non-NY-employer case) so 1n truly reflects
    # the ratio that produced ny.ny_source_wages (see docstring).
    if not ny.employer_in_ny:
        wage_pct = 0.0
    elif ny.total_work_days > 0:
        wage_pct = max(0.0, min(1.0, ny.ny_work_days / ny.total_work_days))
    else:
        wage_pct = 1.0

    field_map = {
        "name": f"{ident.first_name} {ident.last_name}".strip(),
        "occupation": ident.occupation,
        "ssn": ident.primary_tin,
        # Schedule A — job 1
        "1a": str(total_days),
        "1g": str(nonworking_days),
        "1h": str(days_worked),
        "1i": str(days_outside_ny),
        "1j": "0",
        "1k": str(days_outside_ny),
        "1l": str(int(ny.ny_work_days)),
        "1m": str(days_worked),
        "1n": f"{wage_pct:.4f}",
        "1o": f"{float(state.income.total_w2_wages):.0f}",
        "1p": f"{float(ny.ny_source_wages):.0f}",
        # Schedule B — living quarters maintained in NY
        "days_in_ny": str(int(ny.days_in_ny)),
        "_note": (
            "Schedule A only completed for a single aggregate job (this "
            "engine does not track per-employer allocation); the page-3 "
            "continuation blocks for a 2nd/3rd job are blank. Schedule C "
            "(college tuition itemized deduction) has no supporting "
            "intake data and is left entirely blank."
        ),
    }

    if int(ny.abode_months_in_year) >= 12:
        field_map["quarters_maintained_all_year"] = "/Yes"

    # Gate on abode_months_in_year (months an NY abode was maintained), not
    # days_in_ny (mere physical-presence days) — a filer who only visited
    # NY briefly with no living quarters there has days_in_ny > 0 but
    # abode_months_in_year == 0 and must NOT get an address row here.
    if int(ny.abode_months_in_year) > 0:
        field_map["address_1"] = ident.us_address_line1
        field_map["city_1"] = ident.us_city
        field_map["zip_1"] = ident.us_zip
        # Column E ("living quarters still maintained for/by you") has no
        # dedicated intake signal — the state model only tracks whether the
        # filer is still physically in the US at all, not whether this
        # specific NY address is still leased/occupied. is_still_in_us is
        # used as the best available proxy (a filer who departed the US
        # for good has, in every real intake scenario this engine models,
        # also given up their NY housing) rather than fabricating a
        # separate signal with no backing data.
        if state.residency.is_still_in_us:
            field_map["still_maintained_1"] = "/Yes"

    return field_map
