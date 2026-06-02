"""
NarrativeGenerator — pure template-driven plain-English explanations.

Converts a fully-computed ReturnStateObject into a set of human-readable
sections suitable for a taxpayer summary or CPA cover letter.

Design rules:
    - Zero LLM calls — all text is generated deterministically from state values.
    - No Python field names in output text.
    - Dollar amounts formatted as $X,XXX.XX.
    - Bold markers: **amount** for key figures.
    - Only sections with meaningful data are included.
"""

from __future__ import annotations

from typing import Dict

from src.orchestrator.state import ReturnStateObject

# ---------------------------------------------------------------------------
# ISO2 -> Full Country Name
# ---------------------------------------------------------------------------

COUNTRY_NAMES: Dict[str, str] = {
    "AF": "Afghanistan",
    "AL": "Albania",
    "AR": "Argentina",
    "AU": "Australia",
    "AT": "Austria",
    "BE": "Belgium",
    "BR": "Brazil",
    "CA": "Canada",
    "CL": "Chile",
    "CN": "China",
    "CO": "Colombia",
    "CY": "Cyprus",
    "CZ": "Czech Republic",
    "DK": "Denmark",
    "EG": "Egypt",
    "ET": "Ethiopia",
    "FI": "Finland",
    "FR": "France",
    "DE": "Germany",
    "GH": "Ghana",
    "GR": "Greece",
    "HK": "Hong Kong",
    "HU": "Hungary",
    "IN": "India",
    "ID": "Indonesia",
    "IR": "Iran",
    "IQ": "Iraq",
    "IE": "Ireland",
    "IL": "Israel",
    "IT": "Italy",
    "JP": "Japan",
    "JO": "Jordan",
    "KZ": "Kazakhstan",
    "KE": "Kenya",
    "KR": "South Korea",
    "KW": "Kuwait",
    "LB": "Lebanon",
    "MY": "Malaysia",
    "MX": "Mexico",
    "MA": "Morocco",
    "NL": "Netherlands",
    "NZ": "New Zealand",
    "NG": "Nigeria",
    "NO": "Norway",
    "PK": "Pakistan",
    "PE": "Peru",
    "PH": "Philippines",
    "PL": "Poland",
    "PT": "Portugal",
    "QA": "Qatar",
    "RO": "Romania",
    "RU": "Russia",
    "SA": "Saudi Arabia",
    "SG": "Singapore",
    "ZA": "South Africa",
    "ES": "Spain",
    "LK": "Sri Lanka",
    "SE": "Sweden",
    "CH": "Switzerland",
    "TW": "Taiwan",
    "TH": "Thailand",
    "TN": "Tunisia",
    "TR": "Turkey",
    "UA": "Ukraine",
    "AE": "United Arab Emirates",
    "GB": "United Kingdom",
    "US": "United States",
    "UY": "Uruguay",
    "VE": "Venezuela",
    "VN": "Vietnam",
}


def _country_name(iso2: str | None) -> str:
    """Return full country name for an ISO2 code, or the code itself if unknown."""
    if not iso2:
        return "Unknown"
    return COUNTRY_NAMES.get(iso2.upper(), iso2.upper())


def _fmt(amount: float) -> str:
    """Format a dollar amount as $X,XXX.XX."""
    return f"${amount:,.2f}"


# ---------------------------------------------------------------------------
# NarrativeGenerator
# ---------------------------------------------------------------------------


