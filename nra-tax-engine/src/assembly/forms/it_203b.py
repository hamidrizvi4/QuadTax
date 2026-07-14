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
    1o  Wages to be allocated = total_w2_wages.
    1p  NY-allocated wages, taken directly from ``ny.ny_source_wages``
        (independently computed by ``ny_source_allocator``) rather than
        recomputed as 1n × 1o here, to avoid rounding drift against the
        number that actually drives the tax calculation.

Schedule B: living quarters maintained in NY. Schedule C (college tuition
itemized deduction) has no backing intake data and is left entirely
blank.
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
    # Matches ny_source_allocator.allocate()'s exact formula so 1n truly
    # reflects the ratio that produced ny.ny_source_wages (see docstring).
    wage_pct = (
        max(0.0, min(1.0, ny.ny_work_days / ny.total_work_days))
        if ny.total_work_days > 0
        else 1.0
    )

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

    if int(ny.days_in_ny) > 0:
        field_map["address_1"] = ident.us_address_line1
        field_map["city_1"] = ident.us_city
        field_map["zip_1"] = ident.us_zip
        if state.residency.is_still_in_us:
            field_map["still_maintained_1"] = "/Yes"

    return field_map
