"use client";

import { useRouter } from "next/navigation";
import { useTaxStore } from "@/store/taxStore";
import { FileUp, Trash2, ChevronRight, FileCheck, Info } from "lucide-react";

export default function DocumentsPage() {
  const router = useRouter();
  const { 
    i94File, setI94File, 
    w2Files, addW2File, 
    form1042sFiles, addForm1042sFile 
  } = useTaxStore();

  const handleNext = () => {
    if (!i94File) {
      alert("Please upload your I-94 Travel History.");
      return;
    }
    router.push("/intake/context");
  };

  const FileCard = ({ label, file, onClear, type }: any) => (
    <div className="bg-white border border-slate-200 rounded-2xl p-4 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-green-50 rounded-full flex items-center justify-center">
          <FileCheck className="text-green-600 w-5 h-5" />
        </div>
        <div>
          <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">{type}</p>
          <p className="text-slate-900 font-medium truncate max-w-[150px]">{file.name}</p>
        </div>
      </div>
      <button 
        onClick={onClear}
        className="text-slate-400 hover:text-red-500 p-2"
      >
        <Trash2 className="w-5 h-5" />
      </button>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-24">
      <header className="mb-8 text-center text-balance">
        <h1 className="text-2xl font-bold text-slate-900">Upload Documents</h1>
        <p className="text-slate-500 text-sm mt-1">Take a clear photo or upload a PDF of each document.</p>
      </header>

      <div className="space-y-8 flex-1 max-w-md mx-auto w-full">
        
        {/* I-94 TRAVEL HISTORY */}
        <div className="space-y-4">
          <label className="text-sm font-bold text-slate-700 flex items-center gap-2">
            I-94 Travel History <span className="text-red-500 font-normal italic">(Required)</span>
          </label>
          {i94File ? (
            <FileCard type="I-94" file={i94File} onClear={() => setI94File(null)} />
          ) : (
            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-slate-300 rounded-3xl bg-white hover:bg-slate-50 cursor-pointer transition-colors active:bg-blue-50/50">
              <FileUp className="w-8 h-8 text-blue-500 mb-2" />
              <span className="text-sm font-semibold text-slate-600">Snap Photo or Upload</span>
              <input 
                type="file" 
                className="hidden" 
                accept="image/*,application/pdf"
                capture="environment"
                onChange={(e) => setI94File(e.target.files?.[0] || null)}
              />
            </label>
          )}
        </div>

        {/* W-2 RECORDS */}
        <div className="space-y-4">
          <label className="text-sm font-bold text-slate-700">W-2 Forms (Wages)</label>
          <div className="space-y-3">
            {w2Files.map((f, i) => (
              <FileCard key={i} type="W-2" file={f} onClear={() => {}} /> 
              /* Future: Add specific remove logic */
            ))}
            <label className="flex flex-col items-center justify-center w-full h-24 border-2 border-dashed border-slate-200 rounded-3xl bg-white hover:bg-slate-50 cursor-pointer transition-colors active:bg-blue-50/50">
              <span className="text-sm font-semibold text-slate-500">+ Add W-2 Form</span>
              <input 
                type="file" 
                className="hidden" 
                multiple
                accept="image/*,application/pdf"
                onChange={(e) => {
                  if (e.target.files) {
                    Array.from(e.target.files).forEach(addW2File);
                  }
                }}
              />
            </label>
          </div>
        </div>

        {/* 1042-S RECORDS */}
        <div className="space-y-4">
          <label className="text-sm font-bold text-slate-700">1042-S Forms (Scholarships)</label>
          <div className="space-y-3">
            {form1042sFiles.map((f, i) => (
              <FileCard key={i} type="1042-S" file={f} onClear={() => {}} />
            ))}
            <label className="flex flex-col items-center justify-center w-full h-24 border-2 border-dashed border-slate-200 rounded-3xl bg-white hover:bg-slate-50 cursor-pointer transition-colors active:bg-blue-50/50">
              <span className="text-sm font-semibold text-slate-500">+ Add 1042-S Form</span>
              <input 
                type="file" 
                className="hidden" 
                multiple
                accept="image/*,application/pdf"
                onChange={(e) => {
                  if (e.target.files) {
                    Array.from(e.target.files).forEach(addForm1042sFile);
                  }
                }}
              />
            </label>
          </div>
        </div>

        {/* Tip Section */}
        <div className="bg-blue-50 p-4 rounded-2xl flex gap-3">
          <Info className="w-5 h-5 text-blue-600 shrink-0" />
          <p className="text-xs text-blue-900 leading-tight">
            Our AI works best with high-resolution photos. Ensure all four corners of the document are visible.
          </p>
        </div>
      </div>

      {/* Floating Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 p-6 bg-slate-50 border-t border-slate-200 sm:relative sm:border-0 sm:bg-transparent">
        <button
          onClick={handleNext}
          className="w-full h-16 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 max-w-md mx-auto shadow-2xl active:scale-95 transition-all"
        >
          Review Context
          <ChevronRight className="w-6 h-6" />
        </button>
      </div>
    </div>
  );
}
