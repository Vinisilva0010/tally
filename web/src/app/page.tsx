import Link from "next/link";

import { getFindings, getRun, RULE_SHORT } from "@/lib/data";
import { Stat } from "@/components/Stat";

export default function Home() {
  const run = getRun();
  const findings = getFindings();
  const confirmed = findings.filter((f) => f.is_finding);
  const context = findings.filter((f) => !f.is_finding);

  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <h1 className="text-4xl">Who counted the same tonne twice?</h1>
        <p className="max-w-3xl text-lg">
          Six registries issue carbon credits independently and none of them can
          see what the others issued. Tally reads their public records, finds
          cases where one physical project was credited for the same year of
          emission reduction in two of them, and publishes the result on Solana
          so anyone can check it without trusting us.
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Credits evidenced"
          value={run.credits_evidenced.toLocaleString()}
          note="tonnes credited more than once"
        />
        <Stat
          label="Confirmed findings"
          value={String(confirmed.length)}
          note="rules R1 and R3"
        />
        <Stat
          label="Projects analysed"
          value={run.project_count.toLocaleString()}
          note="across six registries"
        />
        <Stat
          label="Credit events read"
          value={run.credit_event_count.toLocaleString()}
          note="issuance, retirement, cancellation"
        />
      </section>

      <section className="border border-border bg-surface p-6">
        <h2 className="text-xl">The attestation</h2>
        <dl className="mt-4 grid gap-x-8 gap-y-3 sm:grid-cols-[max-content_1fr]">
          <dt className="font-bold">Merkle root</dt>
          <dd className="mono break-all">{run.merkle_root}</dd>
          <dt className="font-bold">Aggregate file</dt>
          <dd className="mono break-all">{run.aggregate_sha256}</dd>
          <dt className="font-bold">Registry file</dt>
          <dd className="mono break-all">{run.registry_sha256}</dd>
          <dt className="font-bold">Run account</dt>
          <dd className="mono break-all">
            <a
              href={`https://explorer.solana.com/address/${run.run_account}?cluster=${run.cluster}`}
              target="_blank"
              rel="noreferrer"
            >
              {run.run_account}
            </a>
          </dd>
        </dl>
        <p className="mt-4 max-w-3xl text-muted">
          The checksums were recorded before the analysis ran. Download the same
          two workbooks, confirm they hash to these values, run the pipeline and
          compare roots. Every finding below carries a proof you can recompute
          in your own browser.
        </p>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl">Confirmed findings</h2>
        <table className="w-full">
          <thead>
            <tr>
              <th>Project</th>
              <th>Rule</th>
              <th>Registry records</th>
              <th>Country</th>
              <th>Vintages</th>
              <th className="text-right">Credits</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {confirmed
              .slice()
              .sort((a, b) => b.credits_milli - a.credits_milli)
              .map((f) => (
                <tr key={f.index}>
                  <td className="font-bold">{f.note || "—"}</td>
                  <td className="whitespace-nowrap">
                    {f.rule} · {RULE_SHORT[f.rule]}
                  </td>
                  <td className="mono text-sm">{f.subjects.join(" / ")}</td>
                  <td>{f.country}</td>
                  <td className="tabular-nums">{f.vintages.join(", ")}</td>
                  <td className="text-right font-bold tabular-nums">
                    {f.credits.toLocaleString()}
                  </td>
                  <td>
                    <Link href={`/finding/${f.index}`}>Verify</Link>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </section>

      <section className="space-y-3 border border-border p-6">
        <h2 className="text-xl">What is not a finding</h2>
        <p className="max-w-3xl">
          {context.filter((f) => f.rule === "R2").length} projects appear in two
          registries without any overlapping vintage. Those are legitimate
          registry moves and Tally clears them. A further{" "}
          {context.filter((f) => f.rule === "R4").length} cases are the same
          transaction exported twice by a registry, which is a data quality
          problem rather than double counting. Both are published alongside the
          findings: a tool that only ever accuses cannot be checked.
        </p>
        <p className="max-w-3xl">
          Another {run.queue_count} candidate pairs are awaiting human review
          and are deliberately <strong>not</strong> part of the attested result.{" "}
          <Link href="/queue">See the queue</Link>.
        </p>
      </section>
    </div>
  );
}
