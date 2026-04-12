"""
Treaty Evaluator — Deterministic calculation of tax treaty exemptions.

This module evaluates tax treaty provisions for Nonresident Aliens using
the hardcoded parameters defined in the treaties database. It is entirely
deterministic and free of LLM calls.
"""

import json
from pathlib import Path
from typing import Any, Union


class TreatyEvaluator:
    """Evaluates treaty eligibility and applies exemption amounts."""

    def __init__(self, db_path: Union[str, Path, type(None)] = None):
        """Initialize the Treaty Evaluator and load the local database.

        Args:
            db_path: Path to the treaties.json file. Defaults to the internal DB.
        """
        if db_path is None:
            # Default to the known location in the project
            db_path = Path(__file__).parent.parent / "database" / "treaties.json"
        
        with open(db_path, "r", encoding="utf-8") as f:
            self.treaty_db: dict[str, dict[str, Any]] = json.load(f)

    def apply_treaty(
        self, country: str, income_type: str, gross_income: float, years_present: int
    ) -> dict[str, Any]:
        """Evaluate treaty applicability and calculate the exempt amount.

        Args:
            country: The student's country of tax residency (e.g., "China", "India").
            income_type: Category of income (e.g., "scholarship", "teaching_research").
            gross_income: The total gross amount of that income.
            years_present: Number of calendar years the student has been in the US.

        Returns:
            Dictionary matching the TreatyState fields detailing eligibility,
            article number, applied exemption amount, and the applicable rate.
        """
        ineligible_result = {
            "is_eligible": False,
            "article_number": None,
            "exempt_amount_applied": 0.0,
            "rate": None,
        }

        # Step 1: Check existence
        if country not in self.treaty_db:
            return ineligible_result

        country_data = self.treaty_db[country]
        if income_type not in country_data:
            return ineligible_result

        treaty_article = country_data[income_type]

        # In case it's a structural deviation like the standard_deduction in India
        if "max_years" not in treaty_article:
            return ineligible_result

        # Step 2: Check Time Limits
        max_years = treaty_article["max_years"]
        if max_years is not None and years_present > max_years:
            return ineligible_result

        # Step 3: Calculate Exemption
        exempt_rule = treaty_article.get("exempt_amount", 0)
        
        if exempt_rule == "unlimited":
            # The entire gross amount is exempted
            exempt_amount_applied = gross_income
        else:
            # It's a specific numerical cap (e.g., 5000)
            try:
                cap = float(exempt_rule)
                exempt_amount_applied = min(gross_income, cap)
            except (ValueError, TypeError):
                exempt_amount_applied = 0.0

        # Step 4: Return Success
        return {
            "is_eligible": True,
            "article_number": treaty_article["article"],
            "exempt_amount_applied": exempt_amount_applied,
            "rate": treaty_article.get("rate"),
        }
