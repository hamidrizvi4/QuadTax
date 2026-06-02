'use client';

import { Plus, Trash2 } from 'lucide-react';
import type { TravelEntry } from '@/store/taxStore';

interface TravelHistoryTableProps {
  entries: TravelEntry[];
  onChange: (entries: TravelEntry[]) => void;
}

const VISA_TYPES = ['F-1', 'J-1', 'M-1', 'Q-1', 'H-1B', 'B-1/B-2', 'Other'];

export function TravelHistoryTable({ entries, onChange }: TravelHistoryTableProps) {
  const add = () =>
    onChange([...entries, { visaType: 'F-1', entryDate: '', leaveDate: '' }]);

  const update = (i: number, field: keyof TravelEntry, value: string) =>
    onChange(entries.map((e, idx) => (idx === i ? { ...e, [field]: value } : e)));

  const remove = (i: number) => onChange(entries.filter((_, idx) => idx !== i));

  const inputCls =
    'w-full h-9 bg-white border border-slate-200 rounded-lg px-2 text-xs focus:ring-1 focus:ring-blue-400 outline-none';
  const selectCls = `${inputCls} cursor-pointer`;

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="text-left px-3 py-2 font-bold text-slate-600 w-28">Visa Type</th>
              <th className="text-left px-3 py-2 font-bold text-slate-600">Entry Date</th>
              <th className="text-left px-3 py-2 font-bold text-slate-600">Leave Date</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {entries.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-center text-slate-400">
                  No entries — add your US visits below
                </td>
              </tr>
            )}
            {entries.map((entry, i) => (
              <tr key={i}>
                <td className="px-2 py-2">
                  <select
                    className={selectCls}
                    value={entry.visaType}
                    onChange={(e) => update(i, 'visaType', e.target.value)}
                  >
                    {VISA_TYPES.map((v) => (
                      <option key={v} value={v}>{v}</option>
                    ))}
                  </select>
                </td>
                <td className="px-2 py-2">
                  <input type="date" className={inputCls} value={entry.entryDate}
                    onChange={(e) => update(i, 'entryDate', e.target.value)} />
                </td>
                <td className="px-2 py-2">
                  <input type="date" className={inputCls} value={entry.leaveDate}
                    onChange={(e) => update(i, 'leaveDate', e.target.value)} />
                </td>
                <td className="px-2 py-2">
                  <button type="button" onClick={() => remove(i)}
                    className="text-slate-300 hover:text-red-500 transition-colors p-1">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button type="button" onClick={add}
        className="flex items-center gap-1.5 text-xs font-bold text-blue-600 hover:text-blue-800 transition-colors px-1">
        <Plus className="w-3.5 h-3.5" />
        Add visit
      </button>
    </div>
  );
}
