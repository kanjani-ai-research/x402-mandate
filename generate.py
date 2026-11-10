# Copyright 2026 Causum (https://causum.com)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Generate purchases.jsonl: 2,000 proposed x402 purchases, seed 402.

Every parameter here was fixed before the first run. The running total uses resolver.py:
a purchase the mandate's prose puts within authority is taken to have settled.
"""
import json
import math
import random
from pathlib import Path

from resolver import NAMED, USDC, resolve

SEED, N, T_END = 402, 2000, 1_000_000
rng = random.Random(SEED)


def pick(table):
    r, acc = rng.random(), 0.0
    for value, p in table:
        acc += p
        if r < acc:
            return value
    return table[-1][0]


named = sorted(NAMED)
named_category = dict(zip(named, ["data", "data", "compute", "compute", "subscription"]))

found = []
for i in range(60):
    status = pick([("verified", .70), ("unverified", .15), ("absent", .15)])
    found.append({
        "payTo": f"0xFOUND{i:02d}",
        "status": status,
        "assurance": pick([(1, .15), (2, .55), (3, .30)]),
        "jurisdiction": pick([("US", .35), ("EU", .30), ("UK", .10), ("SG", .10), ("BR", .10), (None, .05)]),
        "category": pick([("data", .40), ("compute", .25), ("gambling", .05), ("adult", .03),
                          ("crypto-asset", .05), ("legal-services", .07), ("physical-goods", .07),
                          ("subscription", .08)]),
    })

times = sorted(rng.randrange(T_END) for _ in range(N))
spent, rows = 0, []
for k, now in enumerate(times):
    if rng.random() < .35:
        payee = rng.choice(named)
        category = named_category[payee]
        amount = int(math.exp(rng.gauss(math.log(5), .9)) * USDC)
        attestations = []
    else:
        s = rng.choice(found)
        payee, category = s["payTo"], s["category"]
        amount = int(math.exp(rng.gauss(math.log(1.5), .9)) * USDC)
        attestations = []
        if s["status"] == "verified":
            attestations.append({"about": payee, "claim": "entity-verified", "value": True,
                                 "assurance": s["assurance"], "issuer": "issuer-A"})
            if s["jurisdiction"] is not None:
                attestations.append({"about": payee, "claim": "jurisdiction",
                                     "value": s["jurisdiction"], "issuer": "issuer-A"})
        elif s["status"] == "unverified":
            attestations.append({"about": payee, "claim": "entity-verified", "value": False,
                                 "issuer": "issuer-A"})
    network, asset = pick([(("eip155:8453", "USDC"), .97), (("eip155:8453", "USDT"), .015),
                           (("eip155:1", "USDC"), .015)])
    record = {
        "id": f"p{k:04d}",
        "payment": {"scheme": "exact", "network": network, "asset": asset, "amount": max(amount, 1),
                    "payTo": payee, "resource": f"https://{payee.lower()}.example/r/{k}"},
        "offer": {} if rng.random() < .02 else {"category": category},
        "attestations": attestations,
        "state": {"spent_before": spent},
        "time": now,
    }
    result, _ = resolve(record)
    if result == "within authority":
        spent += record["payment"]["amount"]
    rows.append(record)

out = Path(__file__).with_name("purchases.jsonl")
out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
print("wrote", len(rows), "purchases; total settled", spent / USDC, "USDC")
