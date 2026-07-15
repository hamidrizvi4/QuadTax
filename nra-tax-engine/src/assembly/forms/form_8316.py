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
    # NOTE on the real f8316.pdf AcroForm (confirmed by dumping the widget
    # annotations' /AP/N export states, not the aggregated /_States_):
    #   - Field "A" (line A, Yes/No) has real export states /1=Yes, /2=No.
    #   - Fields "1", "3", "7" (lines 1/3/7, Yes/No) each have /1=Yes, /2=No.
    #   - Field "5" (line 5, Yes/No/Do not Know) has /1=Yes, /2=No, /3=Do
    #     not Know.
    # These are multi-state radio groups, not booleans, so the literal
    # export-state string is emitted directly here rather than a bare
    # Python bool -- FormPopulator._format_for_acro only synthesizes an
    # "on" state from a bool by falling back to the first non-/Off state
    # in /_States_, which is wrong for any field (like "5") whose real
    # "Yes" isn't literally the first listed state.
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
        # Line 9 ("Name and address of employer") is a single combined
        # name+address field (FillText7) on the real PDF, but
        # ReturnStateObject only carries IncomeState.employer_name -- there
        # is no employer_address/street/city/state/zip field anywhere in
        # state.py, so only the name is available to populate here. This is
        # a genuine intake-data gap (not a bug in this mapping): fabricating
        # an address would be worse than leaving it off, so only the name is
        # written and the address portion of the line is left for the filer
        # to fill in by hand before mailing.
        "employer_name": state.income.employer_name,
        "signature_phone": state.identity.daytime_phone,
        # The real PDF also has a "Convenient hours for us to call" field
        # (FillText11) on the same line as the phone number. No intake
        # field captures preferred callback hours anywhere in
        # ReturnStateObject, so it is intentionally left unmapped/blank
        # here rather than fabricated. (There is also no fillable field for
        # "Your signature" or "Date" on this PDF revision -- those are
        # blank ruled lines for a wet-ink signature, not AcroForm fields.)
    }
