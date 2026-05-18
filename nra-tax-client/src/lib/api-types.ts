// AUTO-MIRRORED FROM nra-tax-engine/src/intake/intake_schema.py + api/main.py.
// Regenerate properly with:
//   cd ../nra-tax-engine && python -m scripts.gen_openapi
//   npx openapi-typescript ../nra-tax-client/openapi.json -o src/lib/api-types.ts
// Manually curated here so the client compiles before the codegen toolchain
// runs at install time.

export type FilingStatus = 'single' | 'mfs' | 'qss';

export type VisaSubtype = 'student' | 'teacher_researcher' | 'trainee' | 'other';

export type PriorYearResidencyStatus =
  | 'nonresident_alien'
  | 'resident_alien'
  | 'none';

export interface IntakeIdentity {
  first_name: string;
  middle_initial: string;
  last_name: string;
  suffix: string;
  date_of_birth: string | null;
  ssn: string;
  itin: string;
  country_of_citizenship: string;
  country_of_tax_residence: string;
  passport_number: string;
  passport_country: string;
  us_address_line1: string;
  us_address_line2: string;
  us_city: string;
  us_state: string;
  us_zip: string;
  foreign_address_line1: string;
  foreign_address_line2: string;
  foreign_city: string;
  foreign_state_province: string;
  foreign_country: string;
  foreign_postal_code: string;
  occupation: string;
  daytime_phone: string;
  email: string;
  filing_status: FilingStatus;
  spouse_first_name: string;
  spouse_last_name: string;
  spouse_ssn_or_itin: string;
}

export interface IntakeResidency {
  tax_year: number;
  visa_type: string;
  visa_subtype: VisaSubtype;
  first_us_arrival_year: number;
  prior_us_visa_history: string[];
  prior_year_residency_status: PriorYearResidencyStatus;
}

export interface IntakeIncome {
  income_description: string;
  requires_services: boolean;
  is_qualified_expense: boolean;
  prior_year_treaty_claim_total: number;
}

export interface IntakeNYContext {
  days_in_ny: number;
  has_permanent_abode_in_ny: boolean;
  abode_months_in_year: number;
  is_student_dorm: boolean;
  domiciled_in_ny: boolean;
  moved_into_ny_mid_year: boolean;
  moved_out_of_ny_mid_year: boolean;
  nyc_address: boolean;
  yonkers_address: boolean;
  ny_work_days: number;
  total_work_days: number;
  employer_in_ny: boolean;
  institution_1042s_in_ny: boolean;
}

export interface IntakeFICA {
  employer_attempted_refund: boolean;
  has_form_8316: boolean;
  employer_name: string;
  employer_ein: string;
}

export interface IntakeBanking {
  direct_deposit: boolean;
  routing_number: string;
  account_number: string;
  account_type: 'checking' | 'savings' | '';
}

export interface IntakeElections {
  section_6013g_election: boolean;
  section_6013h_election: boolean;
  section_871d_election: boolean;
  large_foreign_gifts_over_100k: boolean;
  closer_connection_exception_claimed: boolean;
}

export interface IntakePayload {
  identity: IntakeIdentity;
  residency: IntakeResidency;
  income: IntakeIncome;
  ny: IntakeNYContext | null;
  fica: IntakeFICA;
  banking: IntakeBanking;
  elections: IntakeElections;
}

export interface SubmitRequest {
  intake: IntakePayload;
  i94_ocr_text?: string;
  w2_ocr_texts?: string[];
  form_1042s_ocr_texts?: string[];
  output_dir?: string;
}

export interface TaxProcessResponse {
  status: string;
  tax_year: number;
  federal_refund_or_owed: number;
  ny_refund_or_owed: number;
  fica_refund_amount: number;
  forms_required: string[];
  completed_layers: string[];
  generated_form_outputs: string[];
  federal_packet_path: string | null;
  ny_packet_path: string | null;
  fica_packet_path: string | null;
}
