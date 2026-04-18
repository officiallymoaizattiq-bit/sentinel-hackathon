import type { CallRecord } from "@/lib/api";

export function CohortPanel({ last }: { last: CallRecord | null }) {
  if (!last) return null;
  const sims = last.similar_calls ?? [];
  const outcomes = sims.reduce<Record<string, number>>((acc, s) => {
    acc[s.outcome] = (acc[s.outcome] ?? 0) + 1;
    return acc;
  }, {});
  return (
    <div className="rounded border border-slate-800 p-4">
      <div className="mb-2 text-sm text-slate-400">
        Similar prior cases
      </div>
      <ul className="space-y-1">
        {sims.map((s) => (
          <li key={s.case_id} className="flex justify-between font-mono text-sm">
            <span>{s.case_id.slice(0, 8)}</span>
            <span>{s.outcome}</span>
            <span className="text-slate-500">{s.similarity.toFixed(2)}</span>
          </li>
        ))}
      </ul>
      <div className="mt-3 text-sm text-slate-300">
        Outcome mix:{" "}
        {Object.entries(outcomes).map(([k, v]) => (
          <span key={k} className="mr-2">{k}: {v}</span>
        ))}
      </div>
    </div>
  );
}
