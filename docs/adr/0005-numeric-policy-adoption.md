# ADR 0005: numeric policy adoption

Status: proposed, frozen by the phase 1 exit gate. Panel finding answered: 7.

## Context

An epsilon chosen per repository makes cross-repository comparison meaningless, and a fixture could
end up accepted only because the corpus was more forgiving than the library.

## Decision

The numeric policy is defined once, by `P1.2` in `libviprs/pvec#1`, as `docs/NUMERIC_POLICY.md` in
`libviprs/pvec`. This repository pins a version of it (`policy/pvec-numeric-policy.<version>.json`,
adopted as "PVec numeric policy v1") and defines no epsilon of its own.

- The only place a numeric threshold may exist here is the vendored policy file, and a repository
  check fails on any tolerance-shaped literal outside it.
- The loader refuses to run without a policy or with one that has no version id.
- The adopted version id is stamped on every `comparison.json`, `*.verification.json` and the corpus
  manifest.
- Moving to a new revision is a version bump plus a report of how many accept and quarantine outcomes
  changed.
- Which comparisons run is this repository's decision. What counts as equal is the policy's.

## Consequences

If the policy moves, this repository follows by a visible version change. If this repository ever
needs a looser comparison than the policy gives, the answer is a change to the policy, not a local
exception.
