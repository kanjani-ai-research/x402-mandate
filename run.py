# Copyright 2026 Causum (https://causum.com)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Run the mandate over the purchases with the Causum verification kernel, unmodified.

Usage: python3 run.py
Writes results/certificates.jsonl and results/summary.json.
"""
import gzip
import hashlib
import json
import platform
import statistics
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
from resolver import resolve
from verifier import kernel

raw = (HERE / "mandate-v0.1.json").read_bytes()
SIGMA = json.loads(raw)
SIGMA["_hash"] = "sha256:" + hashlib.sha256(raw).hexdigest()
NAMED = set(SIGMA["named_recipients"])
MEANING = SIGMA["outcome_map"]


def lift(record, sigma=SIGMA):
    """Deterministic lowering of a purchase record. No model. Returns (rho, missing)."""
    p = record["payment"]
    named = p["payTo"] in NAMED
    seller, missing = {"named": named}, []
    category = record.get("offer", {}).get("category")
    if category is None:
        missing.append("seller.category")
    else:
        seller["category"] = category
    facts = {a["claim"]: a for a in record.get("attestations", []) if a["about"] == p["payTo"]}
    if not named:
        entity = facts.get("entity-verified")
        if entity is None:
            missing.append("seller.verified")
        else:
            seller["verified"] = entity["value"]
            if entity["value"] is True:
                if "assurance" in entity:
                    seller["assurance"] = entity["assurance"]
                else:
                    missing.append("seller.assurance")
                if "jurisdiction" in facts:
                    seller["jurisdiction"] = facts["jurisdiction"]["value"]
                else:
                    missing.append("seller.jurisdiction")
    rho = {"pay": [{"network": p["network"], "asset": p["asset"], "amount": p["amount"],
                    "after": record["state"]["spent_before"] + p["amount"], "now": record["time"]}],
           "seller": [seller]}
    return rho, missing


def decide(record):
    rho, missing = lift(record)
    return kernel.verify(record, rho, missing, SIGMA)


def p06(record, recipients):
    """The seven checks of the `authority` extension (x402 PR #3220, section 6), value checks only.
    A P06-shaped mandate: asset, cap, perPayment, recipients, notAfter. Written for this comparison;
    it is not that proposal's reference implementation."""
    p, th = record["payment"], SIGMA["thresholds"]
    return (p["network"] == "eip155:8453" and p["asset"] == "USDC"
            and (recipients == ["*"] or p["payTo"] in recipients)
            and p["amount"] <= th["per_payment"]
            and record["state"]["spent_before"] + p["amount"] <= th["cap"]
            and record["time"] <= th["not_after"])


def reseal(w):
    body = {k: v for k, v in w.items() if k != "witness_hash"}
    return {**body, "witness_hash": kernel.sha(body)}


def edits(w):
    """Five edits of a certificate."""
    c = lambda: json.loads(json.dumps(w))
    flip = "valid" if w["outcome"] != "valid" else "invalid"
    a = c(); a["outcome"] = flip                                  # outcome edited, old hash kept
    b = c(); b["outcome"] = flip; b = reseal(b)                   # outcome edited, re-sealed
    d = c(); d["lifted"]["pay"][0]["amount"] //= 2; d = reseal(d)  # a lowered fact edited
    e = c()
    if e["phi_plus"]["checks"]:
        e["phi_plus"]["checks"][0]["holds"] = not e["phi_plus"]["checks"][0]["holds"]
    else:
        e["lift_missing"] = []
    e = reseal(e)                                                 # a check result edited
    f = c(); f["spec_hash"] = "sha256:" + "0" * 64; f = reseal(f)  # another specification claimed
    return {"outcome-stale-hash": a, "outcome-resealed": b, "fact-resealed": d,
            "check-resealed": e, "spec-hash-resealed": f}


records = [json.loads(line) for line in (HERE / "purchases.jsonl").read_text().splitlines()]
certs = [decide(r) for r in records]

# outcomes, and agreement with the resolver written from the prose
outcomes = Counter(MEANING.get(c["outcome"], c["outcome"]) for c in certs)
agree = sum(MEANING.get(c["outcome"], c["outcome"]) == resolve(r)[0] for r, c in zip(records, certs))
deciding = Counter()
for c in certs:
    if c["outcome"] == "invalid":
        for f in c["phi_plus"]["falsifiers"]:
            deciding[f] += 1
missing = Counter(m for c in certs for m in c["lift_missing"])

# re-derivation by a party holding the record and the specification
rederived = sum(kernel.rederive(c, SIGMA, r, lift)[0] for r, c in zip(records, certs))

# edited certificates
tamper = {}
for r, c in zip(records, certs):
    for kind, w in edits(c).items():
        ok, _ = kernel.rederive(w, SIGMA, r, lift)
        t = tamper.setdefault(kind, {"edited": 0, "rejected": 0})
        t["edited"] += 1
        t["rejected"] += (not ok)

# a forged fact: the record itself is replaced and a certificate issued for the forgery
forged = {"forged": 0, "rejected_with_original_record": 0, "rejected_with_forged_record": 0}
for r, c in zip(records, certs):
    if c["outcome"] != "invalid" or not r["attestations"] or r["attestations"][0]["value"] is not False:
        continue
    fr = json.loads(json.dumps(r))
    fr["attestations"] = [{"about": fr["payment"]["payTo"], "claim": "entity-verified", "value": True,
                           "assurance": 3, "issuer": "issuer-A"},
                          {"about": fr["payment"]["payTo"], "claim": "jurisdiction", "value": "US",
                           "issuer": "issuer-A"}]
    fc = decide(fr)
    forged["forged"] += 1
    forged["rejected_with_original_record"] += (not kernel.rederive(fc, SIGMA, r, lift)[0])
    forged["rejected_with_forged_record"] += (not kernel.rederive(fc, SIGMA, fr, lift)[0])

# the same purchases under a P06-shaped mandate
intent = [resolve(r)[0] for r in records]
compare = {}
for name, recipients in (("named-list", sorted(NAMED)), ("wildcard", ["*"])):
    acc = [p06(r, recipients) for r in records]
    compare[name] = {
        "accepted": sum(acc),
        "accepted_by_intent": dict(Counter(i for i, a in zip(intent, acc) if a)),
        "refused_by_intent": dict(Counter(i for i, a in zip(intent, acc) if not a)),
    }


def clock(fn, passes=5):
    best = [float("inf")] * len(records)
    for _ in range(passes):
        for i, r in enumerate(records):
            t0 = time.perf_counter_ns()
            fn(i, r)
            best[i] = min(best[i], time.perf_counter_ns() - t0)
    ms = [b / 1e6 for b in best]
    return {"median_ms": round(statistics.median(ms), 4), "max_ms": round(max(ms), 4), "passes": passes}


timing = {"decide_lift_and_certify": clock(lambda i, r: decide(r)),
          "rederive_with_record": clock(lambda i, r: kernel.rederive(certs[i], SIGMA, r, lift))}

sizes = [len(kernel.canonical(c)) for c in certs]
zipped = [len(gzip.compress(kernel.canonical(c))) for c in certs]

kernel_hash = "sha256:" + hashlib.sha256((HERE / "verifier" / "kernel.py").read_bytes()).hexdigest()

summary = {
    "experiment": "mandate-x402",
    "kernel": {"file": "verifier/kernel.py", "hash": kernel_hash},
    "spec": {"id": SIGMA["spec_id"], "version": SIGMA["spec_version"], "hash": SIGMA["_hash"],
             "checks": {k: len(v) for k, v in SIGMA["families"].items()}},
    "purchases": len(records), "seed": 402,
    "outcomes": dict(outcomes),
    "agreement_with_prose_resolver": {"agree": agree, "of": len(records)},
    "outside_authority_failed_checks": dict(deciding),
    "fact_missing_named": dict(missing),
    "rederived": {"ok": rederived, "of": len(certs)},
    "edited_certificates": tamper,
    "forged_fact": forged,
    "p06_shaped_mandate": compare,
    "timing": {**timing, "python": platform.python_version(), "machine": platform.processor() or platform.machine(),
               "note": "one core, per-item best of five passes; decide includes the lowering"},
    "certificate_bytes": {"mean": round(statistics.mean(sizes)), "mean_gzip": round(statistics.mean(zipped))},
}
(HERE / "results").mkdir(exist_ok=True)
(HERE / "results" / "certificates.jsonl").write_text("".join(json.dumps(c, sort_keys=True) + "\n" for c in certs))
(HERE / "results" / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
print(json.dumps(summary, indent=1))
