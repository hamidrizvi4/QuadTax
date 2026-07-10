'use client';

import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import { ChevronRight, ClipboardCheck, MapPin, Shield, CreditCard, AlertTriangle } from 'lucide-react';
import { FormField, inputCls, selectCls } from '@/components/FormField';

function Toggle({
  value,
  onChange,
  label,
  sublabel,
}: {
  value: boolean;
  onChange: (v: boolean) => void;
  label: string;
  sublabel: string;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-4 flex items-center justify-between gap-4 shadow-sm">
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-slate-900 text-sm leading-snug">{label}</p>
        <p className="text-xs text-slate-500 mt-1 leading-relaxed">{sublabel}</p>
      </div>
      <button
        type="button"
        onClick={() => onChange(!value)}
        className={`shrink-0 w-14 h-8 rounded-full transition-colors flex items-center p-1 ${
          value ? 'bg-blue-600' : 'bg-slate-200'
        }`}
      >
        <div
          className={`w-6 h-6 bg-white rounded-full shadow-md transition-transform ${
            value ? 'translate-x-6' : 'translate-x-0'
          }`}
        />
      </button>
    </div>
  );
}

function SectionHeader({
  icon: Icon,
  title,
  subtitle,
}: {
  icon: React.ElementType;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="flex items-center gap-3 mb-3">
      <div className="w-8 h-8 bg-slate-100 rounded-xl flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4 text-slate-600" />
      </div>
      <div>
        <p className="text-sm font-bold text-slate-800">{title}</p>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
    </div>
  );
}

