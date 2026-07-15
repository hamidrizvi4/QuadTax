"""Schedule OI (1040-NR) — Other Information. ALWAYS required.

Captures the demographic information the IRS uses to validate residency,
treaty claims, prior-year filings, and elections. Most NRA tax software
gets this wrong by omitting Item L (treaty article table); QuadTax
populates it from :attr:`TreatyState.applied_benefits`.

Field-letter map (verified against the real vendored TY2025 AcroForm —
``assets/templates/2025/f1040nro.pdf`` — via its embedded XFA template's
accessibility ``<speak>`` text, which gives the authoritative line label
for every field; do NOT trust letter assumptions from older Schedule OI
revisions, they were reshuffled in the 2022+ redesign):

    Header — name / identifying number  (f1_1 / f1_2)
    A  — country of citizenship                          (f1_3)
    B  — country of tax residence                         (f1_4)
    C  — ever applied for a green card?           Yes/No  (c1_1[0]/[1])
    D1 — ever a U.S. citizen?                     Yes/No  (c1_2[0]/[1])
    D2 — ever a green card holder?                Yes/No  (c1_3[0]/[1])
    E  — visa type / immigration status on 12/31          (f1_5)
    F  — ever changed visa/immigration status?    Yes/No  (c1_4[0]/[1])
         if yes, date and nature of the change             (f1_6)
    G  — dates entered/left the US (up to 8 pairs)        (f1_7..f1_22)
         Canada/Mexico frequent-commuter exception          (c1_5[0]/[1])
    H  — days present: tax_year-2, tax_year-1, tax_year   (f1_23/f1_24/f1_25)
    I  — filed a US return in a prior year?       Yes/No  (c1_6[0]/[1])
         if yes, latest year + form number filed           (f1_26)
    J  — filing a return for a trust?             Yes/No  (c1_7[0]/[1])
         if yes, grantor-trust ownership/distribution Q     (c1_8[0]/[1])
    K  — total compensation >= $250,000?          Yes/No  (c1_9[0]/[1])
         if yes, alternative sourcing method used?          (c1_10[0]/[1])
    L1 — treaty table, up to 3 rows: country / article /
         months claimed in prior years / amount exempt      (f1_27..f1_38)
         (e) Total -> Form 1040-NR line 1k                  (f1_39)
    L2 — subject to tax in a foreign country on 1(d)?       (c1_11[0]/[1])
    L3 — claiming benefits under Competent Authority?       (c1_12[0]/[1])
    M1 — first year of a §871(d) real-property election      (c1_13)
    M2 — continuing (previous-year, unrevoked) §871(d)
         election                                            (c1_14)

Several of the above (C, D1, D2, F, G's date table and commuter box, J,
K, L2, L3, M2) have no backing field anywhere in ``ReturnStateObject`` —
this engine's intake never asks them — and are intentionally left
unmapped rather than fabricated. See the inline comments below for the
per-item reasoning.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from src.assembly.forms.form_1040nr import WAGE_TREATY_CATEGORIES

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject


def _full_name(ident) -> str:
    parts = [ident.first_name, ident.middle_initial, ident.last_name, ident.suffix]
    return " ".join(p for p in parts if p)


def compute_field_map(state: "ReturnStateObject") -> dict:
    ident = state.identity
    residency = state.residency
    treaty = state.treaty
    elections = state.elections
    extras = state.extras

    treaty_rows: List[dict] = []
    for benefit in treaty.applied_benefits:
        # India Article 21(2) is a standard-DEDUCTION equivalent claimed on
        # 1040-NR line 12, NOT an income exemption — it does not belong in the
        # Item L treaty-exempt-income table (listing the full wages here would
        # wrongly imply they were exempt from tax).
        if benefit.get("country_iso2") == "IN" and benefit.get("article_id") == "21(2)":
            continue
        # "First row" means the first row that actually gets displayed,
        # not the first entry of applied_benefits — if applied_benefits[0]
        # happens to be the excluded India 21(2) entry above, the *next*
        # benefit becomes treaty_rows[0] and should still carry the
        # prior-year total (a plain ``i == 0`` check against the
        # pre-filter index would silently drop it in that case).
        is_first_displayed_row = len(treaty_rows) == 0
        treaty_rows.append(
            {
                "country": benefit.get("country_name", ""),
                "article": benefit.get("article_id", ""),
                "amount_this_year": float(benefit.get("exempt_amount", 0.0)),
                # Column (c) on the *current* AcroForm revision is "number of
                # months claimed in prior tax years" (an integer count), NOT
                # a dollar amount — this engine has no month-level treaty
                # history, only a lifetime dollar total
                # (TreatyState.prior_year_treaty_claim_total). Surfacing a
                # dollar figure in a "number of months" box would be a unit
                # mismatch as wrong as the field it used to (incorrectly)
                # target on an older Schedule OI revision, so it is kept as
                # a display-only key (see amount_prior_years below) and
                # deliberately never wired into the AcroForm remap.
                "amount_prior_years": (
                    float(treaty.prior_year_treaty_claim_total)
                    if is_first_displayed_row
                    else 0.0
                ),
            }
        )

    # Item L (e) Total: IRS instructions say "Enter this amount on Form
    # 1040-NR, line 1k. Do not enter it anywhere else on line 1" — i.e. this
    # total must equal *exactly* what 1040-NR reports as
    # line_1k_treaty_exempt_wages, not the sum of every row shown in the
    # Item L table (which may also list non-wage benefits, e.g. a
    # scholarship_fellowship article, that never touch line 1a/1k at all).
    # Reuses form_1040nr.py's own category filter so the two forms can never
    # silently disagree on this figure. Computed from the *full*
    # applied_benefits list (not the display-capped treaty_rows above) so it
    # stays correct even for a filer with more than the 3 treaty articles
    # the printed table has room for.
    total_exempt_wages = sum(
        float(b.get("exempt_amount", 0.0))
        for b in treaty.applied_benefits
        if b.get("category") in WAGE_TREATY_CATEGORIES
        and not (b.get("country_iso2") == "IN" and b.get("article_id") == "21(2)")
    )

    return {
        # Header — every attached schedule must repeat the filer's name and
        # identifying number.
        "header_name": _full_name(ident),
        "header_identifying_number": ident.primary_tin,
        # A — country of citizenship
        "item_A_country_citizenship": ident.country_of_citizenship,
        # B — country of tax residence
        "item_B_country_tax_residence": ident.country_of_tax_residence,
        # C (ever applied for a green card), D1 (ever a US citizen), D2
        # (ever a green card holder) — added to Schedule OI in the 2022+
        # redesign. No intake question or state field captures any of these
        # for an NRA filer (they're expatriation-history questions, IRC
        # §877A territory) — intentionally left unmapped rather than
        # defaulting to "No", which would be a fabricated answer to a legal
        # disclosure question. See f1040nro_fields.json: c1_1/c1_2/c1_3 are
        # not present in the remap.
        #
        # E — visa type / immigration status on the last day of the tax
        # year (the field itself is f1_5; historically this used to be
        # lettered "C" on pre-2022 Schedule OI revisions).
        "item_E_visa_type": residency.exempt_visa_type or "",
        # F — "have you ever changed your visa type/immigration status" and
        # its "if yes, date and nature of the change" follow-up. No state
        # field tracks visa-change history (years_in_exempt_status is a
        # *count*, not a change-event log) — intentionally left unmapped.
        # NOTE: an earlier version of this module wrote a computed
        # "first year in visa" integer into the follow-up text field
        # (f1_6); that field actually expects a change-event description on
        # the real 2025 AcroForm (confirmed via the XFA accessibility
        # text), so that mapping was a wrong-field bug, not just a stale
        # letter — removed rather than fixed-in-place because no state
        # field describes a change event to put there instead.
        #
        # G — days present in the US, by year (field letter was
        # historically "G"; the real 2025 form's day-count table is
        # actually Item H — see below). The *date-range* portion of G
        # (individual entry/exit date pairs, up to 8 on this form, plus the
        # Canada/Mexico frequent-commuter checkbox) has no backing state:
        # ResidencyState only retains aggregate day counts from I-94 OCR,
        # never the individual trip dates — intentionally left unmapped.
        #
        # H — days present in the US during tax_year-2, tax_year-1,
        # tax_year (raw physical presence, populated by L1 from I-94 OCR —
        # same source as Form 8843).
        "item_H_days_year_minus_2": residency.days_present_year_minus_2,
        "item_H_days_year_minus_1": residency.days_present_year_minus_1,
        "item_H_days_current_year": residency.days_present_current_year,
        # I — filed a US income tax return in a prior year? Plus, if yes,
        # the latest year + form number filed. The real AcroForm represents
        # Yes/No as two INDEPENDENT checkbox fields (c1_6[0]="/1" for Yes,
        # c1_6[1]="/2" for No), not one shared radio group — a plain bool
        # only ever drives the Yes box, so a confident "No" answer would
        # otherwise render as *both* boxes blank (indistinguishable from
        # "unanswered") instead of affirmatively checking No. Mirrors the
        # existing digital_assets_yes/digital_assets_no pattern in
        # form_1040nr.py.
        "item_I_filed_1040_prior_year_yes": extras.filed_previous_federal_return,
        "item_I_filed_1040_prior_year_no": not extras.filed_previous_federal_return,
        "item_I_prior_return_year_and_form": (
            f"{extras.previous_return_year} {extras.previous_return_type}".strip()
            if extras.filed_previous_federal_return and extras.previous_return_year
            else ""
        ),
        # J — filing a return for a trust, and (if yes) the grantor-trust
        # ownership/distribution follow-up. This engine only prepares
        # individual NRA returns, never trust returns — no state field
        # exists for either question — intentionally left unmapped.
        #
        # K — total compensation >= $250,000, and (if yes) whether an
        # alternative sourcing method was used. Deliberately NOT inferred
        # from income.total_w2_wages + income.fdap_taxable_total: "total
        # compensation" is a narrower legal concept than gross FDAP+wages
        # (FDAP mixes in interest/dividends/royalties that are not
        # compensation for personal services), so guessing from those
        # totals risks answering a Yes/No legal disclosure incorrectly.
        # Left unmapped absent a dedicated intake question.
        #
        # L1 — treaty benefit table (one row per applied benefit, after
        # dropping India 21(2) — see loop above), plus the (e) Total that
        # must equal 1040-NR line 1k.
        "item_L_treaty_rows": treaty_rows,
        "item_L_total_exempt_amount": total_exempt_wages,
        # L2 — subject to tax in a foreign country on the income in L1(d)?
        # L3 — claiming benefits under a Competent Authority determination?
        # Neither has a supporting intake question/state field —
        # intentionally left unmapped.
        #
        # M1 — first year of a §871(d) election to treat US real-property
        # income as ECI. M2 — a *continuing* (made-in-a-prior-year,
        # unrevoked) version of the same election. ElectionsState only
        # tracks a single section_871d_election bool with no first-year-vs-
        # continuing distinction, so this maps to M1 (the more common case
        # for a filer reaching this branch at all) rather than M2; M2 is
        # left unmapped. In practice this is moot for automatic assembly:
        # per ElectionsState's docstring, validate_post_l1 blocks assembly
        # entirely whenever section_871d_election is True, because this
        # engine has no §871(d) real-property-as-ECI income computation —
        # this field is only reachable via a manual force_assembly
        # override, same as the three informational-only elections below.
        "item_M1_871d_election_first_year": elections.section_871d_election,
        # --- Informational only (no backing field on the TY2025 AcroForm; see
        # module docstring) — kept for the JSON-fallback / human-review
        # view, never written to the PDF (leading underscore is filtered by
        # FormPopulator before the remap is even consulted). Pre-2022
        # Schedule OI revisions had checkboxes for a §6013(g)/(h) election
        # (Item I) and a $100k+ foreign gift disclosure (Item K); the
        # current revision has neither — a §6013 election isn't disclosed
        # on Schedule OI at all now, and large foreign gifts are disclosed
        # via standalone Form 3520 instead. The closer-connection exception
        # was never on Schedule OI itself; it requires standalone Form 8840.
        "_election_6013_reported": (
            elections.section_6013g_election or elections.section_6013h_election
        ),
        "_large_foreign_gifts_reported": elections.large_foreign_gifts_over_100k,
        "_closer_connection_reported": elections.closer_connection_exception_claimed,
        # Filer-reported prior-year residency status. Pre-2022 Schedule OI
        # revisions had an explicit "were you a US resident in a prior
        # year?" Item E checkbox; the current revision's Item E is the visa
        # -type text field instead (see above) and there is no other
        # checkbox anywhere on the form asking this question — this value
        # now only feeds L1's dual-status detection
        # (see ResidencyState.prior_year_residency_status), not any PDF
        # field. Kept informational for the JSON-fallback/audit view.
        "_prior_year_resident_status_reported": (
            residency.prior_year_residency_status == "resident_alien"
        ),
    }
