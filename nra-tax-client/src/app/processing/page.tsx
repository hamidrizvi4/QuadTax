"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTaxStore } from "@/store/taxStore";
import { submitTaxReturn } from "@/lib/api";
import { Sparkles, Loader2, AlertCircle } from "lucide-react";

export default function ProcessingPage() {
  const router = useRouter();
  const store = useTaxStore();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function executePipeline() {
      try {
        const data = await submitTaxReturn(store);
        
        // Save results to global store
        store.setResults({
          taxLiability: data.tax_liability,
          refundOrOwed: data.refund_or_owed,
          requiresFicaClaim: data.requires_843_fica_claim,
          generatedForms: data.generated_forms,
        });

        // Redirect to success
        router.push("/results");
      } catch (err: any) {
        setError(err.message || "An unexpected error occurred.");
      }
    }

    executePipeline();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-8 text-center">
        <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mb-6 text-red-500">
          <AlertCircle className="w-10 h-10" />
        </div>
        <h2 className="text-xl font-bold text-slate-900 mb-2">Calculation Failed</h2>
        <p className="text-slate-500 max-w-xs mb-8">{error}</p>
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
    <div className="min-h-screen bg-white flex flex-col items-center justify-center p-8 text-center">
      <div className="relative mb-10">
        <div className="absolute inset-0 bg-blue-400 blur-3xl opacity-20 animate-pulse" />
        <Loader2 className="w-16 h-16 text-blue-600 animate-spin relative z-10" />
      </div>

      <header className="space-y-4">
        <div className="flex items-center justify-center gap-2 text-blue-600 font-bold uppercase tracking-widest text-xs">
          <Sparkles className="w-4 h-4" />
          <span>Intelligent Engine</span>
        </div>
        <h1 className="text-2xl font-extrabold text-slate-900">Calculating Liability...</h1>
        <p className="text-slate-500 text-sm max-w-xs leading-relaxed mx-auto">
          Our AI is currently mapping your travel records, W-2s, and Treaty articles into a deterministic IRS audit model.
        </p>
      </header>
      
      <div className="mt-12 w-full max-w-[200px] h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className="h-full bg-blue-600 animate-[loading_3s_ease-in-out_infinite]" />
      </div>

      <style jsx>{`
        @keyframes loading {
          0% { transform: translateX(-100%); }
          50% { transform: translateX(0%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
}
