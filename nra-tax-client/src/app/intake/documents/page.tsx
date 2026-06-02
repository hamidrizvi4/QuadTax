'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTaxStore } from '@/store/taxStore';
import { FileUp, Trash2, FileCheck, Info, Sparkles, Loader2 } from 'lucide-react';
import { extractDocuments } from '@/lib/api';

function FileCard({ label, file, onClear }: { label: string; file: File; onClear: () => void }) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-3 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 bg-green-50 rounded-full flex items-center justify-center shrink-0">
          <FileCheck className="text-green-600 w-4 h-4" />
        </div>
        <div>
          <p className="text-xs text-slate-400 font-bold uppercase tracking-wider">{label}</p>
          <p className="text-slate-800 font-medium truncate max-w-[180px] text-sm">{file.name}</p>
        </div>
      </div>
      <button type="button" onClick={onClear}
        className="text-slate-300 hover:text-red-500 transition-colors p-2 rounded-full hover:bg-red-50">
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  );
}

function DropZone({ label, multiple, onChange }: { label: string; multiple?: boolean; onChange: (files: File[]) => void }) {
  return (
    <label className="flex flex-col items-center justify-center w-full h-20 border-2 border-dashed border-slate-200 rounded-2xl bg-white hover:bg-slate-50 hover:border-blue-300 cursor-pointer transition-all">
      <FileUp className="w-5 h-5 text-blue-400 mb-1" />
      <span className="text-xs font-semibold text-slate-500">{label}</span>
      <input type="file" className="hidden" multiple={multiple}
        accept="image/*,application/pdf" capture="environment"
        onChange={(e) => { if (e.target.files) { onChange(Array.from(e.target.files)); e.target.value = ''; } }} />
    </label>
  );
}

export default function DocumentsPage() {
  const router = useRouter();
  const {
    i94File, setI94File,
    w2Files, addW2File, removeW2File,
    form1042sFiles, addForm1042sFile, removeForm1042sFile,
    residency, setOcrResult,
  } = useTaxStore();

  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [form1099Files, setForm1099Files] = useState<File[]>([]);

  const hasAtLeastOneDoc = i94File || w2Files.length > 0 || form1042sFiles.length > 0;

  const handleScan = async () => {
    setScanError(null);
    setScanning(true);
    try {
      const result = await extractDocuments({
        taxYear: residency.tax_year,
        i94File,
        w2Files,
        form1042sFiles,
        form1099Files,
      });
      setOcrResult(result);
      router.push('/intake/ocr-review');
    } catch (err) {
      setScanError(err instanceof Error ? err.message : 'Scanning failed. Please try again.');
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 pb-28">
      <header className="mb-8 text-center">
        <h1 className="text-2xl font-bold text-slate-900">Upload Documents</h1>
        <p className="text-slate-500 text-sm mt-1">
          Our AI will extract all the numbers automatically — you&apos;ll review them next.
        </p>
      </header>

      <div className="space-y-7 max-w-md mx-auto w-full">
        <div className="space-y-2">
          <label className="text-sm font-bold text-slate-700 flex items-center gap-2">
            I-94 Travel History
            <span className="text-red-500 font-normal text-xs italic">(Required)</span>
          </label>
          {i94File
            ? <FileCard label="I-94" file={i94File} onClear={() => setI94File(null)} />
            : <DropZone label="Snap photo or upload I-94 PDF" onChange={(f) => setI94File(f[0])} />}
        </div>

        <div className="space-y-2">
          <label className="text-sm font-bold text-slate-700">
            W-2 Forms <span className="text-slate-400 font-normal text-xs">(one per employer)</span>
          </label>
          <div className="space-y-2">
            {w2Files.map((f, i) => <FileCard key={i} label="W-2" file={f} onClear={() => removeW2File(i)} />)}
            <DropZone label="+ Add W-2 Form" multiple onChange={(fs) => fs.forEach(addW2File)} />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-bold text-slate-700">
            1042-S Forms <span className="text-slate-400 font-normal text-xs">(scholarships, fellowships)</span>
          </label>
          <div className="space-y-2">
            {form1042sFiles.map((f, i) => <FileCard key={i} label="1042-S" file={f} onClear={() => removeForm1042sFile(i)} />)}
            <DropZone label="+ Add 1042-S Form" multiple onChange={(fs) => fs.forEach(addForm1042sFile)} />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-bold text-slate-700">
            1099 Forms <span className="text-slate-400 font-normal text-xs">(interest, dividends)</span>
          </label>
          <div className="space-y-2">
            {form1099Files.map((f, i) => (
              <FileCard key={i} label="1099" file={f}
                onClear={() => setForm1099Files((p) => p.filter((_, idx) => idx !== i))} />
            ))}
            <DropZone label="+ Add 1099 Form" multiple
              onChange={(fs) => setForm1099Files((p) => [...p, ...fs])} />
          </div>
        </div>

        <div className="bg-slate-100 rounded-2xl p-4 flex gap-3">
          <Info className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
          <p className="text-xs text-slate-500 leading-relaxed">
            Upload clear photos or PDFs. All four corners must be visible. We extract all box values
            automatically — you will review and confirm them on the next screen.
          </p>
        </div>

        {scanError && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-3 text-xs text-red-800">{scanError}</div>
        )}
      </div>

      <div className="fixed bottom-0 left-0 right-0 p-5 bg-white/90 backdrop-blur border-t border-slate-100">
        <button onClick={handleScan} disabled={scanning || !hasAtLeastOneDoc}
          className="w-full h-14 bg-blue-600 text-white rounded-2xl font-bold text-base flex items-center justify-center gap-3 max-w-md mx-auto shadow-2xl shadow-blue-200 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed">
          {scanning
            ? <><Loader2 className="w-5 h-5 animate-spin" /> Scanning documents…</>
            : <><Sparkles className="w-5 h-5" /> Scan All Documents</>}
        </button>
      </div>
    </div>
  );
}
