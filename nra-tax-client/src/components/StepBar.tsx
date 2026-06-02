'use client';

import { usePathname } from 'next/navigation';
import { Check } from 'lucide-react';

const STEPS = [
  { path: '/intake/profile', label: 'Profile' },
  { path: '/intake/documents', label: 'Documents' },
  { path: '/intake/context', label: 'Context' },
  { path: '/processing', label: 'Calculating' },
  { path: '/results', label: 'Results' },
];

export function StepBar() {
  const pathname = usePathname();
  const currentIdx = STEPS.findIndex((s) => pathname.startsWith(s.path));

  if (currentIdx < 0) return null;

  return (
    <div className="w-full bg-white border-b border-slate-100 px-4 py-3 sticky top-0 z-50">
      <div className="max-w-md mx-auto flex items-center gap-0">
        {STEPS.map((step, i) => {
          const isDone = i < currentIdx;
          const isActive = i === currentIdx;
          return (
            <div key={step.path} className="flex items-center flex-1 min-w-0">
              <div className="flex flex-col items-center gap-1">
                <div
                  className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold transition-all ${
                    isDone
                      ? 'bg-blue-600 text-white'
                      : isActive
                      ? 'bg-slate-900 text-white ring-2 ring-slate-900 ring-offset-2'
                      : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {isDone ? <Check className="w-3.5 h-3.5" /> : i + 1}
                </div>
                <span
                  className={`text-[10px] font-medium whitespace-nowrap transition-colors ${
                    isActive ? 'text-slate-900' : isDone ? 'text-blue-600' : 'text-slate-400'
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-1 mb-4 transition-colors ${
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
