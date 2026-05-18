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
            template_path = self.templates_dir / f"{form_name}.pdf"

            if template_path.exists():
                pdf_out = out_path / f"{stem}_{form_name}.pdf"
                self._inject_pdf_data(template_path, field_map, pdf_out)
                generated.append(str(pdf_out))
            else:
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
                generated.append(str(json_out))

        return generated

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

    def _inject_pdf_data(
        self,
        template_path: Path,
        data: Dict[str, Any],
        output_path: Path,
    ) -> None:
        """Inject ``data`` into AcroForm fields of ``template_path`` and flatten."""
        if not os.path.exists(template_path):
            logger.warning(
                "Template %s does not exist. Skipping physical PDF generation.",
                template_path,
            )
            return

        reader = PdfReader(str(template_path))
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        # AcroForm fill — pypdf wants string values.
        str_data = {k: _fmt_value(v) for k, v in data.items() if not k.startswith("_")}
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
