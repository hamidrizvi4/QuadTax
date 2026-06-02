# Document-First Intake Flow + OCR Auto-Fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current manual form-heavy intake with a document-first wizard that OCR-extracts W-2/1042-S/1099/I-94 fields automatically, pre-fills the profile, and only asks questions that documents can't answer.

**Architecture:** A new `POST /api/v1/ocr` backend endpoint takes uploaded tax documents and returns structured extracted fields (W-2 boxes, 1042-S boxes, identity hints) using the existing LLM extraction models from `l3_income.py`. The frontend wizard is restructured into 7 steps — eligibility gate → visa/travel → document upload → OCR review (auto-filled) → extras → context → processing — replacing the manual profile form entirely with OCR-confirmed fields.

**Tech Stack:** FastAPI + Pydantic v2 (backend OCR endpoint), Next.js 16 + TypeScript + Zustand (frontend wizard), OpenAI gpt-4o structured outputs (LLM extraction, already wired), pdfplumber + pytesseract (text extraction, already installed)

---

## New Wizard Flow

```
/ (landing)
  → /intake/eligibility    Step 1 — Are you a US citizen? Green card? (gating)
  → /intake/visa           Step 2 — Visa type, program dates, travel history, country
  → /intake/documents      Step 3 — Upload all documents → "Scan Documents" button
  → /intake/ocr-review     Step 4 — OCR auto-filled form, user confirms/edits
  → /intake/extras         Step 5 — Dependency, marital, digital assets, prior returns
  → /intake/context        Step 6 — NY wizard, FICA, banking (existing, lightly trimmed)
  → /processing            Step 7 — Animated pipeline (existing)
  → /results               Step 8 — Results (existing)
```

---

## File Map

### Backend — new files
| File | Responsibility |
|------|---------------|
| `nra-tax-engine/src/intake/document_extractor.py` | Orchestrates OCR text extraction + LLM structured parsing per document type. Returns `OcrResult`. |
| `nra-tax-engine/src/api/ocr_endpoint.py` | FastAPI router: `POST /api/v1/ocr` accepts multipart files, delegates to `document_extractor`, returns `OcrResult`. |

### Backend — modified files
| File | Change |
|------|--------|
| `nra-tax-engine/src/api/main.py` | Include new `ocr_endpoint` router. |

### Frontend — new files
| File | Responsibility |
|------|---------------|
| `nra-tax-client/src/app/intake/eligibility/page.tsx` | Step 1: 3 yes/no gating questions (US citizen? GC? Applied for residence?) |
| `nra-tax-client/src/app/intake/visa/page.tsx` | Step 2: Visa type, program dates, first arrival, travel history table, country of citizenship/residence |
| `nra-tax-client/src/app/intake/ocr-review/page.tsx` | Step 4: Auto-filled editable form per document. Confirms data into store. |
| `nra-tax-client/src/app/intake/extras/page.tsx` | Step 5: Dependency, married, digital assets, OPT/CPT, estimated tax payments, prior returns |
| `nra-tax-client/src/components/TravelHistoryTable.tsx` | Editable table of entry/exit dates for visa step |
| `nra-tax-client/src/components/OcrDocumentCard.tsx` | Card showing extracted fields for one document with confirm button |
| `nra-tax-client/src/components/YesNoToggle.tsx` | Reusable styled yes/no toggle pair (Sprintax style) |

### Frontend — modified files
| File | Change |
|------|--------|
| `nra-tax-client/src/app/intake/documents/page.tsx` | Remove income description (moves to visa page). Add "Scan All Documents" button that calls OCR endpoint and navigates to ocr-review. |
| `nra-tax-client/src/app/intake/profile/page.tsx` | DELETE — replaced by eligibility + visa + ocr-review flow. Redirect `/intake/profile` → `/intake/eligibility`. |
| `nra-tax-client/src/app/intake/context/page.tsx` | Remove income classification toggles (move to extras). Keep NY, FICA, banking. |
| `nra-tax-client/src/store/taxStore.ts` | Add `eligibility`, `travelHistory`, `ocrResult` state slices + actions. |
| `nra-tax-client/src/lib/api.ts` | Add `extractDocuments(files)` function. |
| `nra-tax-client/src/components/StepBar.tsx` | Update to 7 steps matching new flow. |

---

## Task 1: Backend — `document_extractor.py`

**Files:**
- Create: `nra-tax-engine/src/intake/document_extractor.py`

- [ ] **Step 1: Create the extractor module**

Create `nra-tax-engine/src/intake/document_extractor.py`:

```python
"""Document extractor — OCR text extraction + LLM structured parsing.

Accepts raw file bytes per document type and returns a typed OcrResult.
Reuses the existing W2Data / Form1042SData / Form1099Data models from l3_income.py
and the DocumentParser from ocr_parser.py. No new LLM models needed.
"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

from src.agents.l3_income import Form1042SData, Form1099Data, W2Data
from src.agents._llm_safety import safe_parse
from src.intake.ocr_parser import DocumentParser


# ---------------------------------------------------------------------------
# Extended W-2 extraction: add identity hints present on the form
# ---------------------------------------------------------------------------

class W2Extracted(BaseModel):
    """W-2 box values + identity hints extracted from the document."""
    box_1_wages: float = 0.0
    box_2_fed_withholding: float = 0.0
    box_3_ss_wages: float = 0.0
    box_4_ss_withheld: float = 0.0
    box_5_medicare_wages: float = 0.0
    box_6_medicare_withheld: float = 0.0
    box_17_state_income_tax: float = 0.0
    box_18_local_wages: float = 0.0
    box_19_local_income_tax: float = 0.0
    box_20_locality_name: str = ""
    employer_name: str = Field(default="", description="Employer name from box c")
    employer_ein: str = Field(default="", description="Employer EIN from box b")
    employee_name: str = Field(default="", description="Employee first+last from box e")
    employee_ssn_or_itin: str = Field(default="", description="SSN/ITIN from box a (may be masked)")
    tax_year: int = Field(default=0, description="Tax year printed on the W-2")


class Form1042SExtracted(BaseModel):
    """1042-S values extracted from the document."""
    income_code: int = 0
    gross_income: float = 0.0
    exemption_rate: float = 0.0
    exemption_code: str = ""
    fed_withheld: float = 0.0
    chapter_indicator: int = 3
    recipient_name: str = ""
    withholding_agent_name: str = ""


class Form1099Extracted(BaseModel):
    """1099-INT/DIV/B/MISC extracted values."""
    form_kind: str = ""
    gross_amount: float = 0.0
    fed_withholding: float = 0.0
    payer_name: str = ""


class I94Extracted(BaseModel):
    """I-94 travel record extracted values."""
    days_current_year: int = 0
    days_minus_1: int = 0
    days_minus_2: int = 0
    latest_entry_date: str = ""
    latest_class_of_admission: str = ""


class OcrResult(BaseModel):
    """Structured extraction result for all uploaded documents."""
    i94: Optional[I94Extracted] = None
    w2s: List[W2Extracted] = Field(default_factory=list)
    form_1042s: List[Form1042SExtracted] = Field(default_factory=list)
    form_1099s: List[Form1099Extracted] = Field(default_factory=list)


class DocumentExtractor:
    """Extracts structured fields from tax document bytes using OCR + LLM."""

    def __init__(self, llm_client: Any = None):
        if llm_client is None:
            from openai import OpenAI
            self.llm_client = OpenAI()
        else:
            self.llm_client = llm_client
        self.parser = DocumentParser()

    def _parse(self, schema, system: str, text: str):
        return safe_parse(
            primary_client=self.llm_client,
            primary_model="gpt-4o-2024-08-06",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
            response_format=schema,
        )

    def extract_w2(self, file_bytes: bytes, filename: str) -> W2Extracted:
        text = self.parser.parse_file(file_bytes, filename)
        result = self._parse(
            W2Extracted,
            (
                "You are a precise W-2 OCR parser. Extract every field listed. "
                "For employee_ssn_or_itin return the exact digits shown (may be masked as XXX-XX-1234). "
                "For tax_year look for the year printed on the form header. "
                "Return 0.0 for any dollar field not present."
            ),
            f"W-2 OCR text:\n{text}",
        )
        return result

    def extract_1042s(self, file_bytes: bytes, filename: str) -> Form1042SExtracted:
        text = self.parser.parse_file(file_bytes, filename)
        result = self._parse(
            Form1042SExtracted,
            "You are a precise 1042-S OCR parser. Extract every field. Chapter indicator: 3=NRA withholding, 4=FATCA.",
            f"1042-S OCR text:\n{text}",
        )
        return result

    def extract_1099(self, file_bytes: bytes, filename: str) -> Form1099Extracted:
        text = self.parser.parse_file(file_bytes, filename)
        result = self._parse(
            Form1099Extracted,
            "You are a precise 1099 OCR parser. Identify form_kind as INT/DIV/B/MISC. Extract gross_amount, fed_withholding (box 4), payer_name.",
            f"1099 OCR text:\n{text}",
        )
        return result

    def extract_i94(self, file_bytes: bytes, filename: str, tax_year: int = 2025) -> I94Extracted:
        text = self.parser.parse_file(file_bytes, filename)
        result = self._parse(
            I94Extracted,
            (
                f"You are a precise I-94 travel data extractor for tax year {tax_year}. "
                "Count days physically present in the US for each year requested. "
                "Arrival and departure days both count as full days. "
                "Also extract the latest entry date and class of admission (visa type)."
            ),
            f"I-94 OCR text:\n{text}",
        )
        return result

    def extract_all(
        self,
        i94_bytes: Optional[bytes] = None,
        i94_filename: str = "i94.pdf",
        w2_files: Optional[List[tuple[bytes, str]]] = None,
        form_1042s_files: Optional[List[tuple[bytes, str]]] = None,
        form_1099_files: Optional[List[tuple[bytes, str]]] = None,
        tax_year: int = 2025,
    ) -> OcrResult:
        result = OcrResult()
        if i94_bytes:
            result.i94 = self.extract_i94(i94_bytes, i94_filename, tax_year)
        for file_bytes, filename in (w2_files or []):
            result.w2s.append(self.extract_w2(file_bytes, filename))
        for file_bytes, filename in (form_1042s_files or []):
            result.form_1042s.append(self.extract_1042s(file_bytes, filename))
        for file_bytes, filename in (form_1099_files or []):
            result.form_1099s.append(self.extract_1099(file_bytes, filename))
        return result
```

