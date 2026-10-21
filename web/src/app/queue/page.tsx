import { getQueue, getRun } from "@/lib/data";

export default function QueuePage() {
  const queue = getQueue();
  const run = getRun();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl">Review queue</h1>
        <p className="mt-3 max-w-3xl text-lg">
          These pairs look like the same project registered twice, but matching
          by name alone is not proof. They are <strong>not</strong> part of the
          attested result and no credit figure here is claimed as double
          counted. Each needs a person to open both registry records and decide.
        </p>
      </div>

      <div className="border border-border bg-surface p-5">
        <p>
          The linker compared {run.linkage.compared?.toLocaleString() ?? "—"}{" "}
          cross-registry pairs and rejected all but {queue.length} of the new
          ones: {run.linkage.rejected_marker ?? 0} because the names carry
          different identifying numbers or places,{" "}
          {run.linkage.rejected_distinctive ?? 0} because nothing distinctive
          remained once sector vocabulary was removed,{" "}
          {run.linkage.rejected_state ?? 0} for conflicting states and{" "}
          {run.linkage.rejected_type ?? 0} for conflicting project types.
        </p>
      </div>

      <table className="w-full">
        <thead>
          <tr>
            <th>Projects</th>
            <th>Country</th>
            <th>Vintages</th>
            <th className="text-right">Name match</th>
            <th className="text-right">Developer</th>
            <th className="text-right">Credits at stake</th>
          </tr>
        </thead>
        <tbody>
          {queue.map((item) => (
            <tr key={`${item.project_a}-${item.project_b}`}>
              <td>
                <div className="mono font-bold">
                  {item.registry_a} {item.project_a} / {item.registry_b}{" "}
                  {item.project_b}
                </div>
                <div>{item.name_a}</div>
                <div className="text-muted">{item.name_b}</div>
              </td>
              <td>{item.country}</td>
              <td className="tabular-nums">{item.vintages.join(", ")}</td>
              <td className="text-right tabular-nums">
                {item.name_cosine.toFixed(2)}
              </td>
              <td className="text-right tabular-nums">
                {item.developer_sim < 0 ? "—" : item.developer_sim.toFixed(0)}
              </td>
              <td className="text-right font-bold tabular-nums">
                {item.credits.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
