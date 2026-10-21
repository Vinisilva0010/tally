# Tally — Problem and solution summary

**IEEE ClimateChain Global Hackathon 2026**
Track 1: Carbon Markets & Emissions Transparency
Vinicius S. Pontual, individual submission

Live site: https://tally-henna-nine.vercel.app/
Repository: https://github.com/Vinisilva0010/tally
Attestation: Solana devnet, account FBG6tQ5BVzK4jg3VEiHNSawZDvmdsLJG712tuWEDcuJH

---

## The problem

A carbon credit represents one tonne of CO2 that was not emitted or was
removed from the atmosphere. The buyer uses it to offset their own
emissions. The entire market rests on one rule: each tonne is counted
once.

Six registries issue credits independently — Verra, Gold Standard,
American Carbon Registry, Climate Action Reserve, ART and Isometric.
Each keeps its own database, in its own format, with no link to the
others. None can see what the others issued.

Nothing therefore prevents one physical project from being registered
twice and earning credits in both registries for the same reduction. A
2025 systematic review in the Annual Review of Environment and Resources
names double counting among the most severe failure modes in carbon
markets. No public tool reconciles the six registries against each
other.

Double counting is also the one failure mode on that list that is
detectable from public data alone. Judging whether a forest would have
been cut anyway, or whether its carbon will persist, requires field
measurement. Determining whether two registries credited the same
project for the same year is arithmetic over records already published.

## The solution

Tally reads the complete public record of all six registries — 11,856
projects and 541,290 credit-level events — and identifies credits
claimed more than once.

**What it found:** 361,903 credits counted more than once. Thirteen
projects credited for the same vintage year by two registries; one
project whose own serial numbers were retired across three overlapping
events. Of those, 13,252 credits were retired on both sides: two
different buyers offset their emissions against the same tonne.

**What it clears:** 56 projects appear in two registries with no
overlapping vintage. Those are legitimate registry migrations and Tally
publishes them as cleared. A further six cases are the same transaction
exported twice by a registry — a data quality issue, not double
counting. Eight additional candidate pairs await human review and are
deliberately excluded from the attested result.

A tool that only ever accuses cannot be checked. Publishing what it
clears is what makes the findings credible.

**How detection works.** 977,904 cross-registry pairs are compared,
blocked by country. A field populated on both sides that disagrees
rejects the pair outright; an empty field never rejects, because absence
is not evidence. Identity markers are derived from the corpus rather
than hand-written: a token appearing in under 1% of projects identifies
one, and a token occurring in exactly one country is a place name — which
is what separates a Gujarat wind project from a Karnataka one when every
other word in both names is identical. A name match alone is never a
finding: two registries must have credited the same vintage year, the
year the reduction physically occurred.

## Why it uses a blockchain

The parties whose records are audited are the registries themselves.
Storing audit results in a database that a single operator controls
would ask readers to trust precisely the kind of party the tool exists
to check.

The result is committed to an append-only Solana account. The SHA-256 of
both source workbooks is written *before* the result, so the attestation
covers the inputs as well as the output. Findings must arrive in order,
the run seals only when complete, and once sealed nothing can be added,
changed or removed. The same dataset version cannot be attested twice.

On the website, pressing "Run the check" makes the reader's browser
fetch the account from Solana, rebuild the finding's fingerprint from
the fields displayed on the page, walk the Merkle proof to the root, and
compare. The browser verification is a second, independent
implementation of the hashing in TypeScript; if it disagreed with the
Python pipeline it would fail visibly rather than quietly agree with
itself.

## Technical implementation

| Layer | Technology |
| --- | --- |
| Pipeline | Python, pandas, scikit-learn, RapidFuzz, SQLite |
| Record linkage | TF-IDF over character n-grams, token-set comparison, corpus-derived vocabulary |
| Attestation | Rust, Anchor, Solana devnet |
| Interface | Next.js, static export, Web Crypto API |
| Tests | 96 Python tests, 8 on-chain tests |

No large language model is used. Record linkage is classical machine
learning, which runs on CPU at no marginal cost and, crucially, is
reproducible by a third party. A model behind an API would make the
result unverifiable, defeating the purpose of the attestation.

Credit amounts are stored as integer thousandths. The Isometric registry
reports removals to three decimal places, and summing those as floating
point yields different grand totals depending on where rounding occurs —
unacceptable for a tool that publishes a total and invites recomputation.

## Honesty about limits

Tally does not assert that any registry or developer acted in bad faith.
A flagged pair is a case requiring explanation; some will have
legitimate explanations the public record does not contain.

Thirteen findings is a floor, not a total. Where two registries describe
the same project very differently, Tally misses it.

Three methodological errors were found and corrected during development
and all are documented in SECURITY.md, including a finding worth 4.5
million credits that research disproved before publication. An audit
tool that conceals its own mistakes has no standing to report anyone
else's.

## Real-world impact

361,903 tonnes is a small fraction of the 5.2 gigatonnes issued since
1989. Tally does not claim to have found the market's largest integrity
problem. It claims that a specific named failure was entirely
unmonitored, is detectable at zero marginal cost, and is now
reproducible and published in a form nobody can silently revise. The
comparison is not against the size of the market; it is against the
alternative, which was nothing.

A tonne counted twice is worse than a tonne never credited: it actively
authorises an emission elsewhere that a buyer believes is offset.

The data also exposes a disclosure gap directly relevant to COP 31. Over
7.1 million credits from Mexican projects were retired through a US
registry by predominantly foreign buyers, every one recording the Article
6 corresponding adjustment as "No"; Verra publishes no such field at all,
while Shell and Eni alone retired over 46 million tonnes from projects in
Indonesia, Peru, the DRC and Zambia. Tally does not claim those tonnes
were double claimed — it reports that the public record does not permit
the question to be answered, for transfers measuring in the tens of
millions of tonnes. Requiring the field that the ACR and Gold Standard
already publish would cost registries nothing and make the question
answerable.

## Reproducing this

Download the two workbooks from the Berkeley Carbon Trading Project,
confirm their checksums against DATA_SOURCE.md, run the test suite, run
the audit, and compare the Merkle root with the sealed account. Every
figure in this document is covered by an automated test.
