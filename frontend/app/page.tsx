import { api } from "@/lib/api";
import { PatientCard } from "@/components/PatientCard";
import { AlertFeed } from "@/components/AlertFeed";
import { ConvaiWidget } from "@/components/ConvaiWidget";
import { FinalizeButton } from "@/components/FinalizeButton";

export const revalidate = 0;

export default async function Dashboard() {
  const patients = await api.patients();
  const agentId = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID ?? "";

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
      <section className="md:col-span-2 space-y-6">
        <div>
          <h2 className="mb-2 text-lg font-semibold">Patients</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {patients.map((p) => (
              <PatientCard key={p.id} p={p} />
            ))}
          </div>
        </div>
        <ConvaiWidget agentId={agentId} />
        <FinalizeButton />
      </section>
      <aside>
        <h2 className="mb-2 text-lg font-semibold">Recent alerts</h2>
        <AlertFeed />
      </aside>
    </div>
  );
}
