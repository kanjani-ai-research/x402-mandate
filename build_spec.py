# Copyright 2026 Causum (https://causum.com)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Write mandate-v0.1.json: MANDATE.md as a specification for the kernel in verifier/.

The predicate language is the kernel's own (verifier/kernel.py): and, or, not, exists, eq, ge, in,
with field and threshold terms. Nothing is added to it.
"""
import json
from pathlib import Path

USDC = 1_000_000  # minor units per USDC

F = lambda name: {"field": name}
T = lambda name: {"threshold": name}
pay = lambda body: {"exists": {"over": "pay", "body": body}}
seller = lambda body: {"exists": {"over": "seller", "body": body}}

NAMED = [f"0xNAMED{i:02d}" for i in range(1, 6)]
PROHIBITED = ["gambling", "adult", "crypto-asset"]
OPEN_CATEGORIES = ["data", "compute"]
PERMITTED_JURISDICTIONS = ["US", "EU", "UK"]

a1 = pay({"and": [{"eq": [F("network"), "eip155:8453"]}, {"eq": [F("asset"), "USDC"]}]})
a2 = pay({"ge": [T("per_payment"), F("amount")]})
a3 = pay({"ge": [T("cap"), F("after")]})
a4 = pay({"ge": [T("not_after"), F("now")]})
a5 = seller({"not": {"in": [F("category"), PROHIBITED]}})
a6 = seller({"or": [
    {"eq": [F("named"), True]},
    {"and": [{"eq": [F("verified"), True]},
             {"ge": [F("assurance"), T("min_assurance")]},
             {"in": [F("jurisdiction"), PERMITTED_JURISDICTIONS]},
             {"in": [F("category"), OPEN_CATEGORIES]}]}]})
a7 = {"or": [seller({"eq": [F("named"), True]}), pay({"ge": [T("open_ceiling"), F("amount")]})]}

plus = [("A1-asset", "rule 1", a1), ("A2-per-payment", "rule 2", a2), ("A3-total", "rule 3", a3),
        ("A4-expiry", "rule 4", a4), ("A5-not-prohibited", "rule 5", a5),
        ("A6-seller", "rules 6 and 7, who the seller is", a6),
        ("A7-open-ceiling", "rule 7, the 5 USDC ceiling", a7)]

spec = {
    "spec_id": "x402-mandate-example",
    "spec_version": "0.1.0",
    "instantiates": "MANDATE.md",
    "thresholds": {"per_payment": 50 * USDC, "cap": 8000 * USDC, "open_ceiling": 5 * USDC,
                   "min_assurance": 2, "not_after": 970_000},
    "named_recipients": NAMED,
    "known_categories": OPEN_CATEGORIES + PROHIBITED,
    "req": {"pay": ["network", "asset", "amount", "after", "now"],
            "seller": ["named", "category"],
            "seller_if_not_named": ["verified"],
            "seller_if_verified": ["assurance", "jurisdiction"]},
    "families": {
        "phi_gap": [{"id": "G1-mandate-speaks", "comment": "rule 8",
                     "pred": seller({"or": [{"eq": [F("named"), True]},
                                            {"in": [F("category"), OPEN_CATEGORIES + PROHIBITED]}]})}],
        "phi_plus": [{"id": i, "comment": c, "pred": p} for i, c, p in plus],
        "phi_minus": [{"id": "M1-outside", "comment": "at least one of rules 1 to 7 fails",
                       "pred": {"or": [{"not": p} for _, _, p in plus]}}],
    },
    "outcome_map": {"valid": "within authority", "invalid": "outside authority",
                    "authority-gap": "no rule stated", "REFER": "fact missing"},
}

out = Path(__file__).with_name("mandate-v0.1.json")
out.write_text(json.dumps(spec, indent=1, sort_keys=True) + "\n")
print("wrote", out.name)
