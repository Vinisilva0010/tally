/**
 * Merkle verification in the browser.
 *
 * This is a second, independent implementation of what the Python
 * pipeline does. That is the point: if the two disagree, verification
 * fails visibly rather than quietly agreeing with itself. The domain
 * prefixes and the field separator must match src/tally/merkle.py
 * exactly -- a leaf is SHA-256 of 0x00 followed by the payload, an
 * internal node is SHA-256 of 0x01 followed by both children, and the
 * canonical payload joins fields with the 0x1f unit separator.
 */

const LEAF_PREFIX = 0x00;
const NODE_PREFIX = 0x01;
const FIELD_SEPARATOR = 0x1f;

async function sha256(bytes: Uint8Array): Promise<Uint8Array> {
  const digest = await crypto.subtle.digest("SHA-256", bytes as BufferSource);
  return new Uint8Array(digest);
}

function concat(...parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

export function hexToBytes(hex: string): Uint8Array {
  const clean = hex.startsWith("0x") ? hex.slice(2) : hex;
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i++) {
    out[i] = parseInt(clean.substring(i * 2, i * 2 + 2), 16);
  }
  return out;
}

export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** Canonical payload, matching encode_leaf in the Python module. */
export function encodeLeaf(fields: (string | number)[]): Uint8Array {
  const encoder = new TextEncoder();
  const encoded = fields.map((f) =>
    encoder.encode(typeof f === "number" ? String(f) : f)
  );
  const parts: Uint8Array[] = [];
  encoded.forEach((part, i) => {
    if (i > 0) parts.push(new Uint8Array([FIELD_SEPARATOR]));
    parts.push(part);
  });
  return concat(...parts);
}

export async function leafHash(payload: Uint8Array): Promise<Uint8Array> {
  return sha256(concat(new Uint8Array([LEAF_PREFIX]), payload));
}

export async function nodeHash(
  left: Uint8Array,
  right: Uint8Array
): Promise<Uint8Array> {
  return sha256(concat(new Uint8Array([NODE_PREFIX]), left, right));
}

export type VerificationResult = {
  recomputedLeaf: string;
  leafMatches: boolean;
  computedRoot: string;
  rootMatches: boolean;
};

/**
 * Rebuild the leaf from the displayed fields, walk the proof, and compare
 * with the root held on chain.
 */
export async function verifyFinding(
  fields: (string | number)[],
  expectedLeafHex: string,
  proof: { sibling: string; sibling_is_left: boolean }[],
  onChainRootHex: string
): Promise<VerificationResult> {
  const leaf = await leafHash(encodeLeaf(fields));
  const recomputedLeaf = bytesToHex(leaf);

  let current = leaf;
  for (const step of proof) {
    const sibling = hexToBytes(step.sibling);
    current = step.sibling_is_left
      ? await nodeHash(sibling, current)
      : await nodeHash(current, sibling);
  }
  const computedRoot = bytesToHex(current);

  return {
    recomputedLeaf,
    leafMatches: recomputedLeaf === expectedLeafHex.toLowerCase(),
    computedRoot,
    rootMatches: computedRoot === onChainRootHex.toLowerCase(),
  };
}
