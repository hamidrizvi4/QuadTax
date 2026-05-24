# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""Income Code Mapper — Routes 1042-S income to proper tax treatment.

Categorizes each 1042-S entry as ECI (graduated brackets) / FDAP
(flat-rate) / EXCLUDED (not taxable) per IRS rules. Specifically:

    * §117 qualified scholarships are EXCLUDED before any treaty applies.
    * Code 36 (bank deposit interest) is EXCLUDED by statute.
    * Codes the IRS designates as personal-services compensation route to ECI.
    * Codes the IRS designates as passive income route to FDAP at the
      statutory rate (treaty-reduced rate is applied later in L4/L6).

Reference: 2024 Instructions for Form 1042-S, Box 1 (Income Code).
"""

from typing import Any, Union


class IncomeCodeMapper:
    """Maps 1042-S Box 1 income codes to ECI / FDAP / EXCLUDED routing."""

    # Effectively Connected Income — taxed at graduated rates.
    # 17 Independent personal services; 18 Dependent personal services;
    # 19 Teaching/research compensation; 20 Studying & training; 29 Wages received
    # by foreign government employee; 42 Earnings of artists/athletes.
    ECI_CODES = frozenset({17, 18, 19, 20, 29, 42})

    # FDAP — flat statutory rate (typically 30%) unless reduced by treaty.
    # Expanded for Phase 2 to cover the income types we see in the wild:
    #   1 Interest paid by US obligors (other than bank deposits)
    #   2 Interest on real-property mortgages
    #   3 Interest on real property
    #   6 Dividends paid by US corporations (general)
    #   7 Dividends qualifying for direct dividend rate
    #   8 Dividends paid by foreign corporations
    #   10 Industrial royalties
    #   11 Motion picture or TV copyright royalties
    #   12 Other royalties (e.g., copyright, recording, publishing)
    #   14 Real property income & natural resources royalties
    #   15 Pensions, annuities, alimony / insurance premiums
    #   22 Interest paid to controlling foreign corporations
    #   24 Qualified investment entity (QIE) distributions of capital gains
    #   25 Trust distributions subject to IRC §1445 withholding
    #   27 Publicly traded partnership distributions subject to §1446
    #   28 Gambling winnings
    #   30 Original issue discount (OID)
    #   31 Short-term OID
    #   32 Notional principal contract income
    #   33 Substitute payment - interest
    #   34 Substitute payment - dividends
    #   35 Substitute payment - other
    #   37 Return of capital
    #   38 Eligible deferred compensation items subject to IRC §877A
    #   39 Distributions from a nongrantor trust subject to IRC §877A
    #   40 Other dividend equivalents under IRC §871(m)
    #   41 Guarantee of indebtedness
    #   43 REMIC excess inclusions
    #   44 Specified Federal procurement payments
    #   45 Income previously reported under escrow procedures
    #   50 Other income
    #   51 Interest paid on certain actively traded or publicly offered securities
    #   52 Dividends paid on certain actively traded or publicly offered securities
    #   53 Substitute payments - dividends from certain actively traded or publicly offered securities
    #   54 Substitute payments - interest from certain actively traded or publicly offered securities
    FDAP_CODES = frozenset({
        1, 2, 3, 6, 7, 8, 10, 11, 12, 14, 15,
        22, 24, 25, 27, 28, 30, 31, 32, 33, 34, 35,
        37, 38, 39, 40, 41, 43, 44, 45, 50, 51, 52, 53, 54,
    })

    # Statutorily excluded codes — never taxable to NRAs.
    # 36 Bank deposit interest paid to NRA (IRC §871(i)(2)(A)).
    EXCLUDED_CODES = frozenset({36})

    def route_1042s_income(
        self,
        income_code: Union[int, str],
        gross_amount: float,
        requires_services: bool,
        is_qualified_expense: bool,
    ) -> dict[str, Any]:
        """Route 1042-S gross income deterministically per IRS rules.

        Args:
            income_code: 1042-S Box 1 two-digit integer code.
            gross_amount: Box 2 gross income.
            requires_services: True if the underlying grant required teaching,
                research, or other services (MCQ-derived).
            is_qualified_expense: True if the scholarship is for qualifying
                tuition / fees only (§117).

        Returns:
            Dict with ``category`` (ECI / FDAP / EXCLUDED), ``taxable_amount``,
            and optionally ``statutory_rate`` for FDAP entries.
        """
        try:
            code = int(income_code)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid income code format: {income_code}") from exc

        if code in self.EXCLUDED_CODES:
            return {"category": "EXCLUDED", "taxable_amount": 0.0}

        # Code 16 scholarship/fellowship has the most nuanced branching.
        if code == 16:
            # §117: qualified-tuition portion is statutorily excluded — always
            # subtracted BEFORE any treaty is applied.
            if is_qualified_expense:
                return {"category": "EXCLUDED", "taxable_amount": 0.0}

            # If the grant required services, it's treated as compensation → ECI.
            if requires_services:
                return {"category": "ECI", "taxable_amount": gross_amount}

            # Otherwise it's FDAP — F/J/M/Q visa holders pay 14% (Sch NEC), not 30%.
            return {
                "category": "FDAP",
                "taxable_amount": gross_amount,
                "statutory_rate": 0.14,
            }

        if code in self.ECI_CODES:
            return {"category": "ECI", "taxable_amount": gross_amount}

        if code in self.FDAP_CODES:
            return {"category": "FDAP", "taxable_amount": gross_amount}

        raise ValueError(f"Unknown or unsupported 1042-S income code: {code}")
