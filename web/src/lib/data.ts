import { readFileSync } from "node:fs";
import { join } from "node:path";

import type { Finding, Project, QueueItem, RunManifest } from "./types";

/**
 * Data is read from disk at build time. Nothing is fetched at runtime
 * except the attestation account itself, so the published site is a set
 * of static files that behave identically when served from a folder.
 */
function load<T>(name: string): T {
  const path = join(process.cwd(), "public", "data", name);
  return JSON.parse(readFileSync(path, "utf-8")) as T;
}

export const getRun = () => load<RunManifest>("run.json");
export const getFindings = () => load<Finding[]>("findings.json");
export const getProjects = () => load<Record<string, Project>>("projects.json");
export const getQueue = () => load<QueueItem[]>("queue.json");

export const RULE_LABELS: Record<string, string> = {
  R1: "Same vintage credited by two registries",
  R2: "Cross-listed, no vintage overlap",
  R3: "Same credit serial disposed of twice",
  R4: "Duplicate row in the registry export",
};

export const RULE_SHORT: Record<string, string> = {
  R1: "Vintage overlap",
  R2: "Registry move",
  R3: "Serial overlap",
  R4: "Export duplicate",
};
