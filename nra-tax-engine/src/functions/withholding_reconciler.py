# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""Withholding reconciler — sums every federal/state/FICA withholding source.

A NRA return can have federal withholding on:
    * W-2 box 2 (federal income tax)
    * 1042-S box 7a (federal tax withheld, Ch 3 NRA withholding)
    * 1099-INT box 4, 1099-DIV box 4, 1099-B box 4, 1099-MISC box 4
    * Estimated tax payments (Form 1040-ES (NR))

And on:
    * W-2 box 4 (Social Security) / box 6 (Medicare) — FICA, separate refund path
    * W-2 box 17 (state income tax — NY) / box 19 (locality, NYC)

This module aggregates them deterministically. It does NOT attempt to detect
double-credit between Ch 3 and Ch 4 of the 1042-S — that requires the
``box_3_chapter_indicator`` field on the source and is a Phase-3 refinement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable

ZERO = Decimal("0")


def _d(value) -> Decimal:
    """Coerce a number to ``Decimal`` defensively."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True)
class W2Entry:
    """Subset of W-2 box values relevant to withholding reconciliation."""

    box_1_wages: float = 0.0
    box_2_fed_withholding: float = 0.0
    box_4_ss_withheld: float = 0.0
    box_6_medicare_withheld: float = 0.0
    box_17_state_income_tax: float = 0.0  # NY for our v1 scope
    box_19_local_income_tax: float = 0.0  # NYC / Yonkers
    box_18_local_wages: float = 0.0
    box_20_locality_name: str = ""


@dataclass(frozen=True)
class Form1042SEntry:
    box_1_income_code: int = 0
    box_2_gross_income: float = 0.0
    box_7a_fed_withheld: float = 0.0
    chapter_indicator: int = 3  # 3 = NRA withholding; 4 = FATCA


@dataclass(frozen=True)
class Form1099Entry:
    """Generic 1099 federal-withholding entry covering INT/DIV/B/MISC."""

    form_kind: str  # "INT" | "DIV" | "B" | "MISC"
    gross_amount: float = 0.0
    fed_withholding: float = 0.0


@dataclass
class WithholdingReport:
    """Aggregated, year-final withholding totals."""

    federal_w2: Decimal = ZERO
    federal_1042s_ch3: Decimal = ZERO
    federal_1042s_ch4: Decimal = ZERO
    federal_1099: Decimal = ZERO
    federal_estimated_payments: Decimal = ZERO
    ss_withheld_w2: Decimal = ZERO
    medicare_withheld_w2: Decimal = ZERO
    state_income_tax_w2: Decimal = ZERO  # NY in v1
    local_income_tax_w2: Decimal = ZERO  # NYC / Yonkers in v1

    sources_seen: list[str] = field(default_factory=list)

    @property
    def federal_total(self) -> Decimal:
        return (
            self.federal_w2
            + self.federal_1042s_ch3
            + self.federal_1042s_ch4
            + self.federal_1099
            + self.federal_estimated_payments
        )

    def to_dict_floats(self) -> dict:
        return {
            "federal_w2": float(self.federal_w2),
            "federal_1042s_ch3": float(self.federal_1042s_ch3),
            "federal_1042s_ch4": float(self.federal_1042s_ch4),
            "federal_1099": float(self.federal_1099),
            "federal_estimated_payments": float(self.federal_estimated_payments),
            "federal_total": float(self.federal_total),
            "ss_withheld_w2": float(self.ss_withheld_w2),
            "medicare_withheld_w2": float(self.medicare_withheld_w2),
            "state_income_tax_w2": float(self.state_income_tax_w2),
            "local_income_tax_w2": float(self.local_income_tax_w2),
            "sources_seen": list(self.sources_seen),
        }


def reconcile(
    w2s: Iterable[W2Entry] = (),
    f1042s: Iterable[Form1042SEntry] = (),
    f1099s: Iterable[Form1099Entry] = (),
    estimated_payments: Iterable[float] = (),
) -> WithholdingReport:
    """Sum every withholding source into a single :class:`WithholdingReport`."""
    report = WithholdingReport()

    for w in w2s:
        report.federal_w2 += _d(w.box_2_fed_withholding)
        report.ss_withheld_w2 += _d(w.box_4_ss_withheld)
        report.medicare_withheld_w2 += _d(w.box_6_medicare_withheld)
        report.state_income_tax_w2 += _d(w.box_17_state_income_tax)
        report.local_income_tax_w2 += _d(w.box_19_local_income_tax)
        report.sources_seen.append("W-2")

    for f in f1042s:
        if f.chapter_indicator == 4:
            report.federal_1042s_ch4 += _d(f.box_7a_fed_withheld)
        else:
            report.federal_1042s_ch3 += _d(f.box_7a_fed_withheld)
        report.sources_seen.append(f"1042-S (Ch{f.chapter_indicator})")

    for f in f1099s:
        report.federal_1099 += _d(f.fed_withholding)
        report.sources_seen.append(f"1099-{f.form_kind}")

    for amt in estimated_payments:
        report.federal_estimated_payments += _d(amt)
        report.sources_seen.append("1040-ES")

    return report