- [ ] **Step 2: Commit**
```bash
git add nra-tax-engine/src/intake/document_extractor.py
git commit -m "feat: document_extractor — OCR + LLM structured extraction for W-2/1042-S/1099/I-94"
```

---

## Task 2: Backend — OCR endpoint

**Files:**
- Create: `nra-tax-engine/src/api/ocr_endpoint.py`
- Modify: `nra-tax-engine/src/api/main.py`

- [ ] **Step 1: Create the router**

Create `nra-tax-engine/src/api/ocr_endpoint.py`:

```python
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
    """Extract structured fields from uploaded tax documents using OCR + LLM.

    All files are optional — send only the ones you have. Returns an OcrResult
    with pre-filled fields the client can show in a review form.
    """
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
```

- [ ] **Step 2: Register the router in main.py**

In `nra-tax-engine/src/api/main.py`, add after the existing imports:
```python
from src.api.ocr_endpoint import router as ocr_router
```

Add after `app.add_middleware(...)`:
```python
app.include_router(ocr_router)
```

Also add the secure packet download endpoint if not already present:
```python
import os
from fastapi.responses import FileResponse

@app.get("/api/v1/packet", tags=["tax"])
def download_packet(path: str) -> FileResponse:
    abs_path = os.path.realpath(path)
    outputs_abs = os.path.realpath("outputs")
    if not abs_path.startswith(outputs_abs):
        raise HTTPException(status_code=403, detail="Access denied.")
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Packet not found.")
    return FileResponse(abs_path, media_type="application/pdf",
                        filename=os.path.basename(abs_path))
```

- [ ] **Step 3: Restart the backend and verify the new endpoint appears**

```bash
curl http://localhost:8000/docs
# Look for POST /api/v1/ocr in the Swagger UI
```

- [ ] **Step 4: Commit**
```bash
git add nra-tax-engine/src/api/ocr_endpoint.py nra-tax-engine/src/api/main.py
git commit -m "feat: POST /api/v1/ocr endpoint — multipart document OCR extraction"
```

---

## Task 3: Store — add eligibility, travelHistory, ocrResult slices

**Files:**
- Modify: `nra-tax-client/src/store/taxStore.ts`

- [ ] **Step 1: Add new interfaces and state to taxStore.ts**

At the top of `nra-tax-client/src/store/taxStore.ts`, after the existing type imports, add:

```typescript
// ── New intake state types ──────────────────────────────────────────────────

export interface EligibilityAnswers {
  isUsCitizen: boolean | null;
  isGreenCardHolder: boolean | null;
  hasAppliedForResidence: boolean | null;
}

export interface TravelEntry {
  visaType: string;
  entryDate: string;  // YYYY-MM-DD
  leaveDate: string;  // YYYY-MM-DD or '' if still in US
}

export interface VisaDetails {
  visaType: string;
  visaIssueDate: string;
  visaExpiryDate: string;
  programStartDate: string;
  programEndDate: string;
  firstUsEntryDate: string;
  intendedDepartureDate: string;
  countryOfCitizenship: string;
  countryOfResidenceBeforeUs: string;
  changedVisaDuring2025: boolean | null;
  isStillInUs: boolean | null;
  travelHistory: TravelEntry[];
}

// OcrResult mirrors the backend OcrResult model
export interface W2Extracted {
  box_1_wages: number;
  box_2_fed_withholding: number;
  box_3_ss_wages: number;
  box_4_ss_withheld: number;
  box_5_medicare_wages: number;
  box_6_medicare_withheld: number;
  box_17_state_income_tax: number;
  box_18_local_wages: number;
  box_19_local_income_tax: number;
  box_20_locality_name: string;
  employer_name: string;
  employer_ein: string;
  employee_name: string;
  employee_ssn_or_itin: string;
  tax_year: number;
}

export interface Form1042SExtracted {
  income_code: number;
  gross_income: number;
  exemption_rate: number;
  exemption_code: string;
  fed_withheld: number;
  chapter_indicator: number;
  recipient_name: string;
  withholding_agent_name: string;
}

export interface Form1099Extracted {
  form_kind: string;
  gross_amount: number;
  fed_withholding: number;
  payer_name: string;
}

export interface I94Extracted {
  days_current_year: number;
  days_minus_1: number;
  days_minus_2: number;
  latest_entry_date: string;
  latest_class_of_admission: string;
}

export interface OcrResult {
  i94: I94Extracted | null;
  w2s: W2Extracted[];
  form_1042s: Form1042SExtracted[];
  form_1099s: Form1099Extracted[];
}

export interface ExtrasAnswers {
  isFullTimeStudent: boolean | null;
  isDegreeCandidate: boolean | null;
  isOptCpt: boolean | null;
  hadDigitalAssets: boolean | null;
  canBeClaimedAsDependent: boolean | null;
  wasMarriedOnLastDay: boolean | null;
  madeEstimatedFederalPayments: boolean | null;
  estimatedFederalPaymentAmount: number;
  madeEstimatedStatePayments: boolean | null;
  filedFederalExtension: boolean | null;
  filedPreviousFederalReturn: boolean | null;
  previousReturnYear: number | null;
  previousReturnType: string;
}
```

- [ ] **Step 2: Add initial values and interface to TaxState**

Add initial values:
```typescript
const initialEligibility: EligibilityAnswers = {
  isUsCitizen: null,
  isGreenCardHolder: null,
  hasAppliedForResidence: null,
};

const initialVisaDetails: VisaDetails = {
  visaType: 'F-1',
  visaIssueDate: '',
  visaExpiryDate: '',
  programStartDate: '',
  programEndDate: '',
  firstUsEntryDate: '',
  intendedDepartureDate: '',
  countryOfCitizenship: '',
  countryOfResidenceBeforeUs: '',
  changedVisaDuring2025: null,
  isStillInUs: null,
  travelHistory: [],
};

const initialExtras: ExtrasAnswers = {
  isFullTimeStudent: null,
  isDegreeCandidate: null,
  isOptCpt: null,
  hadDigitalAssets: null,
  canBeClaimedAsDependent: null,
  wasMarriedOnLastDay: null,
  madeEstimatedFederalPayments: null,
  estimatedFederalPaymentAmount: 0,
  madeEstimatedStatePayments: null,
  filedFederalExtension: null,
  filedPreviousFederalReturn: null,
  previousReturnYear: null,
  previousReturnType: '',
};
```

In `TaxState` interface, add:
```typescript
  eligibility: EligibilityAnswers;
  visaDetails: VisaDetails;
  extras: ExtrasAnswers;
  ocrResult: OcrResult | null;

  updateEligibility: (updates: Partial<EligibilityAnswers>) => void;
  updateVisaDetails: (updates: Partial<VisaDetails>) => void;
  updateExtras: (updates: Partial<ExtrasAnswers>) => void;
  setOcrResult: (result: OcrResult) => void;
```

In the store implementation, add:
```typescript
  eligibility: { ...initialEligibility },
  visaDetails: { ...initialVisaDetails },
  extras: { ...initialExtras },
  ocrResult: null,

  updateEligibility: (updates) =>
    set((state) => ({ eligibility: { ...state.eligibility, ...updates } })),
  updateVisaDetails: (updates) =>
    set((state) => ({ visaDetails: { ...state.visaDetails, ...updates } })),
  updateExtras: (updates) =>
    set((state) => ({ extras: { ...state.extras, ...updates } })),
  setOcrResult: (result) => set({ ocrResult: result }),
```

