'use client';

import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import { FileUp, Trash2, ChevronRight, FileCheck, Info } from 'lucide-react';
import { FormField, textareaCls } from '@/components/FormField';

function FileCard({
  label,
  file,
  onClear,
}: {
  label: string;
  file: File;
  onClear: () => void;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-4 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-green-50 rounded-full flex items-center justify-center shrink-0">
          <FileCheck className="text-green-600 w-5 h-5" />
        </div>
        <div>
          <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">{label}</p>
          <p className="text-slate-900 font-medium truncate max-w-[180px] text-sm">{file.name}</p>
          <p className="text-xs text-slate-400">{(file.size / 1024).toFixed(0)} KB</p>
        </div>
      </div>
      <button
        type="button"
        onClick={onClear}
        className="text-slate-300 hover:text-red-500 transition-colors p-2 rounded-full hover:bg-red-50"
        aria-label="Remove file"
      >
        <Trash2 className="w-5 h-5" />
      </button>
    </div>
  );
}

function DropZone({
  label,
  multiple,
  onChange,
}: {
  label: string;
  multiple?: boolean;
  onChange: (files: File[]) => void;
}) {
  return (
    <label className="flex flex-col items-center justify-center w-full h-24 border-2 border-dashed border-slate-200 rounded-2xl bg-white hover:bg-slate-50 hover:border-blue-300 cursor-pointer transition-all active:bg-blue-50/50">
      <FileUp className="w-6 h-6 text-blue-400 mb-1" />
      <span className="text-sm font-semibold text-slate-500">{label}</span>
      <input
        type="file"
        className="hidden"
        multiple={multiple}
        accept="image/*,application/pdf"
        capture="environment"
        onChange={(e) => {
          if (e.target.files) {
            onChange(Array.from(e.target.files));
            e.target.value = '';
          }
        }}
      />
    </label>
  );
}

export default function DocumentsPage() {
  const router = useRouter();
  const {
    i94File,
    setI94File,
    w2Files,
    addW2File,
    removeW2File,
    form1042sFiles,
    addForm1042sFile,
    removeForm1042sFile,
    income,
    updateIncome,
  } = useTaxStore();

  const handleNext = () => {
    if (!i94File) {
      alert('Please upload your I-94 Travel History.');
      return;
    }
    if (!income.income_description.trim()) {
      alert('Please describe your income source so we can apply the correct tax treaty.');
      return;
    }
    router.push('/intake/context');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-8 text-center">
        <h1 className="text-2xl font-bold text-slate-900">Documents & Income</h1>
        <p className="text-slate-500 text-sm mt-1">
          Upload your tax documents and describe your income.
        </p>
      </header>

      <div className="space-y-8 max-w-md mx-auto w-full">

        {/* ── Income Description (most critical field for treaty) ── */}
        <div className="bg-blue-50 border border-blue-200 rounded-3xl p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-blue-600 shrink-0" />
            <p className="text-sm font-bold text-blue-900">Describe Your Income Source</p>
          </div>
          <p className="text-xs text-blue-700 leading-relaxed">
            This is used to apply your country&apos;s tax treaty. Be specific — e.g.{' '}
            <em>&quot;PhD teaching assistant at NYU, paid hourly&quot;</em> or{' '}
            <em>&quot;NSF research fellowship, no services required&quot;</em>.
          </p>
          <FormField label="" required>
            <textarea
              className={textareaCls}
              rows={3}
              value={income.income_description}
              onChange={(e) => updateIncome({ income_description: e.target.value })}
              placeholder="e.g. Graduate research assistant at MIT, stipend from university…"
              required
            />
          </FormField>
        </div>

        {/* ── I-94 Travel History ── */}
        <div className="space-y-3">
          <label className="text-sm font-bold text-slate-700 flex items-center gap-2">
            I-94 Travel History
            <span className="text-red-500 font-normal text-xs italic">(Required)</span>
          </label>
          {i94File ? (
            <FileCard label="I-94" file={i94File} onClear={() => setI94File(null)} />
          ) : (
            <DropZone
              label="Snap photo or upload I-94"
              onChange={(files) => setI94File(files[0])}
            />
          )}
        </div>

        {/* ── W-2 Forms ── */}
        <div className="space-y-3">
          <label className="text-sm font-bold text-slate-700">
            W-2 Forms{' '}
            <span className="font-normal text-slate-400 text-xs">(add all employers)</span>
          </label>
          <div className="space-y-2">
            {w2Files.map((f, i) => (
              <FileCard key={i} label="W-2" file={f} onClear={() => removeW2File(i)} />
            ))}
            <DropZone
              label="+ Add W-2 Form"
              multiple
              onChange={(files) => files.forEach(addW2File)}
            />
          </div>
        </div>

        {/* ── 1042-S Forms ── */}
        <div className="space-y-3">
          <label className="text-sm font-bold text-slate-700">
            1042-S Forms{' '}
            <span className="font-normal text-slate-400 text-xs">
              (scholarships, fellowships, stipends)
            </span>
          </label>
          <div className="space-y-2">
            {form1042sFiles.map((f, i) => (
              <FileCard key={i} label="1042-S" file={f} onClear={() => removeForm1042sFile(i)} />
            ))}
            <DropZone
              label="+ Add 1042-S Form"
              multiple
              onChange={(files) => files.forEach(addForm1042sFile)}
            />
          </div>
        </div>

        <div className="bg-slate-100 rounded-2xl p-4 flex gap-3">
          <Info className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
          <p className="text-xs text-slate-500 leading-relaxed">
            Our AI works best with clear, well-lit photos. Make sure all four corners of the
            document are visible and text is readable.
          </p>
        </div>
      </div>

      {/* ── Floating Action ── */}
      <div className="fixed bottom-0 left-0 right-0 p-5 bg-white/90 backdrop-blur border-t border-slate-100">
        <button
          onClick={handleNext}
          className="w-full h-14 bg-slate-900 text-white rounded-2xl font-bold text-lg flex items-center justify-center gap-2 max-w-md mx-auto shadow-2xl active:scale-95 transition-all"
        >
          Review Context
          <ChevronRight className="w-6 h-6" />
        </button>
      </div>
    </div>
  );
}
