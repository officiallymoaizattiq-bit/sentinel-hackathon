import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { api } from "@/lib/api";
import { TrajectoryChart } from "@/components/TrajectoryChart";

export const revalidate = 0;

type SessionInfo = { role: string; patient_id?: string };

async function getSession(): Promise<SessionInfo | null> {
  const token = cookies().get("sentinel_session")?.value;
  if (!token) return null;
  const backend = process.env.BACKEND_URL ?? "http://localhost:8000";
  try {
    const r = await fetch(`${backend}/api/auth/me`, {
      headers: { cookie: `sentinel_session=${token}` },
      cache: "no-store",
    });
    if (!r.ok) return null;
    return r.json();
  } catch {
    return null;
  }
}

export default async function PatientHome() {
  const session = await getSession();
  if (!session || session.role !== "patient" || !session.patient_id) {
    redirect("/login");
  }
  const pid = session.patient_id;

  const [patients, calls] = await Promise.all([
    api.patients().catch(() => []),
    api.calls(pid).catch(() => []),
  ]);
  const me = patients.find((p) => p.id === pid);
  const points = calls
    .filter((c) => c.score !== null)
    .map((c) => ({
      t: new Date(c.called_at).toLocaleTimeString(),
      deterioration: c.score!.deterioration,
    }));
  const last = calls[calls.length - 1] ?? null;

  return (
    <div className="mx-auto max-w-lg space-y-6 p-4">
      <header>
        <h1 className="text-2xl font-semibold">
          {me?.name ?? "Welcome"}
        </h1>
        <p className="text-sm text-slate-400">
          Your recent check-ins
        </p>
      </header>

      {last?.score && (
        <section
          className={
            "rounded-2xl border p-4 " +
            (last.score.recommended_action === "suggest_911"
              ? "border-red-500/40 bg-red-950/40"
              : "border-white/10 bg-white/5")
          }
        >
          <div className="mb-1 text-sm text-slate-400">
            Latest check-in
          </div>
          <div className="text-lg">{last.score.summary}</div>
          <div className="mt-2 text-xs text-slate-500">
            {new Date(last.called_at).toLocaleString()}
          </div>
        </section>
      )}

      <section>
        <h2 className="mb-2 text-sm text-slate-400">Trend</h2>
        <TrajectoryChart points={points} />
      </section>

      <footer className="pt-4">
        <form action="/api/auth/logout" method="POST">
          <button
            type="submit"
            className="text-xs text-slate-500 underline"
          >
            Sign out
          </button>
        </form>
      </footer>
    </div>
  );
}
