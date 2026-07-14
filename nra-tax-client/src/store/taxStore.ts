import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import type { components } from '@/lib/api-types';

type IntakeBanking = components['schemas']['IntakeBanking'];
type IntakeElections = components['schemas']['IntakeElections'];
type IntakeFICA = components['schemas']['IntakeFICA'];
type IntakeIdentity = components['schemas']['IntakeIdentity'];
type IntakeIncome = components['schemas']['IntakeIncome'];
type IntakeNYContext = components['schemas']['IntakeNYContext'];
type IntakePayload = components['schemas']['IntakePayload'];
type IntakeResidency = components['schemas']['IntakeResidency'];

// OCR extraction types — sourced from the engine's OpenAPI schema (see
// /api/v1/ocr in nra-tax-engine/src/api/ocr_endpoint.py). Re-exported under
// their original names so existing imports (`@/store/taxStore`) don't churn.
// Regenerate via `npm run sync-api` whenever the engine's OCR schemas change.
export type W2Extracted = components['schemas']['W2Extracted'];
export type Form1042SExtracted = components['schemas']['Form1042SExtracted'];
export type Form1099Extracted = components['schemas']['Form1099Extracted'];
export type I94Extracted = components['schemas']['I94Extracted'];
export type OcrResult = components['schemas']['OcrResult'];

// ── New intake state types ─────────────────────────────────────────────────

export interface EligibilityAnswers {
  isUsCitizen: boolean | null;
  isGreenCardHolder: boolean | null;
  hasAppliedForResidence: boolean | null;
}

export interface TravelEntry {
  visaType: string;
  entryDate: string;
  leaveDate: string;
}

export interface VisaDetails {
  visaType: string;
  visaSubtype: NonNullable<IntakeResidency['visa_subtype']>;
  visaIssueDate: string;
  visaExpiryDate: string;
  programStartDate: string;
  programEndDate: string;
  firstUsEntryDate: string;
  intendedDepartureDate: string;
  countryOfCitizenship: string;
  countryOfResidenceBeforeUs: string;
  changedVisaDuring2025: boolean | null;
  isStillInUs: boolean | null;
  travelHistory: TravelEntry[];
}

export interface ExtrasAnswers {
  isFullTimeStudent: boolean | null;
  isDegreeCandidate: boolean | null;
  isOptCpt: boolean | null;
  hadDigitalAssets: boolean | null;
  canBeClaimedAsDependent: boolean | null;
  wasMarriedOnLastDay: boolean | null;
  madeEstimatedFederalPayments: boolean | null;
  estimatedFederalPaymentAmount: number;
  madeEstimatedStatePayments: boolean | null;
  filedFederalExtension: boolean | null;
  filedPreviousFederalReturn: boolean | null;
  previousReturnYear: number | null;
  previousReturnType: string;
}

// ── Results ────────────────────────────────────────────────────────────────

export interface ResultsView {
  taxLiability: number | null;
  refundOrOwed: number | null;
  requiresFicaClaim: boolean | null;
  generatedForms: string[];
  nyRefundOrOwed: number;
  ficaRefundAmount: number;
  requiresHumanReview: string[];
  federalPacketPath: string | null;
  nyPacketPath: string | null;
  ficaPacketPath: string | null;
  completedLayers: string[];
  narrativeSections: Record<string, string>;
}

// ── Initial values ─────────────────────────────────────────────────────────

const initialIdentity: IntakeIdentity = {
  first_name: '',
  middle_initial: '',
  last_name: '',
  suffix: '',
  date_of_birth: null,
  ssn: '',
  itin: '',
  country_of_citizenship: '',
  country_of_tax_residence: '',
  passport_number: '',
  passport_country: '',
  us_address_line1: '',
  us_address_line2: '',
  us_city: '',
  us_state: '',
  us_zip: '',
  foreign_address_line1: '',
  foreign_address_line2: '',
  foreign_city: '',
  foreign_state_province: '',
  foreign_country: '',
  foreign_postal_code: '',
  occupation: 'Student',
  daytime_phone: '',
  email: '',
  filing_status: 'single',
  spouse_first_name: '',
  spouse_last_name: '',
  spouse_ssn_or_itin: '',
};

const initialResidency: IntakeResidency = {
  tax_year: new Date().getFullYear() - 1,
  visa_type: 'F-1',
  visa_subtype: 'student',
  first_us_arrival_year: new Date().getFullYear() - 1,
  prior_us_visa_history: [],
  prior_year_residency_status: 'none',
  is_still_in_us: true,
};

