'use client';

import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import { ChevronRight, User } from 'lucide-react';
import { FormField, inputCls, selectCls } from '@/components/FormField';
import { CountrySelect } from '@/components/CountrySelect';

export default function ProfilePage() {
  const router = useRouter();
  const { identity, updateIdentity, residency, updateResidency } = useTaxStore();

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    // Auto-seed NY context if the user's state is NY
    router.push('/intake/documents');
  };

  const handleTIN = (raw: string) => {
    const digits = raw.replace(/\D/g, '').slice(0, 9);
    // ITINs always start with 9
    if (digits.startsWith('9')) {
      updateIdentity({ itin: digits, ssn: '' });
    } else {
      updateIdentity({ ssn: digits, itin: '' });
    }
  };

  const tinValue = identity.ssn || identity.itin;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-8 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-200">
          <User className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Personal Profile</h1>
        <p className="text-slate-500 text-sm mt-1">
          This appears on every IRS form — match your passport exactly.
        </p>
      </header>

      <form onSubmit={handleNext} className="max-w-md mx-auto w-full space-y-5">

        {/* ── Name ── */}
        <div className="grid grid-cols-2 gap-3">
          <FormField label="First Name" required>
            <input
              className={inputCls}
              value={identity.first_name}
              onChange={(e) => updateIdentity({ first_name: e.target.value })}
              placeholder="Wei"
              required
            />
          </FormField>
          <FormField label="Last Name" required>
            <input
              className={inputCls}
              value={identity.last_name}
              onChange={(e) => updateIdentity({ last_name: e.target.value })}
              placeholder="Chen"
              required
            />
          </FormField>
        </div>

        <FormField label="Date of Birth" required>
          <input
            type="date"
            className={inputCls}
            value={identity.date_of_birth ?? ''}
            onChange={(e) => updateIdentity({ date_of_birth: e.target.value || null })}
            required
          />
        </FormField>

        {/* ── TIN ── */}
        <FormField
          label="SSN or ITIN"
          hint="9 digits, no dashes. ITINs start with 9. Leave blank if you don't have one yet — we'll add Form W-7."
        >
          <input
            className={inputCls}
            value={tinValue}
            onChange={(e) => handleTIN(e.target.value)}
            maxLength={9}
            placeholder="123456789"
            inputMode="numeric"
          />
        </FormField>

        {/* ── Visa ── */}
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Visa Type" required>
            <select
              className={selectCls}
              value={residency.visa_type}
              onChange={(e) => updateResidency({ visa_type: e.target.value })}
              required
            >
              <option value="F-1">F-1 Student</option>
              <option value="J-1">J-1 Exchange Visitor</option>
              <option value="M-1">M-1 Vocational</option>
              <option value="Q-1">Q-1 Cultural Exchange</option>
            </select>
          </FormField>
          <FormField label="Filing Status">
            <select
              className={selectCls}
              value={identity.filing_status}
              onChange={(e) =>
                updateIdentity({ filing_status: e.target.value as 'single' | 'mfs' | 'qss' })
              }
            >
              <option value="single">Single</option>
              <option value="mfs">Married Filing Separately</option>
              <option value="qss">Qualifying Surviving Spouse</option>
            </select>
          </FormField>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <FormField label="First US Arrival Year" required>
            <input
              type="number"
              className={inputCls}
              min={1990}
              max={new Date().getFullYear()}
              value={residency.first_us_arrival_year}
              onChange={(e) =>
                updateResidency({ first_us_arrival_year: parseInt(e.target.value) || 2020 })
              }
              required
            />
          </FormField>
          <FormField label="Tax Year" required>
            <select
              className={selectCls}
              value={residency.tax_year}
              onChange={(e) => updateResidency({ tax_year: parseInt(e.target.value) })}
            >
              <option value={2025}>2025</option>
              <option value={2024}>2024</option>
            </select>
          </FormField>
        </div>

        {/* ── Country ── */}
        <FormField
          label="Country of Tax Residence"
          required
          hint="Your home country — determines which treaty applies."
        >
          <CountrySelect
            value={identity.country_of_tax_residence}
            onChange={(v) =>
              updateIdentity({ country_of_tax_residence: v, country_of_citizenship: v })
            }
            required
          />
        </FormField>

        {/* ── US Address ── */}
        <div className="border-t border-slate-100 pt-4 space-y-4">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">US Address</p>

          <FormField label="Street Address" required>
            <input
              className={inputCls}
              value={identity.us_address_line1}
              onChange={(e) => updateIdentity({ us_address_line1: e.target.value })}
              placeholder="100 Main St, Apt 2B"
              required
            />
          </FormField>

          <div className="grid grid-cols-3 gap-2">
            <FormField label="City" required>
              <input
                className={inputCls}
                value={identity.us_city}
                onChange={(e) => updateIdentity({ us_city: e.target.value })}
                placeholder="New York"
                required
              />
            </FormField>
            <FormField label="State" required>
              <input
                className={inputCls}
                value={identity.us_state}
                onChange={(e) => updateIdentity({ us_state: e.target.value.toUpperCase().slice(0, 2) })}
                placeholder="NY"
                maxLength={2}
                required
              />
            </FormField>
            <FormField label="ZIP" required>
              <input
                className={inputCls}
                value={identity.us_zip}
                onChange={(e) => updateIdentity({ us_zip: e.target.value.replace(/\D/g, '').slice(0, 5) })}
                placeholder="10012"
                maxLength={5}
                inputMode="numeric"
                required
              />
            </FormField>
          </div>
        </div>

        {/* ── Occupation ── */}
        <FormField label="Occupation" hint="As it will appear on your 1040-NR signature block.">
          <input
            className={inputCls}
            value={identity.occupation}
            onChange={(e) => updateIdentity({ occupation: e.target.value })}
            placeholder="Graduate Student"
          />
        </FormField>

        <div className="pt-4">
          <button
            type="submit"
            className="w-full h-14 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 hover:bg-slate-800 active:scale-95 transition-all shadow-xl shadow-slate-200"
          >
            Next: Documents
            <ChevronRight className="w-6 h-6" />
          </button>
        </div>
      </form>
    </div>
  );
}
