# Findings Index

The durable scientific record is now chunked by 30 finding blocks per file.
For fast recovery, use [findings_compact.md](./findings_compact.md) for the
thematic digest and [deadends_compact.md](./deadends_compact.md) for durable
failed, parked, closed, or blocked paths derived from the findings.

Current chunks:
- [findings-00001-00030.md](./findings-00001-00030.md)
- [findings-00031-00060.md](./findings-00031-00060.md)
- [findings-00061-00090.md](./findings-00061-00090.md)
- [findings-00091-00120.md](./findings-00091-00120.md)
- [findings-00121-00150.md](./findings-00121-00150.md)
- [findings-00151-00180.md](./findings-00151-00180.md)
- [findings-00181-00210.md](./findings-00181-00210.md)
- [findings-00211-00240.md](./findings-00211-00240.md)
- [findings-00241-00270.md](./findings-00241-00270.md)
- [findings-00271-00300.md](./findings-00271-00300.md)
- [findings-00301-00330.md](./findings-00301-00330.md)
- [findings-00331-00360.md](./findings-00331-00360.md)
- [findings-00361-00390.md](./findings-00361-00390.md)
- [findings-00391-00420.md](./findings-00391-00420.md) (F391-F398)

## Convention

- Findings are append-only.
- Add new findings to the current highest chunk file until it reaches 30 finding blocks.
- Then create the next chunk file using the next block range, padded to a 30-block filename range.
- Chunk ranges are positional block ranges in document order, not necessarily contiguous `F` labels.
- If the final chunk has fewer than 30 findings, still name it with the padded end range, e.g. `findings-00061-00090.md`.
- Update this index and any cross-references whenever a new chunk file is created.

## How To Read

Start here, then open the chunk file that contains the finding you need.
`findings-00391-00420.md` is now the active findings chunk.
