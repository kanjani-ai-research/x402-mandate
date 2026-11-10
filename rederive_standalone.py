# Copyright 2026 Causum (https://causum.com)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Re-derive every certificate without the kernel.

Usage: python3 rederive_standalone.py
Needs only this folder: mandate-v0.1.json, purchases.jsonl, results/certificates.jsonl.
It imports nothing from the kernel or from run.py. It is what a third party would write from the
published specification and certificate format: lower the record, evaluate the checks, derive the
outcome, compare with the certificate, and check the hashes.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
raw = (HERE / "mandate-v0.1.json").read_bytes()
SPEC = json.loads(raw)
SPEC_HASH = "sha256:" + hashlib.sha256(raw).hexdigest()
TH, NAMED = SPEC["thresholds"], set(SPEC["named_recipients"])


def digest(obj):
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def term(t, el):
    if isinstance(t, dict):
        return el[t["field"]] if "field" in t else TH[t["threshold"]]
    return t


def holds(p, rho, el=None):
    if "and" in p:
        return all(holds(q, rho, el) for q in p["and"])
    if "or" in p:
        return any(holds(q, rho, el) for q in p["or"])
    if "not" in p:
        return not holds(p["not"], rho, el)
    if "exists" in p:
        return any(holds(p["exists"]["body"], rho, e) for e in rho[p["exists"]["over"]])
    if "eq" in p:
        return term(p["eq"][0], el) == term(p["eq"][1], el)
    if "ge" in p:
        return term(p["ge"][0], el) >= term(p["ge"][1], el)
    if "in" in p:
        return term(p["in"][0], el) in p["in"][1]
    raise ValueError(p)


def lower(record):
    p = record["payment"]
    seller, missing = {"named": p["payTo"] in NAMED}, []
    category = record.get("offer", {}).get("category")
    if category is None:
        missing.append("seller.category")
    else:
        seller["category"] = category
    facts = {a["claim"]: a for a in record.get("attestations", []) if a["about"] == p["payTo"]}
    if not seller["named"]:
        if "entity-verified" not in facts:
            missing.append("seller.verified")
        else:
            seller["verified"] = facts["entity-verified"]["value"]
            if seller["verified"] is True:
                if "assurance" in facts["entity-verified"]:
                    seller["assurance"] = facts["entity-verified"]["assurance"]
                else:
                    missing.append("seller.assurance")
                if "jurisdiction" in facts:
                    seller["jurisdiction"] = facts["jurisdiction"]["value"]
                else:
                    missing.append("seller.jurisdiction")
    pay = {"network": p["network"], "asset": p["asset"], "amount": p["amount"],
           "after": record["state"]["spent_before"] + p["amount"], "now": record["time"]}
    return {"pay": [pay], "seller": [seller]}, sorted(missing)


def family(name, rho):
    checks = [{"id": c["id"], "holds": bool(holds(c["pred"], rho))} for c in SPEC["families"][name]]
    fals = [c["id"] for c in checks if not c["holds"]]
    return {"verdict": "NONCONFORMING" if fals else "CONFORMING", "checks": checks, "falsifiers": fals}


def outcome(gap, plus, minus):
    if gap == "NONCONFORMING":
        return "authority-gap"
    return {("CONFORMING", "NONCONFORMING"): "valid", ("NONCONFORMING", "CONFORMING"): "invalid",
            ("NONCONFORMING", "NONCONFORMING"): "indeterminate-by-spec",
            ("CONFORMING", "CONFORMING"): "conflict-spec-gap"}[(plus, minus)]


def check(record, cert):
    body = {k: v for k, v in cert.items() if k != "witness_hash"}
    if cert.get("witness_hash") != digest(body):
        return "certificate hash"
    if cert["spec_hash"] != SPEC_HASH:
        return "specification hash"
    if cert["input_sha256"] != digest(record):
        return "record hash"
    rho, missing = lower(record)
    if rho != cert["lifted"] or missing != cert["lift_missing"]:
        return "lowered record"
    if missing:
        return None if cert["outcome"] == "REFER" else "outcome"
    fams = {n: family(n, rho) for n in ("phi_gap", "phi_plus", "phi_minus")}
    for n, f in fams.items():
        if f != cert[n]:
            return n
    want = outcome(*(fams[n]["verdict"] for n in ("phi_gap", "phi_plus", "phi_minus")))
    return None if want == cert["outcome"] else "outcome"


if __name__ == "__main__":
    records = [json.loads(x) for x in (HERE / "purchases.jsonl").read_text().splitlines()]
    certs = [json.loads(x) for x in (HERE / "results" / "certificates.jsonl").read_text().splitlines()]
    bad = [(c["item_id"], why) for r, c in zip(records, certs) for why in [check(r, c)] if why]
    print(f"re-derived {len(certs) - len(bad)} of {len(certs)} certificates; specification {SPEC_HASH}")
    for item, why in bad[:10]:
        print("  differs:", item, why)

    # the same five edits as run.py, to show this script also rejects them
    rejected = total = 0
    for r, c in zip(records, certs):
        flip = "valid" if c["outcome"] != "valid" else "invalid"
        e1 = dict(c, outcome=flip)
        e2 = dict(c, outcome=flip); e2["witness_hash"] = digest({k: v for k, v in e2.items() if k != "witness_hash"})
        e3 = json.loads(json.dumps(c)); e3["lifted"]["pay"][0]["amount"] //= 2
        e3["witness_hash"] = digest({k: v for k, v in e3.items() if k != "witness_hash"})
        e5 = dict(c, spec_hash="sha256:" + "0" * 64)
        e5["witness_hash"] = digest({k: v for k, v in e5.items() if k != "witness_hash"})
        for e in (e1, e2, e3, e5):
            total += 1
            rejected += check(r, e) is not None
    print(f"rejected {rejected} of {total} edited certificates (four kinds)")
