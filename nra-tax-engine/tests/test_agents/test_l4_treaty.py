"""Tests for the L4 Treaty Agent (Phase 1: multi-article evaluator)."""

from unittest.mock import MagicMock

from src.agents.l4_treaty import TreatyAgent, TreatyCategoryMapping
from src.orchestrator.state import ReturnStateObject


def _mock_classifier(category: str) -> MagicMock:
    """Build a mock OpenAI client that returns the given mapped_category."""
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.parsed = TreatyCategoryMapping(
        mapped_category=category  # type: ignore[arg-type]
    )
    mock_client.beta.chat.completions.parse.return_value = mock_completion
    return mock_client


class TestL4TreatyAgent:
    def test_china_teaching_research_within_window(self):
        """Chinese J-1 researcher in year 2 with $30k ECI — Art 19 fully exempts."""
        client = _mock_classifier("teaching_research")
        agent = TreatyAgent(llm_client=client)

        state = ReturnStateObject()
        state.residency.status = "nonresident_alien"
        state.residency.exempt_visa_type = "J-1"
        state.residency.years_in_exempt_status = 2
        state.income.eci_taxable_total = 30000.0

        updated = agent.process_treaties(
            tax_residence_country="China",
            income_description="Visiting researcher at MIT",
            current_state=state,
        )

        assert updated.treaty.is_eligible is True
        assert updated.treaty.country == "CN"
        assert updated.treaty.article_number == "19"
        assert updated.treaty.exempt_amount_applied == 30000.0
        assert "L4" in updated.completed_layers
        assert "8833" in updated.forms_required

    def test_china_student_wages_5k_cap(self):
        """Chinese F-1 in year 2 with $30k US wages — Art 20(c) caps at $5k."""
        client = _mock_classifier("student_personal_services")
        agent = TreatyAgent(llm_client=client)

        state = ReturnStateObject()
        state.residency.status = "nonresident_alien"
        state.residency.exempt_visa_type = "F-1"
        state.residency.years_in_exempt_status = 2
        state.income.eci_taxable_total = 30000.0

        updated = agent.process_treaties(
            tax_residence_country="CN",
            income_description="On-campus dining hall worker",
            current_state=state,
        )

        assert updated.treaty.is_eligible is True
        assert updated.treaty.article_number == "20(c)"
        assert updated.treaty.exempt_amount_applied == 5000.0
        assert updated.treaty.requires_form_8833 is True

    def test_unknown_country_skips(self):
        """An unrecognized country falls through to skip."""
        client = _mock_classifier("student_personal_services")
        agent = TreatyAgent(llm_client=client)
        state = ReturnStateObject()
        state.residency.status = "nonresident_alien"
        state.residency.exempt_visa_type = "F-1"
        state.residency.years_in_exempt_status = 1
        state.income.eci_taxable_total = 20000.0

        updated = agent.process_treaties(
            tax_residence_country="Vulcan",  # nonexistent
            income_description="Tutor",
            current_state=state,
        )

        # Classifier should not even be invoked — but if it is, no benefits applied.
        assert updated.treaty.is_eligible is False
        # Either L4 or L4_Skipped is acceptable for this branch.
        assert (
            "L4_Skipped" in updated.completed_layers
            or "L4" in updated.completed_layers
        )

    def test_resident_alien_without_saving_clause_skips(self):
        """Resident alien whose country has NO saving-clause exception → skip."""
        client = _mock_classifier("student_personal_services")
        agent = TreatyAgent(llm_client=client)

        state = ReturnStateObject()
        state.residency.status = "resident_alien"
        state.residency.exempt_visa_type = "F-1"
        # Pick a country whose articles do NOT have saving_clause_exception.
        # Korea Article 21(1) has saving_clause_exception=True per our seeding, so use Germany
        # (DE 20(4) defaults to saving_clause_exception=False).
        updated = agent.process_treaties(
            tax_residence_country="DE",
            income_description="Campus job",
            current_state=state,
        )
        assert "L4_Skipped" in updated.completed_layers
        client.beta.chat.completions.parse.assert_not_called()

    def test_china_resident_alien_saving_clause_keeps_benefit(self):
        """Chinese student in year 6 (resident alien) keeps Art 20(c) via saving clause."""
        client = _mock_classifier("student_personal_services")
        agent = TreatyAgent(llm_client=client)

        state = ReturnStateObject()
        state.residency.status = "resident_alien"
        state.residency.exempt_visa_type = "F-1"
        state.residency.years_in_exempt_status = 6
        state.income.eci_taxable_total = 30000.0

        updated = agent.process_treaties(
            tax_residence_country="CN",
            income_description="On-campus worker",
            current_state=state,
        )
        assert updated.treaty.is_eligible is True
        assert updated.treaty.article_number == "20(c)"
        # Saving-clause exception flag should be true on at least one benefit.
        assert any(
            b.get("applies_after_saving_clause") for b in updated.treaty.applied_benefits
        )
