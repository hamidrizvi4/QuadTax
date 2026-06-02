"""POST /api/v1/ocr — extract structured fields from uploaded tax documents."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.intake.document_extractor import DocumentExtractor, OcrResult

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/v1/ocr", response_model=OcrResult, tags=["ocr"])
async def extract_documents(
    tax_year: int = Form(default=2025),
    i94_file: Optional[UploadFile] = File(default=None),
    w2_files: List[UploadFile] = File(default=[]),
    form_1042s_files: List[UploadFile] = File(default=[]),
    form_1099_files: List[UploadFile] = File(default=[]),
) -> OcrResult:
    """Extract structured fields from uploaded tax documents using OCR + LLM."""
    extractor = DocumentExtractor()
    try:
        i94_bytes = await i94_file.read() if i94_file else None
        i94_name = i94_file.filename or "i94.pdf" if i94_file else "i94.pdf"

        w2_data = [(await f.read(), f.filename or f"w2_{i}.pdf") for i, f in enumerate(w2_files)]
        f1042s_data = [(await f.read(), f.filename or f"1042s_{i}.pdf") for i, f in enumerate(form_1042s_files)]
        f1099_data = [(await f.read(), f.filename or f"1099_{i}.pdf") for i, f in enumerate(form_1099_files)]

        return extractor.extract_all(
            i94_bytes=i94_bytes,
            i94_filename=i94_name,
            w2_files=w2_data,
            form_1042s_files=f1042s_data,
            form_1099_files=f1099_data,
            tax_year=tax_year,
        )
    except Exception as exc:
        logger.exception("OCR extraction failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
