# Dead Ends Index

The durable failed, parked, closed, or blocked record is chunked by 30 dead-end
blocks per file. For fast recovery, use [deadends_compact.md](./deadends_compact.md).

Current chunks:
- [deadends-001-030.md](./deadends-001-030.md)

## Convention

- Dead ends are append-only.
- Add new dead ends to the current highest chunk file until it reaches 30
  dead-end blocks.
- Then create the next chunk file using the next block range, padded to a
  30-block filename range.
- Chunk ranges are positional block ranges in document order, not necessarily
  contiguous `D` labels.
- If the final chunk has fewer than 30 dead ends, still name it with the padded
  end range, e.g. `deadends-001-030.md`.
- Update this index and compact references whenever a new chunk file is created.

## How To Read

Start here, then open the chunk file that contains the dead end you need.
`deadends-001-030.md` is now the active dead-end chunk.
