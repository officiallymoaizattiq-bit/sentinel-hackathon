"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Patient } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [role, setRole] = useState<"admin" | "patient">("admin");
  const [passkey, setPasskey] = useState("");
  const [patientId, setPatientId] = useState("");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (role === "patient") {
      fetch("/api/patients", { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : []))
        .then((ps) => setPatients(ps))
        .catch(() => setPatients([]));
    }
  }, [role]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const body: Record<string, unknown> = { role, passkey };
      if (role === "patient") body.patient_id = patientId;
      const r = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      if (r.ok) {
        router.push(role === "admin" ? "/admin" : "/patient");
        return;
      }
      const j = await r.json().catch(() => ({}));
      setErr(j?.detail?.error ?? `login failed (${r.status})`);
    } catch (e) {
      setErr(`network: ${String(e)}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-[80vh] items-center justify-center">
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-4 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl"
      >
        <h1 className="text-xl font-semibold">Sentinel</h1>
        <p className="text-sm text-slate-400">
          Sign in with your passkey.
        </p>

        <div className="flex gap-2 rounded-full border border-white/10 p-1 text-sm">
          <button
            type="button"
            onClick={() => setRole("admin")}
            className={
              "flex-1 rounded-full py-1.5 " +
              (role === "admin"
                ? "bg-white/15 text-white"
                : "text-slate-400")
            }
          >
            Clinician
          </button>
          <button
            type="button"
            onClick={() => setRole("patient")}
            className={
              "flex-1 rounded-full py-1.5 " +
              (role === "patient"
                ? "bg-white/15 text-white"
                : "text-slate-400")
            }
          >
            Patient
          </button>
        </div>

        {role === "patient" && (
          <select
            className="w-full rounded-lg border border-white/10 bg-slate-950/60 px-3 py-2 text-sm"
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
            required
          >
            <option value="">Choose your name…</option>
            {patients.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        )}

        <input
          type="password"
          placeholder="Passkey"
          className="w-full rounded-lg border border-white/10 bg-slate-950/60 px-3 py-2 text-sm"
          value={passkey}
          onChange={(e) => setPasskey(e.target.value)}
          required
          autoFocus
        />

        {err && (
          <div className="rounded-md border border-red-600/40 bg-red-950/40 p-2 text-xs text-red-300">
            {err}
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-white/10 py-2 text-sm font-medium hover:bg-white/15 disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
