# ADR 0006: quarantine policy

Status: frozen at the phase 1 exit gate (open route, 2026-10-28). Panel findings answered: 1 (a disagreement stays visible
instead of being averaged away) and 8 (provenance and licence problems are first-class).

## Context

Some fixtures can't be trusted as they stand. If they sit in the corpus with a quiet note, they get
used anyway.

## Decision

A fixture is `QUARANTINED` (ADR 0001) when any of these holds, and the record names which one:

- `UNRESOLVED_DISAGREEMENT`: the converters disagree materially and nobody has explained why.
- `UNSUPPORTED_ENTITY`: a construct a converter, or the profile, doesn't carry.
- `APPROXIMATION`: the best available representation is a bounded approximation.
- `MALFORMED_FIXTURE`: the source fails to parse or fails its own record.
- `LICENCE_OR_PROVENANCE`: a licensing or provenance problem.

A quarantine reason is never "unknown". If the reason can't be named yet, the fixture is not admitted
to the corpus at all. Only the repository owner clears a quarantine, through a pull request that
states the evidence for clearing it, and the previous reason stays in the fixture's history.

## Consequences

The corpus can be read as "everything here is either accepted for a stated reason or quarantined for a
stated reason".
