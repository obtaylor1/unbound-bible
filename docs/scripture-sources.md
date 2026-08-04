# Scripture source registry

Scripture text is published only through the verified ingestion pipeline. Source archives and application databases are not committed to this repository.

## Ge'ez Bible (1980 EC) — Research Use

- Edition code: `GEEZ1980-RESEARCH`
- Reading and source language: Ge'ez
- Script: Ethiopic
- Relationship: exact Ethiopian source text
- Provenance: [EOTCOpenSource/80-weahadu](https://github.com/EOTCOpenSource/80-weahadu), with Ran HaCohen's Ethiopic Bible identified by the supplied bundle as a supplementary source
- Source archive SHA-256: `7b66e154d0ad5f6f22d166831d3bea966541913c58bad45d8b5ece6ac5553d5c`
- License and use limitation: `CC-BY-NC-ND-4.0` applies to the identified repository material; the Bible text is identified as copyright Ethiopian Bible Society. This edition is enabled for local research and prototyping only. Redistribution and commercial use require permission from the applicable rights holders.

### Reviewed coverage

Only Genesis is currently approved for publication:

- 50 chapters
- 1,533 verse positions
- 31 verses in Genesis 1
- no empty text, duplicate positions, invalid positions, or coverage gaps
- one reviewed repeated-text warning: Genesis 39:15 and 39:18 are identical in this source

The remaining archive books are not approved merely because they are present. Their empty rows, duplicate positions, invalid positions, canon mapping, edition identity, and rights must be reviewed independently before their work IDs are added to a manifest allowlist.

### Reproducible local import

The `weahadu_bundle` adapter reads a single checksummed ZIP without extracting or executing it. Its manifest must sit beside the frozen archive and must explicitly map each approved source book to one canonical work. The standard operator sequence is:

```text
python -m app.library.ingest.cli seed-canon --database-url <migrated-database-url>
python -m app.library.ingest.cli stage --manifest <reviewed-manifest> --database-url <migrated-database-url>
python -m app.library.ingest.cli validate --run-id <run-id> --database-url <migrated-database-url>
python -m app.library.ingest.cli publish --run-id <run-id> --confirm --database-url <migrated-database-url>
```

The reader displays the human edition name and the persisted provenance metadata. It does not relabel the edition as a synthetic `ETHIO81` translation; `ETHIO81` remains the canon selector.
