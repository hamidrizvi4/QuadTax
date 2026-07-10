'use client';

import { useEffect } from 'react';
import { useTaxStore } from '@/store/taxStore';
import { useRouter } from 'next/navigation';
import {
  CheckCircle2,
  ArrowLeft,
  FileText,
  ShieldCheck,
  AlertTriangle,
  Download,
} from 'lucide-react';
import { HumanReviewBanner } from '@/components/HumanReviewBanner';
import { NarrativeCard } from '@/components/NarrativeCard';

function fmt(n: number) {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function ResultsPage() {
  const router = useRouter();
  const { results, resetFastStore } = useTaxStore();

  const federalRefund = -(results.refundOrOwed ?? 0);
  const nyRefund = -(results.nyRefundOrOwed ?? 0);
  const ficaRefund = results.ficaRefundAmount ?? 0;
  const totalRecovered =
    Math.max(0, federalRefund) + Math.max(0, nyRefund) + Math.max(0, ficaRefund);
  const hasTreatyForm = results.generatedForms.some((f) =>
    f.toLowerCase().includes('8833')
  );

  // Confetti on mount if there's money coming back
  useEffect(() => {
    if (totalRecovered > 0) {
      import('canvas-confetti')
        .then((m) => {
          m.default({ particleCount: 140, spread: 80, origin: { y: 0.55 } });
        })
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (results.taxLiability === null) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center p-8 text-center">
        <p className="text-slate-500 mb-4">No results available yet.</p>
        <button
          onClick={() => router.push('/')}
          className="text-blue-600 font-bold"
        >
          Return Home
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col pb-20">
      {/* ── Header ── */}
      <header className="bg-white border-b border-slate-100 px-6 py-12 text-center">
        <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl shadow-blue-100">
          <CheckCircle2 className="text-white w-10 h-10" />
        </div>
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
          Return Complete!
        </h1>
        <p className="text-slate-500 mt-2 text-sm">
          Your tax package is ready to print and mail.
        </p>
      </header>

      <div className="p-6 max-w-md mx-auto w-full space-y-5 -mt-6">

        {/* ── CPA review banner ── */}
        <HumanReviewBanner reasons={results.requiresHumanReview ?? []} />

        {/* ── Total recovered card ── */}
        <div className="bg-slate-900 rounded-[28px] p-7 text-white shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 opacity-5 p-6">
            <ShieldCheck className="w-28 h-28" />
          </div>
          <p className="text-blue-400 font-bold text-xs uppercase tracking-[0.2em] mb-1">
            Total Amount Recovered
          </p>
          <p className="text-5xl font-black mb-6">${fmt(totalRecovered)}</p>

          <div className="grid grid-cols-3 gap-3 border-t border-white/10 pt-5">
            <div>
              <p className="text-[10px] text-white/40 uppercase font-bold tracking-widest mb-1">
                Federal
              </p>
              <p className="text-lg font-bold">
                {federalRefund >= 0 ? `$${fmt(federalRefund)}` : `-$${fmt(-federalRefund)}`}
              </p>
              <p className="text-[10px] text-white/40 mt-0.5">
                {federalRefund >= 0 ? 'refund' : 'owed'}
              </p>
            </div>
            <div>
              <p className="text-[10px] text-white/40 uppercase font-bold tracking-widest mb-1">
                FICA
              </p>
              <p className="text-lg font-bold text-green-400">${fmt(ficaRefund)}</p>
              <p className="text-[10px] text-white/40 mt-0.5">Form 843</p>
            </div>
            <div>
              <p className="text-[10px] text-white/40 uppercase font-bold tracking-widest mb-1">
                NY State
              </p>
              <p className="text-lg font-bold">
                {nyRefund >= 0 ? `$${fmt(nyRefund)}` : `-$${fmt(-nyRefund)}`}
              </p>
              <p className="text-[10px] text-white/40 mt-0.5">
                {nyRefund >= 0 ? 'refund' : 'owed'}
              </p>
            </div>
          </div>
        </div>

        {/* ── Treaty badge ── */}
        {hasTreatyForm && (
          <div className="bg-blue-50 border border-blue-100 rounded-3xl p-4 flex gap-3 items-start">
            <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-bold text-blue-900">Tax Treaty Applied 🎉</p>
              <p className="text-xs text-blue-700 mt-1 leading-relaxed">
                Your country&apos;s income tax treaty with the US reduced your liability. Form
                8833 (treaty disclosure) is included in your packet.
              </p>
            </div>
          </div>
        )}

        {/* ── FICA notice ── */}
        {results.requiresFicaClaim && (
          <div className="bg-amber-50 border border-amber-200 rounded-3xl p-4 flex gap-3 items-start">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-bold text-amber-900">FICA Refund Detected</p>
              <p className="text-xs text-amber-800 mt-1 leading-relaxed">
                Social Security/Medicare was incorrectly withheld. Form 843 is in your packet —
                mail it <strong>separately</strong> to the IRS (different address than your
                1040-NR).
              </p>
            </div>
          </div>
        )}

        {/* ── Why these numbers (narrative) ── */}
        <NarrativeCard sections={results.narrativeSections ?? {}} />

        {/* ── Generated forms list ── */}
        {results.generatedForms.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-bold text-slate-700 ml-1">Filing Package</h2>
            <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden divide-y divide-slate-100 shadow-sm">
              {results.generatedForms.map((path, idx) => {
                const filename = path.split(/[/\\]/).pop() ?? path;
                return (
                  <div key={idx} className="p-4 flex items-center gap-3">
                    <FileText className="w-5 h-5 text-blue-500 shrink-0" />
                    <span className="text-sm font-medium text-slate-700 truncate flex-1">
                      {filename}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Download buttons ── */}
        {results.federalPacketPath && (
          <button
            onClick={() => {
              const url = `/api/packet?path=${encodeURIComponent(results.federalPacketPath!)}`;
              window.open(url, '_blank');
            }}
            className="w-full h-14 bg-blue-600 text-white rounded-2xl font-bold text-base flex items-center justify-center gap-3 shadow-xl active:scale-95 transition-all"
          >
            <Download className="w-5 h-5" />
            Download Federal Packet
          </button>
        )}

        {results.nyPacketPath && (
          <button
            onClick={() => {
              const url = `/api/packet?path=${encodeURIComponent(results.nyPacketPath!)}`;
              window.open(url, '_blank');
            }}
            className="w-full h-12 bg-slate-700 text-white rounded-2xl font-bold text-sm flex items-center justify-center gap-3 active:scale-95 transition-all"
          >
            <Download className="w-4 h-4" />
            Download NY State Packet
          </button>
        )}

        <button
          onClick={() => {
            resetFastStore();
            router.push('/');
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
