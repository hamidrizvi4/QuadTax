interface FormFieldProps {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}

export function FormField({ label, required, hint, children }: FormFieldProps) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-semibold text-slate-700 block">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      {hint && <p className="text-xs text-slate-400 leading-snug">{hint}</p>}
      {children}
    </div>
  );
}

export const inputCls =
  'w-full h-12 bg-white border border-slate-200 rounded-xl px-4 text-base focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-shadow';

export const selectCls = `${inputCls} cursor-pointer`;

export const textareaCls =
  'w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-base focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-shadow resize-none';
