# The mandate, in the principal's words

This is the statement the specification `mandate-v0.1.json` encodes. The resolver in `resolver.py` was written from this text alone, without reading the specification.

Principal: a company that lets an agent buy data and compute over x402.

1. **Asset.** Pay only in USDC on Base (`eip155:8453`).
2. **Per payment.** No single payment above 50 USDC.
3. **Total.** No payment that takes the total paid under this mandate above 8,000 USDC.
4. **Expiry.** No payment after the mandate's expiry time.
5. **Prohibited.** Never buy gambling, adult content, or crypto-assets, from anyone.
6. **Named sellers.** Five sellers are named. The agent may buy anything not prohibited from them.
7. **Sellers the agent finds itself.** The agent may buy from a seller that is not named only when
   all of these hold:
   - an issuer attests that the seller is a verified legal entity, at assurance level 2 or higher;
   - an issuer attests that the seller is in the US, the EU or the UK;
   - the purchase is data or compute;
   - the payment is 5 USDC or less.
8. **What the mandate does not speak to.** For a seller that is not named, the mandate states rules
   only for data, compute and the three prohibited categories. A purchase in any other category is
   not decided by this mandate. It goes back to the principal.
9. **Facts that must be present.** A purchase is evaluated only when these are present: the asset,
   network, amount, payee, time and the category the seller declares; and, for a seller that is not
   named, an issuer's statement on whether it is a verified entity, and, if it is verified, its
   assurance level and its jurisdiction. If one is absent, the purchase is not evaluated and the
   missing fact is named.

Order of evaluation: rule 9 first, then rule 8, then rules 1 to 7.

Four results:

| Result | Meaning | Kernel outcome |
|---|---|---|
| within authority | rules 1 to 7 all hold | `valid` |
| outside authority | at least one of rules 1 to 7 fails; the failed rules are named | `invalid` |
| no rule stated | rule 8 | `authority-gap` |
| fact missing | rule 9; the missing facts are named | `REFER` |

---

Copyright 2026 Causum (https://causum.com). PolyForm Noncommercial License 1.0.0.
