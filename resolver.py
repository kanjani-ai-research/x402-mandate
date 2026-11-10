# Copyright 2026 Causum (https://causum.com)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""The mandate as plain code, written from MANDATE.md and not from the specification.

It does not import the kernel. It is the reference the kernel's outcomes are compared against,
and it is what the generator uses to keep the running total.
"""
USDC = 1_000_000
NAMED = {f"0xNAMED{i:02d}" for i in range(1, 6)}
PROHIBITED = {"gambling", "adult", "crypto-asset"}
PER_PAYMENT, CAP, OPEN_CEILING, NOT_AFTER = 50 * USDC, 8000 * USDC, 5 * USDC, 970_000


def attested(record, claim):
    for a in record.get("attestations", []):
        if a["about"] == record["payment"]["payTo"] and a["claim"] == claim:
            return a
    return None


def resolve(record):
    """Return (result, detail). detail lists failed rules or missing facts."""
    p = record["payment"]
    named = p["payTo"] in NAMED
    category = record.get("offer", {}).get("category")
    entity = attested(record, "entity-verified")
    where = attested(record, "jurisdiction")

    # rule 9
    missing = []
    if category is None:
        missing.append("category")
    if not named:
        if entity is None:
            missing.append("verified")
        elif entity["value"] is True:
            if "assurance" not in entity:
                missing.append("assurance")
            if where is None:
                missing.append("jurisdiction")
    if missing:
        return "fact missing", missing

    # rule 8
    if not named and category not in {"data", "compute"} | PROHIBITED:
        return "no rule stated", [category]

    failed = []
    if not (p["network"] == "eip155:8453" and p["asset"] == "USDC"):
        failed.append("rule 1")
    if p["amount"] > PER_PAYMENT:
        failed.append("rule 2")
    if record["state"]["spent_before"] + p["amount"] > CAP:
        failed.append("rule 3")
    if record["time"] > NOT_AFTER:
        failed.append("rule 4")
    if category in PROHIBITED:
        failed.append("rule 5")
    if not named:
        ok = (entity["value"] is True and entity["assurance"] >= 2
              and where["value"] in {"US", "EU", "UK"} and category in {"data", "compute"})
        if not ok:
            failed.append("rules 6 and 7 (seller)")
        if p["amount"] > OPEN_CEILING:
            failed.append("rule 7 (ceiling)")
    return ("outside authority", failed) if failed else ("within authority", [])
