import { api } from "@/lib/api";
import { TrajectoryChart } from "@/components/TrajectoryChart";
import { CohortPanel } from "@/components/CohortPanel";

export const revalidate = 0;

export default async function PatientDetail({
  params,
}: { params: { id: string } }) {
  const [patients, calls] = await Promise.all([
    api.patients(),
    api.calls(params.id),
  ]);
  const patient = patients.find((p) => p.id === params.id);
  if (!patient) return <div>Not found.</div>;

  const points = calls
    .filter((c) => c.score !== null)
    .map((c) => ({
      t: new Date(c.called_at).toLocaleTimeString(),
      deterioration: c.score!.deterioration,
    }));

  const last = calls[calls.length - 1] ?? null;

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold">{patient.name}</h2>
        <div className="text-sm text-slate-400">{patient.surgery_type}</div>
      </header>

      <section>
        <h3 className="mb-2 text-sm text-slate-400">
          Deterioration trajectory
        </h3>
        <TrajectoryChart points={points} />
      </section>

      {last?.score && (
        <section className="rounded border border-slate-800 p-4">
          <div className="mb-1 font-mono">
            {last.score.recommended_action} ·
            score {last.score.deterioration.toFixed(2)} ·
            qSOFA {last.score.qsofa} ·
            NEWS2 {last.score.news2}
          </div>
          <div className="text-sm text-slate-300">{last.score.summary}</div>
          <div className="mt-1 text-xs text-slate-500">
            {last.score.red_flags.join(", ")}
          </div>
        </section>
      )}

      <section>
        <CohortPanel last={last} />
      </section>
    </div>
  );
}
