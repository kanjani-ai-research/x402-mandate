# x402-mandate
> Purchasing mandate and its verification

Copyright 2026 Causum (https://causum.com). Licensed under the PolyForm Noncommercial License 1.0.0; see `LICENSE`.

## What it tests

Whether a principal's purchasing mandate can be

1. written in a fixed, decidable form,
2. applied to each proposed purchase with a result that names the rule that decided it,
3. re-derived by a party that holds only the purchase record and the mandate, and
4. checked at a cost that fits inside a payment.

## What is in this folder

| File | What it is |
|---|---|
| `MANDATE.md` | The mandate in the principal's words. Nine rules. |
| `build_spec.py`, `mandate-v0.1.json` | The same mandate as a specification: one applicability check, seven authority checks, one check for "outside". |
| `resolver.py` | The mandate as plain code, written from `MANDATE.md` without reading the specification. |
| `generate.py`, `purchases.jsonl` | 2,000 proposed purchases, seed 402. Five named sellers, sixty sellers the agent found. |
| `verifier/kernel.py` | The kernel, about 120 lines. |
| `run.py` | Applies the specification with the kernel, re-derives, edits, times, and compares with a P06-shaped mandate. |
| `rederive_standalone.py` | Re-derives every certificate using only this folder. It imports nothing from the kernel. |
| `results/summary.json` | The file of record for every number below. |
| `results/certificates.jsonl` | One certificate per purchase. |

## The kernel

`verifier/kernel.py` is the kernel: the predicate evaluator, the three families of checks, the derived outcome, the certificate and its re-derivation. It holds the parts of Causum's verification kernel that this run uses. `results/summary.json` records its SHA-256.

## Check it without the kernel

```
python3 rederive_standalone.py
```

It lowers each purchase record, evaluates the nine checks of `mandate-v0.1.json`, derives the outcome, and compares all of it and the hashes with the certificate. It prints: re-derived 2,000 of 2,000 certificates, and rejected 8,000 of 8,000 edited certificates over four kinds of edit.

## Reproduce the run

```
python3 build_spec.py
python3 generate.py
python3 run.py
```

It rewrites the specification, the purchases, the certificates
and the summary. The first three come out byte for byte the same; only the timings change.

## Result

**Outcomes over 2,000 purchases**

| Result | Count |
|---|---|
| within authority | 945 |
| outside authority, failed rules named | 564 |
| no rule stated, returned to the principal | 207 |
| fact missing, missing fact named | 284 |

- Agreement with the resolver written from the prose: 2,000 of 2,000.
- Re-derived from record and specification: 2,000 of 2,000 by the kernel, and 2,000 of 2,000 by the standalone script.
- Edited certificates rejected: 10,000 of 10,000, over five kinds of edit (outcome with the old hash, outcome re-sealed, a fact re-sealed, a check result re-sealed, another specification claimed).
- Forged fact: 144 records were replaced with a forged attestation and a certificate issued for the forgery. A verifier holding the original record rejected 144. A verifier holding only the forged record rejected 0.

**The same purchases under a P06-shaped mandate** (asset, cap, per-payment limit, expiry, recipients)

| Recipients | Accepted | Of those, within the principal's mandate | Not authorized by it | Refused although within it |
|---|---|---|---|---|
| the five named sellers | 656 | 641 | 15 | 304 |
| wildcard `*` | 1,870 | 945 | 925 | 0 |

The 925 are 461 outside authority, 198 with no rule stated and 266 with a fact missing. The 15 are purchases from named sellers whose declared category was absent.

**Cost**

| Measure | Value |
|---|---|
| decide (lowering and certificate) | 0.0316 ms median, 0.0402 ms maximum |
| re-derive with the record | 0.0323 ms median, 0.0408 ms maximum |
| certificate | 1,011 bytes mean, 535 bytes gzip |

Python 3.13.3, one core of an Apple M2, per-item best of five passes. No model is called anywhere.

## Copyright and licence

Copyright 2026 Causum (https://causum.com)

Everything in this repository, including the kernel in `verifier/`, is the copyright of Causum and is licensed under the PolyForm Noncommercial License 1.0.0. See `LICENSE` and `NOTICE`. Commercial use requires a licence from Causum.
