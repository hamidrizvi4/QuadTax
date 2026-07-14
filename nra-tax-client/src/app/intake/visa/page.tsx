'use client';

import { useRouter } from 'next/navigation';
import { useTaxStore, type VisaDetails } from '@/store/taxStore';
import { ChevronRight, Plane } from 'lucide-react';
import { FormField, inputCls, selectCls } from '@/components/FormField';
import { CountrySelect } from '@/components/CountrySelect';
import { TravelHistoryTable } from '@/components/TravelHistoryTable';
import { YesNoToggle } from '@/components/YesNoToggle';

export default function VisaPage() {
  const router = useRouter();
  const { visaDetails, updateVisaDetails, updateIdentity, updateResidency } = useTaxStore();

  const isJ1 = visaDetails.visaType === 'J-1';

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    updateIdentity({
      country_of_citizenship: visaDetails.countryOfCitizenship,
      country_of_tax_residence: visaDetails.countryOfResidenceBeforeUs,
    });
    updateResidency({
      visa_type: visaDetails.visaType,
      // J-1 teacher/researcher gets a 2-year SPT exempt window instead of
      // the 5-year student window — visa_type alone can't distinguish the
      // two categories, so this rides in the dedicated subtype field
      // instead of being encoded into visa_type itself.
      visa_subtype: isJ1 ? visaDetails.visaSubtype : 'student',
      first_us_arrival_year: visaDetails.firstUsEntryDate
        ? parseInt(visaDetails.firstUsEntryDate.slice(0, 4))
        : new Date().getFullYear() - 1,
      // Dual-status detection: only meaningful to the engine when this is
      // genuinely the filer's first-ever year in the US, or when they've
      // already left — otherwise these ride along unused, which is fine.
      first_us_entry_date: visaDetails.firstUsEntryDate || undefined,
      is_still_in_us: visaDetails.isStillInUs ?? true,
      intended_departure_date: visaDetails.intendedDepartureDate || undefined,
    });
    router.push('/intake/documents');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-8 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-200">
          <Plane className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Visa & Travel</h1>
        <p className="text-slate-500 text-sm mt-1">Tell us about your visa and time in the US.</p>
      </header>

      <form onSubmit={handleNext} className="max-w-md mx-auto w-full space-y-6">

        <FormField label="Current Visa Type" required>
          <select className={selectCls} value={visaDetails.visaType}
            onChange={(e) => updateVisaDetails({ visaType: e.target.value })} required>
            <option value="F-1">F-1 — Student</option>
            <option value="J-1">J-1 — Exchange Visitor</option>
            <option value="M-1">M-1 — Vocational Student</option>
            <option value="Q-1">Q-1 — Cultural Exchange</option>
            <option value="H-1B">H-1B — Specialty Occupation</option>
          </select>
        </FormField>

        {isJ1 && (
          <FormField
            label="J-1 Category"
            hint="Researchers/teachers get a 2-year exempt window instead of the 5-year student window — this changes your residency determination."
            required
          >
            <select
              className={selectCls}
              value={visaDetails.visaSubtype}
              onChange={(e) =>
                updateVisaDetails({
                  visaSubtype: e.target.value as VisaDetails['visaSubtype'],
                })
              }
              required
            >
              <option value="student">Student</option>
              <option value="teacher_researcher">Researcher / Teacher</option>
            </select>
          </FormField>
        )}

        <div className="border border-slate-200 rounded-2xl p-4 bg-white space-y-4">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Program Dates (I-20 or DS-2019)
          </p>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Visa Issue Date">
              <input type="date" className={inputCls} value={visaDetails.visaIssueDate}
                onChange={(e) => updateVisaDetails({ visaIssueDate: e.target.value })} />
            </FormField>
            <FormField label="Visa Expiry Date">
              <input type="date" className={inputCls} value={visaDetails.visaExpiryDate}
                onChange={(e) => updateVisaDetails({ visaExpiryDate: e.target.value })} />
            </FormField>
            <FormField label="Program Start Date">
              <input type="date" className={inputCls} value={visaDetails.programStartDate}
                onChange={(e) => updateVisaDetails({ programStartDate: e.target.value })} />
            </FormField>
            <FormField label="Program End Date">
              <input type="date" className={inputCls} value={visaDetails.programEndDate}
                onChange={(e) => updateVisaDetails({ programEndDate: e.target.value })} />
            </FormField>
          </div>
          <FormField label="Date You First Entered the US" required>
            <input type="date" className={inputCls} value={visaDetails.firstUsEntryDate}
              onChange={(e) => updateVisaDetails({ firstUsEntryDate: e.target.value })} required />
          </FormField>
          <FormField label="Intended Departure / Program End Date">
            <input type="date" className={inputCls} value={visaDetails.intendedDepartureDate}
              onChange={(e) => updateVisaDetails({ intendedDepartureDate: e.target.value })} />
          </FormField>
        </div>

        <FormField label="Country of Citizenship" required>
          <CountrySelect value={visaDetails.countryOfCitizenship}
            onChange={(v) => updateVisaDetails({ countryOfCitizenship: v })} required />
        </FormField>

        <FormField label="Country of Residence Before Entering the US" hint="Used for tax treaty determination." required>
          <CountrySelect value={visaDetails.countryOfResidenceBeforeUs}
            onChange={(v) => updateVisaDetails({ countryOfResidenceBeforeUs: v })} required />
        </FormField>

        <YesNoToggle label="Are you still in the US?"
          value={visaDetails.isStillInUs}
          onChange={(v) => updateVisaDetails({ isStillInUs: v })} />

        <YesNoToggle
          label="Did you change your visa type during 2025?"
          sublabel="E.g. changed from F-1 student to H-1B worker."
          value={visaDetails.changedVisaDuring2025}
          onChange={(v) => updateVisaDetails({ changedVisaDuring2025: v })} />

        <div className="space-y-2">
          <p className="text-sm font-bold text-slate-700">
            US Travel History
            <span className="ml-1 font-normal text-slate-400 text-xs">(all visits from first arrival)</span>
          </p>
          <p className="text-xs text-slate-500 leading-relaxed">
            Add each trip — entry and exit date. Leave &quot;Leave Date&quot; empty if still in the US.
          </p>
          <TravelHistoryTable
            entries={visaDetails.travelHistory}
            onChange={(entries) => updateVisaDetails({ travelHistory: entries })}
          />
        </div>

        <button type="submit"
          className="w-full h-14 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 hover:bg-slate-800 active:scale-95 transition-all shadow-xl shadow-slate-200">
          Next: Upload Documents
          <ChevronRight className="w-6 h-6" />
        </button>
      </form>
    </div>
  );
}
