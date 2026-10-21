# Data source and attribution

Tally reads the Voluntary Registry Offsets Database published by the
Berkeley Carbon Trading Project at the Goldman School of Public Policy,
University of California, Berkeley.

The database covers all carbon offset projects, credit issuances and
credit retirements listed by six registries: American Carbon Registry
(ACR), Architecture for REDD+ Transactions (ART), Climate Action Reserve
(CAR), Gold Standard, Isometric (ISO) and Verra (VCS).

## Version in use

| Field | Value |
| --- | --- |
| Version | v2026-08 |
| File | `Voluntary-Registry-Offsets-Database--v2026-08.xlsx` |
| Size | 15.90 MB |
| SHA-256 | `cda76b917a574713d040ea27a5098cd77f14f33bc87aa9dfafaf87a3f329cd88` |
| Projects | 11,856 |
| Credits issued | 2,704,143,472.766 |

The checksum is recorded on-chain with every audit run, before the
analysis is performed. Anyone can download the same file, compare the
checksum, re-run this repository and reproduce the published result.

## Licence and citation

Released under Creative Commons Attribution 4.0 (CC BY 4.0).

> Pamela Quartson, Barbara K Haya, Tyler Bernard, Aline Abayo, Xinyun
> Rong, Ivy S So, Micah Elias. (2026). Voluntary Registry Offsets
> Database v2026-08, Berkeley Carbon Trading Project, University of
> California, Berkeley. Retrieved from:
> https://gspp.berkeley.edu/berkeley-carbon-trading-project/offsets-database

## What Tally does not claim

Tally reports what this dataset contains. It does not assert that any
project or registry acted in bad faith, and a flagged pair is a case
requiring explanation rather than a finding of wrongdoing. The Berkeley
Carbon Trading Project is the source of the data and is not connected to
this analysis.

## On-chain attestation

| Field | Value |
| --- | --- |
| Network | Solana devnet |
| Program | `2DNtSVqoQPgrZz17C6zTEKt3WUqgVJo1vxxkYLCBM29e` |
| Audit run account | `FBG6tQ5BVzK4jg3VEiHNSawZDvmdsLJG712tuWEDcuJH` |
| Dataset version | v2026-08 |
| Merkle root | `7f1c1fdf1c66d1526a83b9eae1d8794588aab4713cbc1fc20536611ac8745bd1` |
| Findings | 76 |
| Credits evidenced | 361,903 |

The run account is sealed: no finding can be added, changed or removed.
Reproduce it by downloading the two workbooks named above, confirming
their checksums, running `scripts/run_audit.py` and comparing the root.

The program's upgrade authority is still held by the publisher. That is
deliberate for a hackathon build, where a bug must remain fixable, and it
is a real limitation: whoever holds that authority can change the rules
the program enforces. Production deployment revokes it.
