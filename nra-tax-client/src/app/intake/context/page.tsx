"use client";

import { useRouter } from "next/navigation";
import { useTaxStore } from "@/store/taxStore";
import { ChevronRight, ClipboardCheck, Sparkle } from "lucide-react";

export default function ContextPage() {
  const router = useRouter();
  const { mcqAnswers, updateMcqAnswers } = useTaxStore();

  const handleNext = () => {
    router.push("/processing");
  };

  const Toggle = ({ value, onChange, label, sublabel }: any) => (
    <div className="bg-white border border-slate-200 rounded-3xl p-5 flex items-center justify-between gap-4 shadow-sm">
      <div className="flex-1">
        <p className="font-bold text-slate-900 leading-snug">{label}</p>
        <p className="text-xs text-slate-500 mt-1 leading-relaxed">{sublabel}</p>
      </div>
      <button
        onClick={() => onChange(!value)}
        className={`shrink-0 w-16 h-10 rounded-full transition-all flex items-center p-1 ${
          value ? "bg-blue-600" : "bg-slate-200"
        }`}
      >
        <div className={`w-8 h-8 bg-white rounded-full shadow-md transition-all transform ${
          value ? "translate-x-6" : "translate-x-0"
        }`} />
      </button>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6">
      <header className="mb-10 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 rotate-3 shadow-lg shadow-blue-200">
          <ClipboardCheck className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Final Verification</h1>
        <p className="text-slate-500 text-sm mt-1">Nearly there. We just need to check two specific conditions for Treaty calculation.</p>
      </header>

      <div className="flex-1 max-w-md mx-auto w-full space-y-6">
        
        <Toggle
          label="Services Required?"
          sublabel="Does your funding require you to perform duties like teaching, research assistants, or grading?"
          value={mcqAnswers.requires_services}
          onChange={(val: boolean) => updateMcqAnswers({ requires_services: val })}
        />

        <Toggle
          label="Qualified Expenses?"
          sublabel="Is this funding solely for tuition, fees, books, and required equipment? (No room & board)"
          value={mcqAnswers.is_qualified_expense}
          onChange={(val: boolean) => updateMcqAnswers({ is_qualified_expense: val })}
        />

        <div className="bg-slate-900/5 p-5 rounded-3xl space-y-3">
          <div className="flex items-center gap-2 text-slate-800">
            <Sparkle className="w-4 h-4 text-blue-600 animate-pulse" />
            <span className="text-sm font-bold tracking-tight">AI Audit Shield Active</span>
          </div>
          <p className="text-xs text-slate-500 leading-normal italic">
            "Your answers will be cross-referenced against your W-2 and 1042-S logic to ensure maximum IRS compliance."
          </p>
        </div>

        <div className="pt-4">
          <button
            onClick={handleNext}
            className="w-full h-16 bg-blue-600 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 hover:bg-blue-500 active:scale-95 transition-all shadow-xl shadow-blue-200"
          >
            Submit for Calculation
            <Sparkle className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
