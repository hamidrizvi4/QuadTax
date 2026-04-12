"use client";

import { useRouter } from "next/navigation";
import { useTaxStore } from "@/store/taxStore";
import { ChevronRight, User } from "lucide-react";

export default function ProfilePage() {
  const router = useRouter();
  const { mcqAnswers, updateMcqAnswers } = useTaxStore();

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    router.push("/intake/documents");
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6">
      <header className="mb-10 text-center">
        <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-200">
          <User className="text-white w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Personal Profile</h1>
        <p className="text-slate-500 text-sm mt-1">First, let's get some basic context.</p>
      </header>

      <form onSubmit={handleNext} className="flex-1 max-w-md mx-auto w-full space-y-6">
        {/* Visa Type */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-slate-700 block ml-1">
            What is your current visa type?
          </label>
          <select
            value={mcqAnswers.visa_type}
            onChange={(e) => updateMcqAnswers({ visa_type: e.target.value })}
            className="w-full h-14 bg-white border border-slate-200 rounded-2xl px-4 text-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-shadow"
            required
          >
            <option value="F-1">F-1 Student</option>
            <option value="J-1">J-1 Exchange Visitor</option>
            <option value="M-1">M-1 Vocational Student</option>
            <option value="Q-1">Q-1 Cultural Exchange</option>
          </select>
        </div>

        {/* First Arrival Year */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-slate-700 block ml-1">
            Year of your first US arrival?
          </label>
          <input
            type="number"
            min="1900"
            max={new Date().getFullYear()}
            value={mcqAnswers.first_us_arrival_year}
            onChange={(e) => updateMcqAnswers({ first_us_arrival_year: parseInt(e.target.value) })}
            className="w-full h-14 bg-white border border-slate-200 rounded-2xl px-4 text-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-shadow"
            required
          />
        </div>

        {/* Tax Residence Country */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-slate-700 block ml-1">
            Country of tax residency?
          </label>
          <select
            value={mcqAnswers.tax_residence_country}
            onChange={(e) => updateMcqAnswers({ tax_residence_country: e.target.value })}
            className="w-full h-14 bg-white border border-slate-200 rounded-2xl px-4 text-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-shadow"
            required
          >
            <option value="" disabled>Select your country</option>
            <option value="China">China</option>
            <option value="India">India</option>
            <option value="Spain">Spain</option>
            <option value="Japan">Japan</option>
            <option value="Germany">Germany</option>
            <option value="United Kingdom">United Kingdom</option>
          </select>
        </div>

        <div className="pt-6">
          <button
            type="submit"
            className="w-full h-16 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 hover:bg-slate-800 active:scale-95 transition-all shadow-xl shadow-slate-200"
          >
            Next: Documents
            <ChevronRight className="w-6 h-6" />
          </button>
        </div>
      </form>
    </div>
  );
}
