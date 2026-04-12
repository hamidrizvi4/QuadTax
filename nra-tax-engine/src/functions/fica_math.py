# DETERMINISTIC ZONE: NO LLM CALLS ALLOWED IN THIS FILE.
"""
FICA Math — Evaluates exemption for Social Security and Medicare.

A pure logic evaluation based on IRC § 3121(b)(19) governing the FICA
exemption for Nonresident Alien F, J, M, or Q visa holders.
"""

from typing import Any, Dict


class FicaCalculator:
    """Evaluates whether an individual is exempt from FICA taxes and returns erroneous withholdings."""

    def evaluate_fica_refund(
        self,
        status: str,
        is_exempt_individual: bool,
        raw_ss_withheld: float,
        raw_medicare_withheld: float,
    ) -> Dict[str, Any]:
        """Calculates FICA exemption validity and potential Form 843 requirement.

        Args:
            status: The individual's tax status ("nonresident_alien").
            is_exempt_individual: True if they pass the L1 Exemption check (e.g. <5 yrs F-1).
            raw_ss_withheld: Total SS error from W-2s.
            raw_medicare_withheld: Total Medicare error from W-2s.

        Returns:
            Dictionary matching the required elements of FicaState.
        """
        if status == "nonresident_alien" and is_exempt_individual:
            total_fica = raw_ss_withheld + raw_medicare_withheld
            return {
                "is_exempt": True,
                "incorrect_ss_withheld": raw_ss_withheld,
                "incorrect_medicare_withheld": raw_medicare_withheld,
                "requires_form_843": (total_fica > 0),
            }

        # If resident alien or not an exempt individual, they generally pay FICA
        return {
            "is_exempt": False,
            "incorrect_ss_withheld": 0.0,
            "incorrect_medicare_withheld": 0.0,
            "requires_form_843": False,
        }
