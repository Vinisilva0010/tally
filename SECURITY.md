# Security and data integrity assessment

Tally makes claims about other organisations' records. The assessment
below covers what those claims rest on, how a reader can check them
without trusting us, and where the design is weak.

## What the system asserts, and what it does not

Tally asserts: *this analysis, run over these two files with these
checksums, produced this result, and here is the proof.*

Tally does not assert that any registry or project developer acted in
bad faith. A flagged pair is a case that requires explanation. Several
flagged cases will have legitimate explanations that the public data does
not contain, and the interface says so on every page.

## Trust model

The parties whose records are audited are the registries themselves. Any
design that stores audit results in a database a single operator controls
asks readers to trust exactly the kind of party the tool exists to check.

So the result is committed to an append-only Solana account:

- Both input checksums are written **before** the result, so the
  commitment covers the inputs as well as the output.
- Findings are written in a fixed order and the account refuses an index
  out of sequence or beyond the declared count.
- The run is sealed only when every declared finding is present, and once
  sealed nothing can be added, changed or removed.
- The Merkle root commits to one exact rendering of one exact result;
  reordering or reformatting any field changes it.

Verification runs in the reader's browser against the chain, not against
this project's own copy of the result.

## Threats and mitigations

| Vector | Risk | Mitigation |
| --- | --- | --- |
| Source file substituted or altered | Analysis of data nobody else can reproduce | SHA-256 of both workbooks recorded on chain before analysis; a reader downloads the same files and compares |
| Operator publishes a false result | Fabricated findings | Code and Merkle root public; any third party reruns and compares. A false result is detectable, not merely improbable |
| Operator silently revises a published result | History rewritten | The run account is seeded by dataset version and sealed; a second result for the same version cannot overwrite the first |
| Authority key compromised | Attacker publishes attestations | Sealed runs cannot be modified. New false attestations remain refutable by rerunning the public pipeline |
| Program upgrade authority | Whoever holds it can change the rules the program enforces | **Not mitigated.** Held by the publisher for this build so bugs stay fixable. Production deployment revokes it. Declared rather than hidden |
| False positive harms a legitimate project | Reputational damage from an automated claim | Severity levels; wording of "requires explanation"; 56 cleared projects published alongside the findings; unreviewed candidates held in a separate queue and excluded from the attestation |
| Export artefacts read as fraud | Overstated findings | Six duplicate rows worth 222,579 credits are classified as data quality notes, not double counting, and reported separately |
| Rounding drift | Two parties compute different totals | Credits stored as integer thousandths. The Isometric registry reports to three decimals, and floating point summation gives different grand totals depending on where rounding occurs |
| Row ordering from the database | Non-reproducible root | Finding order is explicit and never depends on amounts, which can tie |
| Endpoint key disclosure | Quota theft | The publishing script reads the RPC endpoint from the local Solana CLI configuration; the browser uses the public endpoint. No key is committed |
| Personal data exposure | Privacy harm | Sources are public registry records about legal entities. Account holder names are published by the registries themselves |

## Errors found in this project's own analysis

Three methodological errors were caught and corrected during
development. They are listed because an audit tool that hides its own
mistakes has no standing to report anyone else's.

1. **Buffer pool subtracted twice.** An initial accounting check reported
   1,036 inconsistent projects. The column documentation states that
   buffer credits have been excluded from both issued and remaining
   totals since database version 6. With the correct identity the maximum
   deviation across 11,856 projects is zero.

2. **Year blocks read as one range.** The PROJECTS sheet carries four
   adjacent blocks of year columns. Reading them as a single block
   compared issued credits against retired and remaining ones. The error
   was visible as an overlap reported as "2018-2018 (6 years)"; the fix
   locates each block by its header label, and the vintage block now
   reconciles with the issued total at every row.

3. **A finding that research disproved.** 4.5 million credits retired for
   compliance with no corresponding adjustment looked like a major
   finding. Corresponding adjustment applies to internationally
   transferred mitigation outcomes; California's programme is subnational
   with domestic projects and buyers, so the absence is expected. The
   figure was discarded before publication.

A fourth guard exists because measurement contradicted intuition: a
vintage-ratio consistency filter would have removed a confirmed finding
whose yearly ratios vary 34-fold, so the ratio is reported as context and
never used to reject.

## Verifying independently

1. Download the two workbooks from the Berkeley Carbon Trading Project.
2. Confirm their SHA-256 values match those in `DATA_SOURCE.md`.
3. Run `pytest` — 96 tests, including every figure published here.
4. Run `scripts/run_audit.py` and compare the Merkle root with the one in
   the sealed account.
5. On any finding page, press "Run the check": the browser recomputes the
   leaf and the proof and compares against the root read from Solana.

## Known limitations

- Linkage uses project names, developers, methodologies, locations and
  vintage profiles. Where two registries name the same project very
  differently, Tally will miss it. The confirmed count is a floor.
- 2,955 projects belong to umbrella programmes whose consolidated totals
  appear nowhere in the data. That opacity is a property of the market,
  not a finding.
- Verra publishes no corresponding-adjustment field, so for its records
  Tally can only report that the public data does not permit the question
  to be settled.
- The analysis covers one dataset version. Findings are a snapshot, not a
  live feed.
