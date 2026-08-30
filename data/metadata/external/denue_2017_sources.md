# DENUE 03/2017 — provenance for Tier A validation

This file documents the exact external sources used by the ENMODO mobility-conversion research program for the Mexico City 2017 Tier A opportunity layer.

## Primary source

INEGI — Directorio Estadístico Nacional de Unidades Económicas (DENUE), March 2017 release.

Official bulk-download pattern verified against INEGI's massive-download tree:

- CDMX (09): https://www.inegi.org.mx/contenidos/masiva/denue/2017_03/denue_09_0317_csv.zip
- Hidalgo (13): https://www.inegi.org.mx/contenidos/masiva/denue/2017_03/denue_13_0317_csv.zip
- Estado de México (15): https://www.inegi.org.mx/contenidos/masiva/denue/2017_03/denue_15_0317_csv.zip

## Reproducible technical mirror

The `mxcensus` project mirrors public INEGI DENUE releases as GeoParquet. INEGI remains the primary source; the mirror is used as a reproducible technical copy and documents its transformations.

Hugging Face bucket resolve URLs:

- CDMX (09): https://huggingface.co/buckets/gperaza/mxcensus/resolve/denue_201703_09.parquet
- Hidalgo (13): https://huggingface.co/buckets/gperaza/mxcensus/resolve/denue_201703_13.parquet
- Estado de México (15): https://huggingface.co/buckets/gperaza/mxcensus/resolve/denue_201703_15.parquet

S3-compatible object URLs:

- CDMX (09): https://s3.hf.co/gperaza/mxcensus/denue_201703_09.parquet
- Hidalgo (13): https://s3.hf.co/gperaza/mxcensus/denue_201703_13.parquet
- Estado de México (15): https://s3.hf.co/gperaza/mxcensus/denue_201703_15.parquet

## Expected SHA-256

From the committed `mxcensus` registry:

- `denue_201703_09.parquet`: `c808122adbb8ba9360a6b175c2a8ad58d30daea594c055d889524b389a47d809`
- `denue_201703_13.parquet`: `27b0937bddb6131d3c9bcc825489725bd73363366dc7868be40a3a58174aaf35`
- `denue_201703_15.parquet`: `ad3ae1e3fe4353c3f7dbd01afbc2bfc66a6a17f412fc40bd283454daa44318e7`

## Pre-specified analytical ontology

Primary domains based on SCIAN México 2013 sectors:

- `61`: Educational services.
- `62`: Health care and social assistance.
- `71`: Arts, entertainment and recreation.
- `72`: Accommodation and food services — sensitivity analysis only for expanded social/leisure opportunity definitions.

Employment access is analysed separately and may use establishment employment-size strata as a sensitivity weight. Service opportunity counts do not automatically use employment size as a proxy for service capacity.

## Reproducibility rule

Any local or archived copy used in the analysis must match the SHA-256 listed above before being accepted as Tier A input. If a hash does not match, the file is rejected or explicitly versioned as a different artifact.