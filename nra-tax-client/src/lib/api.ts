import axios from "axios";
import { TaxState } from "@/store/taxStore";

// Hardcoded for the localhost Python backend we constructed
const API_BASE_URL = "http://localhost:8000/api/v1";

interface TaxResponse {
  status: string;
  generated_forms: string[];
  tax_liability: number;
  refund_or_owed: number;
  requires_843_fica_claim: boolean;
}

export const submitTaxReturn = async (state: TaxState): Promise<TaxResponse> => {
  const formData = new FormData();

  // 1. Process Metadata
  formData.append("mcq_answers_json", JSON.stringify(state.mcqAnswers));

  // 2. Process Files
  if (!state.i94File) {
    throw new Error("An I-94 travel history upload is strictly required.");
  }
  formData.append("i94_file", state.i94File);

  state.w2Files.forEach((w2) => {
    formData.append("w2_files", w2);
  });

  state.form1042sFiles.forEach((f1042s) => {
    formData.append("form_1042s_files", f1042s);
  });

  // 3. Dispatch the payload
  try {
    const response = await axios.post<TaxResponse>(
      `${API_BASE_URL}/upload-and-process`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  } catch (error: any) {
    console.error("API Upload failed", error.response?.data || error.message);
    throw new Error(
      error.response?.data?.detail || "An error occurred while compiling your tax package."
    );
  }
};
