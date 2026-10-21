/**
 * Reading the attestation straight from Solana.
 *
 * The page could simply display the root from its own JSON, but then it
 * would be checking itself. Fetching the account over RPC means the root
 * the browser compares against came from the chain, not from the file the
 * same site served.
 *
 * The public endpoint is used deliberately: a single account read is well
 * within its limits, and embedding a private endpoint key in client code
 * would publish that key to every visitor.
 */

const RPC_URL = "https://api.devnet.solana.com";

const VERSION_LEN = 16;
const DISCRIMINATOR = 8;
const ROOT_OFFSET = DISCRIMINATOR + VERSION_LEN + 32 + 32;
const COUNT_OFFSET = ROOT_OFFSET + 32;

export type OnChainRun = {
  merkleRoot: string;
  projectCount: number;
  findingCount: number;
  findingsWritten: number;
  frozen: boolean;
};

export async function fetchRun(account: string): Promise<OnChainRun> {
  const response = await fetch(RPC_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 1,
      method: "getAccountInfo",
      params: [account, { encoding: "base64", commitment: "confirmed" }],
    }),
  });

  const json = await response.json();
  const value = json?.result?.value;
  if (!value) throw new Error("attestation account not found on devnet");

  const raw = atob(value.data[0]);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

  const view = new DataView(bytes.buffer);
  const merkleRoot = Array.from(bytes.slice(ROOT_OFFSET, ROOT_OFFSET + 32))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  const projectCount = view.getUint32(COUNT_OFFSET, true);
  const findingCount = view.getUint32(COUNT_OFFSET + 4, true);
  const findingsWritten = view.getUint32(COUNT_OFFSET + 8, true);
  const frozen = bytes[COUNT_OFFSET + 12 + 8 + 8 + 32] === 1;

  return { merkleRoot, projectCount, findingCount, findingsWritten, frozen };
}