const initialIncome: IntakeIncome = {
  income_description: '',
  requires_services: false,
  is_qualified_expense: false,
  prior_year_treaty_claim_total: 0,
};

const initialNY: IntakeNYContext = {
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
};

const initialFICA: IntakeFICA = {
  employer_attempted_refund: false,
  has_form_8316: false,
  employer_name: '',
  employer_ein: '',
};

const initialBanking: IntakeBanking = {
  direct_deposit: false,
  routing_number: '',
  account_number: '',
  account_type: '',
};

const initialElections: IntakeElections = {
  section_6013g_election: false,
  section_6013h_election: false,
  section_871d_election: false,
  large_foreign_gifts_over_100k: false,
  closer_connection_exception_claimed: false,
};

const initialEligibility: EligibilityAnswers = {
  isUsCitizen: null,
  isGreenCardHolder: null,
  hasAppliedForResidence: null,
};

const initialVisaDetails: VisaDetails = {
  visaType: 'F-1',
  visaSubtype: 'student',
  visaIssueDate: '',
  visaExpiryDate: '',
  programStartDate: '',
  programEndDate: '',
  firstUsEntryDate: '',
  intendedDepartureDate: '',
  countryOfCitizenship: '',
  countryOfResidenceBeforeUs: '',
  changedVisaDuring2025: null,
  isStillInUs: null,
  travelHistory: [],
};

const initialExtras: ExtrasAnswers = {
  isFullTimeStudent: null,
  isDegreeCandidate: null,
  isOptCpt: null,
  hadDigitalAssets: null,
  canBeClaimedAsDependent: null,
  wasMarriedOnLastDay: null,
  madeEstimatedFederalPayments: null,
  estimatedFederalPaymentAmount: 0,
  madeEstimatedStatePayments: null,
  filedFederalExtension: null,
  filedPreviousFederalReturn: null,
  previousReturnYear: null,
  previousReturnType: '',
};

const initialResults: ResultsView = {
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
  narrativeSections: {},
};

// ── Legacy MCQ back-compat ─────────────────────────────────────────────────

export interface LegacyMcqAnswers {
  tax_year: number;
  visa_type: string;
  first_us_arrival_year: number;
  tax_residence_country: string;
  income_description: string;
  requires_services: boolean;
  is_qualified_expense: boolean;
}

// ── TaxState interface ─────────────────────────────────────────────────────

export interface TaxState {
  identity: IntakeIdentity;
  residency: IntakeResidency;
  income: IntakeIncome;
  ny: IntakeNYContext | null;
  fica: IntakeFICA;
  banking: IntakeBanking;
  elections: IntakeElections;

  eligibility: EligibilityAnswers;
  visaDetails: VisaDetails;
  extras: ExtrasAnswers;
  ocrResult: OcrResult | null;

  // File refs — not persisted
  i94File: File | null;
  w2Files: File[];
  form1042sFiles: File[];

  results: ResultsView;

  updateIdentity: (updates: Partial<IntakeIdentity>) => void;
  updateResidency: (updates: Partial<IntakeResidency>) => void;
  updateIncome: (updates: Partial<IntakeIncome>) => void;
  updateNY: (updates: Partial<IntakeNYContext> | null) => void;
  updateFICA: (updates: Partial<IntakeFICA>) => void;
  updateBanking: (updates: Partial<IntakeBanking>) => void;
  updateElections: (updates: Partial<IntakeElections>) => void;
  updateEligibility: (updates: Partial<EligibilityAnswers>) => void;
  updateVisaDetails: (updates: Partial<VisaDetails>) => void;
  updateExtras: (updates: Partial<ExtrasAnswers>) => void;
  setOcrResult: (result: OcrResult) => void;

  setI94File: (file: File | null) => void;
  addW2File: (file: File) => void;
  addForm1042sFile: (file: File) => void;
  removeW2File: (index: number) => void;
  removeForm1042sFile: (index: number) => void;

  setResults: (results: ResultsView) => void;
  reset: () => void;

  buildIntakePayload: () => IntakePayload;
  buildOcrTexts: () => { i94OcrText: string; w2OcrTexts: string[]; form1042sOcrTexts: string[] };

