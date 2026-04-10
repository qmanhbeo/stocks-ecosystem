# Findings Index

The durable scientific record is now chunked by 30 finding blocks per file.

Current chunks:
- [findings-001-030.md](./findings-001-030.md)
- [findings-031-060.md](./findings-031-060.md)
- [findings-061-090.md](./findings-061-090.md)
- [findings-091-120.md](./findings-091-120.md)
- [findings-121-150.md](./findings-121-150.md)
- [findings-151-180.md](./findings-151-180.md)
- [findings-181-210.md](./findings-181-210.md)
- [findings-211-240.md](./findings-211-240.md)
- [findings-241-270.md](./findings-241-270.md)

## Convention

- Findings are append-only.
- Add new findings to the current highest chunk file until it reaches 30 finding blocks.
- Then create the next chunk file using the next block range, padded to a 30-block filename range.
- Chunk ranges are positional block ranges in document order, not necessarily contiguous `F` labels.
- If the final chunk has fewer than 30 findings, still name it with the padded end range, e.g. `findings-061-090.md`.
- Update this index and any cross-references whenever a new chunk file is created.

## How To Read

Start here, then open the chunk file that contains the finding you need.
`findings-241-270.md` is now the active findings chunk.
