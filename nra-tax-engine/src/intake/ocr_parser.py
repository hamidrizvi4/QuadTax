"""
Intake Layer — PDF OCR and Text Extraction.

Handles native digital PDFs via PDFPlumber and fallback scanned image
extraction via Tesseract OCR to feed raw strings into the LLM Reasoning Zone.
"""

import io

import pdf2image
import pdfplumber
import pytesseract


class DocumentParser:
    """Ingests raw file bytes and extracts text blocks for LLM consumption."""

    def parse_file(self, file_bytes: bytes, filename: str) -> str:
        """Dynamically routes extraction based on file contents.

        First attempts lightweight native abstraction. Falls back to heavy
        OCR if the document is fundamentally an image wrapper.

        Args:
            file_bytes: Raw binary payload of the uploaded document.
            filename: Name of the uploaded file for logging purposes.

        Returns:
            Concatenated string representing all textual content.
        """
        extracted_text = ""

        # 1. Attempt Native PDF Extraction
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                pages_text = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
                extracted_text = "\n".join(pages_text).strip()
        except Exception:
            pass  # Fall through to OCR on PDF structure corruption

        # 2. Check Extraction Validity
        if len(extracted_text) > 50:
            return extracted_text

        # 3. Fallback: Heavy Optical Character Recognition
        extracted_text = ""
        try:
            images = pdf2image.convert_from_bytes(file_bytes)
            ocr_texts = []
            for img in images:
                page_text = pytesseract.image_to_string(img)
                ocr_texts.append(page_text)
            extracted_text = "\n".join(ocr_texts).strip()
        except Exception as e:
            # Reattach the filename to the exception for clearer debugging
            raise RuntimeError(f"OCR failed for {filename}: {str(e)}")

        return extracted_text
