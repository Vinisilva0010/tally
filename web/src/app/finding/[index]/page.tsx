import Link from "next/link";
import { notFound } from "next/navigation";

import { VerifyPanel } from "@/components/VerifyPanel";
import { getFindings, getProjects, getRun, RULE_LABELS } from "@/lib/data";

export function generateStaticParams() {
  return getFindings().map((f) => ({ index: String(f.index) }));
}

export default async function FindingPage({
  params,
}: {
  params: Promise<{ index: string }>;
}) {
  const { index } = await params;
  const finding = getFindings().find((f) => String(f.index) === index);
  if (!finding) notFound();

  const run = getRun();
  const projects = getProjects();

  return (
    <div className="space-y-8">
      <div>
        <Link href="/">← All findings</Link>
        <h1 className="mt-3 text-3xl">
          {finding.rule}: {RULE_LABELS[finding.rule]}
        </h1>
        <p className="mt-2 text-lg">
          {finding.credits.toLocaleString()} credits
          {finding.vintages.length
            ? ` · vintage ${finding.vintages.join(", ")}`
            : ""}
          {finding.country ? ` · ${finding.country}` : ""}
        </p>
      </div>

      <section className="grid gap-4 md:grid-cols-2">
        {finding.subjects.filter(Boolean).map((id) => {
          const project = projects[id];
          if (!project) {
            return (
              <div key={id} className="border border-border bg-surface p-5">
                <div className="mono font-bold">{id}</div>
                <p className="mt-2 text-muted">
                  Serial prefix, not a project identifier.
                </p>
              </div>
            );
          }
          return (
            <div key={id} className="border border-border bg-surface p-5">
              <div className="font-extrabold">
                {project.registry} · <span className="mono">{project.project_id}</span>
              </div>
              <div className="mt-1 text-lg font-bold">{project.name}</div>
              <dl className="mt-3 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
                <dt className="font-bold">Developer</dt>
                <dd>{project.developer ?? "—"}</dd>
                <dt className="font-bold">Type</dt>
                <dd>{project.type ?? "—"}</dd>
                <dt className="font-bold">Where</dt>
                <dd>
                  {project.country}
                  {project.state ? ` · ${project.state}` : ""}
                </dd>
                <dt className="font-bold">Issued</dt>
                <dd className="tabular-nums">
                  {project.issued.toLocaleString()}
                </dd>
              </dl>
              {project.link ? (
                <p className="mt-3">
                  <a href={project.link} target="_blank" rel="noreferrer">
                    Open the registry record
                  </a>
                </p>
              ) : null}
            </div>
          );
        })}
      </section>

      {finding.note ? (
        <section className="border border-border p-5">
          <h2 className="text-lg">Detail</h2>
          <p className="mono mt-2">{finding.note}</p>
        </section>
      ) : null}

      <section className="border border-border p-5">
        <h2 className="text-lg">The exact fields this fingerprint covers</h2>
        <pre className="mono mt-3 overflow-x-auto bg-surface p-4 text-sm">
          {JSON.stringify(finding.leaf_fields, null, 2)}
        </pre>
        <p className="mono mt-3 break-all text-sm">
          <strong>Leaf:</strong> {finding.leaf_hash}
        </p>
        <p className="mt-2 text-muted">
          Proof length: {finding.proof.length} steps to the root.
        </p>
      </section>

      <VerifyPanel
        finding={finding}
        runAccount={run.run_account}
        localRoot={run.merkle_root}
      />
    </div>
  );
}
