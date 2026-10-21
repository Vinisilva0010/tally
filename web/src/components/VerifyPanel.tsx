"use client";

import { useState } from "react";

import { verifyFinding } from "@/lib/merkle";
import { fetchRun } from "@/lib/solana";
import type { Finding } from "@/lib/types";

type Status =
  | { phase: "idle" }
  | { phase: "running"; step: string }
  | { phase: "done"; lines: string[]; ok: boolean }
  | { phase: "error"; message: string };

export function VerifyPanel({
  finding,
  runAccount,
  localRoot,
}: {
  finding: Finding;
  runAccount: string;
  localRoot: string;
}) {
  const [status, setStatus] = useState<Status>({ phase: "idle" });

  async function run() {
    try {
      setStatus({ phase: "running", step: "Reading the attestation from Solana" });
      const onChain = await fetchRun(runAccount);

      setStatus({ phase: "running", step: "Recomputing the leaf and proof" });
      const result = await verifyFinding(
        finding.leaf_fields,
        finding.leaf_hash,
        finding.proof,
        onChain.merkleRoot
      );

      const lines = [
        `Root held on chain:     ${onChain.merkleRoot}`,
        `Root in this page:      ${localRoot}`,
        `Attestation sealed:     ${onChain.frozen ? "yes" : "no"}`,
        `Findings on chain:      ${onChain.findingsWritten} of ${onChain.findingCount}`,
        "",
        `Leaf recomputed here:   ${result.recomputedLeaf}`,
        `Leaf matches published: ${result.leafMatches ? "yes" : "NO"}`,
        `Proof rebuilds root:    ${result.computedRoot}`,
        `Matches chain:          ${result.rootMatches ? "yes" : "NO"}`,
      ];

      const ok =
        result.leafMatches &&
        result.rootMatches &&
        onChain.frozen &&
        onChain.merkleRoot === localRoot.toLowerCase();

      setStatus({ phase: "done", lines, ok });
    } catch (error) {
      setStatus({
        phase: "error",
        message: error instanceof Error ? error.message : String(error),
      });
    }
  }

  return (
    <div className="border-2 border-foreground p-6">
      <h2 className="text-xl">Check this yourself</h2>
      <p className="mt-2 max-w-3xl">
        Your browser rebuilds the fingerprint of this finding from the fields
        shown above, walks the proof up to the root, and compares it with the
        root stored in the Solana account. Nothing here is taken from this
        page&apos;s own copy of the result.
      </p>

      <button
        onClick={run}
        disabled={status.phase === "running"}
        className="mt-4 border-2 border-foreground bg-foreground px-5 py-2.5 font-extrabold text-background disabled:opacity-60"
      >
        {status.phase === "running" ? "Checking…" : "Run the check"}
      </button>

      {status.phase === "running" ? (
        <p className="mt-4 font-bold">{status.step}…</p>
      ) : null}

      {status.phase === "error" ? (
        <p className="mt-4 font-bold text-warn">Could not check: {status.message}</p>
      ) : null}

      {status.phase === "done" ? (
        <div className="mt-4">
          <p
            className={`text-lg font-extrabold ${
              status.ok ? "text-ok" : "text-warn"
            }`}
          >
            {status.ok
              ? "Verified against the sealed attestation on Solana devnet."
              : "Verification failed. The published result does not match."}
          </p>
          <pre className="mono mt-3 overflow-x-auto border border-border bg-surface p-4 text-sm">
            {status.lines.join("\n")}
          </pre>
        </div>
      ) : null}
    </div>
  );
}
