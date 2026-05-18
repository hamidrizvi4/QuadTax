"""Command-line interface for QuadTax.

Usage::

    python -m src.cli generate --intake-json sample.json --output packet/

Reads an intake JSON file describing the filer's documents and MCQ
answers, runs the full L1→L9 pipeline, populates per-form field maps
or PDFs into ``packet/forms/``, and assembles the federal / NY / FICA
mailing packets in ``packet/``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

from src.assembly.form_populator import FormPopulator
from src.assembly.mailing_packager import MailingPackager
from src.intake.ocr_parser import DocumentParser
from src.orchestrator.engine import TaxEngine

logger = logging.getLogger(__name__)


def cmd_generate(args: argparse.Namespace) -> int:
    intake_path = Path(args.intake_json).expanduser().resolve()
    out_dir = Path(args.output).expanduser().resolve()
    forms_dir = out_dir / "forms"
    forms_dir.mkdir(parents=True, exist_ok=True)

    intake: Dict[str, Any] = json.loads(intake_path.read_text(encoding="utf-8"))

    # Pull document paths and parse them via OCR.
    i94_text = _ocr_or_empty(intake.get("i94_file"))
    w2_texts = [_ocr_or_empty(p) for p in intake.get("w2_files", [])]
    f1042s_texts = [_ocr_or_empty(p) for p in intake.get("form_1042s_files", [])]

    mcq = intake.get("mcq_answers", {})
    # Ensure tax_year is present; default to 2025.
    mcq.setdefault("tax_year", args.tax_year)

    # Run the pipeline.
    engine = TaxEngine()
    pdf_paths, state = engine.run_full_pipeline(
        i94_ocr_text=i94_text,
        w2_ocr_texts=w2_texts,
        form_1042s_ocr_texts=f1042s_texts,
        mcq_answers=mcq,
    )

    # Re-populate forms into the requested forms_dir so we can package from a
    # known location (the engine's default outputs/ may differ).
    populator = FormPopulator(
        templates_dir=str(forms_dir.parent / "templates"),
        outputs_dir=str(forms_dir),
        tax_year=state.tax_year,
    )
    populator.generate_filing_package(state, output_dir=str(forms_dir))

    packager = MailingPackager(tax_year=state.tax_year)
    package = packager.assemble(state, forms_dir=forms_dir, output_dir=out_dir)

    summary_path = out_dir / "summary.json"
    summary = {
        "tax_year": state.tax_year,
        "filer": f"{state.identity.first_name} {state.identity.last_name}".strip(),
        "federal_refund_or_owed": float(state.tax.refund_or_owed),
        "ny_refund_or_owed": float(state.ny.ny_refund_or_owed),
        "fica_refund_amount": float(
            state.fica.incorrect_ss_withheld + state.fica.incorrect_medicare_withheld
        ),
        "forms_required": list(state.forms_required),
        "completed_layers": list(state.completed_layers),
        "package": package.to_dict(),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote {summary_path}")
    print(f"Federal packet: {package.federal.pdf_output or package.federal.json_output}")
    if package.ny:
        print(f"NY packet:      {package.ny.pdf_output or package.ny.json_output}")
    if package.fica_843:
        print(f"FICA 843 packet: {package.fica_843.pdf_output or package.fica_843.json_output}")
    return 0


def _ocr_or_empty(path_str: str | None) -> str:
    if not path_str:
        return ""
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        logger.warning("Document %s not found; skipping OCR.", path)
        return ""
    parser = DocumentParser()
    data = path.read_bytes()
    return parser.parse_file(data, path.name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="QuadTax — NRA tax return generator.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Run the full pipeline and assemble mail packets.")
    g.add_argument("--intake-json", required=True, help="Path to the intake JSON.")
    g.add_argument("--output", required=True, help="Output directory.")
    g.add_argument("--tax-year", type=int, default=2025)
    g.set_defaults(func=cmd_generate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
