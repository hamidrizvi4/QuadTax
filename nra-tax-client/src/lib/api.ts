import axios, { AxiosError } from 'axios';

import type {
  IntakePayload,
  SubmitRequest,
  TaxProcessResponse,
} from '@/lib/api-types';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api/v1';

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
  };
  try {
    const r = await axios.post<TaxProcessResponse>(`${API_BASE_URL}/submit`, body);
    return r.data;
  } catch (err) {
    const ax = err as AxiosError<{ detail?: string }>;
    throw new Error(
      ax.response?.data?.detail ?? ax.message ?? 'Failed to submit the return.',
    );
  }
}

export interface MultipartSubmitArgs {
  intake: IntakePayload;
  i94File: File;
  w2Files: File[];
  form1042sFiles: File[];
}

/**
 * Legacy multipart endpoint preserved for backward compatibility. The
 * Phase-6 server reads `mcq_answers_json` as JSON and runs the engine with
 * file uploads OCR'd server-side. New callers should prefer submitReturn().
 */
export async function submitReturnMultipart(
  args: MultipartSubmitArgs,
): Promise<TaxProcessResponse> {
  const form = new FormData();
  // Send the new intake payload nested under mcq_answers_json so the legacy
  // endpoint can also accept the richer body. The server tolerates extra keys.
  form.append('mcq_answers_json', JSON.stringify(legacyMcqShape(args.intake)));
  form.append('i94_file', args.i94File);
  args.w2Files.forEach((f) => form.append('w2_files', f));
  args.form1042sFiles.forEach((f) => form.append('form_1042s_files', f));

  try {
    const r = await axios.post<TaxProcessResponse>(
      `${API_BASE_URL}/upload-and-process`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    );
    return r.data;
  } catch (err) {
    const ax = err as AxiosError<{ detail?: string }>;
    throw new Error(
      ax.response?.data?.detail ?? ax.message ?? 'Failed to submit the return.',
    );
  }
}

/** Flatten the rich intake to the legacy mcq_answers shape the v1 endpoint expects. */
function legacyMcqShape(intake: IntakePayload): Record<string, unknown> {
  return {
    tax_year: intake.residency.tax_year,
    visa_type: intake.residency.visa_type,
    first_us_arrival_year: intake.residency.first_us_arrival_year,
    tax_residence_country: intake.identity.country_of_tax_residence,
    income_description: intake.income.income_description,
    requires_services: intake.income.requires_services,
    is_qualified_expense: intake.income.is_qualified_expense,
    ...(intake.ny ? { ny_intake: intake.ny } : {}),
  };
}

// ---------------------------------------------------------------------------
// Legacy back-compat shim used by the Phase-2 processing page.
// ---------------------------------------------------------------------------

/** @deprecated Phase-2 response shape preserved so older pages compile. */
export interface LegacyTaxResponse {
  status: string;
  tax_liability: number;
  refund_or_owed: number;
  requires_843_fica_claim: boolean;
  generated_forms: string[];
}

interface StoreLike {
  buildIntakePayload?: () => IntakePayload;
  i94File?: File | null;
  w2Files?: File[];
  form1042sFiles?: File[];
}

/**
 * @deprecated Use submitReturn() or submitReturnMultipart() directly with the
 * typed payload. Preserved so the existing intake → processing page flow keeps
 * compiling against the Phase-6 server.
 */
export async function submitTaxReturn(
  store: StoreLike,
): Promise<LegacyTaxResponse> {
  if (!store.buildIntakePayload) {
    throw new Error('Store is missing buildIntakePayload(); update taxStore.ts.');
  }
  const intake = store.buildIntakePayload();
  if (!store.i94File) {
    throw new Error('An I-94 travel history upload is strictly required.');
  }
  const response = await submitReturnMultipart({
    intake,
    i94File: store.i94File,
    w2Files: store.w2Files ?? [],
    form1042sFiles: store.form1042sFiles ?? [],
  });
  // Project the Phase-6 response shape down to the Phase-2 keys the page expects.
  const ficaFlag = response.fica_refund_amount > 0;
  return {
    status: response.status,
    tax_liability:
      response.federal_refund_or_owed > 0 ? response.federal_refund_or_owed : 0,
    refund_or_owed: response.federal_refund_or_owed,
    requires_843_fica_claim: ficaFlag,
    generated_forms: response.generated_form_outputs,
  };
}
