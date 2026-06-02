import { AlertTriangle } from 'lucide-react';

interface HumanReviewBannerProps {
  reasons: string[];
}

export function HumanReviewBanner({ reasons }: HumanReviewBannerProps) {
  if (!reasons || reasons.length === 0) return null;
  return (
    <div className="bg-red-50 border border-red-200 rounded-3xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle className="w-5 h-5 text-red-600 shrink-0" />
        <p className="font-bold text-red-900 text-sm">CPA Review Recommended</p>
      </div>
      <p className="text-xs text-red-700 mb-3 leading-relaxed">
        The engine flagged the following issues. Review with a qualified tax professional before
        filing.
      </p>
      <ul className="space-y-1.5">
        {reasons.map((r, i) => (
          <li key={i} className="text-xs text-red-800 leading-normal">
            • {r}
          </li>
        ))}
      </ul>
    </div>
  );
}
