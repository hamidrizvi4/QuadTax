'use client';

interface YesNoToggleProps {
  label: string;
  sublabel?: string;
  value: boolean | null;
  onChange: (v: boolean) => void;
}

export function YesNoToggle({ label, sublabel, value, onChange }: YesNoToggleProps) {
  return (
    <div className="space-y-2">
      <div>
        <p className="font-semibold text-slate-800 text-sm leading-snug">{label}</p>
        {sublabel && <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{sublabel}</p>}
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onChange(true)}
          className={`flex-1 h-11 rounded-xl font-bold text-sm border-2 transition-all ${
            value === true
              ? 'bg-blue-600 border-blue-600 text-white shadow-md shadow-blue-100'
              : 'bg-white border-slate-200 text-slate-600 hover:border-blue-300'
          }`}
        >
          Yes
        </button>
        <button
          type="button"
          onClick={() => onChange(false)}
          className={`flex-1 h-11 rounded-xl font-bold text-sm border-2 transition-all ${
            value === false
              ? 'bg-slate-800 border-slate-800 text-white shadow-md shadow-slate-100'
              : 'bg-white border-slate-200 text-slate-600 hover:border-slate-400'
          }`}
        >
          No
        </button>
      </div>
    </div>
  );
}
