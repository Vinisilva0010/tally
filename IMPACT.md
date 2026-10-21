# Climate impact, adoption and scalability

## 1. The failure this addresses

A 2025 systematic review in the Annual Review of Environment and
Resources examined 972 million tonnes of issued carbon credits and
concluded that roughly 812 million of them are unlikely to represent
genuine emission reductions. The review names the most severe failure
modes in the market: non-additionality, impermanence, leakage,
**double counting**, perverse incentives, and the gameability of
crediting systems.

Tally addresses one of those six: double counting.

That choice is deliberate and it is the basis of the impact claim below.
Of the six failures, five require measurement that no desk study can
perform. Deciding whether a forest would have been cut down anyway, or
whether its carbon will still be there in forty years, requires field
data, counterfactual modelling and time.

Double counting is different. It is an arithmetic property of records
that are already public. If two registries credited the same project for
the same year of reduction, that is visible in data anyone can download
today — and nobody was checking, because the six registries publish in
six formats and none of them reconciles against the others.

## 2. What was measured

Over the complete public record of six registries — Verra, Gold
Standard, American Carbon Registry, Climate Action Reserve, ART and
Isometric — covering 11,856 projects and 541,290 credit-level events:

| Finding | Credits |
| --- | --- |
| Same vintage credited by two registries (13 projects) | 351,903 |
| Same credit serial retired more than once (1 project) | 10,000 |
| **Total evidenced** | **361,903** |

361,903 tonnes of CO2 equivalent were claimed more than once.

13,252 of those were retired on both sides: two different buyers offset
their own emissions against the same tonne. 1,091,256 credits across the
wider candidate set sit in the state where one copy has been claimed and
the identical copy remains available for sale.

### This is a floor, not a total

Three limits are stated plainly, because an inflated figure is worse
than a small one:

1. Linkage works from project names and surrounding fields. Where two
   registries describe the same project very differently, Tally misses
   it. Eight further candidate pairs, worth 2.4 million credits, are
   awaiting human review and are deliberately excluded from the result.
2. 2,955 projects belong to umbrella programmes whose consolidated
   totals appear nowhere in the public data.
3. The analysis covers the voluntary registries. Double counting between
   a registry and a national inventory under the Paris Agreement is a
   larger problem that this data cannot settle — see section 4.

## 3. Why the number is small, and why that matters

361,903 tonnes is a small fraction of the 5.2 gigatonnes issued since
carbon offsetting began in 1989. Tally does not claim to have found the
market's main integrity problem.

It claims something narrower and more useful: that a specific, named
failure mode was entirely unmonitored, that it is detectable from public
data at zero marginal cost, and that the detection is now reproducible
and published in a form nobody can silently revise.

The comparison that matters is not against the size of the market. It is
against the alternative, which was nothing. No public tool reconciled
these six registries before.

There is also an asymmetry worth stating. A tonne counted twice is worse
than a tonne never credited: it does not merely fail to help, it
actively authorises an emission elsewhere that would otherwise have been
avoided or paid for. Each of the 13,252 double-retired credits
represents an emission that a buyer believes is offset and is not.

## 4. The larger exposure this data reveals

The findings above are what Tally can prove. The data also shows
something it can only report, and the distinction is kept strict.

Across the Climate Action Reserve, 7,167,767 credits from Mexican
projects were retired by buyers that are overwhelmingly foreign — Cool
Effect, Shell Energy Canada, Schneider Electric France, Carbonplace UK,
FORLIANCE and goodcarbon in Germany, Climeworks in Switzerland. Every
one of those retirements records the corresponding adjustment field as
"No".

On Verra, the largest claimants of credits from projects abroad include
Shell with 11.9 million tonnes from Indonesia, 9.6 million from Peru and
5.8 million from the Democratic Republic of the Congo, and Eni with 11.1
million from Zambia and 8.4 million from the DRC. Verra publishes no
corresponding-adjustment field at all.

Corresponding adjustment under Article 6 of the Paris Agreement is the
accounting entry that stops a host country counting a reduction toward
its own national target while a foreign company counts the same
reduction toward its own. Where it is absent, the same tonne can be
claimed by a country and by a company at once.

**Tally does not assert that these tonnes were double claimed.** For
most voluntary retirements no adjustment is required under current
interpretation. What the data shows is that the public record does not
contain the information needed to rule the question out, for transfers
measuring in the tens of millions of tonnes.

