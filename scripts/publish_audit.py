"""Publish the current audit run on chain.

Safe to re-run. The program records how many findings it has accepted,
so an interrupted publication continues where it stopped instead of
starting over or writing anything twice.
"""

import argparse
import hashlib
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tally.audit import MILLI, build  # noqa: E402
from tally.chain import CliConfig, Program  # noqa: E402

DB = ROOT / "data" / "tally.sqlite"
IDL = ROOT / "onchain" / "target" / "idl" / "onchain.json"
RAW = ROOT / "data" / "raw"
VERSION = "v2026-08"

AGGREGATE_PREFIX = "Voluntary-Registry-Offsets-Database"
REGISTRY_PREFIX = "VROD-registry-files"


def sha256_of(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def find(prefix: str) -> Path:
    matches = sorted(
        p for p in RAW.glob("*.xls*")
        if p.name.startswith(prefix) and not p.name.startswith("~$")
    )
    if not matches:
        raise FileNotFoundError(f"no {prefix}*.xlsx in {RAW}")
    return matches[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be published and stop")
    parser.add_argument("--delay", type=float, default=0.4,
                        help="seconds between transactions")
    args = parser.parse_args()

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    run = build(conn)
    project_count = conn.execute("SELECT COUNT(*) FROM project").fetchone()[0]
    conn.close()

    aggregate_sha = sha256_of(find(AGGREGATE_PREFIX))
    registry_sha = sha256_of(find(REGISTRY_PREFIX))
    version = VERSION.encode().ljust(16, b"\x00")

    print(f"dataset version : {VERSION}")
    print(f"aggregate sha256: {aggregate_sha.hex()}")
    print(f"registry sha256 : {registry_sha.hex()}")
    print(f"merkle root     : {run.root.hex()}")
    print(f"projects        : {project_count:,}")
    print(f"findings        : {len(run.findings)}")
    print(f"credits         : {run.credits:,.0f}")

    if args.dry_run:
        print("\n(dry run, nothing sent)")
        return 0

    cfg = CliConfig.load()
    program = Program(IDL, cfg)
    print(f"rpc             : {cfg.safe_url}")
    run_pda = program.run_pda(version)
    print(f"run account     : {run_pda}")

    state = program.fetch_run(run_pda)
    if state is None:
        sig = program.create_run(
            version, aggregate_sha, registry_sha, run.root,
            project_count, len(run.findings),
            sum(f.credits_milli for f in run.findings if f.is_finding),
        )
        print(f"\ncreated run     : {sig}")
        start = 0
    else:
        if state["merkle_root"] != run.root:
            print("\nREFUSING TO CONTINUE")
            print(f"  on chain : {state['merkle_root'].hex()}")
            print(f"  local    : {run.root.hex()}")
            print("  This dataset version is already attested with a "
                  "different result.")
            return 1
        if state["frozen"]:
            print("\nrun is already sealed; nothing to do")
            return 0
        start = state["findings_written"]
        print(f"\nresuming at finding {start}")

    for index in range(start, len(run.findings)):
        finding = run.findings[index]
        sig = program.add_finding(
            version, index, finding.rule, finding.severity,
            "|".join(finding.subjects), finding.country,
            finding.credits_milli, finding.leaf(),
        )
        print(f"  [{index + 1:>3}/{len(run.findings)}] {finding.rule} "
              f"{finding.credits_milli / MILLI:>10,.0f}  {sig[:16]}...")
        time.sleep(args.delay)

    sig = program.freeze_run(version)
    print(f"\nsealed          : {sig}")
    print(f"explorer        : https://explorer.solana.com/address/"
          f"{run_pda}?cluster=devnet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
