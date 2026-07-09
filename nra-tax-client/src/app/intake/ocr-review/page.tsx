'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import type { W2Extracted, Form1042SExtracted, I94Extracted } from '@/store/taxStore';
import { OcrDocumentCard } from '@/components/OcrDocumentCard';
import { ChevronRight, Sparkles } from 'lucide-react';

export default function OcrReviewPage() {
  const router = useRouter();
  const { ocrResult, setOcrResult, updateIdentity } = useTaxStore();

  const [w2s, setW2s] = useState<W2Extracted[]>(ocrResult?.w2s ?? []);
  const [form1042s, setForm1042s] = useState<Form1042SExtracted[]>(ocrResult?.form_1042s ?? []);
  const [i94, setI94] = useState<I94Extracted | null>(ocrResult?.i94 ?? null);

  const [confirmedW2, setConfirmedW2] = useState<boolean[]>([]);
  const [confirmedF1042s, setConfirmedF1042s] = useState<boolean[]>([]);
  const [confirmedI94, setConfirmedI94] = useState(false);

  useEffect(() => {
    setConfirmedW2(new Array(w2s.length).fill(false));
    setConfirmedF1042s(new Array(form1042s.length).fill(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // No OCR data (deep link / refresh) → send the user back to the upload step.
  // Must run in an effect: calling router.push during render breaks React
  // rules and crashes static prerendering ("location is not defined").
  useEffect(() => {
    if (!ocrResult) router.replace('/intake/documents');
  }, [ocrResult, router]);

  const hasDocuments = w2s.length > 0 || form1042s.length > 0 || i94 !== null;

  const allConfirmed =
    (w2s.length === 0 || confirmedW2.every(Boolean)) &&
    (form1042s.length === 0 || confirmedF1042s.every(Boolean)) &&
    (i94 === null || confirmedI94);

  const updateW2Field = (idx: number, key: string, val: string) =>
    setW2s((prev) => prev.map((w, i) => i === idx ? { ...w, [key]: isNaN(Number(val)) || val === '' ? val : Number(val) } : w));

  const updateF1042sField = (idx: number, key: string, val: string) =>
    setForm1042s((prev) => prev.map((f, i) => i === idx ? { ...f, [key]: isNaN(Number(val)) || val === '' ? val : Number(val) } : f));

  const handleContinue = () => {
    if (w2s.length > 0) {
      const first = w2s[0];
      if (first.employee_name) {
        const parts = first.employee_name.trim().split(/\s+/);
        updateIdentity({
          first_name: parts[0] ?? '',
          last_name: parts.slice(1).join(' ') || '',
        });
      }
      if (first.employee_ssn_or_itin) {
        const digits = first.employee_ssn_or_itin.replace(/\D/g, '');
        if (digits.length >= 4) {
          digits.startsWith('9')
            ? updateIdentity({ itin: digits, ssn: '' })
            : updateIdentity({ ssn: digits, itin: '' });
        }
      }
    }
    setOcrResult({ ...ocrResult!, w2s, form_1042s: form1042s, i94 });
    router.push('/intake/personal');
  };

  if (!ocrResult) {
    // Redirect is handled by the effect above; render nothing meanwhile.
    return null;
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-8 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-200">
          <Sparkles className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Review Extracted Data</h1>
        <p className="text-slate-500 text-sm mt-1">
          Our AI read your documents. Check each field and tap &quot;Looks correct&quot; to confirm.
        </p>
      </header>

      <div className="max-w-md mx-auto w-full space-y-5">

        {i94 && (
          <OcrDocumentCard
            title="I-94 Travel History"
            subtitle="Days present in the US per year"
            confirmed={confirmedI94}
            onConfirm={() => setConfirmedI94(true)}
            onFieldChange={(key, val) =>
              setI94((prev) => prev ? { ...prev, [key]: isNaN(Number(val)) ? val : Number(val) } : prev)
            }
            fields={[
              { key: 'days_current_year', label: 'Days in US (2025)', value: i94.days_current_year, type: 'number' },
              { key: 'days_minus_1', label: 'Days in US (2024)', value: i94.days_minus_1, type: 'number' },
              { key: 'days_minus_2', label: 'Days in US (2023)', value: i94.days_minus_2, type: 'number' },
              { key: 'latest_entry_date', label: 'Latest Entry Date', value: i94.latest_entry_date },
              { key: 'latest_class_of_admission', label: 'Visa Class', value: i94.latest_class_of_admission },
            ]}
          />
        )}

        {w2s.map((w2, i) => (
          <OcrDocumentCard
            key={i}
            title={`W-2 Form${w2s.length > 1 ? ` #${i + 1}` : ''}`}
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
              { key: 'box_6_medicare_withheld', label: 'Box 6 — Medicare', value: w2.box_6_medicare_withheld, type: 'number' },
              { key: 'box_17_state_income_tax', label: 'Box 17 — State Tax', value: w2.box_17_state_income_tax, type: 'number' },
              { key: 'box_19_local_income_tax', label: 'Box 19 — Local Tax', value: w2.box_19_local_income_tax, type: 'number' },
              { key: 'box_20_locality_name', label: 'Box 20 — Locality', value: w2.box_20_locality_name },
            ]}
          />
        ))}

        {form1042s.map((f, i) => (
          <OcrDocumentCard
            key={i}
            title={`1042-S Form${form1042s.length > 1 ? ` #${i + 1}` : ''}`}
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

        {!hasDocuments && (
          <div className="bg-amber-50 border border-amber-200 rounded-3xl p-5 text-sm text-amber-800">
            No data was extracted. Documents may have been blurry or unsupported. Go back and try again.
          </div>
        )}

        <div className="bg-blue-50 border border-blue-100 rounded-2xl p-4 text-xs text-blue-700 leading-relaxed">
          <strong>These values go directly into your tax return.</strong> Correct any errors — especially Box 1 wages and Box 2 withholding.
        </div>

        <button onClick={handleContinue}
          disabled={hasDocuments && !allConfirmed}
          className="w-full h-14 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 disabled:opacity-40 hover:bg-slate-800 active:scale-95 transition-all">
          All Confirmed — Continue
          <ChevronRight className="w-6 h-6" />
        </button>
      </div>
    </div>
  );
}