export default function ContextPage() {
  const router = useRouter();
  const {
    identity,
    income,
    updateIncome,
    ny,
    updateNY,
    fica,
    updateFICA,
    banking,
    updateBanking,
    elections,
    updateElections,
  } = useTaxStore();

  const hasOutOfScopeElection =
    elections.section_6013g_election ||
    elections.large_foreign_gifts_over_100k ||
    elections.closer_connection_exception_claimed;

  const isNY = identity.us_state === 'NY';

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    // Auto-initialise NY context if user is in NY but hasn't touched it
    if (isNY && ny === null) {
      updateNY({
        days_in_ny: 0,
        has_permanent_abode_in_ny: false,
        abode_months_in_year: 0,
        is_student_dorm: true,
        domiciled_in_ny: false,
        moved_into_ny_mid_year: false,
        moved_out_of_ny_mid_year: false,
        nyc_address: false,
        yonkers_address: false,
        ny_work_days: 0,
        total_work_days: 0,
        employer_in_ny: true,
        institution_1042s_in_ny: true,
      });
    }
    router.push('/processing');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-8 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 rotate-3 shadow-lg shadow-blue-200">
          <ClipboardCheck className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Final Verification</h1>
        <p className="text-slate-500 text-sm mt-1">
          A few specifics to maximise your refund.
        </p>
      </header>

      <form onSubmit={handleNext} className="max-w-md mx-auto w-full space-y-8">

        {/* ── Income Type ── */}
        <section className="space-y-3">
          <SectionHeader icon={ClipboardCheck} title="Income Classification" />
          <Toggle
            label="Services Required?"
            sublabel="Does your funding require duties like teaching, research, or grading?"
            value={income.requires_services}
            onChange={(v) => updateIncome({ requires_services: v })}
          />
          <Toggle
            label="Qualified Expenses Only?"
            sublabel="Is this funding solely for tuition and required fees? (Not room & board)"
            value={income.is_qualified_expense}
            onChange={(v) => updateIncome({ is_qualified_expense: v })}
          />
        </section>

        {/* ── NY Section — only shown when us_state is NY ── */}
        {isNY && (
          <section className="space-y-3">
            <SectionHeader
              icon={MapPin}
              title="New York State"
              subtitle="NY does not honour federal treaties — extra details needed"
            />
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-3 text-xs text-amber-900 leading-relaxed">
              NY adds back any federal treaty exemption to your NY taxable income. Student dorm
              residents are classified as <strong>NY nonresidents</strong> (Knight case) — this
              is beneficial and saves significant tax.
            </div>
            <Toggle
              label="Do you live in a university dorm?"
              sublabel="Dorm residents qualify as NY nonresidents under the Knight rule."
              value={ny?.is_student_dorm ?? true}
              onChange={(v) => updateNY({ is_student_dorm: v })}
            />
            <Toggle
              label="NYC address? (not dorm)"
              sublabel="NYC residents pay an additional city income tax (~3.9%)."
              value={ny?.nyc_address ?? false}
              onChange={(v) => updateNY({ nyc_address: v })}
            />
            <Toggle
              label="Yonkers address?"
              sublabel="Yonkers residents pay a city surcharge."
              value={ny?.yonkers_address ?? false}
              onChange={(v) => updateNY({ yonkers_address: v })}
            />
            <FormField label="Days spent in New York this tax year">
              <input
                type="number"
                className={inputCls}
                min={0}
                max={366}
                value={ny?.days_in_ny ?? 0}
                onChange={(e) => updateNY({ days_in_ny: parseInt(e.target.value) || 0 })}
              />
            </FormField>
            <div className="grid grid-cols-2 gap-3">
              <FormField label="NY work days">
                <input
                  type="number"
                  className={inputCls}
                  min={0}
                  max={366}
                  placeholder="180"
                  value={ny?.ny_work_days ?? 0}
                  onChange={(e) => updateNY({ ny_work_days: parseInt(e.target.value) || 0 })}
                />
              </FormField>
              <FormField label="Total work days">
                <input
                  type="number"
                  className={inputCls}
                  min={0}
                  max={366}
                  placeholder="200"
                  value={ny?.total_work_days ?? 0}
                  onChange={(e) => updateNY({ total_work_days: parseInt(e.target.value) || 0 })}
                />
              </FormField>
            </div>
          </section>
        )}

        {/* ── FICA / Social Security ── */}
        <section className="space-y-3">
          <SectionHeader
            icon={Shield}
            title="Social Security & Medicare (FICA)"
            subtitle="F-1/J-1 students are exempt — get wrongly-withheld tax back"
          />
          <Toggle
            label="Were SS / Medicare taxes withheld?"
            sublabel="If yes, we'll include Form 843 to claim a full refund."
            value={fica.employer_attempted_refund}
            onChange={(v) => updateFICA({ employer_attempted_refund: v })}
          />
          {fica.employer_attempted_refund && (
            <div className="pl-4 border-l-2 border-blue-200 space-y-3">
              <Toggle
                label="Did you ask your employer for a refund?"
                sublabel="IRS requires you try the employer first. If they refused, we'll note that."
                value={fica.has_form_8316}
                onChange={(v) => updateFICA({ has_form_8316: v })}
              />
              <FormField label="Employer Name">
                <input
                  className={inputCls}
                  value={fica.employer_name}
                  onChange={(e) => updateFICA({ employer_name: e.target.value })}
                  placeholder="New York University"
                />
              </FormField>
              <FormField label="Employer EIN" hint="Found on your W-2 Box b (e.g. 13-5562308)">
                <input
                  className={inputCls}
                  value={fica.employer_ein}
                  onChange={(e) => updateFICA({ employer_ein: e.target.value })}
                  placeholder="12-3456789"
                />
              </FormField>
            </div>
          )}
        </section>

        {/* ── Out-of-scope disclosures ── */}
        <section className="space-y-3">
          <SectionHeader
            icon={AlertTriangle}
            title="A Few Uncommon Situations"
            subtitle="Rare for students, but each one requires a CPA — not automated filing"
          />
          <Toggle
            label="Elected to be treated as a US tax resident (§6013)?"
            sublabel="E.g. married to a US citizen/resident and elected joint resident filing."
            value={elections.section_6013g_election}
            onChange={(v) =>
              updateElections({ section_6013g_election: v, section_6013h_election: v })
            }
          />
          <Toggle
            label="Received a gift or inheritance over $100,000 from abroad?"
            sublabel="From a foreign person or estate this tax year — triggers Form 3520."
            value={elections.large_foreign_gifts_over_100k}
            onChange={(v) => updateElections({ large_foreign_gifts_over_100k: v })}
          />
          <Toggle
            label="Claiming the Closer Connection Exception?"
            sublabel="A separate test from the treaty exemptions above — requires Form 8840."
            value={elections.closer_connection_exception_claimed}
            onChange={(v) => updateElections({ closer_connection_exception_claimed: v })}
          />
          {hasOutOfScopeElection && (
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-3 text-xs text-amber-900 leading-relaxed">
              QuadTax's automated engine doesn't cover this situation — it needs a
              professional preparer. You can still continue to see your other
              calculations, but we won't be able to generate a mailable return.
            </div>
          )}
        </section>

        {/* ── Banking ── */}
        <section className="space-y-3">
          <SectionHeader
            icon={CreditCard}
            title="Refund Delivery"
            subtitle="Direct deposit gets your refund 2–3 weeks faster"
          />
          <Toggle
            label="Use direct deposit?"
            sublabel="We'll include your bank details on Form 1040-NR."
            value={banking.direct_deposit}
            onChange={(v) => updateBanking({ direct_deposit: v })}
          />
          {banking.direct_deposit && (
            <div className="space-y-3">
              <FormField label="Routing Number" hint="9-digit number at the bottom left of a cheque">
                <input
                  className={inputCls}
                  value={banking.routing_number}
                  onChange={(e) =>
                    updateBanking({ routing_number: e.target.value.replace(/\D/g, '').slice(0, 9) })
                  }
                  maxLength={9}
                  inputMode="numeric"
                  placeholder="021000021"
                />
              </FormField>
              <FormField label="Account Number">
                <input
                  className={inputCls}
                  value={banking.account_number}
                  onChange={(e) => updateBanking({ account_number: e.target.value })}
                  placeholder="000123456789"
                />
              </FormField>
              <FormField label="Account Type">
                <select
                  className={selectCls}
                  value={banking.account_type}
                  onChange={(e) =>
                    updateBanking({
                      account_type: e.target.value as 'checking' | 'savings' | '',
                    })
                  }
                >
                  <option value="">Select…</option>
                  <option value="checking">Checking</option>
                  <option value="savings">Savings</option>
                </select>
              </FormField>
            </div>
          )}
        </section>

        <button
          type="submit"
          className="w-full h-14 bg-blue-600 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 hover:bg-blue-500 active:scale-95 transition-all shadow-xl shadow-blue-200"
        >
          Calculate My Return
          <ChevronRight className="w-6 h-6" />
        </button>
      </form>
    </div>
  );
}
