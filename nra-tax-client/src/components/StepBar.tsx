'use client';

import { usePathname } from 'next/navigation';
import { Check } from 'lucide-react';

const STEPS = [
  { paths: ['/intake/eligibility', '/intake/profile'], label: 'Eligibility' },
  { paths: ['/intake/visa'], label: 'Visa' },
  { paths: ['/intake/documents'], label: 'Documents' },
  { paths: ['/intake/ocr-review', '/intake/personal'], label: 'Review' },
  { paths: ['/intake/extras', '/intake/context'], label: 'Details' },
  { paths: ['/processing'], label: 'Calculating' },
  { paths: ['/results'], label: 'Results' },
];

export function StepBar() {
  const pathname = usePathname();
  const currentIdx = STEPS.findIndex((s) => s.paths.some((p) => pathname.startsWith(p)));

  if (currentIdx < 0) return null;

  return (
    <div className="w-full bg-white border-b border-slate-100 px-3 py-2 md:py-3 sticky top-0 z-50">
      <div className="max-w-md md:max-w-2xl mx-auto flex items-center">
        {STEPS.map((step, i) => {
          const isDone = i < currentIdx;
          const isActive = i === currentIdx;
          return (
            <div key={i} className="flex items-center flex-1 min-w-0">
              <div className="flex flex-col items-center gap-0.5 shrink-0">
                <div
                  className={`flex items-center justify-center w-6 h-6 md:w-7 md:h-7 rounded-full text-[10px] md:text-xs font-bold transition-all ${
                    isDone
                      ? 'bg-blue-600 text-white'
                      : isActive
                      ? 'bg-slate-900 text-white ring-2 ring-slate-900 ring-offset-1'
                      : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {isDone ? <Check className="w-3 h-3" /> : i + 1}
                </div>
                <span
                  className={`text-[9px] md:text-[11px] font-medium whitespace-nowrap ${
                    isActive ? 'text-slate-900' : isDone ? 'text-blue-600' : 'text-slate-300'
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-0.5 mb-3 transition-colors ${
                    i < currentIdx ? 'bg-blue-600' : 'bg-slate-100'
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
