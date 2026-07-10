"""Layer 9 — PDF assembly orchestrator.

Iterates :attr:`ReturnStateObject.forms_required`, computes the
field-map for each form via the per-form populators under
:mod:`src.assembly.forms`, and writes the values into the matching IRS
AcroForm PDF under ``assets/templates/<tax_year>/<form>.pdf``.

If a template file is missing the populator writes the field-map JSON
to disk instead so the rest of the pipeline can still produce a
deliverable for review while the IRS PDF templates are being vendored
(IRS publishes year-final 1040-NR PDFs in mid-November of the year).

Phase 3 changes:
    * Single-form-per-module architecture (see ``forms/``).
    * Field-map JSON fallback when templates are absent.
    * Form-name → form-id mapping handles aliases (Schedule-OI,
      Schedule-NEC, Schedule-A) emitted by L4/L6/L7 layers.
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, NumberObject

from src.assembly.forms import FORM_REGISTRY

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject

logger = logging.getLogger(__name__)


# Maps an internal form registry key to the IRS fillable-PDF filename stem
# vendored under ``assets/templates/<year>/``. The IRS publishes these with an
# ``f`` prefix (e.g. ``f1040nr.pdf``) and encodes schedules as ``f1040nro``
# (Schedule OI), ``f1040nra`` (Schedule A), ``f1040nrn`` (Schedule NEC). Forms
# without an entry fall back to ``<form_name>.pdf`` for backward compatibility.
_IRS_TEMPLATE_STEMS = {
    "1040-NR": "f1040nr",
    "Schedule-OI": "f1040nro",
    "Schedule-A": "f1040nra",
    "Schedule-NEC": "f1040nrn",
    "8843": "f8843",
    "8833": "f8833",
    "843": "f843",
    "W-7": "fw7",
    "6251": "f6251",
    "2210": "f2210",
    "8316": "f8316",
}


def _template_stem(form_name: str) -> str:
    """Resolve a registry form name to its vendored IRS PDF filename stem."""
    return _IRS_TEMPLATE_STEMS.get(form_name, form_name)


# Forms always attached to a 1040-NR regardless of treaty / FICA paths.
_ALWAYS_REQUIRED = ["1040-NR", "Schedule-OI", "8843"]


class FormPopulator:
    """Computes field-maps and writes filled PDFs (or JSON fallbacks)."""

    def __init__(
        self,
        templates_dir: str = "assets/templates",
        outputs_dir: str = "outputs",
        tax_year: int = 2025,
    ):
        self.templates_dir = Path(templates_dir).absolute() / str(tax_year)
        self.outputs_dir = Path(outputs_dir).absolute()
        self.tax_year = tax_year

        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_filing_package(
        self,
        current_state: "ReturnStateObject",
        output_dir: str | None = None,
    ) -> List[str]:
        """Produce one output file per required form."""
        if not current_state.ready_for_assembly:
            raise ValueError("ReturnStateObject is not ready for assembly. Check completed_layers.")

        out_path = Path(output_dir).absolute() if output_dir else self.outputs_dir
        out_path.mkdir(parents=True, exist_ok=True)

        # Always include the federal core forms; deduplicate while preserving order.
        required = list(_ALWAYS_REQUIRED)
        for form in current_state.forms_required:
            if form not in required:
                required.append(form)
        # Add Schedule-A if itemized total > 0.
        if float((current_state.sch_a or {}).get("total", 0.0)) > 0 and "Schedule-A" not in required:
            required.append("Schedule-A")
        # Add Schedule-NEC if any FDAP income.
        if float(current_state.income.fdap_taxable_total) > 0 and "Schedule-NEC" not in required:
            required.append("Schedule-NEC")

        generated: List[str] = []
        for form_name in required:
            if form_name not in FORM_REGISTRY:
                logger.warning("No populator registered for form %s; skipping.", form_name)
                continue

            field_map = FORM_REGISTRY[form_name](current_state)
            stem = self._safe_stem(current_state, form_name)
            template_path = self.templates_dir / f"{_template_stem(form_name)}.pdf"
            remap = self._load_remap(_template_stem(form_name))

            # Some forms (e.g. Form 8833) must be filed once per disclosed item —
            # the populator signals this by returning {"rows": [...]} instead of
            # a flat field map. Each row becomes its own complete output file,
            # filled against the same remap. Zero rows means the form isn't
            # actually required for this filer (e.g. no 8833-eligible benefits).
            if isinstance(field_map, dict) and isinstance(field_map.get("rows"), list):
                rows = field_map["rows"]
                if not rows:
                    continue
                for i, row in enumerate(rows, start=1):
                    row_stem = f"{stem}_{i}" if len(rows) > 1 else stem
                    generated.append(
                        self._write_one_form(
                            row, row_stem, form_name, template_path, remap, out_path
                        )
                    )
                continue

            generated.append(
                self._write_one_form(
                    field_map, stem, form_name, template_path, remap, out_path
                )
            )

        return generated

    def _write_one_form(
        self,
        field_map: Dict[str, Any],
        stem: str,
        form_name: str,
        template_path: Path,
        remap: Dict[str, Any],
        out_path: Path,
    ) -> str:
        """Write a single form instance as a filled PDF, or a JSON fallback."""
        if template_path.exists():
            pdf_out = out_path / f"{stem}_{form_name}.pdf"
            self._inject_pdf_data(template_path, field_map, pdf_out, remap)
            return str(pdf_out)

        # Template not yet vendored — emit the field-map as JSON so the
        # downstream UI / human reviewer can verify correctness.
        json_out = out_path / f"{stem}_{form_name}.fieldmap.json"
        json_out.write_text(
            json.dumps(field_map, indent=2, default=_json_default),
            encoding="utf-8",
        )
        logger.warning(
            "Template %s missing; wrote field-map JSON to %s.",
            template_path,
            json_out,
        )
        return str(json_out)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_stem(state: "ReturnStateObject", form_name: str) -> str:
        ident = state.identity
        name = f"{ident.first_name}_{ident.last_name}".strip("_")
        if not name:
            name = "filer"
        return name.replace(" ", "_")

    def _load_remap(self, stem: str) -> Dict[str, str]:
        """Load the human-key -> AcroForm-field-name remap for a form stem.

        The per-form ``<stem>_fields.json`` (vendored alongside the IRS PDF)
        bridges the human-readable keys emitted by ``compute_field_map`` to the
        IRS AcroForm field names (e.g. ``last_name`` -> ``topmostSubform[0].Page1[0].f1_02[0]``).
        Returns ``{}`` when no remap is vendored, so the form degrades to an
        unfilled template rather than crashing.
        """
        path = self.templates_dir / f"{stem}_fields.json"
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to parse remap %s: %s", path, exc)
            return {}

    def _inject_pdf_data(
        self,
        template_path: Path,
        data: Dict[str, Any],
        output_path: Path,
        remap: Dict[str, str] | None = None,
    ) -> None:
        """Inject ``data`` into AcroForm fields of ``template_path`` and flatten.

        ``remap`` translates human-readable field_map keys to IRS AcroForm field
        names. Keys absent from the remap are skipped (the template renders
        unfilled for those lines).
        """
        if not os.path.exists(template_path):
            logger.warning(
                "Template %s does not exist. Skipping physical PDF generation.",
                template_path,
            )
            return

        reader = PdfReader(str(template_path))
        writer = PdfWriter()
        # clone_document_from_reader copies pages AND the /AcroForm dictionary
        # (manual add_page drops it, which makes update_page_form_field_values
        # raise "No /AcroForm dictionary in PDF of PdfWriter Object").
        writer.clone_document_from_reader(reader)

        reader_fields = reader.get_fields() or {}

        def _format_for_acro(acro_name: str, value: Any) -> str:
            # Checkbox widgets don't accept the literal string "X" pypdf's
            # generic _fmt_value produces for True — pypdf only checks the
            # box when the value exactly matches one of the field's defined
            # export states (e.g. "/1"), always with the leading slash.
            field_info = reader_fields.get(acro_name)
            if field_info and field_info.get("/FT") == "/Btn":
                if value is True:
                    states = field_info.get("/_States_") or []
                    on_state = next((s for s in states if s != "/Off"), "/1")
                    return on_state
                if value is False or value is None or value == "":
                    return "/Off"
                # A specific export state was already supplied by the
                # populator (e.g. a multi-way radio group like Form 8316's
                # Yes/No/Do-Not-Know questions) — pass it through as-is.
                return str(value)
            return _fmt_value(value)

        # AcroForm fill — translate keys via the remap, pypdf wants strings.
        remap = remap or {}
        str_data: Dict[str, str] = {}
        for k, v in data.items():
            if k.startswith("_"):
                continue
            acro = remap.get(k)
            if acro is None:
                continue
            if isinstance(v, list) and isinstance(acro, list):
                # Repeating-row table on a single page (e.g. Schedule OI Item L):
                # ``acro`` is a list of {subkey: AcroForm-field-name} dicts, one
                # per pre-printed row slot on the form. Extra data rows beyond
                # the number of available slots are dropped.
                for row_value, row_remap in zip(v, acro):
                    if not isinstance(row_value, dict) or not isinstance(row_remap, dict):
                        continue
                    for subkey, sub_acro in row_remap.items():
                        if subkey in row_value:
                            str_data[sub_acro] = _format_for_acro(sub_acro, row_value[subkey])
                continue
            str_data[acro] = _format_for_acro(acro, v)
        if not str_data:
            logger.warning(
                "No mappable fields for %s; PDF will render unfilled.",
                template_path,
            )
        for page in writer.pages:
            writer.update_page_form_field_values(page, str_data)

        # Flatten: set the ReadOnly flag (bit 7) on every annotation.
        for page in writer.pages:
            if "/Annots" in page:
                for annot in page["/Annots"]:
                    annot_obj = annot.get_object()
                    annot_obj.update({NameObject("/Ff"): NumberObject(1 << 6)})

        with open(output_path, "wb") as out:
            writer.write(out)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_default(obj):
    try:
        return float(obj)
    except (TypeError, ValueError):
        return str(obj)


def _fmt_value(value) -> str:
    if value is True:
        return "X"
    if value is False or value is None:
        return ""
    if isinstance(value, (list, dict)):
        # Complex sub-fields are not directly PDF-writable; the per-form
        # populators expose them via underscore-prefixed keys which we
        # already filter out. Anything reaching here is unexpected.
        return json.dumps(value)
    return str(value)
