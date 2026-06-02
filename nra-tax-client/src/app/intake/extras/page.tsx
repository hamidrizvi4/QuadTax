'use client';

import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import { ChevronRight, ClipboardList } from 'lucide-react';
import { YesNoToggle } from '@/components/YesNoToggle';
import { FormField, inputCls } from '@/components/FormField';

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

        <FormField label="Describe your primary income source" required
          hint='E.g. "PhD teaching assistant at NYU" or "NSF research fellowship — no services required"'>
          <textarea rows={3}
            className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 outline-none transition-shadow resize-none"
            value={income.income_description}
            onChange={(e) => updateIncome({ income_description: e.target.value })}
            placeholder="Describe what you do and who pays you…"
            required />
        </FormField>

        <YesNoToggle label="Are you a full-time student or full-time intern/trainee?"
          value={extras.isFullTimeStudent}
          onChange={(v) => updateExtras({ isFullTimeStudent: v })} />

        <YesNoToggle label="Are you a degree candidate in a US educational institution?"
          value={extras.isDegreeCandidate}
          onChange={(v) => updateExtras({ isDegreeCandidate: v })} />

        <YesNoToggle label="Are you an OPT or CPT program participant?"
          sublabel="Optional Practical Training or Curricular Practical Training."
          value={extras.isOptCpt}
          onChange={(v) => updateExtras({ isOptCpt: v })} />

        <YesNoToggle label="Did you receive, sell, or dispose of any digital assets (crypto) during 2025?"
          value={extras.hadDigitalAssets}
          onChange={(v) => updateExtras({ hadDigitalAssets: v })} />

        <YesNoToggle label="Can you be claimed as a dependent on someone else's US tax return?"
          value={extras.canBeClaimedAsDependent}
          onChange={(v) => updateExtras({ canBeClaimedAsDependent: v })} />

        <YesNoToggle label="Were you married on the last day of 2025?"
          value={extras.wasMarriedOnLastDay}
          onChange={(v) => updateExtras({ wasMarriedOnLastDay: v })} />

        <YesNoToggle
          label="Did you make estimated tax payments directly to the IRS during 2025?"
          sublabel="Payments you made yourself, not through your employer."
          value={extras.madeEstimatedFederalPayments}
          onChange={(v) => updateExtras({ madeEstimatedFederalPayments: v })} />

        {extras.madeEstimatedFederalPayments && (
          <FormField label="Total estimated federal tax payments ($)">
            <input type="number" className={inputCls} min={0} step="0.01"
              value={extras.estimatedFederalPaymentAmount}
              onChange={(e) => updateExtras({ estimatedFederalPaymentAmount: parseFloat(e.target.value) || 0 })} />
          </FormField>
        )}

        <YesNoToggle label="Have you filed a US federal tax return before?"
          value={extras.filedPreviousFederalReturn}
          onChange={(v) => updateExtras({ filedPreviousFederalReturn: v })} />

        {extras.filedPreviousFederalReturn && (
          <div className="grid grid-cols-2 gap-3 pl-2 border-l-2 border-blue-200">
            <FormField label="Most recent tax year filed">
              <input type="number" className={inputCls} min={2018} max={2024}
                value={extras.previousReturnYear ?? ''}
                onChange={(e) => updateExtras({ previousReturnYear: parseInt(e.target.value) || null })} />
            </FormField>
            <FormField label="Return type">
              <select className={inputCls} value={extras.previousReturnType}
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
