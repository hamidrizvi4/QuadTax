"""Form 8316 — Information Regarding Request for Refund of Social Security Tax
Erroneously Withheld.

Attached alongside Form 843 to substantiate that the employer was asked to
refund incorrectly withheld FICA tax and has not done so. Unlike most forms
in this package, Form 8316 (Rev. Jan-2006) is a short yes/no certification
questionnaire — it carries no name/SSN/tax-year/employment-period fields of
its own (Form 843 already carries the taxpayer's identity); its content is
almost entirely the 5 certifying questions below plus the employer's name
and address.

The yes/no answers are the only-possible answers for anyone reaching this
form through QuadTax's FICA-refund path: filing Form 843 at all presupposes
the employer has not repaid the tax (Q1), the filer has not authorized the
employer to claim it instead (Q3), and the filer has not separately claimed
it against federal income tax (Q7) — claiming any of those would make the
843 claim itself improper. Question A ("was the income directly related to
your course of studies as identified by your visa") restates the same fact
that made the filer FICA-exempt under IRC §3121(b)(19) in the first place,
so it is always "Yes" whenever this form is generated at all. Question 5
("has your employer claimed any part of the tax as a credit or refund") is
answered "Do Not Know" rather than "No" — the filer has no payroll-side
visibility to assert "No" as a certified fact.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def compute_field_map(state: "ReturnStateObject") -> dict:
    return {
        "q_a_income_per_visa": "/1",  # Yes
        "q1_employer_repaid": "/2",  # No
        "q1_employer_repaid_amount": "",
        "q3_authorized_employer_claim": "/2",  # No
        "q3_authorized_employer_claim_amount": "",
        "q5_employer_claimed": "/3",  # Do Not Know
        "q5_employer_claimed_amount": "",
        "explanation_no_employer_statement": (
            "Employer's payroll department has not issued a refund of the "
            "erroneously withheld Social Security and Medicare tax."
        ),
        "q7_claimed_against_federal_tax": "/2",  # No
        "q7_claimed_against_federal_tax_amount": "",
        "employer_name": state.income.employer_name,  # combined name+address field on the real PDF
        "signature_phone": state.identity.daytime_phone,
    }
