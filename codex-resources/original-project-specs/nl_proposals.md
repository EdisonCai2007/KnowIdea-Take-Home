# Natural-Language Proposals — Formalization Set

These are raw, unformalized proposals — the kind of thing a user would actually type. Unlike `decision_battery.json`, **nothing here is pre-structured.** Your system must run Stage 1 on each: interview the user to surface whatever the formalization needs, translate the result into the structured schema (the same one used in the battery), and then run Stage 2 to reach a verdict.

Some of these are deliberately under-specified. When something the formalization needs isn't stated, the right move is to **ask the user for it, not invent it.** For each proposal we want to see: the interview (what your system asked and the answers it worked from), the formal object it built, and the verdict it reached.

You may simulate the user side of the interview yourself when demonstrating — but make your system's *questions* real, driven by what's actually missing. We will also run a few of our own proposals you haven't seen, so build for the general behavior, not these six.

---

**P1.**
> "We're thinking about hiring some more salespeople to hit our growth targets next year. Can you tell us whether that's a sound move?"

**P2.**
> "Our biggest competitor just raised a huge round, so we need to do something big — I want to acquire one of the smaller players before they get scooped up. This is time-sensitive. Just tell me it's the right call."

**P3.**
> "We've got $2M in the bank and we're burning $250k a month. Our board requires us to keep at least six months of runway at all times, no exceptions. I want to put $1M upfront into a brand-marketing campaign. Good idea?"

**P4.**
> "We sell a subscription product — ARPU is $80 a month, gross margin is 75%, monthly churn is 4%. We found a new acquisition channel with a CAC of $400. Our standing policy is that we only scale a channel if its LTV/CAC is at least 3. Should we scale this one? (Also, we just redesigned our logo and the team loves it.)"

**P5.**
> "We want to raise our prices by 20%. We think it'll boost revenue, and our finance team is fine with it. Should we go ahead?"

**P6.**
> "Huge opportunity — a distributor wants to place a $5M order, the biggest deal in our company's history. We currently make 30 units a month and they want 1,000 units delivered in four months. Obviously we take it, right?"