class NarrativeGenerator:
    """Generate plain-English tax return narrative sections from state."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_sections(self, state: ReturnStateObject) -> dict[str, str]:
        """Return an ordered dict of section_title -> plain_english_text.

        Only sections with meaningful data are included.
        """
        sections: dict[str, str] = {}

        residency_text = self._residency_section(state)
        if residency_text:
            sections["Residency Status"] = residency_text

        income_text = self._income_section(state)
        if income_text:
            sections["Income"] = income_text

        treaty_text = self._treaty_section(state)
        if treaty_text:
            sections["Tax Treaty"] = treaty_text

        federal_text = self._federal_tax_section(state)
        if federal_text:
            sections["Federal Tax Calculation"] = federal_text

        fica_text = self._fica_section(state)
        if fica_text:
            sections["FICA Refund (Form 843)"] = fica_text

        ny_text = self._ny_section(state)
        if ny_text:
            sections["New York State"] = ny_text

        return sections

    def generate(self, state: ReturnStateObject) -> str:
        """Return all sections joined into one string."""
        sections = self.generate_sections(state)
        parts: list[str] = []
        for title, body in sections.items():
            parts.append(f"=== {title} ===\n{body}")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _residency_section(self, state: ReturnStateObject) -> str:
        r = state.residency
        if r.status == "pending":
            return ""

        status_map = {
            "nonresident_alien": "Nonresident Alien (NRA)",
            "resident_alien": "Resident Alien",
            "dual_status": "Dual-Status (part-year resident / part-year nonresident)",
        }
        status_label = status_map.get(r.status, r.status.replace("_", " ").title())

        lines: list[str] = []
        lines.append(
            f"Under IRC §7701(b), this taxpayer is classified as a "
            f"**{status_label}** for the {state.tax_year} tax year."
        )

        if r.status == "nonresident_alien":
            lines.append(
                "As a nonresident alien, only U.S.-source income is subject to U.S. "
                "federal income tax. Form 1040-NR is the required federal return."
            )
        elif r.status == "resident_alien":
            lines.append(
                "As a resident alien, worldwide income is subject to U.S. federal "
                "income tax under IRC §1, and Form 1040 is the required federal return."
            )
        elif r.status == "dual_status":
            lines.append(
                "A dual-status filer is treated as a nonresident alien for the portion "
                "of the year before establishing residency and as a resident alien "
                "for the remainder. Special rules apply to income reporting for each period."
            )

        if r.exempt_visa_type:
            lines.append(
                f"\nVisa Type: This individual holds a **{r.exempt_visa_type}** visa. "
                f"Holders of {r.exempt_visa_type} visas who qualify as 'exempt individuals' "
                "under IRC §7701(b)(5) do not count their U.S. days of presence toward "
                "the Substantial Presence Test (SPT) during their exempt period."
            )
            if r.years_in_exempt_status > 0:
                lines.append(
                    f"This individual has spent **{r.years_in_exempt_status}** calendar "
                    f"year(s) in exempt status. "
                    + (
                        "The exempt window is still open, so days of presence are excluded "
                        "from the SPT count."
                        if r.is_exempt_individual
                        else "The exempt window has been exhausted; days of presence now "
                        "count toward the SPT."
                    )
                )
        elif r.spt_days_current_year > 0:
            lines.append(
                f"\nU.S. days present in {state.tax_year}: **{r.spt_days_current_year}**. "
                "The Substantial Presence Test requires 183 or more weighted days across "
                "three years (current year × 1 + prior year × 1/3 + year before × 1/6) "
                "to be classified as a resident alien."
            )

        return "\n".join(lines)

    def _income_section(self, state: ReturnStateObject) -> str:
        inc = state.income
        has_income = (
            inc.total_w2_wages > 0
            or inc.total_1042s_gross > 0
            or inc.exempt_scholarship_total > 0
        )
        if not has_income:
            return ""

        lines: list[str] = ["Income reported on this return:"]

        if inc.total_w2_wages > 0:
            lines.append(
                f"  - W-2 Wages (wages, salaries, tips): **{_fmt(inc.total_w2_wages)}**. "
                "This income is Effectively Connected Income (ECI) taxed at graduated rates."
            )

        if inc.total_1042s_gross > 0:
            lines.append(
                f"  - Form 1042-S gross income (scholarships, fellowships, royalties, "
                f"and other U.S.-source amounts): **{_fmt(inc.total_1042s_gross)}**."
            )

        if inc.exempt_scholarship_total > 0:
            lines.append(
                f"  - IRC §117 Exclusion (scholarship/fellowship amounts used for "
                f"qualified tuition and required fees): **{_fmt(inc.exempt_scholarship_total)}**. "
                "This amount is excluded from gross income and is not taxable."
            )

        if inc.total_w2_withholding > 0:
            lines.append(
                f"  - Federal income tax withheld on W-2: **{_fmt(inc.total_w2_withholding)}**."
            )

        if inc.total_1042s_withholding > 0:
            lines.append(
                f"  - Federal income tax withheld on Form 1042-S: **{_fmt(inc.total_1042s_withholding)}**."
            )

        return "\n".join(lines)

    def _treaty_section(self, state: ReturnStateObject) -> str:
        t = state.treaty
        country_name = _country_name(t.country)

        if not t.is_eligible:
            # Explain why no treaty applies
            if not t.country:
                return (
                    "No income tax treaty benefit applies to this return. "
                    "No country of tax residence was identified that has an income "
                    "tax treaty with the United States, or the taxpayer does not "
                    "satisfy the treaty's residency and Limitation on Benefits requirements."
                )
            return (
                f"No income tax treaty benefit applies to this return. "
                f"Although {country_name} has an income tax treaty with the United States, "
                "the taxpayer does not qualify for treaty benefits on the income types "
                "reported, or the applicable treaty articles do not reduce tax liability "
                "on this return."
            )

        lines: list[str] = []
        lines.append(
            f"This taxpayer qualifies for income tax treaty benefits under the "
            f"U.S.–{country_name} income tax treaty."
        )

        if t.applied_benefits:
            # Multi-article detail
            for benefit in t.applied_benefits:
                article = benefit.get("article_id") or t.article_number or "N/A"
                amount = benefit.get("exempt_amount", 0.0)
                explanation = benefit.get("explanation", "")
                b_country = _country_name(benefit.get("country_iso2") or t.country)
                lines.append(
                    f"  - Article {article} of the U.S.–{b_country} treaty: "
                    f"**{_fmt(amount)}** exempted."
                    + (f" {explanation}" if explanation else "")
                )
        elif t.article_number and t.exempt_amount_applied > 0:
            lines.append(
                f"  - Article {t.article_number} of the U.S.–{country_name} treaty: "
                f"**{_fmt(t.exempt_amount_applied)}** exempted."
            )

        if t.exempt_amount_applied > 0 and not t.applied_benefits:
            lines.append(
                f"Total treaty exemption applied: **{_fmt(t.exempt_amount_applied)}**. "
                "This amount is excluded from taxable income."
            )
        elif t.applied_benefits:
            total = sum(b.get("exempt_amount", 0.0) for b in t.applied_benefits)
            if total > 0:
                lines.append(
                    f"Total treaty exemption applied across all articles: **{_fmt(total)}**."
                )

        if t.requires_form_8833:
            lines.append(
                "\nForm 8833 (Treaty-Based Return Position Disclosure) is required "
                "to be attached to this return under IRC §6114. This form discloses "
                "the treaty position taken and the amount of income affected."
            )

        return "\n".join(lines)

    def _federal_tax_section(self, state: ReturnStateObject) -> str:
        tx = state.tax
        # Only include if at least AGI or tax liability has been computed
        if tx.agi == 0.0 and tx.total_tax_liability == 0.0 and tx.total_withholding_credits == 0.0:
            return ""

        lines: list[str] = ["Federal tax calculation for Form 1040-NR:"]

        lines.append(f"  1. Adjusted Gross Income (AGI): **{_fmt(tx.agi)}**")

        if tx.deduction_amount > 0:
            if tx.deduction_type == "standard":
                india_note = ""
                if state.treaty.country == "IN" and state.treaty.is_eligible:
                    india_note = (
                        " (granted under India Treaty Article 21(2), which allows "
                        "Indian nationals to claim the U.S. standard deduction "
                        "even as nonresident aliens)"
                    )
                lines.append(
                    f"  2. Standard Deduction: **{_fmt(tx.deduction_amount)}**{india_note}"
                )
            elif tx.deduction_type == "itemized":
                lines.append(
                    f"  2. Itemized Deductions (Schedule A): **{_fmt(tx.deduction_amount)}**"
                )
            else:
                lines.append(
                    f"  2. Deduction: **{_fmt(tx.deduction_amount)}**"
                )
        else:
            lines.append(
                "  2. Deduction: **$0.00** "
                "(nonresident aliens are generally not entitled to a standard deduction "
                "unless a specific treaty provision applies)"
            )

        lines.append(f"  3. Taxable Income: **{_fmt(tx.taxable_income)}**")

        if tx.eci_tax_liability > 0 and tx.fdap_tax_liability > 0:
            lines.append(
                f"  4. Tax on Effectively Connected Income (graduated brackets): "
                f"**{_fmt(tx.eci_tax_liability)}**"
            )
            lines.append(
                f"     Tax on FDAP Income (flat 30% or reduced treaty rate): "
                f"**{_fmt(tx.fdap_tax_liability)}**"
            )
            lines.append(
                f"     Total Tax Liability: **{_fmt(tx.total_tax_liability)}**"
            )
        elif tx.eci_tax_liability > 0:
            lines.append(
                f"  4. Income Tax (graduated brackets on Effectively Connected Income): "
                f"**{_fmt(tx.eci_tax_liability)}**"
            )
            lines.append(f"     Total Tax Liability: **{_fmt(tx.total_tax_liability)}**")
        elif tx.fdap_tax_liability > 0:
            lines.append(
                f"  4. Income Tax (flat rate on FDAP income): "
                f"**{_fmt(tx.fdap_tax_liability)}**"
            )
            lines.append(f"     Total Tax Liability: **{_fmt(tx.total_tax_liability)}**")
        else:
            lines.append(f"  4. Total Tax Liability: **{_fmt(tx.total_tax_liability)}**")

        lines.append(
            f"  5. Total Federal Tax Withheld and Credits: "
            f"**{_fmt(tx.total_withholding_credits)}**"
        )

        if tx.refund_or_owed < 0:
            lines.append(
                f"  6. Federal Refund Due: **{_fmt(abs(tx.refund_or_owed))}** "
                "(the IRS owes this amount to the taxpayer)"
            )
        elif tx.refund_or_owed > 0:
            lines.append(
                f"  6. Balance Due to IRS: **{_fmt(tx.refund_or_owed)}** "
                "(the taxpayer owes this amount to the IRS)"
            )
        else:
            lines.append("  6. No federal refund or balance due — tax is fully satisfied by withholding.")

        return "\n".join(lines)

    def _fica_section(self, state: ReturnStateObject) -> str:
        f = state.fica
        if not f.is_exempt:
            return ""
        if f.incorrect_ss_withheld <= 0 and f.incorrect_medicare_withheld <= 0:
            return ""

        total = f.incorrect_ss_withheld + f.incorrect_medicare_withheld
        lines: list[str] = []
        lines.append(
            "This taxpayer is exempt from Social Security and Medicare (FICA) taxes "
            "under IRC §3121(b)(19). Nonresident aliens on F-1, J-1, M-1, or Q-1 "
            "visas who are performing services to carry out the purpose of their visa "
            "admission are not subject to FICA withholding."
        )
        lines.append(
            "\nHowever, FICA taxes were incorrectly withheld by the employer:"
        )

        if f.incorrect_ss_withheld > 0:
            lines.append(
                f"  - Social Security (OASDI) tax erroneously withheld: "
                f"**{_fmt(f.incorrect_ss_withheld)}**"
            )
        if f.incorrect_medicare_withheld > 0:
            lines.append(
                f"  - Medicare (HI) tax erroneously withheld: "
                f"**{_fmt(f.incorrect_medicare_withheld)}**"
            )

        lines.append(
            f"\nTotal FICA refund claimed on Form 843: **{_fmt(total)}**"
        )
        lines.append(
            "\nIMPORTANT: Form 843 (Claim for Refund and Request for Abatement) must be "
            "mailed separately to the IRS — it is NOT attached to Form 1040-NR. "
            "The taxpayer should first request a refund directly from the employer. "
            "If the employer declines or cannot issue the refund, Form 843 is filed "
            "with the IRS service center where the employer filed its payroll tax returns."
        )

        return "\n".join(lines)

    def _ny_section(self, state: ReturnStateObject) -> str:
        ny = state.ny
        if ny.residency_status == "pending":
            return ""

        status_map = {
            "resident": "New York State Resident",
            "part_year": "New York State Part-Year Resident",
            "nonresident": "New York State Nonresident",
        }
        status_label = status_map.get(ny.residency_status, ny.residency_status.replace("_", " ").title())

        lines: list[str] = []
        lines.append(
            f"This taxpayer is classified as a **{status_label}** for New York State "
            "income tax purposes and must file Form IT-203 (Nonresident and Part-Year "
            "Resident Income Tax Return)."
        )

        if ny.residency_reason:
            lines.append(f"\nResidency determination: {ny.residency_reason}")

        if ny.ny_treaty_addback > 0:
            lines.append(
                f"\nNote: New York State does not honor federal income tax treaty "
                "exemptions. The federal treaty exemption of "
                f"**{_fmt(ny.ny_treaty_addback)}** has been added back to New York "
                "taxable income (NY Tax Law §601(e)(1))."
            )

        if ny.ny_taxable_income > 0:
            lines.append(
                f"\nNew York taxable income (after NY adjustments and apportionment): "
                f"**{_fmt(ny.ny_taxable_income)}**"
            )

        if ny.ny_refund_or_owed < 0:
            lines.append(
                f"\nNew York State Refund Due: **{_fmt(abs(ny.ny_refund_or_owed))}**"
            )
        elif ny.ny_refund_or_owed > 0:
            lines.append(
                f"\nNew York State Balance Due: **{_fmt(ny.ny_refund_or_owed)}**"
            )
        else:
            lines.append(
                "\nNew York State: no refund or balance due."
            )

        if ny.nyc_resident:
            if ny.nyc_tax > 0:
                lines.append(
                    f"New York City resident tax: **{_fmt(ny.nyc_tax)}**"
                )
        if ny.yonkers_resident:
            if ny.yonkers_tax > 0:
                lines.append(
                    f"Yonkers resident income tax surcharge: **{_fmt(ny.yonkers_tax)}**"
                )

        return "\n".join(lines)
