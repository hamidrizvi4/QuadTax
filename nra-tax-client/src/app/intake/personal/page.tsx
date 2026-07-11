'use client';

import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import { ChevronRight, User } from 'lucide-react';
import { FormField, inputCls, selectCls } from '@/components/FormField';
import { CountrySelect } from '@/components/CountrySelect';

export default function PersonalPage() {
  const router = useRouter();
  const { identity, updateIdentity } = useTaxStore();

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    router.push('/intake/extras');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-8 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-200">
          <User className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Personal Details</h1>
        <p className="text-slate-500 text-sm mt-1">
          Review auto-filled info from your documents and add the rest.
        </p>
      </header>

      <form onSubmit={handleNext} className="max-w-md mx-auto w-full space-y-5">

        <div className="bg-green-50 border border-green-200 rounded-2xl p-4 space-y-3">
          <p className="text-xs font-bold text-green-800 uppercase tracking-wider">Auto-filled from your W-2</p>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="First Name" required>
              <input className={inputCls} value={identity.first_name}
                onChange={(e) => updateIdentity({ first_name: e.target.value })} required />
            </FormField>
            <FormField label="Last Name" required>
              <input className={inputCls} value={identity.last_name}
                onChange={(e) => updateIdentity({ last_name: e.target.value })} required />
            </FormField>
          </div>
          <FormField label="SSN / ITIN" hint="Edit if OCR extracted incorrectly.">
            <input className={inputCls} value={identity.ssn || identity.itin}
              onChange={(e) => {
                const v = e.target.value.replace(/\D/g, '').slice(0, 9);
                v.startsWith('9') ? updateIdentity({ itin: v, ssn: '' }) : updateIdentity({ ssn: v, itin: '' });
              }} maxLength={9} inputMode="numeric" />
          </FormField>
        </div>

        <FormField label="Date of Birth" required>
          <input type="date" className={inputCls} value={identity.date_of_birth ?? ''}
            onChange={(e) => updateIdentity({ date_of_birth: e.target.value || null })} required />
        </FormField>

        <FormField label="Occupation" hint="E.g. Graduate Student, Researcher, Intern">
          <input className={inputCls} value={identity.occupation}
            onChange={(e) => updateIdentity({ occupation: e.target.value })} placeholder="Graduate Student" />
        </FormField>

        <FormField label="Filing Status">
          <select className={selectCls} value={identity.filing_status}
            onChange={(e) => updateIdentity({ filing_status: e.target.value as 'single' | 'mfs' | 'qss' })}>
            <option value="single">Single</option>
            <option value="mfs">Married Filing Separately</option>
            <option value="qss">Qualifying Surviving Spouse</option>
          </select>
        </FormField>

        <div className="border-t border-slate-100 pt-4 space-y-3">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">US Address</p>
          <FormField label="Street Address" required>
            <input className={inputCls} value={identity.us_address_line1}
              onChange={(e) => updateIdentity({ us_address_line1: e.target.value })} placeholder="100 Main St" required />
          </FormField>
          <div className="grid grid-cols-3 gap-2">
            <FormField label="City" required>
              <input className={inputCls} value={identity.us_city}
                onChange={(e) => updateIdentity({ us_city: e.target.value })} required />
            </FormField>
            <FormField label="State" required>
              <input className={inputCls} value={identity.us_state} maxLength={2}
                onChange={(e) => updateIdentity({ us_state: e.target.value.toUpperCase().slice(0, 2) })} required />
            </FormField>
            <FormField label="ZIP" required>
              <input className={inputCls} value={identity.us_zip} maxLength={5}
                onChange={(e) => updateIdentity({ us_zip: e.target.value.replace(/\D/g, '').slice(0, 5) })} required />
            </FormField>
          </div>
        </div>

        <div className="border-t border-slate-100 pt-4 space-y-3">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Home Address (Outside the US)</p>
          <FormField label="Street / Building">
            <input className={inputCls} value={identity.foreign_address_line1}
              onChange={(e) => updateIdentity({ foreign_address_line1: e.target.value })} />
          </FormField>
          <div className="grid grid-cols-2 gap-2">
            <FormField label="City">
              <input className={inputCls} value={identity.foreign_city}
                onChange={(e) => updateIdentity({ foreign_city: e.target.value })} />
            </FormField>
            <FormField label="Postal Code">
              <input className={inputCls} value={identity.foreign_postal_code}
                onChange={(e) => updateIdentity({ foreign_postal_code: e.target.value })} />
            </FormField>
          </div>
          <FormField label="Country">
            <CountrySelect value={identity.foreign_country}
              onChange={(v) => updateIdentity({ foreign_country: v })} />
          </FormField>
        </div>

        <div className="border-t border-slate-100 pt-4 space-y-3">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Passport (Optional)</p>
          <FormField label="Passport Number" hint="Used on Form 8843, if filed.">
            <input className={inputCls} value={identity.passport_number}
              onChange={(e) => updateIdentity({ passport_number: e.target.value })} placeholder="EA1234567" />
          </FormField>
          <FormField label="Passport Country">
            <CountrySelect value={identity.passport_country}
              onChange={(v) => updateIdentity({ passport_country: v })} placeholder="Select passport country…" />
          </FormField>
        </div>

        <div className="border-t border-slate-100 pt-4 space-y-3">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">Contact Info (Optional)</p>
          <FormField label="Daytime Phone">
            <input type="tel" className={inputCls} value={identity.daytime_phone}
              onChange={(e) => updateIdentity({ daytime_phone: e.target.value })} placeholder="212-555-0123" />
          </FormField>
          <FormField label="Email">
            <input type="email" className={inputCls} value={identity.email}
              onChange={(e) => updateIdentity({ email: e.target.value })} placeholder="you@nyu.edu" />
          </FormField>
        </div>

        <button type="submit"
          className="w-full h-14 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 hover:bg-slate-800 active:scale-95 transition-all shadow-xl">
          Continue
          <ChevronRight className="w-6 h-6" />
        </button>
      </form>
    </div>
  );
}
