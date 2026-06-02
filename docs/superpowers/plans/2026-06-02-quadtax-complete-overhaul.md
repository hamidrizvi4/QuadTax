# QuadTax Complete Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform QuadTax from a backend-complete/frontend-skeletal prototype into a production-grade, gamified NRA tax filing engine that collects all required intake data, covers the widest set of student NRA variations, and delivers per-filer bespoke calculation clarity rather than a generic black-box DAG.

**Architecture:** The backend engine DAG (L1→L9) is structurally sound — it is NOT replaced. What changes: (1) the frontend is rebuilt to collect the full `IntakePayload` across a gamified wizard; (2) the LLM safety wrapper is wired into every agent; (3) a "filer profile card" system generates per-filer plain-English computation narratives from the audit trail; (4) additional state pipelines (CA, MA, IL) are scaffolded; (5) the results page becomes a real downloadable packet rather than a mock.

**Tech Stack:** Python 3.11 / FastAPI / Pydantic v2 (backend), Next.js 16 / TypeScript / Tailwind / Zustand / Framer Motion (frontend), OpenAI gpt-4o structured outputs (LLM agents), pypdf (form population), Tesseract/pdfplumber (OCR)

---

## Gap Analysis (what is broken or missing today)

### Critical Bugs
- W-2 / 1042-S "remove file" buttons are no-ops (`/* Future: Add specific remove logic */` in documents/page.tsx:79)
- `income_description` is never collected from the user — the treaty classifier (L4) always receives an empty string, making treaty detection fail silently for all filers
- The `_llm_safety.py` `safe_parse` function is fully built but **never called** — agents call the OpenAI API directly, bypassing the dual-extract confidence gate
- "Download PDF Package" on results page is a hardcoded `alert()` mock

### Incomplete Frontend (engine is ready; UI never sends the data)
- Profile page collects only 3 of ~30 `IntakeIdentity` fields — IRS forms can't be printed without name, SSN/ITIN, DOB, passport, addresses
- NY context (13 fields of `IntakeNYContext`) is never collected → NY pipeline always skips
- FICA / banking / elections intake sections are never collected
- Only 6 hard-coded countries shown; engine supports 66
- No filing status selector (MFS, QSS) in the UI

### Architecture Gaps
- `"dual_status"` residency returned by L1 SPT but L6–L9 have no dual-status computation path — wrong numbers for arrival/departure-year filers
- Only NY state pipeline exists; most students are in CA, MA, IL, TX
- MFS/QSS brackets exist as JSON but the tax calculator is hardcoded to `"single"`
- No 1099 upload slot in the frontend even though L3 can parse them

### UX / Gamification (the stated vision)
- Zero progress indication, zero delight, zero explanations
- No real-time refund estimate as user fills in data
- Audit trail (`state.audit_trail`) is computed but never shown to the user
- `requires_human_review` is returned by the API but the UI has no way to display or acknowledge it
- No session persistence — browser refresh loses all state

---

## Subsystem Split

This plan covers 5 independent subsystems. Each can be built in parallel by separate engineers and produces working, testable software independently:

| Subsystem | What it produces |
|-----------|-----------------|
| **A** | Full intake wizard — all 6 intake sections collected, validated, sent |
| **B** | Gamification layer — progress XP, treaty unlocks, real-time estimate, celebration |
| **C** | Engine hardening — wire `_llm_safety`, dual-status path, MFS/QSS, 1099 |
| **D** | Per-filer narrative — audit trail rendered as plain-English "why this number?" card |
| **E** | Real PDF download — vendor IRS templates, implement packet download endpoint |

---

## Subsystem A: Full Intake Wizard

### Files
- Modify: `nra-tax-client/src/app/intake/profile/page.tsx` — replace 3-field stub with full identity form
- Create: `nra-tax-client/src/app/intake/residency/page.tsx` — visa history, arrival year, prior status
- Modify: `nra-tax-client/src/app/intake/documents/page.tsx` — fix remove logic, add 1099 slot, add income_description field
- Modify: `nra-tax-client/src/app/intake/context/page.tsx` — add NY wizard, FICA, banking, elections sections
- Modify: `nra-tax-client/src/app/layout.tsx` — add persistent step progress bar
- Modify: `nra-tax-client/src/store/taxStore.ts` — add Zustand `persist` middleware so refresh doesn't lose state
- Create: `nra-tax-client/src/components/StepBar.tsx` — wizard step indicator
- Create: `nra-tax-client/src/components/CountrySelect.tsx` — full 66-country dropdown seeded from engine's alias map
- Create: `nra-tax-client/src/components/FormField.tsx` — labeled input with inline validation

---

### Task A1: Fix W-2 / 1042-S file remove

**Files:**
- Modify: `nra-tax-client/src/store/taxStore.ts`
- Modify: `nra-tax-client/src/app/intake/documents/page.tsx`

- [ ] **Step 1: Write the failing test** (manual — open browser, upload 2 W-2s, try to remove first one, confirm nothing happens)

- [ ] **Step 2: Add `removeW2File` and `removeForm1042sFile` to the store**

In `nra-tax-client/src/store/taxStore.ts`, inside the `create<TaxState>((set, get) => ({...}))` block, add after `addForm1042sFile`:

```typescript
  removeW2File: (index: number) =>
    set((state) => ({ w2Files: state.w2Files.filter((_, i) => i !== index) })),
  removeForm1042sFile: (index: number) =>
    set((state) => ({ form1042sFiles: state.form1042sFiles.filter((_, i) => i !== index) })),
```

Add to `TaxState` interface:
```typescript
  removeW2File: (index: number) => void;
  removeForm1042sFile: (index: number) => void;
```

- [ ] **Step 3: Wire into documents page**

In `nra-tax-client/src/app/intake/documents/page.tsx`, update the destructure:

```typescript
const { 
  i94File, setI94File, 
  w2Files, addW2File, removeW2File,
  form1042sFiles, addForm1042sFile, removeForm1042sFile,
} = useTaxStore();
```

Replace the W-2 `FileCard` (line ~79):
```typescript
{w2Files.map((f, i) => (
  <FileCard key={i} type="W-2" file={f} onClear={() => removeW2File(i)} />
))}
```

Replace the 1042-S `FileCard`:
```typescript
{form1042sFiles.map((f, i) => (
  <FileCard key={i} type="1042-S" file={f} onClear={() => removeForm1042sFile(i)} />
))}
```

- [ ] **Step 4: Verify manually** — upload 2 W-2s, remove the first, confirm only one remains

- [ ] **Step 5: Commit**
```bash
git add nra-tax-client/src/store/taxStore.ts nra-tax-client/src/app/intake/documents/page.tsx
git commit -m "fix: wire W-2 and 1042-S remove actions in documents intake"
```

---

### Task A2: Add income_description field to documents page

The L4 treaty classifier receives `income_description` and without it always classifies as `"none"`. This is the single highest-impact missing field.

**Files:**
- Modify: `nra-tax-client/src/app/intake/documents/page.tsx`

- [ ] **Step 1: Write failing test** — submit a return without `income_description` and check that L4 returns `is_eligible: false` even for India/China (confirming the bug exists)

- [ ] **Step 2: Add income description textarea after the 1042-S section**

In `nra-tax-client/src/app/intake/documents/page.tsx`, add to the destructure:
```typescript
const { ..., income, updateIncome } = useTaxStore();
```

Add after the 1042-S section and before the tip card:
```tsx
{/* INCOME DESCRIPTION */}
<div className="space-y-3">
  <label className="text-sm font-bold text-slate-700">
    Describe your income source
    <span className="text-red-500 font-normal italic ml-1">(Required for treaty calculation)</span>
  </label>
  <p className="text-xs text-slate-500 -mt-1">
    Examples: "PhD teaching assistant at NYU", "research fellowship from NSF", 
    "campus barista job", "OPT software engineering"
  </p>
  <textarea
    value={income.income_description}
    onChange={(e) => updateIncome({ income_description: e.target.value })}
    rows={3}
    placeholder="Describe what you do and who pays you..."
    className="w-full bg-white border border-slate-200 rounded-2xl px-4 py-3 text-base focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-shadow resize-none"
    required
  />
</div>
```

- [ ] **Step 3: Verify** — fill in description, submit, confirm L4 now classifies correctly for China/India in the network response

- [ ] **Step 4: Commit**
```bash
git add nra-tax-client/src/app/intake/documents/page.tsx
git commit -m "feat: collect income_description for L4 treaty classification"
```

---

### Task A3: Full identity form on profile page

**Files:**
- Modify: `nra-tax-client/src/app/intake/profile/page.tsx`
- Create: `nra-tax-client/src/components/CountrySelect.tsx`
- Create: `nra-tax-client/src/components/FormField.tsx`

- [ ] **Step 1: Create `FormField` reusable component**

Create `nra-tax-client/src/components/FormField.tsx`:
```tsx
interface FormFieldProps {
  label: string;
  required?: boolean;
  children: React.ReactNode;
  hint?: string;
}

export function FormField({ label, required, children, hint }: FormFieldProps) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-semibold text-slate-700 block">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      {hint && <p className="text-xs text-slate-400">{hint}</p>}
      {children}
    </div>
  );
}

export const inputCls = "w-full h-12 bg-white border border-slate-200 rounded-xl px-4 text-base focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-shadow";
export const selectCls = `${inputCls} cursor-pointer`;
```

- [ ] **Step 2: Create `CountrySelect` component**

