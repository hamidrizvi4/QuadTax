'use client';

import { CheckCircle2, FileText } from 'lucide-react';

interface Field {
  key: string;
  label: string;
  value: string | number;
  type?: 'number' | 'text';
}

interface OcrDocumentCardProps {
  title: string;
  subtitle?: string;
  fields: Field[];
  confirmed: boolean;
  onFieldChange: (key: string, value: string) => void;
  onConfirm: () => void;
}

const inputCls =
  'w-full h-10 bg-white border border-slate-200 rounded-xl px-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-shadow';

export function OcrDocumentCard({
  title, subtitle, fields, confirmed, onFieldChange, onConfirm,
}: OcrDocumentCardProps) {
  return (
    <div className={`bg-white border-2 rounded-3xl overflow-hidden transition-all ${
      confirmed ? 'border-green-300 shadow-green-50 shadow-lg' : 'border-slate-200'
    }`}>
      <div className={`px-5 py-4 flex items-center gap-3 ${confirmed ? 'bg-green-50' : 'bg-slate-50'}`}>
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${confirmed ? 'bg-green-100' : 'bg-white'}`}>
          <FileText className={`w-5 h-5 ${confirmed ? 'text-green-600' : 'text-blue-500'}`} />
        </div>
        <div className="flex-1">
          <p className="font-bold text-slate-900 text-sm">{title}</p>
          {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        </div>
        {confirmed && <CheckCircle2 className="w-5 h-5 text-green-500" />}
      </div>
      <div className="p-5 grid grid-cols-2 gap-3">
        {fields.map((field) => (
          <div key={field.key} className="space-y-1">
            <label className="text-xs font-semibold text-slate-500 block">{field.label}</label>
            <input
              type={field.type ?? 'text'}
              value={field.value}
              onChange={(e) => onFieldChange(field.key, e.target.value)}
              className={inputCls}
              step={field.type === 'number' ? '0.01' : undefined}
            />
          </div>
        ))}
      </div>
      {!confirmed && (
        <div className="px-5 pb-5">
          <button type="button" onClick={onConfirm}
            className="w-full h-11 bg-blue-600 text-white rounded-xl font-bold text-sm hover:bg-blue-500 active:scale-95 transition-all">
            ✓ Looks correct
          </button>
        </div>
      )}
    </div>
  );
}
