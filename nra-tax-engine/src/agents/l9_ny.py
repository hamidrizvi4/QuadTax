"""L9 NY Agent — Drives the New York state pipeline.

Deterministic orchestrator that reads NY-specific MCQ answers from intake,
classifies NY residency, allocates NY-source income, computes NY/NYC/Yonkers
tax liability, and writes the results to :class:`NYTaxState`.

No LLM calls in this layer — every decision is deterministic and cited.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from src.functions import ny_residency, ny_source_allocator
from src.functions.ny_tax_math import NYTaxCalculator

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


class NYAgent:
    """Drives the NY pipeline using the deterministic ny_* modules."""

    def process_ny(
        self,
        current_state: "ReturnStateObject",
        ny_intake: Dict[str, Any] | None = None,
    ) -> "ReturnStateObject":
        """Compute NY residency, allocation, and tax. Mutates ``current_state.ny``.

        Args:
            current_state: Federal pipeline output (L1-L8 complete).
            ny_intake: NY-specific MCQ dict with keys:
                ``days_in_ny`` (int), ``has_permanent_abode_in_ny`` (bool),
                ``abode_months_in_year`` (int), ``is_student_dorm`` (bool),
                ``domiciled_in_ny`` (bool), ``moved_into_ny_mid_year`` (bool),
                ``moved_out_of_ny_mid_year`` (bool), ``nyc_address`` (bool),
                ``yonkers_address`` (bool), ``ny_work_days`` (int),
                ``total_work_days`` (int), ``employer_in_ny`` (bool),
                ``institution_1042s_in_ny`` (bool).
                Missing keys default to safe values for a typical F-1 student
                at a NY-located university living in dorm housing.
        """
        intake = ny_intake or {}

        # --- Step 1: NY residency classification --------------------------
        residency = ny_residency.evaluate(
            days_in_ny=intake.get("days_in_ny", 0),
            has_permanent_abode_in_ny=intake.get("has_permanent_abode_in_ny", False),
            abode_months_in_year=intake.get("abode_months_in_year", 0),
            is_student_dorm=intake.get("is_student_dorm", True),
            domiciled_in_ny=intake.get("domiciled_in_ny", False),
            moved_into_ny_mid_year=intake.get("moved_into_ny_mid_year", False),
            moved_out_of_ny_mid_year=intake.get("moved_out_of_ny_mid_year", False),
            nyc_address=intake.get("nyc_address", False),
            yonkers_address=intake.get("yonkers_address", False),
        )

        # --- Step 2: NY-source allocation (for nonresidents) --------------
        allocation = ny_source_allocator.allocate(
            total_w2_wages=current_state.income.total_w2_wages,
            ny_work_days=intake.get("ny_work_days", 0),
            total_work_days=intake.get("total_work_days", 0),
            employer_in_ny=intake.get("employer_in_ny", True),
            total_1042s_gross=current_state.income.total_1042s_gross,
            institution_1042s_in_ny=intake.get("institution_1042s_in_ny", True),
        )

        # --- Step 3: NY tax math ------------------------------------------
        # The treaty exemption that NY adds back excludes the India Article 21(2)
        # standard-deduction equivalent (which is not a treaty wage exemption).
        treaty_addback = sum(
            float(b.get("exempt_amount", 0.0))
            for b in current_state.treaty.applied_benefits
            if not (b.get("country_iso2") == "IN" and b.get("article_id") == "21(2)")
        )
        # Federal AGI on 1040-NR is POST-treaty (line 1k subtracted): gross wages
        # minus the wage-category treaty exemption. NY then adds the same amount
        # back via the federal-modifications line.
        federal_agi = max(
            0.0,
            float(current_state.income.total_w2_wages)
            + float(current_state.income.fdap_taxable_total)
            - treaty_addback,
        )

        ny_source_income = allocation.ny_source_wages + allocation.ny_source_1042s_gross

        ny_calc = NYTaxCalculator(tax_year=current_state.tax_year)
        ny_result = ny_calc.compute(
            federal_agi=federal_agi,
            federal_treaty_exemption=treaty_addback,
            ny_source_income=ny_source_income,
            ny_residency_status=residency.status,
            filing_status=current_state.identity.filing_status,
            nyc_resident=residency.nyc_resident,
            yonkers_resident=residency.yonkers_resident,
        )

        # --- Step 4: State mutation ---------------------------------------
        ny_state = current_state.ny
        ny_state.residency_status = residency.status  # type: ignore[assignment]
        ny_state.residency_reason = residency.reason
        ny_state.days_in_ny = residency.days_in_ny
        ny_state.nyc_resident = residency.nyc_resident
        ny_state.yonkers_resident = residency.yonkers_resident
        # Raw intake counts already drive the allocation math above but were
        # never written back to state, so IT-203-B (which needs to *display*
        # these same figures) had nothing to read.
        ny_state.ny_work_days = intake.get("ny_work_days", 0)
        ny_state.total_work_days = intake.get("total_work_days", 0)
        ny_state.abode_months_in_year = intake.get("abode_months_in_year", 0)
        # Same class of bug as above: employer_in_ny drives the allocate()
        # apportionment branch above but was never written back, so
        # IT-203-B line 1n had no way to reproduce allocate()'s exact
        # formula for a non-NY employer (it would silently fall back to
        # the day-ratio branch even when allocate() zeroed out NY-source
        # wages because the employer isn't NY-based).
        ny_state.employer_in_ny = intake.get("employer_in_ny", True)

        ny_state.ny_source_wages = allocation.ny_source_wages
        ny_state.ny_source_1042s_gross = allocation.ny_source_1042s_gross
        ny_state.ny_source_income = ny_source_income
        ny_state.ny_income_percentage = float(ny_result.ny_income_percentage)

        ny_state.ny_agi = float(ny_result.ny_agi)
        ny_state.ny_treaty_addback = float(ny_result.ny_treaty_addback)
        ny_state.ny_standard_deduction = float(ny_result.ny_standard_deduction)
        ny_state.ny_taxable_income = float(ny_result.ny_taxable_income)
        ny_state.ny_tax_resident_basis = float(ny_result.ny_tax_resident_basis)
        ny_state.ny_tax_apportioned = float(ny_result.ny_tax_apportioned)
        ny_state.nyc_tax = float(ny_result.nyc_tax)
        ny_state.yonkers_tax = float(ny_result.yonkers_tax)
        ny_state.total_ny_state_local = float(ny_result.total_ny_state_local)

        ny_state.ny_withholding = float(
            (current_state.withholding_report or {}).get("state_income_tax_w2", 0.0)
        )
        ny_state.nyc_withholding = float(
            (current_state.withholding_report or {}).get("local_income_tax_w2", 0.0)
        )
        ny_state.ny_refund_or_owed = (
            ny_state.total_ny_state_local
            - ny_state.ny_withholding
            - ny_state.nyc_withholding
        )

        # --- Step 5: Forms required --------------------------------------
        if residency.status == "nonresident":
            for form in ("IT-203", "IT-203-B"):
                if form not in current_state.forms_required:
                    current_state.forms_required.append(form)
        elif residency.status == "part_year":
            for form in ("IT-203", "IT-203-B"):
                if form not in current_state.forms_required:
                    current_state.forms_required.append(form)
        else:  # resident
            if "IT-201" not in current_state.forms_required:
                current_state.forms_required.append("IT-201")

        current_state.mark_layer_complete("L9")
        return current_state