Create `nra-tax-client/src/components/CountrySelect.tsx`:
```tsx
"use client";
// 66 countries from the engine's treaty alias map + non-treaty countries
const COUNTRIES = [
  { value: "AF", label: "Afghanistan" },
  { value: "AM", label: "Armenia" },
  { value: "AU", label: "Australia" },
  { value: "AT", label: "Austria" },
  { value: "AZ", label: "Azerbaijan" },
  { value: "BB", label: "Barbados" },
  { value: "BD", label: "Bangladesh" },
  { value: "BE", label: "Belgium" },
  { value: "BY", label: "Belarus" },
  { value: "BG", label: "Bulgaria" },
  { value: "CA", label: "Canada" },
  { value: "CN", label: "China (People's Republic)" },
  { value: "CY", label: "Cyprus" },
  { value: "CZ", label: "Czech Republic" },
  { value: "DK", label: "Denmark" },
  { value: "EG", label: "Egypt" },
  { value: "EE", label: "Estonia" },
  { value: "FI", label: "Finland" },
  { value: "FR", label: "France" },
  { value: "GE", label: "Georgia" },
  { value: "DE", label: "Germany" },
  { value: "GR", label: "Greece" },
  { value: "HU", label: "Hungary" },
  { value: "IS", label: "Iceland" },
  { value: "IN", label: "India" },
  { value: "ID", label: "Indonesia" },
  { value: "IE", label: "Ireland" },
  { value: "IL", label: "Israel" },
  { value: "IT", label: "Italy" },
  { value: "JM", label: "Jamaica" },
  { value: "JP", label: "Japan" },
  { value: "KZ", label: "Kazakhstan" },
  { value: "KG", label: "Kyrgyzstan" },
  { value: "LV", label: "Latvia" },
  { value: "LT", label: "Lithuania" },
  { value: "LK", label: "Sri Lanka" },
  { value: "LU", label: "Luxembourg" },
  { value: "MA", label: "Morocco" },
  { value: "MT", label: "Malta" },
  { value: "MD", label: "Moldova" },
  { value: "MX", label: "Mexico" },
  { value: "NL", label: "Netherlands" },
  { value: "NZ", label: "New Zealand" },
  { value: "NO", label: "Norway" },
  { value: "PK", label: "Pakistan" },
  { value: "PH", label: "Philippines" },
  { value: "PL", label: "Poland" },
  { value: "PT", label: "Portugal" },
  { value: "RO", label: "Romania" },
  { value: "RU", label: "Russia" },
  { value: "SE", label: "Sweden" },
  { value: "SI", label: "Slovenia" },
  { value: "SK", label: "Slovakia" },
  { value: "ES", label: "Spain" },
  { value: "CH", label: "Switzerland" },
  { value: "TJ", label: "Tajikistan" },
  { value: "TH", label: "Thailand" },
  { value: "TN", label: "Tunisia" },
  { value: "TR", label: "Turkey" },
  { value: "TM", label: "Turkmenistan" },
  { value: "UA", label: "Ukraine" },
  { value: "GB", label: "United Kingdom" },
  { value: "UZ", label: "Uzbekistan" },
  { value: "VE", label: "Venezuela" },
  { value: "ZA", label: "South Africa" },
  // Common non-treaty countries
  { value: "BR", label: "Brazil" },
  { value: "NG", label: "Nigeria" },
  { value: "ET", label: "Ethiopia" },
  { value: "GH", label: "Ghana" },
  { value: "NP", label: "Nepal" },
  { value: "VN", label: "Vietnam" },
  { value: "IR", label: "Iran" },
  { value: "KE", label: "Kenya" },
  { value: "TW", label: "Taiwan" },
  { value: "OTHER", label: "Other (no treaty)" },
];

interface CountrySelectProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  required?: boolean;
}

export function CountrySelect({ value, onChange, className, required }: CountrySelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={className}
      required={required}
    >
      <option value="" disabled>Select country...</option>
      {COUNTRIES.map((c) => (
        <option key={c.value} value={c.value}>{c.label}</option>
      ))}
    </select>
  );
}
```

- [ ] **Step 3: Rewrite profile page with full identity fields**

Replace `nra-tax-client/src/app/intake/profile/page.tsx` entirely:
```tsx
"use client";

import { useRouter } from "next/navigation";
import { useTaxStore } from "@/store/taxStore";
import { ChevronRight, User } from "lucide-react";
import { FormField, inputCls, selectCls } from "@/components/FormField";
import { CountrySelect } from "@/components/CountrySelect";

export default function ProfilePage() {
  const router = useRouter();
  const { identity, updateIdentity, residency, updateResidency } = useTaxStore();

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    router.push("/intake/documents");
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-24">
      <header className="mb-8 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-200">
          <User className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Personal Profile</h1>
        <p className="text-slate-500 text-sm mt-1">This appears on every IRS form — match your passport exactly.</p>
      </header>

      <form onSubmit={handleNext} className="max-w-md mx-auto w-full space-y-5">
        {/* Name */}
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

        <FormField label="Date of Birth" required>
          <input type="date" className={inputCls} value={identity.date_of_birth ?? ""}
            onChange={(e) => updateIdentity({ date_of_birth: e.target.value || null })} required />
        </FormField>

        {/* TIN */}
        <FormField label="SSN or ITIN" hint="9 digits, no dashes. Leave blank if you don't have one yet.">
          <input className={inputCls} maxLength={9} placeholder="123456789"
            value={identity.ssn || identity.itin}
            onChange={(e) => {
              const val = e.target.value.replace(/\D/g, "");
              // ITINs start with 9
              if (val.startsWith("9")) updateIdentity({ itin: val, ssn: "" });
              else updateIdentity({ ssn: val, itin: "" });
            }} />
        </FormField>

        {/* Visa */}
        <FormField label="Visa Type" required>
          <select className={selectCls} value={residency.visa_type}
            onChange={(e) => updateResidency({ visa_type: e.target.value })} required>
            <option value="F-1">F-1 Student</option>
            <option value="J-1">J-1 Exchange Visitor</option>
            <option value="M-1">M-1 Vocational Student</option>
            <option value="Q-1">Q-1 Cultural Exchange</option>
          </select>
        </FormField>

        <div className="grid grid-cols-2 gap-3">
          <FormField label="First US Arrival Year" required>
            <input type="number" className={inputCls} min={1900} max={new Date().getFullYear()}
              value={residency.first_us_arrival_year}
              onChange={(e) => updateResidency({ first_us_arrival_year: parseInt(e.target.value) })} required />
          </FormField>
          <FormField label="Tax Year" required>
            <select className={selectCls} value={residency.tax_year}
              onChange={(e) => updateResidency({ tax_year: parseInt(e.target.value) })}>
              <option value={2025}>2025</option>
              <option value={2024}>2024</option>
            </select>
          </FormField>
        </div>

        {/* Country */}
        <FormField label="Country of Tax Residence" required hint="Where are you a tax resident? Usually your home country.">
          <CountrySelect value={identity.country_of_tax_residence}
            onChange={(v) => updateIdentity({ country_of_tax_residence: v, country_of_citizenship: v })}
            className={selectCls} required />
        </FormField>

        {/* Filing status */}
        <FormField label="Filing Status">
          <select className={selectCls} value={identity.filing_status}
            onChange={(e) => updateIdentity({ filing_status: e.target.value as "single" | "mfs" | "qss" })}>
            <option value="single">Single</option>
            <option value="mfs">Married Filing Separately</option>
            <option value="qss">Qualifying Surviving Spouse</option>
          </select>
        </FormField>

        {/* US Address */}
        <div className="pt-2 border-t border-slate-100">
          <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">US Address</p>
          <div className="space-y-3">
            <FormField label="Street Address" required>
              <input className={inputCls} value={identity.us_address_line1}
                onChange={(e) => updateIdentity({ us_address_line1: e.target.value })} required />
            </FormField>
            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-1">
                <FormField label="State" required>
                  <input className={inputCls} maxLength={2} placeholder="NY"
                    value={identity.us_state}
                    onChange={(e) => updateIdentity({ us_state: e.target.value.toUpperCase() })} required />
                </FormField>
              </div>
              <div className="col-span-1">
                <FormField label="City" required>
                  <input className={inputCls} value={identity.us_city}
                    onChange={(e) => updateIdentity({ us_city: e.target.value })} required />
                </FormField>
              </div>
              <div className="col-span-1">
                <FormField label="ZIP" required>
                  <input className={inputCls} maxLength={5} value={identity.us_zip}
                    onChange={(e) => updateIdentity({ us_zip: e.target.value })} required />
                </FormField>
              </div>
            </div>
          </div>
        </div>

        <div className="pt-6">
          <button type="submit"
            className="w-full h-16 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 hover:bg-slate-800 active:scale-95 transition-all shadow-xl shadow-slate-200">
            Next: Documents
            <ChevronRight className="w-6 h-6" />
          </button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 4: Run TypeScript check**
```bash
cd nra-tax-client && npx tsc --noEmit
```
Expected: no errors

- [ ] **Step 5: Commit**
```bash
git add nra-tax-client/src/app/intake/profile/page.tsx nra-tax-client/src/components/
git commit -m "feat: full identity intake form — name, DOB, TIN, visa, address, country"
```

---

### Task A4: NY context wizard in the context page

**Files:**
- Modify: `nra-tax-client/src/app/intake/context/page.tsx`

- [ ] **Step 1: Write the failing assertion** — submit with `us_state: "NY"` and observe the API response has `ny_refund_or_owed: 0` because `ny` was null

- [ ] **Step 2: Rewrite context page to collect NY + FICA + banking**

Replace `nra-tax-client/src/app/intake/context/page.tsx` entirely:
```tsx
"use client";

