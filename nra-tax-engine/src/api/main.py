"""
API Interface — NRA Tax Engine.

Provides a FastAPI wrapper to receive multipart HTTP payloads representing
scanned tax documents and metadata, feeds them through the OCR parser,
and triggers the full mathematical execution DAG.
"""

import json
from typing import List

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.intake.ocr_parser import DocumentParser
from src.orchestrator.engine import TaxEngine


class TaxProcessResponse(BaseModel):
    """Synchronized output returning final financial liabilities and generated PDFs."""
    status: str
    generated_forms: List[str]
    tax_liability: float
    refund_or_owed: float
    requires_843_fica_claim: bool


app = FastAPI(title="NRA Tax Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/v1/upload-and-process", response_model=TaxProcessResponse)
async def upload_and_process_endpoint(
    i94_file: UploadFile = File(...),
    w2_files: List[UploadFile] = File(default=[]),
    form_1042s_files: List[UploadFile] = File(default=[]),
    mcq_answers_json: str = Form(...),
):
    """Accepts raw PDF uploads, processes them into strings, and executes the tax pipeline."""
    try:
        # 1. Decode standard metadata parameters
        mcq_answers = json.loads(mcq_answers_json)

        # 2. Intake Initialization
        parser = DocumentParser()

        # 3. Synchronous Byte Hand-off for I-94
        i94_bytes = await i94_file.read()
        i94_ocr_text = parser.parse_file(i94_bytes, i94_file.filename or "i94.pdf")

        # 4. W-2 Document Loops
        w2_ocr_texts = []
        for w2 in w2_files:
            w2_bytes = await w2.read()
            w2_ocr_texts.append(parser.parse_file(w2_bytes, w2.filename or "w2.pdf"))

        # 5. 1042-S Document Loops
        form_1042s_ocr_texts = []
        for f1042s in form_1042s_files:
            f1042s_bytes = await f1042s.read()
            form_1042s_ocr_texts.append(
                parser.parse_file(f1042s_bytes, f1042s.filename or "1042s.pdf")
            )

        # 6. Execute DAG Pipeline
        engine = TaxEngine()
        pdf_paths, final_state = engine.run_full_pipeline(
            i94_ocr_text=i94_ocr_text,
            w2_ocr_texts=w2_ocr_texts,
            form_1042s_ocr_texts=form_1042s_ocr_texts,
            mcq_answers=mcq_answers,
        )

        return TaxProcessResponse(
            status="success",
            generated_forms=pdf_paths,
            tax_liability=final_state.tax.total_tax_liability,
            refund_or_owed=final_state.tax.refund_or_owed,
            requires_843_fica_claim=final_state.fica.requires_form_843,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
