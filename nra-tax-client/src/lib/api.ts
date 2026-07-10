import axios, { AxiosError } from 'axios';

import type { components } from '@/lib/api-types';
import type { OcrResult } from '@/store/taxStore';

type IntakePayload = components['schemas']['IntakePayload'];
type SubmitRequest = components['schemas']['SubmitRequest'];
type TaxProcessResponse = components['schemas']['TaxProcessResponse'];

// The browser only ever talks to same-origin Next.js proxy routes
// (/api/submit, /api/ocr). Those routes hold the engine API key server-side,
// so it never appears in the client bundle. See src/app/api/*/route.ts.
const PROXY_SUBMIT = '/api/submit';
const PROXY_OCR = '/api/ocr';

export interface SubmitArgs {
  intake: IntakePayload;
  i94OcrText?: string;
  w2OcrTexts?: string[];
  form1042sOcrTexts?: string[];
}

/** Modern Phase-6 typed endpoint. Send OCR'd text + intake JSON. */
export async function submitReturn(args: SubmitArgs): Promise<TaxProcessResponse> {
  const body: SubmitRequest = {
    intake: args.intake,
    i94_ocr_text: args.i94OcrText ?? '',
    w2_ocr_texts: args.w2OcrTexts ?? [],
    form_1042s_ocr_texts: args.form1042sOcrTexts ?? [],
    output_dir: 'outputs',
    force_assembly: false,
  };
  try {
    const r = await axios.post<TaxProcessResponse>(PROXY_SUBMIT, body);
    return r.data;
  } catch (err) {
    const ax = err as AxiosError<{ detail?: string }>;
    throw new Error(
      ax.response?.data?.detail ?? ax.message ?? 'Failed to submit the return.',
    );
  }
}

export interface ExtractDocumentsArgs {
  taxYear: number;
  i94File?: File | null;
  w2Files?: File[];
  form1042sFiles?: File[];
  form1099Files?: File[];
}

/** Call POST /api/ocr — upload documents, get structured extracted fields back. */
export async function extractDocuments(args: ExtractDocumentsArgs): Promise<OcrResult> {
  const form = new FormData();
  form.append('tax_year', String(args.taxYear));
  if (args.i94File) form.append('i94_file', args.i94File);
  (args.w2Files ?? []).forEach((f) => form.append('w2_files', f));
  (args.form1042sFiles ?? []).forEach((f) => form.append('form_1042s_files', f));
  (args.form1099Files ?? []).forEach((f) => form.append('form_1099_files', f));

  try {
    // Let the browser set the multipart boundary automatically — do NOT set
    // Content-Type explicitly here.
    const r = await axios.post<OcrResult>(PROXY_OCR, form);
    return r.data;
  } catch (err) {
    const ax = err as AxiosError<{ detail?: string }>;
    throw new Error(ax.response?.data?.detail ?? ax.message ?? 'OCR extraction failed.');
  }
}
