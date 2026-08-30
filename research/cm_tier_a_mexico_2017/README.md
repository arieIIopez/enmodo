# CM Tier A.1 — Ciudad de México EOD 2017

## Status

Development/validation layer only. This is **not** the final Mobility Coefficient and is **not** historical network space-time accessibility. It implements the preregistered Tier A.1 external-opportunity test with DENUE 03/2017 and simplified geometric impedance.

## Provenance

Primary source: INEGI DENUE 03/2017. The research workflow downloads the reproducible `mxcensus` GeoParquet mirror and verifies the source files against preregistered SHA-256 hashes before deriving an analysis core.

Verified source hashes:

- CDMX (09): `c808122adbb8ba9360a6b175c2a8ad58d30daea594c055d889524b389a47d809`
- Hidalgo (13): `27b0937bddb6131d3c9bcc825489725bd73363366dc7868be40a3a58174aaf35`
- Estado de México (15): `ad3ae1e3fe4353c3f7dbd01afbc2bfc66a6a17f412fc40bd283454daa44318e7`

Derived analysis-core SHA-256:

`6efe48bf809764475eee2e06c1e8f6f61bca61ae525046131ac4027e75a0a157`

The analysis is restricted to the exact 76 entity–municipality pairs represented by the EOD weekday person universe: 16 CDMX alcaldías, 59 Estado de México municipalities, and Tizayuca (Hidalgo).

## Frozen opportunity ontology

- SCIAN 61 — education
- SCIAN 62 — health and social assistance
- SCIAN 71 — arts, entertainment, sports and recreation
- SCIAN 72 — accommodation/food, sensitivity only

Post-filter inventory:

- 61: 25,426 establishments
- 62: 38,087
- 71: 12,423
- 72: 99,980 (sensitivity)

## Tier A.1 impedance

District centroids from the official EOD district geography are used as person origins. DENUE establishment points are projected to EPSG:32614. The primary development specification uses an equivalent Euclidean speed of 20 km/h and budgets `tau={15,30,45,60,90}` minutes; 15 and 25 km/h are sensitivity specifications. These speeds are **not interpreted as historical network travel speeds**.

## Main 20 km/h standardized primal results

Population-weighted mean establishments reachable:

| Domain | 15 min | 30 min | 45 min | 60 min | 90 min |
|---|---:|---:|---:|---:|---:|
| Education 61 | 895 | 3,190 | 6,519 | 10,310 | 17,153 |
| Health 62 | 1,433 | 5,202 | 10,630 | 16,644 | 26,923 |
| Recreation 71 | 439 | 1,546 | 3,184 | 5,031 | 8,376 |
| Food 72 sensitivity | 3,809 | 13,612 | 27,870 | 43,540 | 70,516 |

Normalized to each domain's 90-minute value, the 30-minute shares are approximately 0.185–0.193 and the 60-minute shares 0.601–0.618. The similarity across domains suggests that this geometric layer is strongly shaped by common metropolitan spatial structure.

A descriptive normalized dual inversion gives roughly 52–53 minutes at 20 km/h to reach 50% of the corresponding 90-minute opportunity set. Under 15 vs 25 km/h this benchmark moves by roughly nine minutes, which is one reason Tier A.1 cannot be treated as a final accessibility measure.

## Construct checks

Among observed students, study-trip realization remains approximately 76–80% across quintiles of educational access; there is no stable monotonic gradient. For persons with fixed work/study obligations, social/recreation realization at tau=30 rises from about 3.21% in the lowest access quintile to 4.63% in the highest, but the middle quintiles are non-monotonic. Purpose-code mismatch is material: the EOD social/recreation purpose includes visits to friends/family homes, which DENUE sector 71 cannot represent.

## Interpretation

Tier A.1 succeeds as an **independent external supply layer** and removes the circularity of Tier B revealed destinations. It does not yet establish a canonical Mobility Coefficient. The next confirmatory step is Tier A.2: replace equivalent Euclidean budgets with historically defensible multimodal network travel-time impedance while keeping the opportunity ontology and temporal budgets fixed.
