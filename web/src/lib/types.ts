export type ProofStep = { sibling: string; sibling_is_left: boolean };

export type Finding = {
  index: number;
  rule: string;
  severity: number;
  subjects: string[];
  registries: string[];
  country: string;
  vintages: number[];
  credits: number;
  credits_milli: number;
  note: string;
  is_finding: boolean;
  leaf_fields: (string | number)[];
  leaf_hash: string;
  proof: ProofStep[];
};

export type Project = {
  project_id: string;
  registry: string;
  name: string;
  country: string;
  state: string | null;
  type: string | null;
  developer: string | null;
  methodology: string | null;
  issued: number;
  link: string;
};

export type QueueItem = {
  project_a: string;
  project_b: string;
  name_a: string;
  name_b: string;
  registry_a: string;
  registry_b: string;
  country: string;
  vintages: number[];
  credits: number;
  name_cosine: number;
  developer_sim: number;
};

export type RunManifest = {
  dataset_version: string;
  aggregate_sha256: string;
  registry_sha256: string;
  merkle_root: string;
  cluster: string;
  program_id: string;
  run_account: string;
  project_count: number;
  credit_event_count: number;
  finding_count: number;
  credits_evidenced: number;
  totals: Record<string, { count: number; credits: number }>;
  queue_count: number;
  linkage: Record<string, number>;
};
