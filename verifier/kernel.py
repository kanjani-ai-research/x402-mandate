# Copyright 2026 Causum (https://causum.com)
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""The kernel: predicate evaluation, per-family verdicts, derived outcome, certificate, re-derivation.

A specification has three families of checks. The applicability family says whether the authority
has anything to say about the record; when any of its checks fails the outcome is an authority gap,
which is an abstention and not a verdict. A missing required fact (REFER) comes first, the authority
gap second, the derived verdict last.
"""

import hashlib
import json

FAMILIES = ("phi_gap", "phi_plus", "phi_minus")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode()


def sha(obj):
    return "sha256:" + hashlib.sha256(canonical(obj)).hexdigest()


def _term(t, sigma, element):
    if isinstance(t, dict):
        if "field" in t:
            if element is None or t["field"] not in element:
                raise KeyError(t["field"])
            return element[t["field"]]
        if "threshold" in t:
            return sigma["thresholds"][t["threshold"]]
    return t


def eval_pred(p, rho, sigma, element=None):
    """Evaluate an op-tree predicate against the lowered record rho."""
    if "and" in p:
        return all(eval_pred(q, rho, sigma, element) for q in p["and"])
    if "or" in p:
        return any(eval_pred(q, rho, sigma, element) for q in p["or"])
    if "not" in p:
        return not eval_pred(p["not"], rho, sigma, element)
    if "exists" in p:
        spec = p["exists"]
        return any(eval_pred(spec["body"], rho, sigma, el) for el in rho[spec["over"]])
    if "eq" in p:
        a, b = p["eq"]
        return _term(a, sigma, element) == _term(b, sigma, element)
    if "ge" in p:
        a, b = p["ge"]
        return _term(a, sigma, element) >= _term(b, sigma, element)
    if "in" in p:
        a, b = p["in"]
        return _term(a, sigma, element) in b
    raise ValueError(f"unknown op: {list(p)}")


def family_verdict(checks, rho, sigma):
    evaluated = [{"id": c["id"], "holds": bool(eval_pred(c["pred"], rho, sigma))} for c in checks]
    falsifiers = [c["id"] for c in evaluated if not c["holds"]]
    return ("NONCONFORMING" if falsifiers else "CONFORMING"), evaluated, falsifiers


def derived_outcome(v_gap, v_plus, v_minus):
    if v_gap == "NONCONFORMING":
        return "authority-gap"
    return {("CONFORMING", "NONCONFORMING"): "valid",
            ("NONCONFORMING", "CONFORMING"): "invalid",
            ("NONCONFORMING", "NONCONFORMING"): "indeterminate-by-spec",
            ("CONFORMING", "CONFORMING"): "conflict-spec-gap"}[(v_plus, v_minus)]


def verify(record, rho, missing, sigma):
    """Issue the certificate for a record, its lowering rho, and the required facts it lacks."""
    body = {"item_id": record["id"], "input_sha256": sha(record),
            "spec_id": sigma["spec_id"], "spec_hash": sigma["_hash"],
            "lifted": rho, "lift_missing": sorted(missing)}
    if missing:
        for fam in FAMILIES:
            body[fam] = {"verdict": "REFER", "checks": [], "falsifiers": []}
        body["outcome"] = "REFER"
    else:
        verdicts = []
        for fam in FAMILIES:
            v, checks, fals = family_verdict(sigma["families"][fam], rho, sigma)
            body[fam] = {"verdict": v, "checks": checks, "falsifiers": fals}
            verdicts.append(v)
        body["outcome"] = derived_outcome(*verdicts)
    return {**body, "witness_hash": sha(body)}


def rederive(witness, sigma, record, lift_fn):
    """Recompute the certificate from the record and the specification. Fail-closed.

    The lowering is recomputed from the record as well, so a re-sealed certificate of a different
    lowered record is rejected.
    """
    body = {k: v for k, v in witness.items() if k != "witness_hash"}
    if witness.get("witness_hash") != sha(body):
        return False, "witness_hash mismatch"
    if witness["spec_hash"] != sigma["_hash"]:
        return False, "spec_hash does not match trusted sigma"
    if witness["input_sha256"] != sha(record):
        return False, "input binding: record hash mismatch"
    rho, missing = lift_fn(record, sigma)
    if rho != witness["lifted"] or sorted(missing) != witness["lift_missing"]:
        return False, "input binding: re-lift differs from stored lift"
    if witness["outcome"] == "REFER":
        return (bool(witness["lift_missing"]),
                "ok" if witness["lift_missing"] else "REFER without missing fields")
    try:
        verdicts = []
        for fam in FAMILIES:
            v, checks, fals = family_verdict(sigma["families"][fam], witness["lifted"], sigma)
            got = witness[fam]
            if v != got["verdict"] or checks != got["checks"] or fals != got["falsifiers"]:
                return False, f"{fam} recomputation differs"
            verdicts.append(v)
        if derived_outcome(*verdicts) != witness["outcome"]:
            return False, "derived outcome differs"
    except (KeyError, TypeError, ValueError) as e:
        return False, f"recomputation impossible ({e})"
    return True, "ok"
