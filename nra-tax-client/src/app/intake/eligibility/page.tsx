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
            Green card holders are taxed as US residents on worldwide income and likely
            need Form 1040. Consult a CPA to confirm your filing requirements.
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
