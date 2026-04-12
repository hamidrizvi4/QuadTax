"""Tests for the Treaty Evaluator."""

import pytest
from src.functions.treaty_evaluator import TreatyEvaluator


class TestTreatyEvaluator:
    """Test suite for the deterministic treaty applicator."""

    def setup_method(self):
        # We can use the actual JSON data deployed in our system
        # since it aligns precisely with our China/India specification.
        self.evaluator = TreatyEvaluator()

    def test_apply_treaty_chinese_scholarship_eligible(self):
        """Case 1: Chinese student on scholarship, present for 2 years."""
        result = self.evaluator.apply_treaty(
            country="China",
            income_type="scholarship",
            gross_income=25000.0,
            years_present=2
        )
        
        assert result["is_eligible"] is True
        assert result["article_number"] == "20(b)"
        # "unlimited" means entire gross amount should be exempt
        assert result["exempt_amount_applied"] == 25000.0
        assert result["rate"] == 0.0

    def test_apply_treaty_chinese_research_expired(self):
        """Case 2: Chinese researcher present 4 years exceeds the 3-year limit."""
        result = self.evaluator.apply_treaty(
            country="China",
            income_type="teaching_research",
            gross_income=60000.0,
            years_present=4 # max_years is 3
        )
        
        assert result["is_eligible"] is False
        assert result["article_number"] is None
        assert result["exempt_amount_applied"] == 0.0

    def test_apply_treaty_brazil_ineligible(self):
        """Case 3: Country missing from database."""
        result = self.evaluator.apply_treaty(
            country="Brazil",
            income_type="scholarship",
            gross_income=25000.0,
            years_present=1
        )
        
        assert result["is_eligible"] is False
        assert result["article_number"] is None
        assert result["exempt_amount_applied"] == 0.0

    def test_apply_treaty_partial_amount(self):
        """Case Edge: Specific explicit amount cap (simulated)."""
        # Inject custom DB just for this test
        self.evaluator.treaty_db = {
            "Testing": {
                "wages": {
                    "article": "100",
                    "exempt_amount": 5000,
                    "max_years": None,
                    "rate": 0.0
                }
            }
        }
        
        # Test earning $10K when cap is $5K
        result1 = self.evaluator.apply_treaty("Testing", "wages", 10000.0, 1)
        assert result1["is_eligible"] is True
        assert result1["exempt_amount_applied"] == 5000.0

        # Test earning $3K when cap is $5K
        result2 = self.evaluator.apply_treaty("Testing", "wages", 3000.0, 1)
        assert result2["is_eligible"] is True
        assert result2["exempt_amount_applied"] == 3000.0