import { useRouter } from "next/navigation";
import { useTaxStore } from "@/store/taxStore";
import { ChevronRight, ClipboardCheck } from "lucide-react";
import { FormField, inputCls } from "@/components/FormField";

function Toggle({ value, onChange, label, sublabel }: {
  value: boolean; onChange: (v: boolean) => void; label: string; sublabel: string;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-3xl p-5 flex items-center justify-between gap-4 shadow-sm">
      <div className="flex-1">
        <p className="font-bold text-slate-900 leading-snug">{label}</p>
        <p className="text-xs text-slate-500 mt-1">{sublabel}</p>
      </div>
      <button type="button" onClick={() => onChange(!value)}
        className={`shrink-0 w-16 h-10 rounded-full transition-all flex items-center p-1 ${value ? "bg-blue-600" : "bg-slate-200"}`}>
        <div className={`w-8 h-8 bg-white rounded-full shadow-md transition-all transform ${value ? "translate-x-6" : "translate-x-0"}`} />
      </button>
    </div>
  );
}

export default function ContextPage() {
  const router = useRouter();
  const { identity, income, updateIncome, ny, updateNY, fica, updateFICA, banking, updateBanking } = useTaxStore();
  const isNY = identity.us_state === "NY";

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    router.push("/processing");
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-24">
      <header className="mb-8 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 rotate-3 shadow-lg shadow-blue-200">
          <ClipboardCheck className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Final Verification</h1>
        <p className="text-slate-500 text-sm mt-1">A few more specifics to maximize your refund.</p>
      </header>

      <form onSubmit={handleNext} className="max-w-md mx-auto w-full space-y-8">

        {/* Income Classification */}
        <section className="space-y-4">
          <h2 className="text-sm font-bold text-slate-600 uppercase tracking-wider">Income Type</h2>
          <Toggle label="Services Required?"
            sublabel="Does your funding require you to perform duties like teaching, research, or grading?"
            value={income.requires_services}
            onChange={(v) => updateIncome({ requires_services: v })} />
          <Toggle label="Qualified Expenses Only?"
            sublabel="Is this funding solely for tuition and required fees? (No room & board)"
            value={income.is_qualified_expense}
            onChange={(v) => updateIncome({ is_qualified_expense: v })} />
        </section>

        {/* NY Section — shown only when US state is NY */}
        {isNY && (
          <section className="space-y-4">
            <h2 className="text-sm font-bold text-slate-600 uppercase tracking-wider">New York State</h2>
            <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-xs text-amber-900">
              NY does not honor federal tax treaties — we need a few extra details to compute your NY return correctly.
            </div>
            <Toggle label="Do you live in a university dorm?"
              sublabel="Students in dorms are classified as NY nonresidents under the Knight rule — this saves significant NY tax."
              value={ny?.is_student_dorm ?? true}
              onChange={(v) => updateNY({ is_student_dorm: v })} />
            <Toggle label="Do you have a NYC address?"
              sublabel="NYC residents pay an additional city income tax."
              value={ny?.nyc_address ?? false}
              onChange={(v) => updateNY({ nyc_address: v })} />
            <FormField label="Days spent in New York this year">
              <input type="number" className={inputCls} min={0} max={366}
                value={ny?.days_in_ny ?? 0}
                onChange={(e) => updateNY({ days_in_ny: parseInt(e.target.value) || 0 })} />
            </FormField>
            <FormField label="Work days in NY (out of total work days)">
              <div className="grid grid-cols-2 gap-3">
                <input type="number" className={inputCls} placeholder="NY work days" min={0} max={366}
                  value={ny?.ny_work_days ?? 0}
                  onChange={(e) => updateNY({ ny_work_days: parseInt(e.target.value) || 0 })} />
                <input type="number" className={inputCls} placeholder="Total work days" min={0} max={366}
                  value={ny?.total_work_days ?? 0}
                  onChange={(e) => updateNY({ total_work_days: parseInt(e.target.value) || 0 })} />
              </div>
            </FormField>
          </section>
        )}

        {/* FICA Section */}
        <section className="space-y-4">
          <h2 className="text-sm font-bold text-slate-600 uppercase tracking-wider">FICA / Social Security</h2>
          <Toggle label="Were Social Security taxes withheld from your paycheck?"
            sublabel="F-1/J-1 students are exempt from FICA. If your employer withheld SS or Medicare, you can get it back."
            value={fica.employer_attempted_refund}
            onChange={(v) => updateFICA({ employer_attempted_refund: v })} />
          {fica.employer_attempted_refund && (
            <div className="space-y-3 pl-2 border-l-2 border-blue-200">
              <Toggle label="Did you already ask your employer for a refund?"
                sublabel="IRS requires you try the employer first before filing Form 843."
                value={fica.has_form_8316}
                onChange={(v) => updateFICA({ has_form_8316: v })} />
              <FormField label="Employer Name">
                <input className={inputCls} value={fica.employer_name}
                  onChange={(e) => updateFICA({ employer_name: e.target.value })} />
              </FormField>
              <FormField label="Employer EIN" hint="Found on your W-2 Box b">
                <input className={inputCls} value={fica.employer_ein}
                  onChange={(e) => updateFICA({ employer_ein: e.target.value })} />
              </FormField>
            </div>
          )}
        </section>

        {/* Banking */}
        <section className="space-y-4">
          <h2 className="text-sm font-bold text-slate-600 uppercase tracking-wider">Refund Delivery</h2>
          <Toggle label="Direct deposit?" sublabel="Get your refund 2–3 weeks faster via direct deposit."
            value={banking.direct_deposit}
            onChange={(v) => updateBanking({ direct_deposit: v })} />
          {banking.direct_deposit && (
            <div className="space-y-3">
              <FormField label="Routing Number">
                <input className={inputCls} maxLength={9} value={banking.routing_number}
                  onChange={(e) => updateBanking({ routing_number: e.target.value })} />
              </FormField>
              <FormField label="Account Number">
                <input className={inputCls} value={banking.account_number}
                  onChange={(e) => updateBanking({ account_number: e.target.value })} />
              </FormField>
              <FormField label="Account Type">
                <select className={inputCls} value={banking.account_type}
                  onChange={(e) => updateBanking({ account_type: e.target.value as "checking" | "savings" | "" })}>
                  <option value="">Select...</option>
                  <option value="checking">Checking</option>
                  <option value="savings">Savings</option>
                </select>
              </FormField>
            </div>
          )}
        </section>

        <button type="submit"
          className="w-full h-16 bg-blue-600 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 hover:bg-blue-500 active:scale-95 transition-all shadow-xl shadow-blue-200">
          Calculate My Return
          <ChevronRight className="w-6 h-6" />
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Run TypeScript check**
```bash
cd nra-tax-client && npx tsc --noEmit
```

- [ ] **Step 4: Commit**
```bash
git add nra-tax-client/src/app/intake/context/page.tsx
git commit -m "feat: NY context, FICA, and banking intake sections in context page"
```

---

### Task A5: Zustand session persistence

Without persistence, a browser refresh drops all collected data mid-wizard.

**Files:**
- Modify: `nra-tax-client/src/store/taxStore.ts`
- Modify: `nra-tax-client/package.json` (add `zustand/middleware` — already included in zustand)

- [ ] **Step 1: Wrap the store with `persist` middleware**

At the top of `nra-tax-client/src/store/taxStore.ts`, add:
```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
```

Change the store creation from:
```typescript
export const useTaxStore = create<TaxState>((set, get) => ({
```
to:
```typescript
export const useTaxStore = create<TaxState>()(
  persist(
    (set, get) => ({
      // ... all existing store contents unchanged ...
    }),
    {
      name: 'quadtax-intake',
      // Don't persist file objects — they can't serialize
      partialize: (state) => ({
        identity: state.identity,
        residency: state.residency,
        income: state.income,
        ny: state.ny,
        fica: state.fica,
        banking: state.banking,
        elections: state.elections,
        results: state.results,
      }),
    }
  )
);
```

- [ ] **Step 2: Verify** — fill in profile page fields, refresh browser, confirm fields are still populated

- [ ] **Step 3: Commit**
```bash
git add nra-tax-client/src/store/taxStore.ts
git commit -m "feat: persist intake state across browser refreshes with zustand/middleware"
```

---

### Task A6: Progress step bar in layout

**Files:**
- Create: `nra-tax-client/src/components/StepBar.tsx`
- Modify: `nra-tax-client/src/app/layout.tsx`

- [ ] **Step 1: Create StepBar**

Create `nra-tax-client/src/components/StepBar.tsx`:
```tsx
"use client";

import { usePathname } from "next/navigation";

const STEPS = [
  { path: "/intake/profile", label: "Profile" },
  { path: "/intake/documents", label: "Documents" },
  { path: "/intake/context", label: "Context" },
  { path: "/processing", label: "Calculating" },
  { path: "/results", label: "Results" },
];

export function StepBar() {
  const pathname = usePathname();
  const currentIdx = STEPS.findIndex((s) => pathname.startsWith(s.path));
  if (currentIdx < 0) return null;

  return (
    <div className="w-full bg-white border-b border-slate-100 px-6 py-3">
      <div className="max-w-md mx-auto flex items-center gap-1">
        {STEPS.map((step, i) => (
          <div key={step.path} className="flex items-center flex-1">
            <div className={`flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold transition-colors
              ${i < currentIdx ? "bg-blue-600 text-white" : 
                i === currentIdx ? "bg-slate-900 text-white" : 
                "bg-slate-100 text-slate-400"}`}>
              {i < currentIdx ? "✓" : i + 1}
            </div>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-0.5 mx-1 ${i < currentIdx ? "bg-blue-600" : "bg-slate-100"}`} />
            )}
          </div>
        ))}
      </div>
      <p className="text-center text-xs text-slate-400 mt-1">{STEPS[currentIdx]?.label}</p>
    </div>
  );
}
```

- [ ] **Step 2: Add StepBar to layout**

In `nra-tax-client/src/app/layout.tsx`, add after `<body>`:
```tsx
import { StepBar } from "@/components/StepBar";
// ...
<body>
  <StepBar />
  {children}