That gap is itself a finding, and it is directly within the scope of
COP 31. A disclosure requirement costing registries nothing — publish
the field Verra currently omits, as the ACR and the Gold Standard
already do — would make the question answerable.

The six Gold Standard retirements that *do* carry Article 6
authorisation, by Singapore Airlines, Scoot and ASG against projects in
Laos, Uzbekistan and Cambodia, demonstrate the point: when the safeguard
exists, it is visible in the data. Tally verifies those as correct.

## 5. Adoption

Tally is a verification layer, not a marketplace, and it needs no
counterparty to be useful. It reads records the registries already
publish and produces results any party can check independently. Four
groups can use it today.

**Credit buyers and their auditors.** A corporate buyer retiring credits
can check, before purchase, whether the project appears in a second
registry with overlapping vintages. The finding pages link directly to
both registry records so the check ends at the source rather than at
Tally's claim.

**Registries.** The findings name specific project pairs across registry
boundaries, which is precisely the reconciliation no single registry can
perform. Six export duplicates were also found within registry files —
a data quality signal registries can act on immediately.

**Researchers and standards bodies.** The pipeline is public, the
dataset is public and CC BY licensed, and every published figure is
covered by an automated test. The method can be challenged line by line
rather than argued about.

**Policymakers preparing Article 6 implementation.** Section 4 quantifies
exactly which disclosure is missing and what volume of cross-border
transfers it affects.

### Barriers, stated honestly

Tally has no authority. It cannot compel a registry to respond, and a
flagged project has no obligation to explain itself. Its influence
depends on buyers and auditors finding the check worth running. That is
a real limit on near-term impact and no architecture fixes it.

## 6. Scalability

The design is deliberately cheap to run, because a verification tool
that costs money to operate will stop being operated.

| Measure | Value |
| --- | --- |
| Full pipeline over 11,856 projects and 541,290 events | Under 9 seconds on a laptop, after ingestion |
| Initial ingestion of both workbooks | About 2 minutes, cached thereafter by checksum |
| Cross-registry comparisons per run | 977,904 |
| Infrastructure cost | Zero: local compute, static hosting, no paid API |
| On-chain cost per audit run | 78 transactions: one to open, 76 findings, one to seal |

No large language model is used anywhere. Record linkage is classical —
TF-IDF over character n-grams, token-set comparison, and vocabulary
derived from the corpus itself — which runs on CPU, costs nothing per
run, and is reproducible by a third party. A model behind an API would
make the result unverifiable, which would defeat the purpose.

### Roadmap

**Near term.** The Berkeley database updates roughly quarterly. Each
version becomes a new sealed attestation keyed by version, so results
accumulate as a history rather than overwriting each other. The eight
queued candidates get human review and either become findings in the
next run or are recorded as cleared.

**Scaling the analysis.** Country blocking keeps comparison cost
quadratic only within a country rather than across the whole corpus. The
largest block is India with 974 issuing projects, so the method has
substantial headroom before cost becomes a constraint. Adding registries
means adding one sheet specification each; the serial parser already
handles four distinct formats.

**Strengthening linkage.** The current confirmed count is bounded by
name similarity. Geographic coordinates, where registries publish them,
would raise the ceiling. The Isometric registry already publishes
coordinates; others do not consistently.

**Production hardening.** The program's upgrade authority is currently
held by the publisher so bugs stay fixable during the hackathon.
Production deployment revokes it, after which the attestation rules
cannot be changed by anyone, including the publisher. This is recorded
as an open limitation in SECURITY.md rather than presented as resolved.

## 7. Sources

- Romm, J. et al. (2025). Annual Review of Environment and Resources.
  Systematic review of 972 Mt of issued credits; 812 Mt unlikely to
  represent genuine reductions. Names double counting among the most
  severe failure modes.
- University of Oxford, Smith School of Enterprise and the Environment
  (6 October 2025), summary of the above.
- Nature Communications (2024): fewer than one in six credits studied
  represented actual emission reductions.
- Berkeley Carbon Trading Project, Voluntary Registry Offsets Database
  v2026-08. CC BY 4.0. Full citation in DATA_SOURCE.md.
- All figures attributed to Tally in this document are reproducible from
  the repository and are covered by the test suite.

Market valuation figures were deliberately omitted. Published 2026
estimates for the voluntary carbon market range from roughly USD 1.7
billion to USD 23.8 billion depending on methodology, a spread wide
enough that any single figure would be misleading.
