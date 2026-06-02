'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, BookOpen } from 'lucide-react';

interface NarrativeCardProps {
  sections: Record<string, string>;
}

// Strip **bold** markers for plain display
function stripMarkdown(text: string): string {
  return text.replace(/\*\*(.*?)\*\*/g, '$1');
}

export function NarrativeCard({ sections }: NarrativeCardProps) {
  const [open, setOpen] = useState(false);
  const entries = Object.entries(sections ?? {});
  if (entries.length === 0) return null;

  return (
    <div className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-sm">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full p-5 flex items-center justify-between text-left hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <BookOpen className="w-5 h-5 text-blue-600 shrink-0" />
          <div>
            <p className="font-bold text-slate-900 text-sm">Why these numbers?</p>
            <p className="text-xs text-slate-500">Full plain-English explanation</p>
          </div>
        </div>
        {open ? (
          <ChevronUp className="w-5 h-5 text-slate-400 shrink-0" />
        ) : (
          <ChevronDown className="w-5 h-5 text-slate-400 shrink-0" />
        )}
      </button>

      {open && (
        <div className="divide-y divide-slate-100">
          {entries.map(([title, body]) => (
            <div key={title} className="p-5">
              <h3 className="font-bold text-slate-800 text-sm mb-2">{title}</h3>
              <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-line">
                {stripMarkdown(body)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
