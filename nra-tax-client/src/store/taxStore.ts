import { create } from "zustand";

export interface TaxState {
  // MCQ Answers
  mcqAnswers: {
    tax_year: number;
    visa_type: string;
    first_us_arrival_year: number;
    tax_residence_country: string;
    income_description: string;
    requires_services: boolean;
    is_qualified_expense: boolean;
  };
  
  // File Arrays
  i94File: File | null;
  w2Files: File[];
  form1042sFiles: File[];

  // Computed Financial Results
  results: {
    taxLiability: number | null;
    refundOrOwed: number | null;
    requiresFicaClaim: boolean | null;
    generatedForms: string[];
  };

  // Actions
  updateMcqAnswers: (updates: Partial<TaxState["mcqAnswers"]>) => void;
  setI94File: (file: File | null) => void;
  addW2File: (file: File) => void;
  addForm1042sFile: (file: File) => void;
  setResults: (results: TaxState["results"]) => void;
  resetFastStore: () => void;
}

const initialMcqState = {
  tax_year: new Date().getFullYear() - 1, // Defaulting to the previous tax year
  visa_type: "F-1",
  first_us_arrival_year: new Date().getFullYear() - 1,
  tax_residence_country: "",
  income_description: "",
  requires_services: true,
  is_qualified_expense: false,
};

export const useTaxStore = create<TaxState>((set) => ({
  mcqAnswers: { ...initialMcqState },
  i94File: null,
  w2Files: [],
  form1042sFiles: [],
  results: {
    taxLiability: null,
    refundOrOwed: null,
    requiresFicaClaim: null,
    generatedForms: [],
  },
  
  updateMcqAnswers: (updates) =>
    set((state) => ({
      mcqAnswers: { ...state.mcqAnswers, ...updates },
    })),
    
  setI94File: (file) => set({ i94File: file }),
  
  addW2File: (file) =>
    set((state) => ({ w2Files: [...state.w2Files, file] })),
    
  addForm1042sFile: (file) =>
    set((state) => ({ form1042sFiles: [...state.form1042sFiles, file] })),
    
  setResults: (results) => set({ results }),
  
  resetFastStore: () =>
    set({
      mcqAnswers: { ...initialMcqState },
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
}));
