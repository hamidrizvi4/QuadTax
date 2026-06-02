'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import { submitReturn } from '@/lib/api';
import { Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';

const PIPELINE_STEPS = [
  { id: 'L1', label: 'Verifying travel history (I-94)', emoji: '🛂' },
  { id: 'L3', label: 'Parsing income documents (W-2 / 1042-S)', emoji: '📄' },
  { id: 'L4', label: 'Applying tax treaty benefits', emoji: '🌍' },
  { id: 'L6', label: 'Computing federal tax liability', emoji: '🧮' },
  { id: 'L7', label: 'Reconciling withholding credits', emoji: '💰' },
  { id: 'L8', label: 'Checking FICA exemption (Social Security)', emoji: '🏛️' },
  { id: 'L9', label: 'Running New York state pipeline', emoji: '🗽' },
  { id: 'assembly', label: 'Assembling your mailing packet', emoji: '📬' },
];

export default function ProcessingPage() {
  const router = useRouter();
  const store = useTaxStore();
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    // Visual step progression — one step every ~1.8 s while the API call runs
    const interval = setInterval(() => {
      setCurrentStep((s) => Math.min(s + 1, PIPELINE_STEPS.length - 1));
    }, 1800);

    async function run() {
      try {
        const intake = store.buildIntakePayload();
        const data = await submitReturn({ intake });

        clearInterval(interval);
        setCurrentStep(PIPELINE_STEPS.length - 1);

        // Map the full API response into the store
        store.setResults({
          taxLiability: data.federal_refund_or_owed > 0 ? data.federal_refund_or_owed : 0,
          refundOrOwed: data.federal_refund_or_owed,
          requiresFicaClaim: data.fica_refund_amount > 0,
          generatedForms: data.generated_form_outputs ?? [],
          nyRefundOrOwed: data.ny_refund_or_owed ?? 0,
          ficaRefundAmount: data.fica_refund_amount ?? 0,
          requiresHumanReview: data.requires_human_review ?? [],
          federalPacketPath: data.federal_packet_path ?? null,
          nyPacketPath: data.ny_packet_path ?? null,
          ficaPacketPath: data.fica_packet_path ?? null,
          completedLayers: data.completed_layers ?? [],
          // narrative_sections may not exist yet on older API responses — safe default
          narrativeSections: (data as Record<string, unknown>)['narrative_sections'] as Record<string, string> ?? {},
        });

        // Brief pause so users see the final step complete
        setTimeout(() => router.push('/results'), 700);
      } catch (err: unknown) {
        clearInterval(interval);
        const msg = err instanceof Error ? err.message : 'An unexpected error occurred.';
        setError(msg);
      }
    }

    run();
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-8 text-center">
        <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mb-6">
          <AlertCircle className="w-10 h-10 text-red-500" />
        </div>
        <h2 className="text-xl font-bold text-slate-900 mb-2">Calculation Failed</h2>
        <p className="text-slate-500 max-w-xs mb-8 text-sm leading-relaxed">{error}</p>
        <button
          onClick={() => router.back()}
          className="bg-slate-900 text-white px-8 py-3 rounded-2xl font-bold active:scale-95 transition-all"
        >
          Go Back & Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center p-8">
      {/* Spinner */}
      <div className="relative mb-10">
        <div className="absolute inset-0 bg-blue-400 blur-3xl opacity-10 animate-pulse rounded-full" />
        <Loader2 className="w-14 h-14 text-blue-600 animate-spin relative z-10" />
      </div>

      <h1 className="text-xl font-extrabold text-slate-900 mb-1">Calculating your return…</h1>
      <p className="text-slate-400 text-sm mb-10">This usually takes 15–30 seconds</p>

      {/* Step-by-step pipeline display */}
      <div className="w-full max-w-sm space-y-2">
        {PIPELINE_STEPS.map((step, i) => {
          const isDone = i < currentStep;
          const isActive = i === currentStep;
          return (
            <div
              key={step.id}
              className={`flex items-center gap-3 px-4 py-3 rounded-2xl transition-all duration-300 ${
                isActive
                  ? 'bg-blue-50 border border-blue-100 scale-[1.02] shadow-sm'
                  : isDone
                  ? 'opacity-50'
                  : 'opacity-20'
              }`}
            >
              <span className="text-xl w-8 text-center">{step.emoji}</span>
              <span
                className={`text-sm font-medium flex-1 ${
                  isActive ? 'text-blue-900' : 'text-slate-700'
                }`}
              >
                {step.label}
              </span>
              {isDone && <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />}
              {isActive && (
                <Loader2 className="w-4 h-4 text-blue-400 animate-spin shrink-0" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