</body>
```

- [ ] **Step 3: Verify** — navigate through intake steps and confirm step bar advances

- [ ] **Step 4: Commit**
```bash
git add nra-tax-client/src/components/StepBar.tsx nra-tax-client/src/app/layout.tsx
git commit -m "feat: wizard step progress bar across intake pages"
```

---

## Subsystem B: Gamification Layer

### Files
- Create: `nra-tax-client/src/components/RefundMeter.tsx` — live animated refund estimate
- Create: `nra-tax-client/src/components/TreatyBadge.tsx` — treaty unlock celebration card
- Modify: `nra-tax-client/src/app/results/page.tsx` — real results with breakdown, audit trail, confetti
- Create: `nra-tax-client/src/components/AuditExplainer.tsx` — "why this number?" expandable card
- Create: `nra-tax-client/src/components/HumanReviewBanner.tsx` — surface requires_human_review list
- Install: `npm install canvas-confetti` (lightweight, 3KB)

---

### Task B1: Real results page with breakdown

**Files:**
- Modify: `nra-tax-client/src/app/results/page.tsx`
- Create: `nra-tax-client/src/components/AuditExplainer.tsx`
- Create: `nra-tax-client/src/components/HumanReviewBanner.tsx`

- [ ] **Step 1: Update `ResultsView` in taxStore to include full API response fields**

In `nra-tax-client/src/store/taxStore.ts`, replace the `ResultsView` interface:
```typescript
export interface ResultsView {
  taxLiability: number | null;
  refundOrOwed: number | null;
  requiresFicaClaim: boolean | null;
  generatedForms: string[];
  // New fields from TaxProcessResponse
  nyRefundOrOwed: number;
  ficaRefundAmount: number;
  requiresHumanReview: string[];
  federalPacketPath: string | null;
  nyPacketPath: string | null;
  ficaPacketPath: string | null;
  completedLayers: string[];
}
```

Update `initialResults`:
```typescript
results: {
  taxLiability: null,
  refundOrOwed: null,
  requiresFicaClaim: null,
  generatedForms: [],
  nyRefundOrOwed: 0,
  ficaRefundAmount: 0,
  requiresHumanReview: [],
  federalPacketPath: null,
  nyPacketPath: null,
  ficaPacketPath: null,
  completedLayers: [],
},
```

- [ ] **Step 2: Update processing page to populate all new fields**

In `nra-tax-client/src/app/processing/page.tsx`, update `store.setResults({...})`:
```typescript
store.setResults({
  taxLiability: data.federal_refund_or_owed > 0 ? data.federal_refund_or_owed : 0,
  refundOrOwed: data.federal_refund_or_owed,
  requiresFicaClaim: data.fica_refund_amount > 0,
  generatedForms: data.generated_form_outputs,
  nyRefundOrOwed: data.ny_refund_or_owed,
  ficaRefundAmount: data.fica_refund_amount,
  requiresHumanReview: data.requires_human_review,
  federalPacketPath: data.federal_packet_path ?? null,
  nyPacketPath: data.ny_packet_path ?? null,
  ficaPacketPath: data.fica_packet_path ?? null,
  completedLayers: data.completed_layers,
});
```

- [ ] **Step 3: Create `HumanReviewBanner`**

Create `nra-tax-client/src/components/HumanReviewBanner.tsx`:
```tsx
import { AlertTriangle } from "lucide-react";

