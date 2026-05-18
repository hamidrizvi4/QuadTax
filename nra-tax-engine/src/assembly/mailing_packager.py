"""Mailing packager — assembles printable, mail-ready packets.

Produces three deliverables for the typical NRA student:

1. ``packet_federal.pdf`` — 1040-NR and all federal attachments in
   IRS Pub 519 Ch 8 assembly order. Includes a Markdown cover sheet
   listing every enclosed form and the correct mailing address based on
   whether the filer has a balance due, a W-7 application, or just a
   refund.
2. ``packet_NY.pdf`` — IT-203 + IT-203-B + IT-203-D when applicable.
   Separate Albany NY DTF address.
3. ``packet_843.pdf`` — Form 843 FICA refund claim. Mails separately to
   a different IRS service center per the Form 843 instructions.

PDF merger uses pypdf. When the underlying form template is missing,
the packager merges the per-form JSON field-maps into the packet
manifest instead so the deliverable is still useful for human review
before the IRS publishes year-final PDFs.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from pypdf import PdfReader, PdfWriter

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject

logger = logging.getLogger(__name__)


# Pub 519 Ch 8 mailing order for the federal packet. Forms not present in
# ``forms_required`` are simply skipped.
FEDERAL_ASSEMBLY_ORDER: List[str] = [
    "1040-NR",
    "Schedule-1",
    "Schedule-2",
    "Schedule-3",
    "Schedule-NEC",
    "Schedule-OI",
    "Schedule-A",
    "Schedule-P",
    "6251",
    "8833",
    "8843",
    "2210",
    "W-7",  # When attached, mails with 1040-NR but routes to ITIN Operations.
]

# NY packet assembly order. Note: NY does NOT mix with federal forms.
NY_ASSEMBLY_ORDER: List[str] = [
    "IT-201",
    "IT-203",
    "IT-203-B",
    "IT-203-D",
]


@dataclass
class PacketManifest:
    """Description of a single mailing packet."""

    name: str                                   # 'federal' / 'ny' / 'fica_843'
    forms_in_order: List[str] = field(default_factory=list)
    pdf_output: Optional[str] = None            # Path if PDFs were available
    json_output: Optional[str] = None           # Field-map JSON fallback
    cover_sheet: Optional[str] = None           # Markdown cover sheet
    mailing_address: Dict[str, str] = field(default_factory=dict)
    has_payment: bool = False
    has_w7: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "forms_in_order": self.forms_in_order,
            "pdf_output": self.pdf_output,
            "json_output": self.json_output,
            "cover_sheet": self.cover_sheet,
            "mailing_address": self.mailing_address,
            "has_payment": self.has_payment,
            "has_w7": self.has_w7,
        }


@dataclass
class MailingPackage:
    """Container for all packets produced for one return."""

    federal: PacketManifest
    ny: Optional[PacketManifest] = None
    fica_843: Optional[PacketManifest] = None

    def to_dict(self) -> dict:
        return {
            "federal": self.federal.to_dict(),
            "ny": self.ny.to_dict() if self.ny else None,
            "fica_843": self.fica_843.to_dict() if self.fica_843 else None,
        }


class MailingPackager:
    """Assembles printable packets with cover sheets and correct addresses."""

    def __init__(
        self,
        tax_year: int = 2025,
        addresses_path: Optional[Path] = None,
    ) -> None:
        self.tax_year = tax_year
        if addresses_path is None:
            addresses_path = (
                Path(__file__).parent.parent
                / "database"
                / "tax_year"
                / str(tax_year)
                / "mailing_addresses.json"
            )
        with open(addresses_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # Strip _meta keys but preserve nested dicts of addresses.
        self.addresses = _strip_meta(raw)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assemble(
        self,
        state: "ReturnStateObject",
        forms_dir: Path,
        output_dir: Path,
    ) -> MailingPackage:
        """Build all three packets from per-form outputs in ``forms_dir``.

        Args:
            state: Finalized ReturnStateObject.
            forms_dir: Directory containing the per-form PDF / JSON outputs
                produced by :class:`FormPopulator`.
            output_dir: Directory to write the merged packet files into.

        Returns:
            :class:`MailingPackage` with manifests for each packet.
        """
        output_dir = Path(output_dir).absolute()
        output_dir.mkdir(parents=True, exist_ok=True)
        forms_dir = Path(forms_dir).absolute()

        federal = self._build_federal_packet(state, forms_dir, output_dir)
        ny = self._build_ny_packet(state, forms_dir, output_dir)
        fica_843 = self._build_fica_packet(state, forms_dir, output_dir)
        return MailingPackage(federal=federal, ny=ny, fica_843=fica_843)

    # ------------------------------------------------------------------
    # Per-packet builders
    # ------------------------------------------------------------------

    def _build_federal_packet(
        self,
        state: "ReturnStateObject",
        forms_dir: Path,
        output_dir: Path,
    ) -> PacketManifest:
        # Federal forms required, in Pub 519 Ch 8 order. Exclude Form 843
        # (mails separately) — handled in the FICA packet path below.
        present = {f for f in state.forms_required + ["1040-NR", "Schedule-OI", "8843"]}
        if float(state.income.fdap_taxable_total) > 0:
            present.add("Schedule-NEC")
        if float((state.sch_a or {}).get("total", 0.0)) > 0:
            present.add("Schedule-A")
        ordered = [f for f in FEDERAL_ASSEMBLY_ORDER if f in present]

        # Decide the mailing destination.
        has_balance_due = float(state.tax.refund_or_owed) > 0
        has_w7 = "W-7" in present
        if has_w7:
            address_key = "form_w7_itin_application"
        elif has_balance_due:
            address_key = "1040nr_with_payment"
        else:
            address_key = "1040nr_no_payment"
        address = self.addresses["federal"][address_key]

        packet = PacketManifest(
            name="federal",
            forms_in_order=ordered,
            mailing_address=address,
            has_payment=has_balance_due,
            has_w7=has_w7,
        )

        # Try the PDF merge path; fall back to JSON manifest.
        pdf_path = self._merge_pdfs(forms_dir, ordered, output_dir / "packet_federal.pdf")
        if pdf_path is not None:
            packet.pdf_output = str(pdf_path)
        else:
            manifest_path = self._merge_jsons(
                forms_dir, ordered, output_dir / "packet_federal.json"
            )
            packet.json_output = str(manifest_path)

        # Cover sheet.
        cover_path = output_dir / "packet_federal_cover.md"
        cover_path.write_text(self._cover_sheet_markdown(state, packet), encoding="utf-8")
        packet.cover_sheet = str(cover_path)

        return packet

    def _build_ny_packet(
        self,
        state: "ReturnStateObject",
        forms_dir: Path,
        output_dir: Path,
    ) -> Optional[PacketManifest]:
        ny_forms_present = [f for f in NY_ASSEMBLY_ORDER if f in state.forms_required]
        if not ny_forms_present:
            return None

        has_balance_due = float(state.ny.ny_refund_or_owed) > 0
        is_resident = state.ny.residency_status == "resident"
        if is_resident:
            address_key = (
                "it201_full_year_resident_balance_due"
                if has_balance_due
                else "it201_full_year_resident_refund"
            )
        else:
            address_key = "it203_balance_due" if has_balance_due else "it203_refund"
        address = self.addresses["ny"][address_key]

        packet = PacketManifest(
            name="ny",
            forms_in_order=ny_forms_present,
            mailing_address=address,
            has_payment=has_balance_due,
        )

        pdf_path = self._merge_pdfs(forms_dir, ny_forms_present, output_dir / "packet_NY.pdf")
        if pdf_path is not None:
            packet.pdf_output = str(pdf_path)
        else:
            manifest_path = self._merge_jsons(
                forms_dir, ny_forms_present, output_dir / "packet_NY.json"
            )
            packet.json_output = str(manifest_path)

        cover_path = output_dir / "packet_NY_cover.md"
        cover_path.write_text(
            self._cover_sheet_markdown(state, packet), encoding="utf-8"
        )
        packet.cover_sheet = str(cover_path)
        return packet

    def _build_fica_packet(
        self,
        state: "ReturnStateObject",
        forms_dir: Path,
        output_dir: Path,
    ) -> Optional[PacketManifest]:
        if not state.fica.requires_form_843:
            return None

        address = self.addresses["federal"]["form_843_fica_refund"]
        packet = PacketManifest(
            name="fica_843",
            forms_in_order=["843"],
            mailing_address=address,
            has_payment=False,
        )
        pdf_path = self._merge_pdfs(forms_dir, ["843"], output_dir / "packet_843.pdf")
        if pdf_path is not None:
            packet.pdf_output = str(pdf_path)
        else:
            manifest_path = self._merge_jsons(
                forms_dir, ["843"], output_dir / "packet_843.json"
            )
            packet.json_output = str(manifest_path)

        cover_path = output_dir / "packet_843_cover.md"
        cover_path.write_text(
            self._cover_sheet_markdown(state, packet), encoding="utf-8"
        )
        packet.cover_sheet = str(cover_path)
        return packet

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _form_outputs(self, forms_dir: Path, form_name: str) -> List[Path]:
        """Find PDF first, JSON fallback second, for a given form name."""
        pdfs = list(forms_dir.glob(f"*_{form_name}.pdf"))
        if pdfs:
            return pdfs
        return list(forms_dir.glob(f"*_{form_name}.fieldmap.json"))

    def _merge_pdfs(
        self,
        forms_dir: Path,
        ordered_forms: List[str],
        output_path: Path,
    ) -> Optional[Path]:
        """Merge the form PDFs into one combined packet. Returns None if any are missing."""
        writer = PdfWriter()
        any_pdf = False
        for form in ordered_forms:
            pdfs = list(forms_dir.glob(f"*_{form}.pdf"))
            if not pdfs:
                # If even one form lacks a PDF we fall back to JSON manifest.
                return None
            for pdf in pdfs:
                reader = PdfReader(str(pdf))
                for page in reader.pages:
                    writer.add_page(page)
                any_pdf = True
        if not any_pdf:
            return None
        with open(output_path, "wb") as f:
            writer.write(f)
        return output_path

    def _merge_jsons(
        self,
        forms_dir: Path,
        ordered_forms: List[str],
        output_path: Path,
    ) -> Path:
        """Merge per-form JSON field-maps into a single packet manifest JSON."""
        manifest: Dict[str, dict] = {"_assembly_order": ordered_forms, "forms": {}}
        for form in ordered_forms:
            outputs = self._form_outputs(forms_dir, form)
            if not outputs:
                manifest["forms"][form] = {"_status": "no output found"}
                continue
            # Read the first matching JSON.
            json_files = [p for p in outputs if p.suffix == ".json"]
            if json_files:
                manifest["forms"][form] = json.loads(json_files[0].read_text())
            else:
                # PDF exists but no JSON — record the path.
                manifest["forms"][form] = {"_pdf_path": str(outputs[0])}
        output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return output_path

    def _cover_sheet_markdown(
        self,
        state: "ReturnStateObject",
        packet: PacketManifest,
    ) -> str:
        ident = state.identity
        name = f"{ident.first_name} {ident.last_name}".strip() or "(name pending)"
        tin = ident.primary_tin or "(SSN/ITIN pending — Form W-7 attached)"

        addr = packet.mailing_address
        addr_lines = "  \n".join(
            x for x in (
                addr.get("addressee", ""),
                addr.get("line2", ""),
                addr.get("city_state_zip", ""),
                addr.get("country", ""),
            )
            if x
        )

        forms_list = "\n".join(f"- {f}" for f in packet.forms_in_order) or "- (none)"

        if packet.name == "federal":
            title = "Federal Tax Return (Form 1040-NR)"
            money_line = (
                f"**Federal refund:** ${-float(state.tax.refund_or_owed):,.2f}"
                if state.tax.refund_or_owed < 0
                else f"**Federal balance due:** ${float(state.tax.refund_or_owed):,.2f}"
            )
            extra_notes = []
            if packet.has_payment:
                extra_notes.append(
                    "- Enclose a check payable to **United States Treasury**. "
                    "Write your SSN/ITIN, the tax year, and \"Form 1040-NR\" on the check."
                )
            if packet.has_w7:
                extra_notes.append(
                    "- Attach **Form W-7** with original (or certified-copy) identity "
                    "documents per the W-7 instructions. The 1040-NR packet must mail "
                    "to the ITIN Operations address shown above, NOT the regular Austin address."
                )
        elif packet.name == "ny":
            title = "New York State Return (Form IT-203)"
            money_line = (
                f"**NY refund:** ${-float(state.ny.ny_refund_or_owed):,.2f}"
                if state.ny.ny_refund_or_owed < 0
                else f"**NY balance due:** ${float(state.ny.ny_refund_or_owed):,.2f}"
            )
            extra_notes = []
            if packet.has_payment:
                extra_notes.append(
                    "- Enclose a check payable to **New York State Income Tax**."
                )
        elif packet.name == "fica_843":
            title = "FICA Refund Claim (Form 843)"
            total_fica = float(state.fica.incorrect_ss_withheld) + float(
                state.fica.incorrect_medicare_withheld
            )
            money_line = f"**FICA refund claim:** ${total_fica:,.2f}"
            extra_notes = [
                "- Attach a copy of each W-2 showing the FICA withholding.",
                "- Attach **Form 8316** (Information Regarding Request for Refund "
                "of Social Security Tax) — the employer's statement that they will "
                "not refund the tax directly.",
                "- Attach copies of your I-94 and visa stamp evidencing exempt status.",
                "- This claim mails SEPARATELY from your 1040-NR — do NOT bundle.",
            ]
        else:
            title = "Tax Return Packet"
            money_line = ""
            extra_notes = []

        extras = "\n".join(extra_notes)
        return (
            f"# {title} — Tax Year {state.tax_year}\n\n"
            f"**Filer:** {name}\n  \n"
            f"**Taxpayer ID:** {tin}\n  \n"
            f"{money_line}\n\n"
            f"## Mail to\n\n{addr_lines}\n\n"
            f"## Enclosed forms (in Pub 519 Ch 8 assembly order)\n\n{forms_list}\n\n"
            f"## Before mailing\n\n"
            f"- **Sign and date** the 1040-NR (or IT-203 / Form 843) on the signature line.\n"
            f"- Make a complete photocopy for your records.\n"
            f"- Use certified mail with return receipt or a trackable carrier.\n"
            + (f"\n{extras}\n" if extras else "")
            + "\n*Generated by QuadTax.*\n"
        )


def _strip_meta(value):
    """Recursively drop keys whose name begins with ``_``."""
    if isinstance(value, dict):
        return {k: _strip_meta(v) for k, v in value.items() if not k.startswith("_")}
    if isinstance(value, list):
        return [_strip_meta(v) for v in value]
    return value
