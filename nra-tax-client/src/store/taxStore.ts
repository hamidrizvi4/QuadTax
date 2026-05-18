import { create } from 'zustand';

import type {
  IntakeBanking,
  IntakeElections,
  IntakeFICA,
  IntakeIdentity,
  IntakeIncome,
  IntakeNYContext,
  IntakePayload,
  IntakeResidency,
} from '@/lib/api-types';

/** Legacy results shape preserved so Phase-2 pages compile against Phase-6 API. */
export interface ResultsView {
  taxLiability: number | null;
  refundOrOwed: number | null;
  requiresFicaClaim: boolean | null;
  generatedForms: string[];
}

// Default seeds. Keep these in sync with nra-tax-engine/src/intake/intake_schema.py.

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

// Legacy MCQ shape kept for backwards-compat with the Phase-2 intake pages.
// New code should read from `identity`, `residency`, `income` directly.
export interface LegacyMcqAnswers {
  tax_year: number;
  visa_type: string;
  first_us_arrival_year: number;
  tax_residence_country: string;
  income_description: string;
  requires_services: boolean;
  is_qualified_expense: boolean;
}

export interface TaxState {
  identity: IntakeIdentity;
  residency: IntakeResidency;
  income: IntakeIncome;
  ny: IntakeNYContext | null;
  fica: IntakeFICA;
  banking: IntakeBanking;
  elections: IntakeElections;

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

  setI94File: (file: File | null) => void;
  addW2File: (file: File) => void;
  addForm1042sFile: (file: File) => void;

  setResults: (results: ResultsView) => void;
  reset: () => void;

  buildIntakePayload: () => IntakePayload;

  /** @deprecated Use identity/residency/income directly. */
  readonly mcqAnswers: LegacyMcqAnswers;
  /** @deprecated Use updateIdentity/updateResidency/updateIncome. */
  updateMcqAnswers: (updates: Partial<LegacyMcqAnswers>) => void;
  /** @deprecated Renamed to reset(). */
  resetFastStore: () => void;
}

export const useTaxStore = create<TaxState>((set, get) => ({
  identity: { ...initialIdentity },
  residency: { ...initialResidency },
  income: { ...initialIncome },
  ny: null,
  fica: { ...initialFICA },
  banking: { ...initialBanking },
  elections: { ...initialElections },

  i94File: null,
  w2Files: [],
  form1042sFiles: [],

  results: {
    taxLiability: null,
    refundOrOwed: null,
    requiresFicaClaim: null,
    generatedForms: [],
  },

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

  setI94File: (file) => set({ i94File: file }),
  addW2File: (file) =>
    set((state) => ({ w2Files: [...state.w2Files, file] })),
  addForm1042sFile: (file) =>
    set((state) => ({ form1042sFiles: [...state.form1042sFiles, file] })),

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
      i94File: null,
      w2Files: [],
      form1042sFiles: [],
      results: {
        taxLiability: null,
        refundOrOwed: null,
        requiresFicaClaim: null,
        generatedForms: [],
      },
    }),

  buildIntakePayload: () => {
    const s = get();
    return {
      identity: s.identity,
      residency: s.residency,
      income: s.income,
      ny: s.ny,
      fica: s.fica,
      banking: s.banking,
      elections: s.elections,
    };
  },

  // --- Legacy back-compat (Phase-2 intake pages still reference these) ---
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
}));