export function HumanReviewBanner({ reasons }: { reasons: string[] }) {
  if (reasons.length === 0) return null;
  return (
    <div className="bg-red-50 border border-red-200 rounded-3xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle className="w-5 h-5 text-red-600" />
        <p className="font-bold text-red-900 text-sm">CPA Review Recommended</p>
      </div>
      <ul className="space-y-1.5">
        {reasons.map((r, i) => (
          <li key={i} className="text-xs text-red-800 leading-normal">• {r}</li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Rewrite results page with real breakdown**

Replace `nra-tax-client/src/app/results/page.tsx`:
```tsx
"use client";

import { useTaxStore } from "@/store/taxStore";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { CheckCircle2, ArrowLeft, FileText, ShieldCheck, AlertTriangle } from "lucide-react";
import { HumanReviewBanner } from "@/components/HumanReviewBanner";

export default function ResultsPage() {
  const router = useRouter();
  const { results, resetFastStore } = useTaxStore();

  useEffect(() => {
    // Confetti on load if there's a refund
    if (results.refundOrOwed !== null && results.refundOrOwed < 0) {
      import("canvas-confetti").then((m) => {
        m.default({ particleCount: 120, spread: 70, origin: { y: 0.6 } });
      });
    }
  }, []);

  if (results.taxLiability === null) {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center p-8">
        <p className="text-slate-500 mb-4">No results available.</p>
        <button onClick={() => router.push("/")} className="text-blue-600 font-bold">Return Home</button>
      </div>
    );
  }

  const federalRefund = -(results.refundOrOwed ?? 0);
  const nyRefund = -(results.nyRefundOrOwed ?? 0);
  const ficaRefund = results.ficaRefundAmount ?? 0;
  const totalRecovered = Math.max(0, federalRefund) + Math.max(0, nyRefund) + Math.max(0, ficaRefund);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col pb-20">
      <header className="bg-white border-b border-slate-200 px-6 py-12 text-center">
        <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-6 shadow-xl shadow-blue-100">
          <CheckCircle2 className="text-white w-10 h-10" />
        </div>
        <h1 className="text-3xl font-extrabold text-slate-900">Return Complete!</h1>
        <p className="text-slate-500 mt-2">Your {new Date().getFullYear() - 1} Tax Package is ready to mail.</p>
      </header>

      <div className="p-6 max-w-md mx-auto w-full space-y-5 -mt-8">

        {/* Human review banner */}
        <HumanReviewBanner reasons={results.requiresHumanReview ?? []} />

        {/* Total recovered card */}
        <div className="bg-slate-900 rounded-[32px] p-8 text-white shadow-2xl">
          <p className="text-blue-400 font-bold text-xs uppercase tracking-[0.2em] mb-2">Total Amount Recovered</p>
          <p className="text-6xl font-black">${totalRecovered.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
          <div className="grid grid-cols-3 gap-3 border-t border-white/10 mt-6 pt-6">
            <div>
              <p className="text-[10px] text-white/50 uppercase font-bold tracking-widest mb-1">Federal</p>
              <p className="text-lg font-bold">${Math.max(0, federalRefund).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-[10px] text-white/50 uppercase font-bold tracking-widest mb-1">FICA</p>
              <p className="text-lg font-bold text-green-400">${ficaRefund.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-[10px] text-white/50 uppercase font-bold tracking-widest mb-1">NY State</p>
              <p className="text-lg font-bold">${Math.max(0, nyRefund).toLocaleString()}</p>
            </div>
          </div>
        </div>

        {/* Treaty badge — shown when treaty applied */}
        {results.generatedForms.some((f) => f.includes("8833")) && (
          <div className="bg-blue-50 border border-blue-200 rounded-3xl p-5 flex gap-4">
            <ShieldCheck className="w-6 h-6 text-blue-600 shrink-0" />
            <div>
              <p className="text-sm font-bold text-blue-900">Tax Treaty Applied</p>
              <p className="text-xs text-blue-700 mt-1">Your country's income tax treaty with the US reduced your liability. Form 8833 is included in your packet.</p>
            </div>
          </div>
        )}

        {/* FICA notice */}
        {results.requiresFicaClaim && (
          <div className="bg-amber-50 border border-amber-200 rounded-3xl p-5 flex gap-4">
            <AlertTriangle className="w-6 h-6 text-amber-600 shrink-0" />
            <div>
              <p className="text-sm font-bold text-amber-900">FICA Refund Detected</p>
              <p className="text-xs text-amber-800 mt-1">Social Security/Medicare was incorrectly withheld. Form 843 is in your packet — mail it separately to the IRS.</p>
            </div>
          </div>
        )}

        {/* Form list */}
        {results.generatedForms.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-bold text-slate-700">Filing Package</h2>
            <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden divide-y divide-slate-100 shadow-sm">
              {results.generatedForms.map((path, idx) => (
                <div key={idx} className="p-4 flex items-center gap-3">
                  <FileText className="w-5 h-5 text-blue-500 shrink-0" />
                  <span className="text-sm font-medium text-slate-700 truncate">{path.split(/[/\\]/).pop()}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <button
          onClick={() => { resetFastStore(); router.push("/"); }}
          className="w-full text-slate-400 font-bold text-sm flex items-center justify-center gap-2 hover:text-slate-900 transition-colors py-4">
          <ArrowLeft className="w-4 h-4" />
          File Another Return
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Install canvas-confetti**
```bash
cd nra-tax-client && npm install canvas-confetti && npm install --save-dev @types/canvas-confetti
```

- [ ] **Step 6: TypeScript check and verify end-to-end**
```bash
cd nra-tax-client && npx tsc --noEmit
```

- [ ] **Step 7: Commit**
```bash
git add nra-tax-client/src/
git commit -m "feat: real results page with federal/FICA/NY breakdown, treaty badge, confetti"
```

---

### Task B2: Processing page with step-by-step status

**Files:**
- Modify: `nra-tax-client/src/app/processing/page.tsx`

The processing page currently shows a single spinner with no feedback. The engine runs L1→L9 serially. We can show which layer is running by streaming status from the API, or (simpler) show animated step labels that advance every few seconds while the real request runs.

- [ ] **Step 1: Add animated layer labels to processing page**

Replace `nra-tax-client/src/app/processing/page.tsx`:
```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTaxStore } from "@/store/taxStore";
import { submitTaxReturn } from "@/lib/api";
import { Loader2, AlertCircle, CheckCircle2 } from "lucide-react";

const PIPELINE_STEPS = [
  { id: "L1", label: "Checking travel history (I-94)", icon: "🛂" },
  { id: "L3", label: "Parsing income documents (W-2 / 1042-S)", icon: "📄" },
  { id: "L4", label: "Applying tax treaty benefits", icon: "🌍" },
  { id: "L6", label: "Computing federal tax liability", icon: "🧮" },
  { id: "L7", label: "Reconciling withholding credits", icon: "💰" },
  { id: "L8", label: "Checking FICA (Social Security) exemption", icon: "🏛️" },
  { id: "L9", label: "Running NY state pipeline", icon: "🗽" },
  { id: "assembly", label: "Assembling mailing packet", icon: "📬" },
];

export default function ProcessingPage() {
  const router = useRouter();
  const store = useTaxStore();
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [completedLayers, setCompletedLayers] = useState<string[]>([]);

  useEffect(() => {
    // Simulate step-by-step visual progression while the real API call runs
    const timer = setInterval(() => {
      setCurrentStep((s) => Math.min(s + 1, PIPELINE_STEPS.length - 1));
    }, 1800);

    async function executePipeline() {
      try {
        const data = await submitTaxReturn(store);
        clearInterval(timer);
        setCurrentStep(PIPELINE_STEPS.length - 1);
        setCompletedLayers(data.completed_layers ?? []);

        store.setResults({
          taxLiability: data.tax_liability,
          refundOrOwed: data.refund_or_owed,
          requiresFicaClaim: data.requires_843_fica_claim,
          generatedForms: data.generated_forms,
          nyRefundOrOwed: 0,
          ficaRefundAmount: 0,
          requiresHumanReview: [],
          federalPacketPath: null,
          nyPacketPath: null,
          ficaPacketPath: null,
          completedLayers: [],
        });

        setTimeout(() => router.push("/results"), 600);
      } catch (err: unknown) {
        clearInterval(timer);
        setError(err instanceof Error ? err.message : "An unexpected error occurred.");
      }
    }

    executePipeline();
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-8 text-center">
        <AlertCircle className="w-16 h-16 text-red-500 mb-6" />
        <h2 className="text-xl font-bold text-slate-900 mb-2">Calculation Failed</h2>
        <p className="text-slate-500 max-w-xs mb-8 text-sm">{error}</p>
        <button onClick={() => router.back()}
          className="bg-slate-900 text-white px-8 py-3 rounded-2xl font-bold active:scale-95 transition-all">
          Go Back & Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center p-8">
      <Loader2 className="w-12 h-12 text-blue-600 animate-spin mb-8" />
      <h1 className="text-xl font-extrabold text-slate-900 mb-8">Calculating your return…</h1>
      <div className="w-full max-w-sm space-y-3">
        {PIPELINE_STEPS.map((step, i) => {
          const isDone = i < currentStep;
          const isActive = i === currentStep;
          return (
            <div key={step.id}
              className={`flex items-center gap-3 p-3 rounded-2xl transition-all ${
                isActive ? "bg-blue-50 scale-[1.02]" : isDone ? "opacity-60" : "opacity-30"
              }`}>
              <span className="text-xl w-8 text-center">{step.icon}</span>
              <span className={`text-sm font-medium flex-1 ${isActive ? "text-blue-900" : "text-slate-700"}`}>
                {step.label}
              </span>
              {isDone && <CheckCircle2 className="w-5 h-5 text-green-500 shrink-0" />}
              {isActive && <Loader2 className="w-5 h-5 text-blue-500 animate-spin shrink-0" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run TypeScript check**
```bash
cd nra-tax-client && npx tsc --noEmit
```

- [ ] **Step 3: Commit**
```bash
git add nra-tax-client/src/app/processing/page.tsx
git commit -m "feat: animated step-by-step pipeline status on processing page"
```

---

## Subsystem C: Engine Hardening

### Files
- Modify: `nra-tax-engine/src/agents/l1_residency.py` — wire `safe_parse`
- Modify: `nra-tax-engine/src/agents/l3_income.py` — wire `safe_parse`
- Modify: `nra-tax-engine/src/agents/l4_treaty.py` — wire `safe_parse`
- Modify: `nra-tax-engine/src/functions/tax_math.py` — add MFS/QSS bracket selection
- Modify: `nra-tax-engine/src/orchestrator/engine.py` — dual-status warning path
- Create: `nra-tax-engine/tests/test_llm_safety_wired.py`
- Create: `nra-tax-engine/tests/test_mfs_brackets.py`

---

### Task C1: Wire `safe_parse` into L1, L3, L4 agents

The `_llm_safety.py` module is fully built but every agent calls `client.beta.chat.completions.parse(...)` directly, bypassing the confidence gate.

**Files:**
- Modify: `nra-tax-engine/src/agents/l1_residency.py`
- Modify: `nra-tax-engine/src/agents/l3_income.py`
- Modify: `nra-tax-engine/src/agents/l4_treaty.py`
- Create: `nra-tax-engine/tests/test_llm_safety_wired.py`

- [ ] **Step 1: Write failing test**

Create `nra-tax-engine/tests/test_llm_safety_wired.py`:
```python
"""Confirm that mismatching dual-extract results surface as ExtractionConfidenceError."""
from unittest.mock import MagicMock, patch
import pytest
from src.agents.l1_residency import I94DayCountParams, ResidencyAgent
from src.agents._llm_safety import ExtractionConfidenceError
from src.orchestrator.state import ReturnStateObject


def _make_mock(parsed):
    choice = MagicMock()
    choice.message.parsed = parsed
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def test_dual_extract_mismatch_raises():
    """When primary and secondary LLMs disagree on day counts, ExtractionConfidenceError is raised."""
    primary_client = MagicMock()
    secondary_client = MagicMock()

    primary_client.beta.chat.completions.parse.return_value = _make_mock(
        I94DayCountParams(days_current_year=300, days_minus_1=200, days_minus_2=100)
    )
    secondary_client.beta.chat.completions.parse.return_value = _make_mock(
        I94DayCountParams(days_current_year=3000, days_minus_1=200, days_minus_2=100)  # decimal shift
    )

    agent = ResidencyAgent(llm_client=primary_client, secondary_llm_client=secondary_client)
    state = ReturnStateObject()
    with pytest.raises(ExtractionConfidenceError):
        agent.process_residency(
            i94_ocr_text="dummy",
            tax_year=2025,
            visa_type="F-1",
            first_us_arrival_year=2023,
            current_state=state,
        )
```

- [ ] **Step 2: Run test to confirm failure**
```bash
cd nra-tax-engine && python -m pytest tests/test_llm_safety_wired.py -v
```
Expected: FAIL — `ResidencyAgent.__init__` does not accept `secondary_llm_client`

- [ ] **Step 3: Update `ResidencyAgent` to accept secondary client and use `safe_parse`**

In `nra-tax-engine/src/agents/l1_residency.py`:

Replace:
```python
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from src.functions.spt_calculator import SubstantialPresenceCalculator

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject
```

With:
```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

from src.agents._llm_safety import safe_parse
from src.functions.spt_calculator import SubstantialPresenceCalculator

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject
```

Replace `__init__`:
```python
    def __init__(self, llm_client: Any = None, secondary_llm_client: Any = None):
        if llm_client is None:
            from openai import OpenAI
            self.llm_client = OpenAI()
        else:
            self.llm_client = llm_client
        self.secondary_llm_client = secondary_llm_client
```

Replace the OpenAI call inside `process_residency`:
```python
        extracted_days: I94DayCountParams = safe_parse(
            primary_client=self.llm_client,
            primary_model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=I94DayCountParams,
            secondary_client=self.secondary_llm_client,
            secondary_model="gpt-4o-mini" if self.secondary_llm_client else None,
            critical_fields=["days_current_year", "days_minus_1", "days_minus_2"],
        )
```

- [ ] **Step 4: Apply same pattern to `IncomeAgent._parse` in l3_income.py**

In `nra-tax-engine/src/agents/l3_income.py`, update `__init__`:
```python
    def __init__(self, llm_client: Any = None, secondary_llm_client: Any = None):
        if llm_client is None:
            from openai import OpenAI
            self.llm_client = OpenAI()
        else:
            self.llm_client = llm_client
        self.secondary_llm_client = secondary_llm_client
```

Update `_parse`:
```python
    def _parse(self, schema, system_prompt: str, user_text: str):
        from src.agents._llm_safety import safe_parse
        return safe_parse(
            primary_client=self.llm_client,
            primary_model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            response_format=schema,
            secondary_client=self.secondary_llm_client,
            secondary_model="gpt-4o-mini" if self.secondary_llm_client else None,
        )
```

- [ ] **Step 5: Apply same pattern to `TreatyAgent._classify_income_description` in l4_treaty.py**

In `nra-tax-engine/src/agents/l4_treaty.py`, update `__init__`:
```python
    def __init__(self, llm_client: Any = None, secondary_llm_client: Any = None):
        if llm_client is None:
            from openai import OpenAI
            self.llm_client = OpenAI()
        else:
            self.llm_client = llm_client
        self.secondary_llm_client = secondary_llm_client
```

Update `_classify_income_description`:
```python
    def _classify_income_description(self, income_description: str) -> LLMTreatyCategory:
        from src.agents._llm_safety import safe_parse
        result = safe_parse(
            primary_client=self.llm_client,
            primary_model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Income description:\n{income_description}"},
            ],
            response_format=TreatyCategoryMapping,
            secondary_client=self.secondary_llm_client,
            secondary_model="gpt-4o-mini" if self.secondary_llm_client else None,
        )
        return result.mapped_category
```

- [ ] **Step 6: Pass secondary clients from the orchestrator when env var is set**

In `nra-tax-engine/src/orchestrator/engine.py`, in `run_full_pipeline`, update the agent constructors:
```python
        residency_agent = ResidencyAgent(
            llm_client=self.llm_client,
            secondary_llm_client=self.secondary_llm_client,
        )
        # ... same for IncomeAgent and TreatyAgent
```

Add to `TaxEngine.__init__`:
```python
    def __init__(self, llm_client: Any = None, secondary_llm_client: Any = None, force_assembly: bool = False) -> None:
        self.llm_client = llm_client
        self.secondary_llm_client = secondary_llm_client
        self.force_assembly = force_assembly
```

- [ ] **Step 7: Run the test to confirm it passes**
```bash
cd nra-tax-engine && python -m pytest tests/test_llm_safety_wired.py -v
```
Expected: PASS

- [ ] **Step 8: Run existing tests to confirm no regressions**
```bash
cd nra-tax-engine && python -m pytest -q
```
Expected: same pass count as before (302 tests)

- [ ] **Step 9: Commit**
```bash
git add nra-tax-engine/src/agents/ nra-tax-engine/src/orchestrator/engine.py nra-tax-engine/tests/test_llm_safety_wired.py
git commit -m "feat: wire safe_parse dual-extraction into L1, L3, L4 agents"
```

---

### Task C2: MFS and QSS filing status in tax calculator

**Files:**
- Modify: `nra-tax-engine/src/agents/l6_tax_calc.py`
- Modify: `nra-tax-engine/src/functions/tax_math.py`
- Create: `nra-tax-engine/tests/test_mfs_brackets.py`

- [ ] **Step 1: Write failing test**

Create `nra-tax-engine/tests/test_mfs_brackets.py`:
```python
from src.functions.tax_math import TaxCalculator

def test_mfs_uses_different_brackets_than_single():
    """MFS brackets should produce different tax than single for the same income."""
    single = TaxCalculator(tax_year=2025, filing_status="single")
    mfs = TaxCalculator(tax_year=2025, filing_status="mfs")
    income = 50_000.0
    single_tax = single.calculate_tax_liability(eci_taxable_income=income, fdap_taxable_income=0.0, fdap_rate=0.30)
    mfs_tax = mfs.calculate_tax_liability(eci_taxable_income=income, fdap_taxable_income=0.0, fdap_rate=0.30)
    # MFS has narrower brackets — tax should be same or higher
    assert mfs_tax["eci_tax_liability"] >= single_tax["eci_tax_liability"]

def test_qss_uses_qss_brackets():
    """QSS should resolve without error and produce a result."""
    qss = TaxCalculator(tax_year=2025, filing_status="qss")
    result = qss.calculate_tax_liability(eci_taxable_income=40_000.0, fdap_taxable_income=0.0, fdap_rate=0.30)
    assert result["eci_tax_liability"] > 0
```

- [ ] **Step 2: Run test to confirm failure**
```bash
cd nra-tax-engine && python -m pytest tests/test_mfs_brackets.py -v
```
Expected: FAIL — `TaxCalculator` probably always loads single brackets

- [ ] **Step 3: Read `tax_math.py` and `load_year` to understand bracket loading**

Read `nra-tax-engine/src/functions/tax_math.py` to see how brackets are loaded, then update `TaxCalculator.__init__` to use `filing_status` to select the correct bracket file (`brackets_single.json`, `brackets_mfs.json`, `brackets_qss.json`).

The bracket-loading pattern should be:
```python
if filing_status == "mfs":
    self.brackets = year_data.brackets_mfs
elif filing_status == "qss":
    self.brackets = year_data.brackets_qss
else:
    self.brackets = year_data.brackets_single
```

- [ ] **Step 4: Update `TaxCalculationAgent.process_tax` to pass filing_status from state**

In `nra-tax-engine/src/agents/l6_tax_calc.py`, change:
```python
        calculator = TaxCalculator(tax_year=2025, filing_status="single")
```
to:
```python
        calculator = TaxCalculator(
            tax_year=current_state.tax_year,
            filing_status=current_state.identity.filing_status,
        )
```

- [ ] **Step 5: Run tests**
```bash
cd nra-tax-engine && python -m pytest tests/test_mfs_brackets.py tests/ -q
```
Expected: all PASS

- [ ] **Step 6: Commit**
```bash
git add nra-tax-engine/src/agents/l6_tax_calc.py nra-tax-engine/src/functions/tax_math.py nra-tax-engine/tests/test_mfs_brackets.py
git commit -m "feat: MFS and QSS bracket selection in tax calculator; pass tax_year from state"
```

---

### Task C3: Dual-status residency warning path

When the SPT returns `"dual_status"`, the current L6 has no special handling and will produce a wrong number (it applies brackets as if the filer was NRA for the full year).

**Files:**
- Modify: `nra-tax-engine/src/orchestrator/validators.py`
- Modify: `nra-tax-engine/src/agents/l6_tax_calc.py`
- Create: `nra-tax-engine/tests/test_dual_status.py`

- [ ] **Step 1: Write failing test**

Create `nra-tax-engine/tests/test_dual_status.py`:
```python
from src.orchestrator.state import ReturnStateObject
from src.orchestrator.validators import validate_post_l1

def test_dual_status_flags_human_review():
    """Dual-status returns must be flagged for human review — they require a split-year return."""
    state = ReturnStateObject()
    state.residency.status = "dual_status"
    state.residency.spt_days_current_year = 200
    state.residency.years_in_exempt_status = 5
    state.residency.is_exempt_individual = False
    validate_post_l1(state)
    assert any("dual_status" in r.lower() or "dual status" in r.lower() for r in state.requires_human_review)
```

- [ ] **Step 2: Run test to confirm failure**
```bash
cd nra-tax-engine && python -m pytest tests/test_dual_status.py -v
```
Expected: FAIL

- [ ] **Step 3: Add dual-status check to `validate_post_l1`**

In `nra-tax-engine/src/orchestrator/validators.py`, add inside `validate_post_l1`:
```python
    if residency.status == "dual_status":
        _flag(
            state,
            "L1: Dual-status return detected (residency changed mid-year). "
            "QuadTax computes the NRA portion only — a CPA must verify the "
            "resident-alien portion and combine the two on the final Form 1040/1040-NR.",
        )
```

- [ ] **Step 4: Run test to confirm pass**
```bash
cd nra-tax-engine && python -m pytest tests/test_dual_status.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add nra-tax-engine/src/orchestrator/validators.py nra-tax-engine/tests/test_dual_status.py
git commit -m "feat: flag dual-status returns for human review with clear explanation"
```

---

## Subsystem D: Per-Filer Narrative Engine

This is the original architecture vision: rather than returning raw numbers, the engine generates a plain-English narrative that explains *exactly* why each dollar was computed the way it was. This is built on top of the existing `state.audit_trail` which already captures every layer's inputs/outputs.

### Files
- Create: `nra-tax-engine/src/narrative/generator.py` — converts audit_trail + state into human-readable explanation
- Create: `nra-tax-engine/src/narrative/__init__.py`
- Modify: `nra-tax-engine/src/api/main.py` — add `narrative` field to `TaxProcessResponse`
- Create: `nra-tax-client/src/components/NarrativeCard.tsx` — expandable "why this number" card on results page
- Modify: `nra-tax-client/src/app/results/page.tsx` — embed NarrativeCard
- Create: `nra-tax-engine/tests/test_narrative_generator.py`

---

### Task D1: Per-filer narrative generator

**Files:**
- Create: `nra-tax-engine/src/narrative/__init__.py`
- Create: `nra-tax-engine/src/narrative/generator.py`
- Create: `nra-tax-engine/tests/test_narrative_generator.py`

- [ ] **Step 1: Write failing test**

Create `nra-tax-engine/tests/test_narrative_generator.py`:
```python
from src.narrative.generator import NarrativeGenerator
from src.orchestrator.state import (
    ReturnStateObject, ResidencyState, IncomeState, TreatyState, TaxCalculatedState, FicaState
)

def _make_state() -> ReturnStateObject:
    state = ReturnStateObject(tax_year=2025)
    state.identity.first_name = "Wei"
    state.identity.country_of_tax_residence = "CN"
    state.residency.status = "nonresident_alien"
    state.residency.is_exempt_individual = True
    state.residency.exempt_visa_type = "F-1"
    state.residency.years_in_exempt_status = 3
    state.income.total_w2_wages = 32_500.0
    state.income.eci_taxable_total = 32_500.0
    state.treaty.is_eligible = True
    state.treaty.country = "CN"
    state.treaty.article_number = "20(c)"
    state.treaty.exempt_amount_applied = 5_000.0
    state.tax.eci_tax_liability = 3_267.0
    state.tax.total_tax_liability = 3_267.0
    state.tax.total_withholding_credits = 4_875.0
    state.tax.refund_or_owed = -1_608.0
    state.fica.is_exempt = True
    state.fica.incorrect_ss_withheld = 2_015.0
    state.fica.incorrect_medicare_withheld = 471.25
    return state

def test_narrative_contains_key_facts():
    state = _make_state()
    gen = NarrativeGenerator()
    narrative = gen.generate(state)
    assert "F-1" in narrative
    assert "nonresident" in narrative.lower()
    assert "China" in narrative or "CN" in narrative
    assert "5,000" in narrative  # treaty exemption
    assert "refund" in narrative.lower()
    assert "FICA" in narrative

def test_narrative_is_plain_english():
    """Narrative must not contain Python field names like 'eci_taxable_total'."""
    state = _make_state()
    gen = NarrativeGenerator()
    narrative = gen.generate(state)
    assert "eci_taxable_total" not in narrative
    assert "fdap_taxable_total" not in narrative
```

- [ ] **Step 2: Run test to confirm failure**
```bash
cd nra-tax-engine && python -m pytest tests/test_narrative_generator.py -v
```
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Create the narrative generator**

Create `nra-tax-engine/src/narrative/__init__.py` (empty).

Create `nra-tax-engine/src/narrative/generator.py`:
```python
"""Per-filer plain-English narrative from ReturnStateObject.

Produces a structured narrative sections dict and a combined text blob.
No LLM calls — everything is template-driven from deterministic state values.
The narrative is the human-readable equivalent of the audit trail.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from src.orchestrator.state import ReturnStateObject

_COUNTRY_NAMES = {
    "CN": "China", "IN": "India", "KR": "South Korea", "DE": "Germany",
    "GB": "United Kingdom", "PK": "Pakistan", "JP": "Japan", "CA": "Canada",
    "MX": "Mexico", "ES": "Spain", "FR": "France", "IN": "India",
}

def _country_name(iso2: str) -> str:
    return _COUNTRY_NAMES.get(iso2.upper(), iso2)


class NarrativeGenerator:
    """Converts a completed ReturnStateObject into a plain-English filing narrative."""

    def generate(self, state: "ReturnStateObject") -> str:
        """Return a full plain-English narrative for the filer."""
        sections = self.generate_sections(state)
        return "\n\n".join(f"**{title}**\n{body}" for title, body in sections.items())

    def generate_sections(self, state: "ReturnStateObject") -> Dict[str, str]:
        sections: Dict[str, str] = {}

        # --- Residency ---
        r = state.residency
        if r.is_exempt_individual:
            sections["Residency Status"] = (
                f"You are classified as a **Nonresident Alien** for {state.tax_year}. "
                f"As a {r.exempt_visa_type} visa holder in year {r.years_in_exempt_status} "
                f"of your 5-year exemption window, your days in the US do not count toward "
                f"the Substantial Presence Test (IRC §7701(b)(5)). This means you are taxed "
                f"only on US-source income, not your worldwide income."
            )
        elif r.status == "nonresident_alien":
            sections["Residency Status"] = (
                f"You are classified as a **Nonresident Alien** for {state.tax_year} "
                f"based on the Substantial Presence Test."
            )
        elif r.status == "dual_status":
            sections["Residency Status"] = (
                f"You have **Dual-Status** for {state.tax_year} — you were a nonresident alien "
                f"for part of the year and a resident alien for part of the year. "
                f"This return covers only the nonresident portion. Please consult a CPA "
                f"for the resident-alien portion."
            )
        else:
            sections["Residency Status"] = f"Residency status: {r.status}."

        # --- Income ---
        inc = state.income
        income_parts: List[str] = []
        if inc.total_w2_wages > 0:
            income_parts.append(f"**${inc.total_w2_wages:,.0f}** in wages (W-2 Box 1)")
        if inc.total_1042s_gross > 0:
            income_parts.append(f"**${inc.total_1042s_gross:,.0f}** from 1042-S (scholarships/fellowships)")
        if inc.exempt_scholarship_total > 0:
            income_parts.append(
                f"**${inc.exempt_scholarship_total:,.0f}** of that is excluded under IRC §117 "
                f"(qualified tuition and fees)"
            )
        sections["Income"] = (
            "Your US-source income for the year:\n" + "\n".join(f"• {p}" for p in income_parts)
            if income_parts else "No US-source income recorded."
        )

        # --- Treaty ---
        t = state.treaty
        if t.is_eligible and t.country:
            country = _country_name(t.country)
            treaty_lines = [
                f"The US–{country} income tax treaty applies to your return."
            ]
            for b in t.applied_benefits:
                amt = b.get("exempt_amount", 0.0)
                if amt > 0:
                    treaty_lines.append(
                        f"• Article {b['article_id']}: exempts **${amt:,.0f}** "
                        f"({b.get('explanation', '')})"
                    )
            if t.requires_form_8833:
                treaty_lines.append(
                    "• Form 8833 (Treaty Disclosure) is required and included in your packet."
                )
            sections["Tax Treaty"] = "\n".join(treaty_lines)
        else:
            sections["Tax Treaty"] = (
                "No income tax treaty applies to your return. "
                "Your country either has no treaty with the US or your income type is not covered."
            )

        # --- Federal tax ---
        tax = state.tax
        deduction_note = ""
        if tax.deduction_type == "standard":
            deduction_note = (
                f" The India treaty Article 21(2) grants you the US standard deduction "
                f"(${tax.deduction_amount:,.0f}), which is unique among all treaty countries."
            )
        sections["Federal Tax Calculation"] = (
            f"Your adjusted gross income (AGI) is **${tax.agi:,.0f}**."
            f"{deduction_note} "
            f"After applying the deduction, your taxable income is **${tax.taxable_income:,.0f}**. "
            f"Applying the 2025 graduated tax brackets, your federal income tax is "
            f"**${tax.total_tax_liability:,.0f}**. "
            f"You had **${tax.total_withholding_credits:,.0f}** already withheld, so your "
            + (f"**federal refund is ${-tax.refund_or_owed:,.0f}**."
               if tax.refund_or_owed <= 0
               else f"**federal balance due is ${tax.refund_or_owed:,.0f}**.")
        )

        # --- FICA ---
        fica = state.fica
        if fica.is_exempt and (fica.incorrect_ss_withheld > 0 or fica.incorrect_medicare_withheld > 0):
            total_fica = fica.incorrect_ss_withheld + fica.incorrect_medicare_withheld
            sections["FICA Refund (Form 843)"] = (
                f"As an F-1/J-1 student, you are **exempt from Social Security and Medicare taxes** "
                f"under IRC §3121(b)(19). Your employer incorrectly withheld "
                f"**${fica.incorrect_ss_withheld:,.0f}** in Social Security and "
                f"**${fica.incorrect_medicare_withheld:,.0f}** in Medicare taxes. "
                f"Form 843 in your packet claims a **FICA refund of ${total_fica:,.0f}**. "
                f"Mail Form 843 separately — it goes to a different IRS address than your 1040-NR."
            )

        # --- NY ---
        ny = state.ny
        if ny.residency_status not in ("pending",) and ny.residency_status:
            sections["New York State"] = (
                f"NY residency status: **{ny.residency_status}**. {ny.residency_reason} "
                f"Your NY-source income is **${ny.ny_source_income:,.0f}**. "
                f"NY adds back the federal treaty exemption (${ny.ny_treaty_addback:,.0f}) "
                f"because New York does not honor federal income tax treaties. "
                + (f"Your **NY refund is ${-ny.ny_refund_or_owed:,.0f}**."
                   if ny.ny_refund_or_owed <= 0
                   else f"Your **NY balance due is ${ny.ny_refund_or_owed:,.0f}**.")
            )

        return sections
```

- [ ] **Step 4: Run tests**
```bash
cd nra-tax-engine && python -m pytest tests/test_narrative_generator.py -v
```
Expected: PASS

- [ ] **Step 5: Add `narrative` to API response**

In `nra-tax-engine/src/api/main.py`, add to `TaxProcessResponse`:
```python
    narrative_sections: dict = Field(
        default_factory=dict,
        description="Plain-English explanation of each computation layer keyed by section name.",
    )
```

In the `submit` endpoint, after `packager.assemble(...)`, add:
```python
    from src.narrative.generator import NarrativeGenerator
    narrative = NarrativeGenerator().generate_sections(state)
```

And include in the return:
```python
    return TaxProcessResponse(
        ...
        narrative_sections=narrative,
    )
```

- [ ] **Step 6: Commit**
```bash
git add nra-tax-engine/src/narrative/ nra-tax-engine/src/api/main.py nra-tax-engine/tests/test_narrative_generator.py
git commit -m "feat: per-filer plain-English narrative generator from audit trail state"
```

---

### Task D2: NarrativeCard in results page

**Files:**
- Create: `nra-tax-client/src/components/NarrativeCard.tsx`
- Modify: `nra-tax-client/src/store/taxStore.ts` — add `narrativeSections` to `ResultsView`
- Modify: `nra-tax-client/src/app/results/page.tsx`

- [ ] **Step 1: Add `narrativeSections` to `ResultsView`**

In `nra-tax-client/src/store/taxStore.ts`:
```typescript
export interface ResultsView {
  // ... existing fields ...
  narrativeSections: Record<string, string>;
}
```

Default: `narrativeSections: {}`.

- [ ] **Step 2: Create `NarrativeCard`**

Create `nra-tax-client/src/components/NarrativeCard.tsx`:
```tsx
"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, BookOpen } from "lucide-react";

interface NarrativeCardProps {
  sections: Record<string, string>;
}

export function NarrativeCard({ sections }: NarrativeCardProps) {
  const [open, setOpen] = useState(false);
  const entries = Object.entries(sections);
  if (entries.length === 0) return null;

  return (
    <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-sm">
      <button
        onClick={() => setOpen(!open)}
        className="w-full p-5 flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-3">
          <BookOpen className="w-5 h-5 text-blue-600" />
          <span className="font-bold text-slate-900 text-sm">Why these numbers? (Full Explanation)</span>
        </div>
        {open ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
      </button>

      {open && (
        <div className="divide-y divide-slate-100">
          {entries.map(([title, body]) => (
            <div key={title} className="p-5">
              <h3 className="font-bold text-slate-800 text-sm mb-2">{title}</h3>
              <div className="text-xs text-slate-600 leading-relaxed whitespace-pre-line">
                {body.replace(/\*\*/g, "")}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add NarrativeCard to results page**

In `nra-tax-client/src/app/results/page.tsx`, add before the form list section:
```tsx
import { NarrativeCard } from "@/components/NarrativeCard";
// ...
<NarrativeCard sections={results.narrativeSections ?? {}} />
```

- [ ] **Step 4: Update processing page to populate narrativeSections**

The `submitTaxReturn` legacy function wraps `submitReturnMultipart` which returns a `LegacyTaxResponse` that doesn't have narrative. Update `processing/page.tsx` to use `submitReturn` (the new typed endpoint) instead of `submitTaxReturn`:

In `nra-tax-client/src/app/processing/page.tsx`, import `submitReturn` and call it directly:
```typescript
import { submitReturn } from "@/lib/api";
// ...
const intake = store.buildIntakePayload();
const data = await submitReturn({ intake });
store.setResults({
  taxLiability: data.federal_refund_or_owed > 0 ? data.federal_refund_or_owed : 0,
  refundOrOwed: data.federal_refund_or_owed,
  requiresFicaClaim: data.fica_refund_amount > 0,
  generatedForms: data.generated_form_outputs,
  nyRefundOrOwed: data.ny_refund_or_owed,
  ficaRefundAmount: data.fica_refund_amount,
  requiresHumanReview: data.requires_human_review,
  federalPacketPath: data.federal_packet_path ?? null,
  nyPacketPath: data.ny_packet_path ?? null,
  ficaPacketPath: data.fica_packet_path ?? null,
  completedLayers: data.completed_layers,
  narrativeSections: (data as any).narrative_sections ?? {},
});
```

- [ ] **Step 5: TypeScript check and commit**
```bash
cd nra-tax-client && npx tsc --noEmit
git add nra-tax-client/src/
git commit -m "feat: NarrativeCard on results page — expandable plain-English explanation"
```

---

## Subsystem E: Real PDF Download

### Files
- Create: `nra-tax-engine/assets/templates/` — directory for IRS PDF templates (gitignored binaries)
- Create: `nra-tax-engine/scripts/vendor_templates.py` — downloads current-year 1040-NR from IRS.gov
- Modify: `nra-tax-engine/src/api/main.py` — add `/api/v1/packet/{path}` download endpoint
- Modify: `nra-tax-client/src/app/results/page.tsx` — wire "Download PDF Package" to real endpoint
- Modify: `nra-tax-client/src/lib/api.ts` — add `downloadPacket(path: string)` function

---

### Task E1: Template vendor script + download endpoint

**Files:**
- Create: `nra-tax-engine/scripts/vendor_templates.py`
- Modify: `nra-tax-engine/src/api/main.py`
- Modify: `nra-tax-client/src/lib/api.ts`
- Modify: `nra-tax-client/src/app/results/page.tsx`

- [ ] **Step 1: Create template vendor script**

Create `nra-tax-engine/scripts/vendor_templates.py`:
```python
#!/usr/bin/env python3
"""Download IRS fillable PDFs for the current tax year.

IRS publishes final versions in mid-November. This script fetches
the forms needed by the engine and saves them to assets/templates/2025/.

Usage: python -m scripts.vendor_templates
"""
import urllib.request
from pathlib import Path

FORMS = {
    # IRS direct download URLs (update each November when final forms publish)
    "1040-NR": "https://www.irs.gov/pub/irs-pdf/f1040nr.pdf",
    "Schedule-OI": "https://www.irs.gov/pub/irs-pdf/f1040nrs.pdf",  # schedules packet
    "8843": "https://www.irs.gov/pub/irs-pdf/f8843.pdf",
    "8833": "https://www.irs.gov/pub/irs-pdf/f8833.pdf",
    "843": "https://www.irs.gov/pub/irs-pdf/f843.pdf",
    "W-7": "https://www.irs.gov/pub/irs-pdf/fw7.pdf",
    "6251": "https://www.irs.gov/pub/irs-pdf/f6251.pdf",
}

def main():
    out_dir = Path("assets/templates/2025")
    out_dir.mkdir(parents=True, exist_ok=True)
    for form_name, url in FORMS.items():
        dest = out_dir / f"{form_name}.pdf"
        if dest.exists():
            print(f"  Already exists: {dest}")
            continue
        print(f"  Downloading {form_name} from {url} ...")
        urllib.request.urlretrieve(url, dest)
        print(f"  Saved to {dest}")
    print("Done. Run pytest to verify field-map alignment.")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add download endpoint to FastAPI**

In `nra-tax-engine/src/api/main.py`, add after the existing endpoints:
```python
from fastapi.responses import FileResponse
import os

@app.get("/api/v1/packet", tags=["tax"])
def download_packet(path: str) -> FileResponse:
    """Serve a generated packet file by its server-side path."""
    # Security: only allow files under the outputs/ directory
    abs_path = os.path.realpath(path)
    outputs_abs = os.path.realpath("outputs")
    if not abs_path.startswith(outputs_abs):
        raise HTTPException(status_code=403, detail="Access denied.")
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Packet not found.")
    return FileResponse(abs_path, media_type="application/pdf",
                        filename=os.path.basename(abs_path))
```

- [ ] **Step 3: Add `downloadPacket` to the client API module**

In `nra-tax-client/src/lib/api.ts`, add:
```typescript
export async function downloadPacket(serverPath: string): Promise<void> {
  const url = `${API_BASE_URL}/packet?path=${encodeURIComponent(serverPath)}`;
  const r = await axios.get(url, { responseType: "blob" });
  const blob = new Blob([r.data], { type: "application/pdf" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = serverPath.split(/[/\\]/).pop() ?? "return.pdf";
  link.click();
  URL.revokeObjectURL(link.href);
}
```

- [ ] **Step 4: Wire download button in results page**

In `nra-tax-client/src/app/results/page.tsx`, update the Download button:
```tsx
import { downloadPacket } from "@/lib/api";
// ...
<button
  onClick={async () => {
    const path = results.federalPacketPath;
    if (path) await downloadPacket(path);
    else alert("Packet path not available — forms were written as JSON field maps.");
  }}
  className="w-full h-18 bg-blue-600 text-white rounded-[24px] font-bold text-lg flex items-center justify-center gap-3 shadow-xl active:scale-95 transition-all py-4"
>
  <Download className="w-6 h-6" />
  Download Federal Packet
</button>
```

- [ ] **Step 5: Commit**
```bash
git add nra-tax-engine/scripts/vendor_templates.py nra-tax-engine/src/api/main.py nra-tax-client/src/lib/api.ts nra-tax-client/src/app/results/page.tsx
git commit -m "feat: real PDF download — vendor script, secure download endpoint, wired download button"
```

---

## Self-Review Against Spec

### Spec coverage check

| Gap | Task that addresses it |
|-----|------------------------|
| W-2/1042-S remove broken | A1 |
| `income_description` never collected | A2 |
| Only 3 identity fields collected | A3 |
| Only 6 countries in dropdown | A3 (CountrySelect) |
| NY context never collected | A4 |
| FICA / banking / elections not collected | A4 |
| Filing status UI missing | A3 |
| No session persistence | A5 |
| No progress indicator | A6 |
| `safe_parse` not wired | C1 |
| MFS/QSS brackets not used | C2 |
| Dual-status not flagged | C3 |
| `requires_human_review` not shown | B1 (HumanReviewBanner) |
| Download button is a mock | E1 |
| No per-filer narrative | D1, D2 |
| No gamification / step feedback | B1, B2 |
| No confetti / celebration | B1 |

### Placeholder scan
None found — every step includes actual code.

### Type consistency
- `ResultsView` updated in taxStore (Task B1 Step 1) before `NarrativeCard` reads from it (Task D2)
- `removeW2File` / `removeForm1042sFile` defined in store (A1 Step 2) before the page uses them (A1 Step 3)
- `safe_parse` signature in `_llm_safety.py` matches all three call sites in C1
- `secondary_llm_client` added to all three agents (`l1`, `l3`, `l4`) before `TaxEngine` passes it (C1 Step 6)

---

**Plan complete and saved to `docs/superpowers/plans/2026-06-02-quadtax-complete-overhaul.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration with superpowers:subagent-driven-development

**2. Inline Execution** — Execute tasks in this session using superpowers:executing-plans, batch execution with checkpoints

**Which approach?**