In `reset()`, add:
```typescript
  eligibility: { ...initialEligibility },
  visaDetails: { ...initialVisaDetails },
  extras: { ...initialExtras },
  ocrResult: null,
```

In `persist` `partialize`, add:
```typescript
  eligibility: state.eligibility,
  visaDetails: state.visaDetails,
  extras: state.extras,
  ocrResult: state.ocrResult,
```

- [ ] **Step 3: Commit**
```bash
git add nra-tax-client/src/store/taxStore.ts
git commit -m "feat: add eligibility, visaDetails, extras, ocrResult slices to store"
```

---

## Task 4: Frontend — `api.ts` OCR client function

**Files:**
- Modify: `nra-tax-client/src/lib/api.ts`

- [ ] **Step 1: Add `extractDocuments` function**

Add to `nra-tax-client/src/lib/api.ts`:

```typescript
import type { OcrResult } from '@/store/taxStore';

export interface ExtractDocumentsArgs {
  taxYear: number;
  i94File?: File | null;
  w2Files?: File[];
  form1042sFiles?: File[];
  form1099Files?: File[];
}

/** Call POST /api/v1/ocr — upload documents, get structured extracted fields back. */
export async function extractDocuments(args: ExtractDocumentsArgs): Promise<OcrResult> {
  const form = new FormData();
  form.append('tax_year', String(args.taxYear));
  if (args.i94File) form.append('i94_file', args.i94File);
  (args.w2Files ?? []).forEach((f) => form.append('w2_files', f));
  (args.form1042sFiles ?? []).forEach((f) => form.append('form_1042s_files', f));
  (args.form1099Files ?? []).forEach((f) => form.append('form_1099_files', f));

  try {
    const r = await axios.post<OcrResult>(`${API_BASE_URL}/ocr`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return r.data;
  } catch (err) {
    const ax = err as AxiosError<{ detail?: string }>;
    throw new Error(ax.response?.data?.detail ?? ax.message ?? 'OCR extraction failed.');
  }
}
```

- [ ] **Step 2: Commit**
```bash
git add nra-tax-client/src/lib/api.ts
git commit -m "feat: extractDocuments() client function for OCR endpoint"
```

---

## Task 5: Component — `YesNoToggle`

**Files:**
- Create: `nra-tax-client/src/components/YesNoToggle.tsx`

- [ ] **Step 1: Create the component**

Create `nra-tax-client/src/components/YesNoToggle.tsx`:

```tsx
'use client';

interface YesNoToggleProps {
  label: string;
  sublabel?: string;
  value: boolean | null;
  onChange: (v: boolean) => void;
}

export function YesNoToggle({ label, sublabel, value, onChange }: YesNoToggleProps) {
  return (
    <div className="space-y-2">
      <div>
        <p className="font-semibold text-slate-800 text-sm leading-snug">{label}</p>
        {sublabel && <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{sublabel}</p>}
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onChange(true)}
          className={`flex-1 h-11 rounded-xl font-bold text-sm border-2 transition-all ${
            value === true
              ? 'bg-blue-600 border-blue-600 text-white shadow-md shadow-blue-100'
              : 'bg-white border-slate-200 text-slate-600 hover:border-blue-300'
          }`}
        >
          Yes
        </button>
        <button
          type="button"
          onClick={() => onChange(false)}
          className={`flex-1 h-11 rounded-xl font-bold text-sm border-2 transition-all ${
            value === false
              ? 'bg-slate-800 border-slate-800 text-white shadow-md shadow-slate-100'
              : 'bg-white border-slate-200 text-slate-600 hover:border-slate-400'
          }`}
        >
          No
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**
```bash
git add nra-tax-client/src/components/YesNoToggle.tsx
git commit -m "feat: YesNoToggle component — Sprintax-style yes/no selector"
```

---

## Task 6: Component — `TravelHistoryTable`

**Files:**
- Create: `nra-tax-client/src/components/TravelHistoryTable.tsx`

- [ ] **Step 1: Create the component**

Create `nra-tax-client/src/components/TravelHistoryTable.tsx`:

```tsx
'use client';

import { Plus, Trash2 } from 'lucide-react';
import type { TravelEntry } from '@/store/taxStore';

interface TravelHistoryTableProps {
  entries: TravelEntry[];
  onChange: (entries: TravelEntry[]) => void;
}

const VISA_TYPES = ['F-1', 'J-1', 'M-1', 'Q-1', 'H-1B', 'B-1/B-2', 'Other'];