  /** @deprecated Use identity/residency/income directly. */
  readonly mcqAnswers: LegacyMcqAnswers;
  /** @deprecated Use updateIdentity/updateResidency/updateIncome. */
  updateMcqAnswers: (updates: Partial<LegacyMcqAnswers>) => void;
  /** @deprecated Renamed to reset(). */
  resetFastStore: () => void;
}

// ── Store ──────────────────────────────────────────────────────────────────

export const useTaxStore = create<TaxState>()(
  persist(
    (set, get) => ({
      identity: { ...initialIdentity },
      residency: { ...initialResidency },
      income: { ...initialIncome },
      ny: null,
      fica: { ...initialFICA },
      banking: { ...initialBanking },
      elections: { ...initialElections },
      eligibility: { ...initialEligibility },
      visaDetails: { ...initialVisaDetails },
      extras: { ...initialExtras },
      ocrResult: null,

      i94File: null,
      w2Files: [],
      form1042sFiles: [],

      results: { ...initialResults },

      updateIdentity: (updates) =>
        set((state) => ({ identity: { ...state.identity, ...updates } })),
      updateResidency: (updates) =>
        set((state) => ({ residency: { ...state.residency, ...updates } })),
      updateIncome: (updates) =>
        set((state) => ({ income: { ...state.income, ...updates } })),
      updateNY: (updates) =>
        set((state) => {
          if (updates === null) return { ny: null };
          const base = state.ny ?? { ...initialNY };
          return { ny: { ...base, ...updates } };
        }),
      updateFICA: (updates) =>
        set((state) => ({ fica: { ...state.fica, ...updates } })),
      updateBanking: (updates) =>
        set((state) => ({ banking: { ...state.banking, ...updates } })),
      updateElections: (updates) =>
        set((state) => ({ elections: { ...state.elections, ...updates } })),
      updateEligibility: (updates) =>
        set((state) => ({ eligibility: { ...state.eligibility, ...updates } })),
      updateVisaDetails: (updates) =>
        set((state) => ({ visaDetails: { ...state.visaDetails, ...updates } })),
      updateExtras: (updates) =>
        set((state) => ({ extras: { ...state.extras, ...updates } })),
      setOcrResult: (result) => set({ ocrResult: result }),

      setI94File: (file) => set({ i94File: file }),
      addW2File: (file) =>
        set((state) => ({ w2Files: [...state.w2Files, file] })),
      addForm1042sFile: (file) =>
        set((state) => ({ form1042sFiles: [...state.form1042sFiles, file] })),
      removeW2File: (index) =>
        set((state) => ({ w2Files: state.w2Files.filter((_, i) => i !== index) })),
      removeForm1042sFile: (index) =>
        set((state) => ({ form1042sFiles: state.form1042sFiles.filter((_, i) => i !== index) })),

      setResults: (results) => set({ results }),

      reset: () =>
        set({
          identity: { ...initialIdentity },
          residency: { ...initialResidency },
          income: { ...initialIncome },
          ny: null,
          fica: { ...initialFICA },
          banking: { ...initialBanking },
          elections: { ...initialElections },
          eligibility: { ...initialEligibility },
          visaDetails: { ...initialVisaDetails },
          extras: { ...initialExtras },
          ocrResult: null,
          i94File: null,
          w2Files: [],
          form1042sFiles: [],
          results: { ...initialResults },
        }),

      buildIntakePayload: () => {
        const s = get();
        const ex = s.extras;
        return {
          identity: s.identity,
          residency: s.residency,
          income: s.income,
          ny: s.ny,
          fica: s.fica,
          banking: s.banking,
          elections: s.elections,
          // Tri-state (boolean | null) on the frontend collapses to a plain
          // bool for the backend — null ("not yet answered") maps to false,
          // matching how every other optional intake toggle in this app
          // already defaults when left untouched.
          extras: {
            is_full_time_student: ex.isFullTimeStudent ?? false,
            is_degree_candidate: ex.isDegreeCandidate ?? false,
            is_opt_cpt: ex.isOptCpt ?? false,
            had_digital_assets: ex.hadDigitalAssets ?? false,
            can_be_claimed_as_dependent: ex.canBeClaimedAsDependent ?? false,
            was_married_on_last_day: ex.wasMarriedOnLastDay ?? false,
            made_estimated_federal_payments: ex.madeEstimatedFederalPayments ?? false,
            estimated_federal_payment_amount: ex.estimatedFederalPaymentAmount,
            made_estimated_state_payments: ex.madeEstimatedStatePayments ?? false,
            filed_federal_extension: ex.filedFederalExtension ?? false,
            filed_previous_federal_return: ex.filedPreviousFederalReturn ?? false,
            previous_return_year: ex.previousReturnYear,
            previous_return_type: ex.previousReturnType,
          },
        };
      },

      buildOcrTexts: () => {
        const s = get();
        const ocr = s.ocrResult;
        if (!ocr) return { i94OcrText: '', w2OcrTexts: [], form1042sOcrTexts: [] };

        const i94OcrText = ocr.i94
          ? [
              `I-94 Data:`,
              `days_current_year=${ocr.i94.days_current_year}`,
              `days_minus_1=${ocr.i94.days_minus_1}`,
              `days_minus_2=${ocr.i94.days_minus_2}`,
              `latest_entry=${ocr.i94.latest_entry_date}`,
              `class_of_admission=${ocr.i94.latest_class_of_admission}`,
            ].join(' ')
          : '';

        const w2OcrTexts = (ocr.w2s ?? []).map(
          (w) =>
            `W-2 Extracted: ` +
            `Box 1 Wages: ${w.box_1_wages}, ` +
            `Box 2 Federal: ${w.box_2_fed_withholding}, ` +
            `Box 3 SS Wages: ${w.box_3_ss_wages}, ` +
            `Box 4 SS Withheld: ${w.box_4_ss_withheld}, ` +
            `Box 5 Medicare Wages: ${w.box_5_medicare_wages}, ` +
            `Box 6 Medicare: ${w.box_6_medicare_withheld}, ` +
            `Box 17 State: ${w.box_17_state_income_tax}, ` +
            `Box 18 Local Wages: ${w.box_18_local_wages}, ` +
            `Box 19 Local Tax: ${w.box_19_local_income_tax}, ` +
            `Box 20 Locality: ${w.box_20_locality_name}, ` +
            `Employer: ${w.employer_name}, EIN: ${w.employer_ein}`,
        );

        const form1042sOcrTexts = (ocr.form_1042s ?? []).map(
          (f) =>
            `1042-S Extracted: ` +
            `Income Code: ${f.income_code}, ` +
            `Gross Income: ${f.gross_income}, ` +
            `Exemption Rate: ${f.exemption_rate}, ` +
            `Exemption Code: ${f.exemption_code}, ` +
            `Fed Withheld: ${f.fed_withheld}, ` +
            `Chapter: ${f.chapter_indicator}, ` +
            `Recipient: ${f.recipient_name}, ` +
            `Agent: ${f.withholding_agent_name}`,
        );

        return { i94OcrText, w2OcrTexts, form1042sOcrTexts };
      },

      // --- Legacy back-compat ---
      get mcqAnswers(): LegacyMcqAnswers {
        const s = get();
        return {
          tax_year: s.residency.tax_year,
          visa_type: s.residency.visa_type,
          first_us_arrival_year: s.residency.first_us_arrival_year,
          tax_residence_country: s.identity.country_of_tax_residence,
          income_description: s.income.income_description,
          requires_services: s.income.requires_services,
          is_qualified_expense: s.income.is_qualified_expense,
        };
      },
      updateMcqAnswers: (updates) =>
        set((state) => {
          const identity = { ...state.identity };
          const residency = { ...state.residency };
          const income = { ...state.income };
          if (updates.tax_year !== undefined) residency.tax_year = updates.tax_year;
          if (updates.visa_type !== undefined) residency.visa_type = updates.visa_type;
          if (updates.first_us_arrival_year !== undefined)
            residency.first_us_arrival_year = updates.first_us_arrival_year;
          if (updates.tax_residence_country !== undefined)
            identity.country_of_tax_residence = updates.tax_residence_country;
          if (updates.income_description !== undefined)
            income.income_description = updates.income_description;
          if (updates.requires_services !== undefined)
            income.requires_services = updates.requires_services;
          if (updates.is_qualified_expense !== undefined)
            income.is_qualified_expense = updates.is_qualified_expense;
          return { identity, residency, income };
        }),
      resetFastStore: () => get().reset(),
    }),
    {
      name: 'quadtax-intake',
      partialize: (state) => ({
        identity: state.identity,
        residency: state.residency,
        income: state.income,
        ny: state.ny,
        fica: state.fica,
        banking: state.banking,
        elections: state.elections,
        eligibility: state.eligibility,
        visaDetails: state.visaDetails,
        extras: state.extras,
        ocrResult: state.ocrResult,
        results: state.results,
      }),
    },
  ),
);
