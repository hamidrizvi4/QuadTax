"use client";

import { useTaxStore } from "@/store/taxStore";
import { useRouter } from "next/navigation";
import { 
  Download, 
  CheckCircle2, 
  ArrowLeft, 
  FileText, 
  ExternalLink,
  ShieldCheck,
  AlertTriangle 
} from "lucide-react";

export default function ResultsPage() {
  const router = useRouter();
  const { results, resetFastStore } = useTaxStore();

  if (results.taxLiability === null) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center p-8">
        <p className="text-slate-500 mb-4">No results available.</p>
        <button onClick={() => router.push("/")} className="text-blue-600 font-bold">Return Home</button>
      </div>
    );
  }

  const isRefund = (results.refundOrOwed || 0) < 0;
  const absoluteBalance = Math.abs(results.refundOrOwed || 0);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col pb-20">
      {/* Success Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-12 text-center">
        <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl shadow-blue-100">
          <CheckCircle2 className="text-white w-10 h-10" />
        </div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Return Complete!</h1>
        <p className="text-slate-500 mt-2">Your 2024 Tax Package has been successfully generated.</p>
      </header>

      <div className="p-6 max-w-md mx-auto w-full space-y-6 -mt-8">
        
        {/* Financial Result Card */}
        <div className="bg-slate-900 rounded-[32px] p-8 text-white shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-10">
            <ShieldCheck className="w-32 h-32" />
          </div>
          
          <p className="text-blue-400 font-bold text-xs uppercase tracking-[0.2em] mb-2">Final Estimated Balance</p>
          <div className="flex items-baseline gap-1 mb-8">
            <span className="text-5xl font-black">${absoluteBalance.toLocaleString()}</span>
            <span className="text-lg opacity-60">{isRefund ? "Refund" : "Owed"}</span>
          </div>

          <div className="grid grid-cols-2 gap-4 border-t border-white/10 pt-6">
            <div>
              <p className="text-[10px] text-white/50 uppercase font-bold tracking-widest mb-1">Total Liability</p>
              <p className="text-lg font-bold">${results.taxLiability.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-[10px] text-white/50 uppercase font-bold tracking-widest mb-1">Status</p>
              <p className="text-lg font-bold text-green-400">Ready to File</p>
            </div>
          </div>
        </div>

        {/* FICA Notice */}
        {results.requiresFicaClaim && (
          <div className="bg-amber-50 border border-amber-200 rounded-3xl p-5 flex gap-4">
            <AlertTriangle className="w-6 h-6 text-amber-600 shrink-0" />
            <div>
              <p className="text-sm font-bold text-amber-900 leading-tight">FICA Refund Required</p>
              <p className="text-xs text-amber-800 mt-1 leading-normal italic">
                Our engine detected you were incorrectly charged Social Security/Medicare tax. We have included Form 843 in your package.
              </p>
            </div>
          </div>
        )}

        {/* Download Section */}
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-700 ml-1">Filing Assets</h2>
          <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden divide-y divide-slate-100 shadow-sm">
            {results.generatedForms.map((path, idx) => (
              <div key={idx} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
                <div className="flex items-center gap-3">
                  <FileText className="w-5 h-5 text-blue-500" />
                  <span className="text-sm font-medium text-slate-700">{path.split("/").pop()}</span>
                </div>
                <button className="text-slate-400 hover:text-blue-600 transition-colors">
                  <ExternalLink className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>

        <button 
          onClick={() => {
            alert("Package download starting... (Mock)");
          }}
          className="w-full h-18 bg-blue-600 text-white rounded-[24px] font-bold text-lg flex items-center justify-center gap-3 shadow-xl active:scale-95 transition-all py-4"
        >
          <Download className="w-6 h-6" />
          Download PDF Package
        </button>

        <button 
          onClick={() => {
            resetFastStore();
            router.push("/");
          }}
          className="w-full text-slate-400 font-bold text-sm flex items-center justify-center gap-2 hover:text-slate-900 transition-colors py-4"
        >
          <ArrowLeft className="w-4 h-4" />
          File Another Return
        </button>
      </div>
    </div>
  );
}