export function TravelHistoryTable({ entries, onChange }: TravelHistoryTableProps) {
  const add = () =>
    onChange([...entries, { visaType: 'F-1', entryDate: '', leaveDate: '' }]);

  const update = (i: number, field: keyof TravelEntry, value: string) =>
    onChange(entries.map((e, idx) => (idx === i ? { ...e, [field]: value } : e)));

  const remove = (i: number) => onChange(entries.filter((_, idx) => idx !== i));

  const inputCls =
    'w-full h-9 bg-white border border-slate-200 rounded-lg px-2 text-xs focus:ring-1 focus:ring-blue-400 outline-none';
  const selectCls = `${inputCls} cursor-pointer`;

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="text-left px-3 py-2 font-bold text-slate-600 w-28">Visa Type</th>
              <th className="text-left px-3 py-2 font-bold text-slate-600">Entry Date</th>
              <th className="text-left px-3 py-2 font-bold text-slate-600">Leave Date</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {entries.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-center text-slate-400">
                  No entries yet — add your US visits below
                </td>
              </tr>
            )}
            {entries.map((entry, i) => (
              <tr key={i}>
                <td className="px-2 py-2">
                  <select
                    className={selectCls}
                    value={entry.visaType}
                    onChange={(e) => update(i, 'visaType', e.target.value)}
                  >
                    {VISA_TYPES.map((v) => (
                      <option key={v} value={v}>
                        {v}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-2 py-2">
                  <input
                    type="date"
                    className={inputCls}
                    value={entry.entryDate}
                    onChange={(e) => update(i, 'entryDate', e.target.value)}
                  />
                </td>
                <td className="px-2 py-2">
                  <input
                    type="date"
                    className={inputCls}
                    value={entry.leaveDate}
                    placeholder="Still in US"
                    onChange={(e) => update(i, 'leaveDate', e.target.value)}
                  />
                </td>
                <td className="px-2 py-2">
                  <button
                    type="button"
                    onClick={() => remove(i)}
                    className="text-slate-300 hover:text-red-500 transition-colors p-1"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        type="button"
        onClick={add}
        className="flex items-center gap-1.5 text-xs font-bold text-blue-600 hover:text-blue-800 transition-colors px-1"
      >
        <Plus className="w-3.5 h-3.5" />
        Add visit
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Commit**
```bash
git add nra-tax-client/src/components/TravelHistoryTable.tsx
git commit -m "feat: TravelHistoryTable — editable entry/exit date grid for visa step"
```

---

## Task 7: Component — `OcrDocumentCard`

**Files:**
- Create: `nra-tax-client/src/components/OcrDocumentCard.tsx`

- [ ] **Step 1: Create the component**

Create `nra-tax-client/src/components/OcrDocumentCard.tsx`:

```tsx
'use client';

import { CheckCircle2, FileText } from 'lucide-react';
import { inputCls } from './FormField';

interface Field {
  key: string;
  label: string;
  value: string | number;
  type?: 'number' | 'text';
}

interface OcrDocumentCardProps {
  title: string;
  subtitle?: string;
  fields: Field[];
  confirmed: boolean;
  onFieldChange: (key: string, value: string) => void;
  onConfirm: () => void;
}

export function OcrDocumentCard({
  title,
  subtitle,
  fields,
  confirmed,
  onFieldChange,
  onConfirm,
}: OcrDocumentCardProps) {
  return (
    <div
      className={`bg-white border-2 rounded-3xl overflow-hidden transition-all ${
        confirmed ? 'border-green-300 shadow-green-50 shadow-lg' : 'border-slate-200'
      }`}
    >
      {/* Header */}
      <div className={`px-5 py-4 flex items-center gap-3 ${confirmed ? 'bg-green-50' : 'bg-slate-50'}`}>
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${confirmed ? 'bg-green-100' : 'bg-white'}`}>
          <FileText className={`w-5 h-5 ${confirmed ? 'text-green-600' : 'text-blue-500'}`} />
        </div>
        <div className="flex-1">
          <p className="font-bold text-slate-900 text-sm">{title}</p>
          {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        </div>
        {confirmed && <CheckCircle2 className="w-5 h-5 text-green-500" />}
      </div>

      {/* Fields */}
      <div className="p-5 grid grid-cols-2 gap-3">
        {fields.map((field) => (
          <div key={field.key} className="space-y-1">
            <label className="text-xs font-semibold text-slate-500 block">{field.label}</label>
            <input
              type={field.type ?? 'text'}
              value={field.value}
              onChange={(e) => onFieldChange(field.key, e.target.value)}
              className={`${inputCls} h-10 text-sm`}
              step={field.type === 'number' ? '0.01' : undefined}
            />
          </div>
        ))}
      </div>

      {/* Confirm */}
      {!confirmed && (
        <div className="px-5 pb-5">
          <button
            type="button"
            onClick={onConfirm}
            className="w-full h-11 bg-blue-600 text-white rounded-xl font-bold text-sm hover:bg-blue-500 active:scale-95 transition-all"
          >
            ✓ Looks correct
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**
```bash
git add nra-tax-client/src/components/OcrDocumentCard.tsx
git commit -m "feat: OcrDocumentCard — editable extracted field card with confirm button"
```

---

## Task 8: Page — Eligibility (Step 1)

**Files:**
- Create: `nra-tax-client/src/app/intake/eligibility/page.tsx`

- [ ] **Step 1: Create the page**

Create `nra-tax-client/src/app/intake/eligibility/page.tsx`:

```tsx
'use client';

import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import { ChevronRight, ShieldCheck } from 'lucide-react';
import { YesNoToggle } from '@/components/YesNoToggle';

export default function EligibilityPage() {
  const router = useRouter();
  const { eligibility, updateEligibility } = useTaxStore();

  const allAnswered =
    eligibility.isUsCitizen !== null &&
    eligibility.isGreenCardHolder !== null &&
    eligibility.hasAppliedForResidence !== null;

  const isIneligible =
    eligibility.isUsCitizen === true || eligibility.isGreenCardHolder === true;

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    if (isIneligible) return;
    router.push('/intake/visa');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-10 text-center">
        <div className="w-14 h-14 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-200">
          <ShieldCheck className="text-white w-7 h-7" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Eligibility Check</h1>
        <p className="text-slate-500 text-sm mt-1">
          QuadTax is for nonresident aliens filing Form 1040-NR.
        </p>
      </header>

      <form onSubmit={handleNext} className="max-w-md mx-auto w-full space-y-7">

        <YesNoToggle
          label="Have you been a US citizen (by birth or naturalization) on the last day of 2025?"
          value={eligibility.isUsCitizen}
          onChange={(v) => updateEligibility({ isUsCitizen: v })}
        />

        {eligibility.isUsCitizen === true && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-sm text-red-800">
            US citizens must file Form 1040, not 1040-NR. QuadTax is designed for
            nonresident aliens. Please use a service like TurboTax or FreeTaxUSA.
          </div>
        )}

        <YesNoToggle
          label="Have you ever been a green card holder (lawful permanent resident)?"
          value={eligibility.isGreenCardHolder}
          onChange={(v) => updateEligibility({ isGreenCardHolder: v })}
        />

        {eligibility.isGreenCardHolder === true && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-amber-800">
            Green card holders are taxed as US residents on worldwide income. You
            likely need Form 1040, not 1040-NR. Consult a CPA to confirm.
          </div>
        )}

        <YesNoToggle
          label="Have you ever applied for US citizenship or lawful permanent residence?"
          sublabel="This affects the saving clause in some tax treaties."
          value={eligibility.hasAppliedForResidence}
          onChange={(v) => updateEligibility({ hasAppliedForResidence: v })}
        />

        {allAnswered && !isIneligible && (
          <div className="bg-green-50 border border-green-200 rounded-2xl p-4 text-sm text-green-800 font-medium">
            ✓ You qualify to file as a Nonresident Alien on Form 1040-NR.
          </div>
        )}

        <button
          type="submit"
          disabled={!allAnswered || isIneligible}
          className="w-full h-14 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800 active:scale-95 transition-all"
        >
          Continue
          <ChevronRight className="w-6 h-6" />
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Redirect old `/intake/profile` → `/intake/eligibility`**

Replace `nra-tax-client/src/app/intake/profile/page.tsx` with a redirect:

```tsx
import { redirect } from 'next/navigation';

export default function ProfileRedirect() {
  redirect('/intake/eligibility');
}
```

- [ ] **Step 3: Commit**
```bash
git add nra-tax-client/src/app/intake/eligibility/ nra-tax-client/src/app/intake/profile/page.tsx
git commit -m "feat: eligibility gating page (Step 1) — US citizen / GC / residence check"
```

---

## Task 9: Page — Visa & Travel (Step 2)

**Files:**
- Create: `nra-tax-client/src/app/intake/visa/page.tsx`

- [ ] **Step 1: Create the page**

Create `nra-tax-client/src/app/intake/visa/page.tsx`:

```tsx
'use client';

import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import { ChevronRight, Plane } from 'lucide-react';
import { FormField, inputCls, selectCls } from '@/components/FormField';
import { CountrySelect } from '@/components/CountrySelect';
import { TravelHistoryTable } from '@/components/TravelHistoryTable';
import { YesNoToggle } from '@/components/YesNoToggle';

export default function VisaPage() {
  const router = useRouter();
  const { visaDetails, updateVisaDetails, updateIdentity, updateResidency } = useTaxStore();

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    // Sync key fields back to the standard identity/residency so the engine gets them
    updateIdentity({
      country_of_citizenship: visaDetails.countryOfCitizenship,
      country_of_tax_residence: visaDetails.countryOfResidenceBeforeUs,
    });
    updateResidency({
      visa_type: visaDetails.visaType,
      first_us_arrival_year: visaDetails.firstUsEntryDate
        ? parseInt(visaDetails.firstUsEntryDate.slice(0, 4))
        : new Date().getFullYear() - 1,
    });
    router.push('/intake/documents');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-8 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-200">
          <Plane className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Visa & Travel</h1>
        <p className="text-slate-500 text-sm mt-1">
          Tell us about your visa and time in the US.
        </p>
      </header>

      <form onSubmit={handleNext} className="max-w-md mx-auto w-full space-y-6">

        {/* ── Was in US in 2025? ── */}
        <YesNoToggle
          label="Were you in the US during the 2025 tax year?"
          value={visaDetails.isStillInUs !== null ? true : null}
          onChange={() => {}}
        />

        {/* ── Visa type ── */}
        <FormField label="Current Visa Type" required>
          <select
            className={selectCls}
            value={visaDetails.visaType}
            onChange={(e) => updateVisaDetails({ visaType: e.target.value })}
            required
          >
            <option value="F-1">F-1 — Student</option>
            <option value="J-1">J-1 — Exchange Visitor (Student)</option>
            <option value="J-1-R">J-1 — Exchange Visitor (Researcher/Teacher)</option>
            <option value="M-1">M-1 — Vocational Student</option>
            <option value="Q-1">Q-1 — Cultural Exchange</option>
            <option value="H-1B">H-1B — Specialty Occupation</option>
          </select>
        </FormField>

        {/* ── Program dates (I-20 / DS-2019) ── */}
        <div className="border border-slate-200 rounded-2xl p-4 bg-white space-y-4">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Program Dates (I-20 or DS-2019)
          </p>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Visa Issue Date">
              <input type="date" className={inputCls}
                value={visaDetails.visaIssueDate}
                onChange={(e) => updateVisaDetails({ visaIssueDate: e.target.value })} />
            </FormField>
            <FormField label="Visa Expiry Date">
              <input type="date" className={inputCls}
                value={visaDetails.visaExpiryDate}
                onChange={(e) => updateVisaDetails({ visaExpiryDate: e.target.value })} />
            </FormField>
            <FormField label="Program Start Date">
              <input type="date" className={inputCls}
                value={visaDetails.programStartDate}
                onChange={(e) => updateVisaDetails({ programStartDate: e.target.value })} />
            </FormField>
            <FormField label="Program End Date">
              <input type="date" className={inputCls}
                value={visaDetails.programEndDate}
                onChange={(e) => updateVisaDetails({ programEndDate: e.target.value })} />
            </FormField>
          </div>
          <FormField label="Date You First Entered the US" required>
            <input type="date" className={inputCls}
              value={visaDetails.firstUsEntryDate}
              onChange={(e) => updateVisaDetails({ firstUsEntryDate: e.target.value })}
              required />
          </FormField>
          <FormField label="Intended Departure / Program End Date">
            <input type="date" className={inputCls}
              value={visaDetails.intendedDepartureDate}
              onChange={(e) => updateVisaDetails({ intendedDepartureDate: e.target.value })} />
          </FormField>
        </div>

        {/* ── Countries ── */}
        <FormField label="Country of Citizenship" required>
          <CountrySelect
            value={visaDetails.countryOfCitizenship}
            onChange={(v) => updateVisaDetails({ countryOfCitizenship: v })}
            required
          />
        </FormField>

        <FormField
          label="Country of Residence Before Entering the US"
          hint="Used for tax treaty determination."
          required
        >
          <CountrySelect
            value={visaDetails.countryOfResidenceBeforeUs}
            onChange={(v) => updateVisaDetails({ countryOfResidenceBeforeUs: v })}
            required
          />
        </FormField>

        {/* ── Still in US ── */}
        <YesNoToggle
          label="Are you still in the US?"
          value={visaDetails.isStillInUs}
          onChange={(v) => updateVisaDetails({ isStillInUs: v })}
        />

        {/* ── Changed visa ── */}
        <YesNoToggle
          label="Did you change your visa type during 2025?"
          sublabel="E.g. changed from F-1 student to H-1B worker."
          value={visaDetails.changedVisaDuring2025}
          onChange={(v) => updateVisaDetails({ changedVisaDuring2025: v })}
        />

        {/* ── Travel history ── */}
        <div className="space-y-2">
          <p className="text-sm font-bold text-slate-700">
            US Travel History
            <span className="ml-1 font-normal text-slate-400 text-xs">(all visits from first arrival)</span>
          </p>
          <p className="text-xs text-slate-500 leading-relaxed">
            Add each trip — entry and exit date. Leave "Leave Date" empty if you are still in the US for that visit.
          </p>
          <TravelHistoryTable
            entries={visaDetails.travelHistory}
            onChange={(entries) => updateVisaDetails({ travelHistory: entries })}
          />
        </div>

        <button
          type="submit"
          className="w-full h-14 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 hover:bg-slate-800 active:scale-95 transition-all shadow-xl shadow-slate-200"
        >
          Next: Upload Documents
          <ChevronRight className="w-6 h-6" />
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Commit**
```bash
git add nra-tax-client/src/app/intake/visa/
git commit -m "feat: visa & travel page (Step 2) — visa type, program dates, travel history, countries"
```

---

## Task 10: Page — Documents with Scan Button (Step 3)

**Files:**
- Modify: `nra-tax-client/src/app/intake/documents/page.tsx`

- [ ] **Step 1: Rewrite the documents page**

Replace `nra-tax-client/src/app/intake/documents/page.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import { FileUp, Trash2, FileCheck, Info, Sparkles, Loader2 } from 'lucide-react';
import { extractDocuments } from '@/lib/api';

function FileCard({ label, file, onClear }: { label: string; file: File; onClear: () => void }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-3 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 bg-green-50 rounded-full flex items-center justify-center shrink-0">
          <FileCheck className="text-green-600 w-4 h-4" />
        </div>
        <div>
          <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">{label}</p>
          <p className="text-slate-800 font-medium truncate max-w-[180px] text-sm">{file.name}</p>
        </div>
      </div>
      <button type="button" onClick={onClear}
        className="text-slate-300 hover:text-red-500 transition-colors p-2 rounded-full hover:bg-red-50">
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  );
}

function DropZone({ label, multiple, onChange }: {
  label: string; multiple?: boolean; onChange: (files: File[]) => void;
}) {
  return (
    <label className="flex flex-col items-center justify-center w-full h-20 border-2 border-dashed border-slate-200 rounded-2xl bg-white hover:bg-slate-50 hover:border-blue-300 cursor-pointer transition-all">
      <FileUp className="w-5 h-5 text-blue-400 mb-1" />
      <span className="text-xs font-semibold text-slate-500">{label}</span>
      <input type="file" className="hidden" multiple={multiple}
        accept="image/*,application/pdf" capture="environment"
        onChange={(e) => { if (e.target.files) { onChange(Array.from(e.target.files)); e.target.value = ''; } }} />
    </label>
  );
}

export default function DocumentsPage() {
  const router = useRouter();
  const {
    i94File, setI94File,
    w2Files, addW2File, removeW2File,
    form1042sFiles, addForm1042sFile, removeForm1042sFile,
    residency, setOcrResult,
  } = useTaxStore();

  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);

  // 1099 files (local state only — added to store in OCR review)
  const [form1099Files, setForm1099Files] = useState<File[]>([]);

  const hasAtLeastOneDoc = i94File || w2Files.length > 0 || form1042sFiles.length > 0;

  const handleScan = async () => {
    if (!i94File && w2Files.length === 0 && form1042sFiles.length === 0) {
      setScanError('Upload at least one document before scanning.');
      return;
    }
    setScanError(null);
    setScanning(true);
    try {
      const result = await extractDocuments({
        taxYear: residency.tax_year,
        i94File,
        w2Files,
        form1042sFiles,
        form1099Files,
      });
      setOcrResult(result);
      router.push('/intake/ocr-review');
    } catch (err) {
      setScanError(err instanceof Error ? err.message : 'Scanning failed. Please try again.');
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-8 text-center">
        <h1 className="text-2xl font-bold text-slate-900">Upload Documents</h1>
        <p className="text-slate-500 text-sm mt-1">
          Upload your tax documents — our AI will extract all the numbers automatically.
        </p>
      </header>

      <div className="space-y-7 max-w-md mx-auto w-full">

        {/* ── I-94 ── */}
        <div className="space-y-2">
          <label className="text-sm font-bold text-slate-700 flex items-center gap-2">
            I-94 Travel History
            <span className="text-red-500 font-normal text-xs italic">(Required for residency test)</span>
          </label>
          {i94File
            ? <FileCard label="I-94" file={i94File} onClear={() => setI94File(null)} />
            : <DropZone label="Snap photo or upload I-94 PDF" onChange={(f) => setI94File(f[0])} />}
        </div>

        {/* ── W-2 ── */}
        <div className="space-y-2">
          <label className="text-sm font-bold text-slate-700">
            W-2 Forms <span className="text-slate-400 font-normal text-xs">(one per employer)</span>
          </label>
          <div className="space-y-2">
            {w2Files.map((f, i) => <FileCard key={i} label="W-2" file={f} onClear={() => removeW2File(i)} />)}
            <DropZone label="+ Add W-2 Form" multiple onChange={(fs) => fs.forEach(addW2File)} />
          </div>
        </div>

        {/* ── 1042-S ── */}
        <div className="space-y-2">
          <label className="text-sm font-bold text-slate-700">
            1042-S Forms <span className="text-slate-400 font-normal text-xs">(scholarships, fellowships)</span>
          </label>
          <div className="space-y-2">
            {form1042sFiles.map((f, i) => <FileCard key={i} label="1042-S" file={f} onClear={() => removeForm1042sFile(i)} />)}
            <DropZone label="+ Add 1042-S Form" multiple onChange={(fs) => fs.forEach(addForm1042sFile)} />
          </div>
        </div>

        {/* ── 1099 ── */}
        <div className="space-y-2">
          <label className="text-sm font-bold text-slate-700">
            1099 Forms <span className="text-slate-400 font-normal text-xs">(interest, dividends, misc income)</span>
          </label>
          <div className="space-y-2">
            {form1099Files.map((f, i) => (
              <FileCard key={i} label="1099" file={f}
                onClear={() => setForm1099Files((prev) => prev.filter((_, idx) => idx !== i))} />
            ))}
            <DropZone label="+ Add 1099 Form" multiple
              onChange={(fs) => setForm1099Files((prev) => [...prev, ...fs])} />
          </div>
        </div>

        <div className="bg-slate-100 rounded-2xl p-4 flex gap-3">
          <Info className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
          <p className="text-xs text-slate-500 leading-relaxed">
            Upload clear, well-lit photos or PDFs. All four corners must be visible. We extract all
            box values automatically — you will review and confirm them on the next screen.
          </p>
        </div>

        {scanError && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-3 text-xs text-red-800">
            {scanError}
          </div>
        )}
      </div>

      {/* ── Scan Button ── */}
      <div className="fixed bottom-0 left-0 right-0 p-5 bg-white/90 backdrop-blur border-t border-slate-100">
        <button
          onClick={handleScan}
          disabled={scanning || !hasAtLeastOneDoc}
          className="w-full h-14 bg-blue-600 text-white rounded-2xl font-bold text-base flex items-center justify-center gap-3 max-w-md mx-auto shadow-2xl shadow-blue-200 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {scanning ? (
            <><Loader2 className="w-5 h-5 animate-spin" /> Scanning documents…</>
          ) : (
            <><Sparkles className="w-5 h-5" /> Scan All Documents</>
          )}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**
```bash
git add nra-tax-client/src/app/intake/documents/page.tsx
git commit -m "feat: documents page (Step 3) — multi-doc upload with AI scan button"
```

---

## Task 11: Page — OCR Review (Step 4)

**Files:**
- Create: `nra-tax-client/src/app/intake/ocr-review/page.tsx`

- [ ] **Step 1: Create the page**

Create `nra-tax-client/src/app/intake/ocr-review/page.tsx`:

```tsx
'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import type { W2Extracted, Form1042SExtracted, I94Extracted } from '@/store/taxStore';
import { OcrDocumentCard } from '@/components/OcrDocumentCard';
import { ChevronRight, Sparkles } from 'lucide-react';

export default function OcrReviewPage() {
  const router = useRouter();
  const { ocrResult, setOcrResult, updateIdentity, updateIncome } = useTaxStore();

  // Local editable copies of each document
  const [w2s, setW2s] = useState<W2Extracted[]>(ocrResult?.w2s ?? []);
  const [form1042s, setForm1042s] = useState<Form1042SExtracted[]>(ocrResult?.form_1042s ?? []);
  const [i94, setI94] = useState<I94Extracted | null>(ocrResult?.i94 ?? null);

  // Which cards have been confirmed
  const [confirmedW2, setConfirmedW2] = useState<boolean[]>([]);
  const [confirmedF1042s, setConfirmedF1042s] = useState<boolean[]>([]);
  const [confirmedI94, setConfirmedI94] = useState(false);

  useEffect(() => {
    setConfirmedW2(new Array(w2s.length).fill(false));
    setConfirmedF1042s(new Array(form1042s.length).fill(false));
  }, []);

  if (!ocrResult) {
    router.push('/intake/documents');
    return null;
  }

  const allConfirmed =
    (w2s.length === 0 || confirmedW2.every(Boolean)) &&
    (form1042s.length === 0 || confirmedF1042s.every(Boolean)) &&
    (i94 === null || confirmedI94);

  const updateW2Field = (idx: number, key: string, val: string) =>
    setW2s((prev) => prev.map((w, i) => i === idx ? { ...w, [key]: isNaN(Number(val)) ? val : Number(val) } : w));

  const updateF1042sField = (idx: number, key: string, val: string) =>
    setForm1042s((prev) => prev.map((f, i) => i === idx ? { ...f, [key]: isNaN(Number(val)) ? val : Number(val) } : f));

  const handleContinue = () => {
    // Auto-fill identity from first W-2
    if (w2s.length > 0) {
      const firstW2 = w2s[0];
      if (firstW2.employee_name) {
        const parts = firstW2.employee_name.trim().split(/\s+/);
        updateIdentity({
          first_name: parts[0] ?? '',
          last_name: parts.slice(1).join(' ') || '',
          ssn: firstW2.employee_ssn_or_itin?.replace(/\D/g, '') ?? '',
        });
      }
    }
    // Save confirmed OCR data back to store for the pipeline
    setOcrResult({ ...ocrResult, w2s, form_1042s: form1042s, i94 });
    router.push('/intake/personal');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-8 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-200">
          <Sparkles className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Review Extracted Data</h1>
        <p className="text-slate-500 text-sm mt-1">
          Our AI read your documents. Check each field and tap "Looks correct" to confirm.
        </p>
      </header>

      <div className="max-w-md mx-auto w-full space-y-5">

        {/* ── I-94 Card ── */}
        {i94 && (
          <OcrDocumentCard
            title="I-94 Travel History"
            subtitle="Days present in the US per year"
            confirmed={confirmedI94}
            onConfirm={() => setConfirmedI94(true)}
            onFieldChange={(key, val) => setI94((prev) => prev ? { ...prev, [key]: Number(val) } : prev)}
            fields={[
              { key: 'days_current_year', label: 'Days in US (2025)', value: i94.days_current_year, type: 'number' },
              { key: 'days_minus_1', label: 'Days in US (2024)', value: i94.days_minus_1, type: 'number' },
              { key: 'days_minus_2', label: 'Days in US (2023)', value: i94.days_minus_2, type: 'number' },
              { key: 'latest_entry_date', label: 'Latest Entry Date', value: i94.latest_entry_date },
              { key: 'latest_class_of_admission', label: 'Visa Class', value: i94.latest_class_of_admission },
            ]}
          />
        )}

        {/* ── W-2 Cards ── */}
        {w2s.map((w2, i) => (
          <OcrDocumentCard
            key={i}
            title={`W-2 Form ${w2s.length > 1 ? `#${i + 1}` : ''}`}
            subtitle={w2.employer_name || 'Employer wages'}
            confirmed={confirmedW2[i] ?? false}
            onConfirm={() => setConfirmedW2((prev) => prev.map((v, idx) => idx === i ? true : v))}
            onFieldChange={(key, val) => updateW2Field(i, key, val)}
            fields={[
              { key: 'employer_name', label: 'Employer Name', value: w2.employer_name },
              { key: 'employer_ein', label: 'Employer EIN', value: w2.employer_ein },
              { key: 'employee_name', label: 'Employee Name', value: w2.employee_name },
              { key: 'employee_ssn_or_itin', label: 'SSN / ITIN', value: w2.employee_ssn_or_itin },
              { key: 'box_1_wages', label: 'Box 1 — Wages', value: w2.box_1_wages, type: 'number' },
              { key: 'box_2_fed_withholding', label: 'Box 2 — Fed Withheld', value: w2.box_2_fed_withholding, type: 'number' },
              { key: 'box_4_ss_withheld', label: 'Box 4 — SS Withheld', value: w2.box_4_ss_withheld, type: 'number' },
              { key: 'box_6_medicare_withheld', label: 'Box 6 — Medicare Withheld', value: w2.box_6_medicare_withheld, type: 'number' },
              { key: 'box_17_state_income_tax', label: 'Box 17 — State Tax', value: w2.box_17_state_income_tax, type: 'number' },
              { key: 'box_19_local_income_tax', label: 'Box 19 — Local Tax', value: w2.box_19_local_income_tax, type: 'number' },
              { key: 'box_20_locality_name', label: 'Box 20 — Locality', value: w2.box_20_locality_name },
            ]}
          />
        ))}

        {/* ── 1042-S Cards ── */}
        {form1042s.map((f, i) => (
          <OcrDocumentCard
            key={i}
            title={`1042-S Form ${form1042s.length > 1 ? `#${i + 1}` : ''}`}
            subtitle={f.withholding_agent_name || 'Scholarship / fellowship income'}
            confirmed={confirmedF1042s[i] ?? false}
            onConfirm={() => setConfirmedF1042s((prev) => prev.map((v, idx) => idx === i ? true : v))}
            onFieldChange={(key, val) => updateF1042sField(i, key, val)}
            fields={[
              { key: 'withholding_agent_name', label: 'Payer Name', value: f.withholding_agent_name },
              { key: 'income_code', label: 'Box 1 — Income Code', value: f.income_code, type: 'number' },
              { key: 'gross_income', label: 'Box 2 — Gross Income', value: f.gross_income, type: 'number' },
              { key: 'fed_withheld', label: 'Box 7a — Fed Withheld', value: f.fed_withheld, type: 'number' },
              { key: 'exemption_code', label: 'Box 3b — Exemption Code', value: f.exemption_code },
            ]}
          />
        ))}

        {w2s.length === 0 && form1042s.length === 0 && !i94 && (
          <div className="bg-amber-50 border border-amber-200 rounded-3xl p-5 text-sm text-amber-800">
            No data was extracted. This can happen if documents were blurry or in an unsupported format.
            Go back and try uploading clearer photos.
          </div>
        )}

        <div className="bg-blue-50 border border-blue-100 rounded-2xl p-4 text-xs text-blue-700 leading-relaxed">
          <strong>These values will be used directly in your tax return.</strong> Please correct any
          errors — especially Box 1 wages and Box 2 withholding.
        </div>

        <button
          onClick={handleContinue}
          disabled={!allConfirmed && (w2s.length > 0 || form1042s.length > 0 || i94 !== null)}
          className="w-full h-14 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 disabled:opacity-40 hover:bg-slate-800 active:scale-95 transition-all"
        >
          All Confirmed — Continue
          <ChevronRight className="w-6 h-6" />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**
```bash
git add nra-tax-client/src/app/intake/ocr-review/
git commit -m "feat: OCR review page (Step 4) — auto-filled editable cards per document"
```

---

## Task 12: Page — Personal Details (Step 4b)

The OCR review auto-fills name/SSN from the W-2. This page collects what OCR can't supply: passport, foreign address, occupation.

**Files:**
- Create: `nra-tax-client/src/app/intake/personal/page.tsx`

- [ ] **Step 1: Create the page**

Create `nra-tax-client/src/app/intake/personal/page.tsx`:

```tsx
'use client';

import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import { ChevronRight, User } from 'lucide-react';
import { FormField, inputCls, selectCls } from '@/components/FormField';
import { CountrySelect } from '@/components/CountrySelect';

export default function PersonalPage() {
  const router = useRouter();
  const { identity, updateIdentity } = useTaxStore();

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    router.push('/intake/extras');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-8 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-200">
          <User className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Personal Details</h1>
        <p className="text-slate-500 text-sm mt-1">
          Review what we auto-filled from your documents and add the rest.
        </p>
      </header>

      <form onSubmit={handleNext} className="max-w-md mx-auto w-full space-y-5">

        {/* Auto-filled from W-2 — shown read-only with edit option */}
        <div className="bg-green-50 border border-green-200 rounded-2xl p-4 space-y-3">
          <p className="text-xs font-bold text-green-800 uppercase tracking-wider">Auto-filled from your W-2</p>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="First Name" required>
              <input className={inputCls} value={identity.first_name}
                onChange={(e) => updateIdentity({ first_name: e.target.value })} required />
            </FormField>
            <FormField label="Last Name" required>
              <input className={inputCls} value={identity.last_name}
                onChange={(e) => updateIdentity({ last_name: e.target.value })} required />
            </FormField>
          </div>
          <FormField label="SSN / ITIN" hint="Extracted from W-2 Box a. Edit if incorrect.">
            <input className={inputCls} value={identity.ssn || identity.itin}
              onChange={(e) => {
                const v = e.target.value.replace(/\D/g, '').slice(0, 9);
                v.startsWith('9') ? updateIdentity({ itin: v, ssn: '' }) : updateIdentity({ ssn: v, itin: '' });
              }} maxLength={9} inputMode="numeric" />
          </FormField>
        </div>

        <FormField label="Date of Birth" required>
          <input type="date" className={inputCls} value={identity.date_of_birth ?? ''}
            onChange={(e) => updateIdentity({ date_of_birth: e.target.value || null })} required />
        </FormField>

        <FormField label="Occupation" hint="E.g. Graduate Student, Researcher, Intern">
          <input className={inputCls} value={identity.occupation}
            onChange={(e) => updateIdentity({ occupation: e.target.value })}
            placeholder="Graduate Student" />
        </FormField>

        <FormField label="Filing Status">
          <select className={selectCls} value={identity.filing_status}
            onChange={(e) => updateIdentity({ filing_status: e.target.value as 'single' | 'mfs' | 'qss' })}>
            <option value="single">Single</option>
            <option value="mfs">Married Filing Separately</option>
            <option value="qss">Qualifying Surviving Spouse</option>
          </select>
        </FormField>

        {/* US Address */}
        <div className="border-t border-slate-100 pt-4 space-y-3">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">US Address</p>
          <FormField label="Street Address" required>
            <input className={inputCls} value={identity.us_address_line1}
              onChange={(e) => updateIdentity({ us_address_line1: e.target.value })}
              placeholder="100 Main St" required />
          </FormField>
          <div className="grid grid-cols-3 gap-2">
            <FormField label="City" required>
              <input className={inputCls} value={identity.us_city}
                onChange={(e) => updateIdentity({ us_city: e.target.value })} required />
            </FormField>
            <FormField label="State" required>
              <input className={inputCls} value={identity.us_state} maxLength={2}
                onChange={(e) => updateIdentity({ us_state: e.target.value.toUpperCase().slice(0, 2) })} required />
            </FormField>
            <FormField label="ZIP" required>
              <input className={inputCls} value={identity.us_zip} maxLength={5}
                onChange={(e) => updateIdentity({ us_zip: e.target.value.replace(/\D/g, '').slice(0, 5) })} required />
            </FormField>
          </div>
        </div>

        {/* Foreign address */}
        <div className="border-t border-slate-100 pt-4 space-y-3">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Home Address (Outside the US)</p>
          <FormField label="Street / Building">
            <input className={inputCls} value={identity.foreign_address_line1}
              onChange={(e) => updateIdentity({ foreign_address_line1: e.target.value })} />
          </FormField>
          <div className="grid grid-cols-2 gap-2">
            <FormField label="City">
              <input className={inputCls} value={identity.foreign_city}
                onChange={(e) => updateIdentity({ foreign_city: e.target.value })} />
            </FormField>
            <FormField label="Postal Code">
              <input className={inputCls} value={identity.foreign_postal_code}
                onChange={(e) => updateIdentity({ foreign_postal_code: e.target.value })} />
            </FormField>
          </div>
          <FormField label="Country">
            <CountrySelect value={identity.foreign_country}
              onChange={(v) => updateIdentity({ foreign_country: v })} />
          </FormField>
        </div>

        <button type="submit"
          className="w-full h-14 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 hover:bg-slate-800 active:scale-95 transition-all shadow-xl">
          Continue
          <ChevronRight className="w-6 h-6" />
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Commit**
```bash
git add nra-tax-client/src/app/intake/personal/
git commit -m "feat: personal details page — shows auto-filled W-2 data, collects remainder"
```

---

## Task 13: Page — Extras (Step 5)

**Files:**
- Create: `nra-tax-client/src/app/intake/extras/page.tsx`

- [ ] **Step 1: Create the page**

Create `nra-tax-client/src/app/intake/extras/page.tsx`:

```tsx
'use client';

import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import { ChevronRight, ClipboardList } from 'lucide-react';
import { YesNoToggle } from '@/components/YesNoToggle';
import { FormField, inputCls } from '@/components/FormField';
import { updateIncome } from '@/store/taxStore'; // will use hook

export default function ExtrasPage() {
  const router = useRouter();
  const { extras, updateExtras, income, updateIncome } = useTaxStore();

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    router.push('/intake/context');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-8 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-200">
          <ClipboardList className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">A Few More Questions</h1>
        <p className="text-slate-500 text-sm mt-1">Almost done — these affect your return type.</p>
      </header>

      <form onSubmit={handleNext} className="max-w-md mx-auto w-full space-y-6">

        {/* ── Income description (for treaty classifier) ── */}
        <FormField label="Describe your primary income source" required
          hint='E.g. "PhD teaching assistant at NYU" or "NSF research fellowship — no services required"'>
          <textarea rows={3}
            className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-shadow resize-none"
            value={income.income_description}
            onChange={(e) => updateIncome({ income_description: e.target.value })}
            placeholder="Describe what you do and who pays you…"
            required />
        </FormField>

        <YesNoToggle
          label="Are you a full-time student in a US educational institution or full-time intern/trainee?"
          value={extras.isFullTimeStudent}
          onChange={(v) => updateExtras({ isFullTimeStudent: v })}
        />

        <YesNoToggle
          label="Are you a degree candidate in a US educational institution?"
          value={extras.isDegreeCandidate}
          onChange={(v) => updateExtras({ isDegreeCandidate: v })}
        />

        <YesNoToggle
          label="Are you an OPT or CPT program participant?"
          sublabel="Optional Practical Training or Curricular Practical Training."
          value={extras.isOptCpt}
          onChange={(v) => updateExtras({ isOptCpt: v })}
        />

        <YesNoToggle
          label="Did you receive, sell, or dispose of any digital assets (crypto) during 2025?"
          value={extras.hadDigitalAssets}
          onChange={(v) => updateExtras({ hadDigitalAssets: v })}
        />

        <YesNoToggle
          label="Can you be claimed as a dependent on someone else's US tax return?"
          value={extras.canBeClaimedAsDependent}
          onChange={(v) => updateExtras({ canBeClaimedAsDependent: v })}
        />

        <YesNoToggle
          label="Were you married on the last day of 2025?"
          value={extras.wasMarriedOnLastDay}
          onChange={(v) => updateExtras({ wasMarriedOnLastDay: v })}
        />

        <YesNoToggle
          label="Did you make estimated tax payments directly to the IRS during 2025?"
          sublabel="Payments you made yourself, not through your employer."
          value={extras.madeEstimatedFederalPayments}
          onChange={(v) => updateExtras({ madeEstimatedFederalPayments: v })}
        />

        {extras.madeEstimatedFederalPayments && (
          <FormField label="Total estimated federal tax payments ($)">
            <input type="number" className={inputCls} min={0} step="0.01"
              value={extras.estimatedFederalPaymentAmount}
              onChange={(e) => updateExtras({ estimatedFederalPaymentAmount: parseFloat(e.target.value) || 0 })} />
          </FormField>
        )}

        <YesNoToggle
          label="Have you filed a US federal tax return before?"
          value={extras.filedPreviousFederalReturn}
          onChange={(v) => updateExtras({ filedPreviousFederalReturn: v })}
        />

        {extras.filedPreviousFederalReturn && (
          <div className="grid grid-cols-2 gap-3 pl-2 border-l-2 border-blue-200">
            <FormField label="Most recent tax year filed">
              <input type="number" className={inputCls} min={2018} max={2024}
                value={extras.previousReturnYear ?? ''}
                onChange={(e) => updateExtras({ previousReturnYear: parseInt(e.target.value) || null })} />
            </FormField>
            <FormField label="Return type">
              <select className={inputCls}
                value={extras.previousReturnType}
                onChange={(e) => updateExtras({ previousReturnType: e.target.value })}>
                <option value="">Select…</option>
                <option value="1040NR">1040-NR</option>
                <option value="1040">1040</option>
                <option value="8843">8843 only</option>
              </select>
            </FormField>
          </div>
        )}

        <button type="submit"
          className="w-full h-14 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 hover:bg-slate-800 active:scale-95 transition-all shadow-xl">
          Continue
          <ChevronRight className="w-6 h-6" />
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Fix the stray import**

The page above has a bad import line (`import { updateIncome } from '@/store/taxStore'`). Remove it — `updateIncome` comes from the hook. The page already uses `const { ..., updateIncome } = useTaxStore()`.

- [ ] **Step 3: Commit**
```bash
git add nra-tax-client/src/app/intake/extras/
git commit -m "feat: extras page (Step 5) — Sprintax-style dependency/student/OPT/prior returns"
```

---

## Task 14: Update StepBar and Landing → Eligibility redirect

**Files:**
- Modify: `nra-tax-client/src/components/StepBar.tsx`
- Modify: `nra-tax-client/src/app/page.tsx`

- [ ] **Step 1: Update StepBar with 7 new steps**

Replace `nra-tax-client/src/components/StepBar.tsx`:

```tsx
'use client';

import { usePathname } from 'next/navigation';
import { Check } from 'lucide-react';

const STEPS = [
  { paths: ['/intake/eligibility'], label: 'Eligibility' },
  { paths: ['/intake/visa'], label: 'Visa' },
  { paths: ['/intake/documents'], label: 'Documents' },
  { paths: ['/intake/ocr-review', '/intake/personal'], label: 'Review' },
  { paths: ['/intake/extras', '/intake/context'], label: 'Details' },
  { paths: ['/processing'], label: 'Calculating' },
  { paths: ['/results'], label: 'Results' },
];

export function StepBar() {
  const pathname = usePathname();
  const currentIdx = STEPS.findIndex((s) => s.paths.some((p) => pathname.startsWith(p)));
  if (currentIdx < 0) return null;

  return (
    <div className="w-full bg-white border-b border-slate-100 px-3 py-2 sticky top-0 z-50">
      <div className="max-w-md mx-auto flex items-center">
        {STEPS.map((step, i) => {
          const isDone = i < currentIdx;
          const isActive = i === currentIdx;
          return (
            <div key={i} className="flex items-center flex-1 min-w-0">
              <div className="flex flex-col items-center gap-0.5">
                <div className={`flex items-center justify-center w-6 h-6 rounded-full text-[10px] font-bold transition-all ${
                  isDone ? 'bg-blue-600 text-white' :
                  isActive ? 'bg-slate-900 text-white ring-2 ring-slate-900 ring-offset-1' :
                  'bg-slate-100 text-slate-400'}`}>
                  {isDone ? <Check className="w-3 h-3" /> : i + 1}
                </div>
                <span className={`text-[9px] font-medium whitespace-nowrap ${
                  isActive ? 'text-slate-900' : isDone ? 'text-blue-600' : 'text-slate-300'}`}>
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-0.5 mb-3 ${i < currentIdx ? 'bg-blue-600' : 'bg-slate-100'}`} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update landing page CTA to go to eligibility**

In `nra-tax-client/src/app/page.tsx`, change:
```tsx
href="/intake/profile"
```
to:
```tsx
href="/intake/eligibility"
```

- [ ] **Step 3: Commit**
```bash
git add nra-tax-client/src/components/StepBar.tsx nra-tax-client/src/app/page.tsx
git commit -m "feat: update StepBar to 7-step flow; CTA links to eligibility page"
```

---

## Task 15: Wire OCR data into the processing pipeline

The processing page currently calls `submitReturn({ intake })` which sends only the `IntakePayload`. The OCR extracted texts need to be passed as `i94OcrText`, `w2OcrTexts`, etc. so the engine's L1/L3 agents can process them.

But the new architecture: OCR happens in the frontend BEFORE submission. The confirmed W-2/1042-S values from `ocrResult` should be passed directly to the engine via the `w2_ocr_texts` field (we re-serialize the confirmed extracted data as text for the engine).

**Files:**
- Modify: `nra-tax-client/src/app/processing/page.tsx`

- [ ] **Step 1: Build OCR text from confirmed ocrResult in store**

In `nra-tax-client/src/store/taxStore.ts`, add a helper getter:

```typescript
  buildOcrTexts: () => {
    const s = get();
    const ocr = s.ocrResult;
    if (!ocr) return { i94OcrText: '', w2OcrTexts: [], form1042sOcrTexts: [] };
    // Serialize confirmed extracted data back to text for the engine's LLM agents
    const i94OcrText = ocr.i94
      ? `I-94 Data: days_current_year=${ocr.i94.days_current_year}, days_minus_1=${ocr.i94.days_minus_1}, days_minus_2=${ocr.i94.days_minus_2}, entry=${ocr.i94.latest_entry_date}, class=${ocr.i94.latest_class_of_admission}`
      : '';
    const w2OcrTexts = ocr.w2s.map((w) =>
      `W-2 Extracted: Box 1 Wages: ${w.box_1_wages}, Box 2 Federal: ${w.box_2_fed_withholding}, Box 3 SS Wages: ${w.box_3_ss_wages}, Box 4 SS Withheld: ${w.box_4_ss_withheld}, Box 5 Medicare Wages: ${w.box_5_medicare_wages}, Box 6 Medicare: ${w.box_6_medicare_withheld}, Box 17 State: ${w.box_17_state_income_tax}, Box 18 Local Wages: ${w.box_18_local_wages}, Box 19 Local Tax: ${w.box_19_local_income_tax}, Box 20 Locality: ${w.box_20_locality_name}, Employer: ${w.employer_name}, EIN: ${w.employer_ein}`
    );
    const form1042sOcrTexts = ocr.form_1042s.map((f) =>
      `1042-S Extracted: Income Code: ${f.income_code}, Gross Income: ${f.gross_income}, Exemption Rate: ${f.exemption_rate}, Exemption Code: ${f.exemption_code}, Fed Withheld: ${f.fed_withheld}, Chapter: ${f.chapter_indicator}, Recipient: ${f.recipient_name}, Agent: ${f.withholding_agent_name}`
    );
    return { i94OcrText, w2OcrTexts, form1042sOcrTexts };
  },
```

Add `buildOcrTexts: () => { i94OcrText: string; w2OcrTexts: string[]; form1042sOcrTexts: string[] }` to the `TaxState` interface.

- [ ] **Step 2: Update processing page to use buildOcrTexts**

In `nra-tax-client/src/app/processing/page.tsx`, update the `run()` function:

```typescript
    async function run() {
      try {
        const intake = store.buildIntakePayload();
        const ocrTexts = store.buildOcrTexts();
        const data = await submitReturn({
          intake,
          i94OcrText: ocrTexts.i94OcrText,
          w2OcrTexts: ocrTexts.w2OcrTexts,
          form1042sOcrTexts: ocrTexts.form1042sOcrTexts,
        });
        // ... rest unchanged
```

- [ ] **Step 3: TypeScript check**
```bash
cd nra-tax-client && npx tsc --noEmit
```

- [ ] **Step 4: Commit**
```bash
git add nra-tax-client/src/store/taxStore.ts nra-tax-client/src/app/processing/page.tsx
git commit -m "feat: wire confirmed OCR data into the engine pipeline via buildOcrTexts()"
```

---

## Self-Review

### Spec coverage
| Sprintax requirement | Task |
|---------------------|------|
| US citizen / GC gating questions | Task 8 (eligibility page) |
| Visa type, program dates (I-20/DS-2019) | Task 9 (visa page) |
| Travel history table (entry/exit dates) | Task 6, Task 9 |
| Country of citizenship + residence before US | Task 9 |
| Changed visa question | Task 9 |
| Document upload (W-2, 1042-S, 1099) | Task 10 |
| OCR auto-fill of document fields | Tasks 1, 2, 11 |
| User reviews extracted fields | Task 11 (ocr-review page) |
| Name/SSN auto-filled from W-2 | Task 11 (handleContinue) |
| Personal details (DOB, address, occupation) | Task 12 (personal page) |
| Dependency, marital, digital assets, OPT/CPT | Task 13 (extras page) |
| Estimated tax payments, prior returns | Task 13 |
| Income description for treaty classifier | Task 13 |
| FICA / banking | existing `/intake/context` (unchanged) |
| NY wizard | existing `/intake/context` (unchanged) |

### Placeholder scan
None found — every step includes actual code.

### Type consistency
- `OcrResult`, `W2Extracted`, `Form1042SExtracted`, `I94Extracted` defined in taxStore (Task 3) and used consistently in ocr-review page (Task 11) and extractDocuments (Task 4)
- `buildOcrTexts()` defined in taxStore (Task 15 Step 1) before processing page calls it (Task 15 Step 2)
- `EligibilityAnswers`, `VisaDetails`, `ExtrasAnswers` all defined in Task 3 before pages use them in Tasks 8, 9, 13

---

**Plan saved to `docs/superpowers/plans/2026-06-02-document-first-intake-flow.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, using superpowers:subagent-driven-development

**2. Inline Execution** — Execute tasks in this session using superpowers:executing-plans

**Which approach?**
