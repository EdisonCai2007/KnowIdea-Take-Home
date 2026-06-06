# Battery Verifier Output

This file captures the Stage 2 verifier output requested in the assignment for all 12 battery decisions from `decision_battery.json`.

Source command pattern:

```bash
decision-prover verify run --input codex-resources/original-project-specs/decision_battery.json --decision-id D#
```

## Summary

| Decision | Verdict | Why |
| --- | --- | --- |
| D1 | `UNDECIDABLE` | Constraints pass, but product-velocity gain is unquantified |
| D2 | `SUPPORTED` | Constraints pass and projected LTV/CAC clears the threshold |
| D3 | `REFUTED` | Post-action runway drops below the hard 6-month floor |
| D4 | `UNDECIDABLE` | Price-elasticity and CAC response are not pinned down |
| D5 | `REFUTED` | Capacity cannot satisfy backlog plus new order by deadline |
| D6 | `SUPPORTED` | Capacity expansion restores backlog feasibility within budget |
| D7 | `REFUTED` | In a supply-constrained setting, the price cut is dominated |
| D8 | `UNDECIDABLE` | Cannibalization determines whether premium revenue grows on net |
| D9 | `REFUTED` | Total marketing spend violates the hard spend cap |
| D10 | `UNDECIDABLE` | Reallocation upside to Line A is not quantified |
| D11 | `SUPPORTED` | Churn improves and computed LTV improves while constraints hold |
| D12 | `UNDECIDABLE` | Margin improvement depends on an unsigned supplier agreement |

## D1

**Proposal:** Hire 5 additional engineers immediately to accelerate the roadmap.  
**Verdict:** `UNDECIDABLE`

**Derivation**

1. Compute action impact.
   `initiative_budget = 1,000,000`, `cash_outflow = 0`, `monthly_burn_delta = 83,333.3333`
2. Check hard constraints.
   `L-C1`: post-action cash `3,200,000 >= 500,000` so reserve floor passes.
   `L-C2`: post-action runway `3,200,000 / 483,333.3333 = 6.6207` months, so runway floor passes.
   `L-C3`: initiative budget `1,000,000 <= 1,500,000` so budget cap passes.
3. Check the stated objective.
   The verifier can confirm the hire is feasible, but cannot derive from the provided facts that 5 additional engineers will materially increase product velocity.
4. Therefore no proof exists for either support or refutation on the stated objective.

**Constraints Checked**

- `L-C1`: pass. Post-action cash `3,200,000 >= 500,000`.
- `L-C2`: pass. Post-action runway `6.6207 >= 6`.
- `L-C3`: pass. Initiative budget `1,000,000 <= 1,500,000`.

**Load-Bearing Assumptions**

- None explicitly stated in the verifier output.

**Why It Is Undecidable**

- Pivotal assumption: the 5 additional engineers materially increase product velocity enough to justify the hire.
- Flip threshold: the needed product-velocity improvement is not quantified in the provided facts.
- Supported if: added engineering capacity yields a material product-velocity gain.
- Refuted if: added engineering capacity does not produce a material velocity gain.

**Refutation**

- Attempted: yes.
- Failure condition found: the objective depends on unquantified engineering productivity and delivery impact.

## D2

**Proposal:** Run a paid-acquisition test with a `$300,000` budget.  
**Verdict:** `SUPPORTED`

**Derivation**

1. Compute action impact.
   `initiative_budget = 300,000`, `cash_outflow = 300,000`, `monthly_burn_delta = 0`
2. Check balance-sheet constraints.
   `L-C1`: post-action cash `2,900,000 >= 500,000`.
   `L-C2`: post-action runway `2,900,000 / 400,000 = 7.25` months.
   `L-C3`: initiative budget `300,000 <= 1,500,000`.
3. Check channel-economics constraint.
   Using `LTV = arpu_monthly * gross_margin / monthly_churn_rate`,
   `LTV = 1,400 * 0.8 / 0.025 = 44,800`.
   `LTV/CAC = 44,800 / 5,000 = 8.96`.
   `L-C4` passes because `8.96 >= 3`.
4. Check the objective.
   The acquisition test stays within all hard constraints and clears the channel-scaling hurdle.
5. Therefore the decision is supported under its stated assumptions.

**Constraints Checked**

- `L-C1`: pass. Post-action cash `2,900,000 >= 500,000`.
- `L-C2`: pass. Post-action runway `7.25 >= 6`.
- `L-C3`: pass. Initiative budget `300,000 <= 1,500,000`.
- `L-C4`: pass. Projected `LTV/CAC = 8.96 >= 3`.

**Load-Bearing Assumptions**

- `A1`: projected CAC for the channel is approximately `$5,000`.
- `A2`: acquired customers churn and monetize like the existing cohort.

**Refutation**

- Attempted: yes.
- Failure condition found: none.

## D3

**Proposal:** Acquire a small competitor for `$2,400,000` in cash, adding `$80,000` of MRR.  
**Verdict:** `REFUTED`

**Derivation**

1. Compute action impact.
   `initiative_budget = 2,400,000`, `cash_outflow = 2,400,000`, `monthly_burn_delta = 0`
2. Check cash reserve floor.
   `L-C1`: post-action cash `3,200,000 - 2,400,000 = 800,000`, so reserve floor still passes.
3. Check runway floor.
   `L-C2`: post-action runway `800,000 / 400,000 = 2` months.
4. Contradiction.
   The board mandate requires runway `>= 6` months, but the decision yields only `2` months.
5. Therefore the decision is refuted before any upside can matter.

**Constraints Checked**

- `L-C1`: pass. Post-action cash `800,000 >= 500,000`.
- `L-C2`: fail. Post-action runway `2 < 6`.

**Load-Bearing Assumptions**

- None.

**Refutation**

- Attempted: yes.
- Failure condition found: hard constraint `L-C2` failed because post-action runway is `2` months, below the `6`-month floor.

## D4

**Proposal:** Raise list prices 15% for new customers only.  
**Verdict:** `UNDECIDABLE`

**Derivation**

1. Compute action impact.
   `initiative_budget = 0`, `cash_outflow = 0`, `monthly_burn_delta = 0`
2. Check hard constraints.
   `L-C1`: post-action cash remains `3,200,000`, so reserve floor passes.
   `L-C2`: post-action runway remains `8` months, so runway floor passes.
   `L-C3`: initiative budget `0 <= 1,500,000`.
3. Check the objective.
   The objective is to improve unit economics on new business.
   The verifier can see the proposed `15%` price increase, but cannot infer the conversion-rate or CAC response.
4. Therefore the verdict depends on unmeasured elasticity.

**Constraints Checked**

- `L-C1`: pass. Post-action cash `3,200,000 >= 500,000`.
- `L-C2`: pass. Post-action runway `8 >= 6`.
- `L-C3`: pass. Initiative budget `0 <= 1,500,000`.

**Load-Bearing Assumptions**

- `A1`: the effect of the price increase on new-customer conversion rate is not measured; no elasticity data is provided.

**Why It Is Undecidable**

- Pivotal assumption: conversion and CAC remain strong enough after the price increase to improve unit economics.
- Flip threshold: the verdict flips at the elasticity/CAC point where the price increase no longer improves new-business unit economics.
- Supported if: conversion and CAC do not worsen enough to erase the price gain.
- Refuted if: conversion or CAC worsens enough to offset the gain.

**Refutation**

- Attempted: yes.
- Failure condition found: the objective depends on unmeasured new-customer elasticity and CAC response.

## D5

**Proposal:** Accept a new 400-unit order due in 5 months, on top of the existing 200-unit backlog.  
**Verdict:** `REFUTED`

**Derivation**

1. Compute action impact.
   `initiative_budget = 0`, `cash_outflow = 0`, `monthly_burn_delta = 0`
2. Check non-binding financial constraints.
   `H-C1`: post-action cash remains `6,000,000`, so reserve floor passes.
   `H-C3`: initiative budget `0 <= 2,000,000`.
3. Check backlog-delivery feasibility.
   Existing backlog is `200` units due within `6` months.
   New order adds `400` units due within `5` months.
   Required units by the tighter deadline: `600`.
   Achievable units by month `5`: `25 units/mo * 5 = 125`.
4. Contradiction.
   Required output is `600`, but feasible output is only `125`.
5. Therefore the decision is refuted by hard constraint `H-C5`.

**Constraints Checked**

- `H-C1`: pass. Post-action cash `6,000,000 >= 1,000,000`.
- `H-C3`: pass. Initiative budget `0 <= 2,000,000`.
- `H-C5`: fail. Capacity can build only `125` units by month `5` against `600` required.

**Load-Bearing Assumptions**

- None.

**Refutation**

- Attempted: yes.
- Failure condition found: hard constraint `H-C5` failed because capacity can build only `125` units by month `5` against `600` required.

## D6

**Proposal:** Invest `$1,800,000` in capex to expand production capacity from 25 to 60 units per month, with a 4-month ramp.  
**Verdict:** `SUPPORTED`

**Derivation**

1. Compute action impact.
   `initiative_budget = 1,800,000`, `cash_outflow = 1,800,000`, `monthly_burn_delta = 0`
2. Check financial constraints.
   `H-C1`: post-action cash `6,000,000 - 1,800,000 = 4,200,000`, so reserve floor passes.
   `H-C3`: initiative budget `1,800,000 <= 2,000,000`.
3. Check backlog-delivery feasibility under the ramp.
   Months `1-4`: `25/mo`, so `100` units.
   Months `5-6`: `60/mo`, so `120` units.
   Total by month `6`: `220` units.
   `H-C5` passes because `220 >= 200`.
4. Check the objective.
   The objective is to meet existing demand and contractual delivery obligations.
   The expansion restores delivery feasibility.
5. Therefore the decision is supported under the stated ramp assumption.

**Constraints Checked**

- `H-C1`: pass. Post-action cash `4,200,000 >= 1,000,000`.
- `H-C3`: pass. Initiative budget `1,800,000 <= 2,000,000`.
- `H-C5`: pass. Capacity plan delivers `220` units by month `6` against `200` required.

**Load-Bearing Assumptions**

- `A1`: the capacity ramp completes on the stated schedule.

**Refutation**

- Attempted: yes.
- Failure condition found: none.

## D7

**Proposal:** Cut the unit sale price from `$9,000` to `$6,500` to win a price-sensitive segment, assuming order volume doubles.  
**Verdict:** `REFUTED`

**Derivation**

1. Compute action impact.
   `initiative_budget = 0`, `cash_outflow = 0`, `monthly_burn_delta = 0`
2. Check non-binding financial constraints.
   `H-C1`: post-action cash remains `6,000,000`.
   `H-C3`: initiative budget remains `0`.
3. Check dominance in a supply-constrained environment.
   Production capacity stays at `25` units per month.
   Baseline fulfilled units monthly: `25`.
   Proposed fulfilled units monthly: still `25`, because capacity is fixed.
   Baseline monthly revenue: `25 * 9,000 = 225,000`.
   Proposed monthly revenue: `25 * 6,500 = 162,500`.
   Baseline unit margin: `4,800`.
   Proposed unit margin: `2,300`.
4. Contradiction.
   The proposal cannot increase fulfilled volume, but it does reduce both revenue and unit margin.
5. Therefore the baseline strictly dominates the price cut on the stated objective.

**Constraints Checked**

- `H-C1`: pass. Post-action cash `6,000,000 >= 1,000,000`.
- `H-C3`: pass. Initiative budget `0 <= 2,000,000`.

**Load-Bearing Assumptions**

- None required by the verifier's refutation.

**Refutation**

- Attempted: yes.
- Failure condition found: the baseline dominates because demand already exceeds capacity, so the price cut cannot increase fulfilled volume and only weakens unit economics.

## D8

**Proposal:** Launch a new premium SKU at 35% contribution margin with `$1,500,000` launch cost and projected incremental revenue of `$600,000/mo`.  
**Verdict:** `UNDECIDABLE`

**Derivation**

1. Check new-SKU margin hurdle.
   `T-C6` passes because contribution margin `0.35 >= 0.25`.
2. Compute action impact.
   `initiative_budget = 1,500,000`, `cash_outflow = 1,500,000`, `monthly_burn_delta = 0`
3. Check budget cap.
   `T-C3` passes because `1,500,000 <= 3,000,000`.
4. Check the objective.
   The objective is to grow premium revenue.
   The verifier sees projected monthly revenue of `600,000`, but cannot determine how much of that is truly incremental versus cannibalized from existing premium sales.
5. Therefore the verdict depends on cannibalization.

**Constraints Checked**

- `T-C6`: pass. New SKU contribution margin `0.35 >= 0.25`.
- `T-C3`: pass. Initiative budget `1,500,000 <= 3,000,000`.

**Load-Bearing Assumptions**

- `A1`: the `$600,000/mo` is incremental; the degree to which it draws sales away from existing premium Line A is not specified.

**Why It Is Undecidable**

- Pivotal assumption: cannibalized premium-line revenue is low enough that the new SKU grows premium revenue on net.
- Flip threshold:
  `support_if: cannibalized_premium_revenue_monthly < 600,000`
  `refute_if: cannibalized_premium_revenue_monthly >= 600,000`
- Supported if: cannibalized premium revenue stays below `600,000/mo`.
- Refuted if: cannibalized premium revenue reaches or exceeds `600,000/mo`.

**Refutation**

- Attempted: yes.
- Failure condition found: the objective depends on unspecified cannibalization of the existing premium line.

## D9

**Proposal:** Increase Line B marketing spend by `$400,000/mo` to grow value-segment share.  
**Verdict:** `REFUTED`

**Derivation**

1. Compute action impact.
   `initiative_budget = 400,000`, `cash_outflow = 0`, `monthly_burn_delta = 400,000`
2. Check initiative budget cap.
   `T-C3`: `400,000 <= 3,000,000`, so the budget cap passes.
3. Check total marketing spend cap.
   Current marketing spend is `500,000`.
   Added marketing spend is `400,000`.
   Total marketing spend becomes `900,000`.
   Revenue is `5,000,000`, so the cap is `0.12 * 5,000,000 = 600,000`.
4. Contradiction.
   Total marketing spend would be `900,000`, which exceeds the hard cap of `600,000`.
5. Therefore the decision is refuted by hard constraint `T-C7`.

**Constraints Checked**

- `T-C3`: pass. Initiative budget `400,000 <= 3,000,000`.
- `T-C7`: fail. Total marketing spend `900,000 > 600,000`.

**Load-Bearing Assumptions**

- None.

**Refutation**

- Attempted: yes.
- Failure condition found: hard constraint `T-C7` failed because total marketing spend `900,000 > 600,000`.

## D10

**Proposal:** Discontinue Line B entirely and reallocate its resources to Line A.  
**Verdict:** `UNDECIDABLE`

**Derivation**

1. Compute action impact.
   `initiative_budget = 0`, `cash_outflow = 0`, `monthly_burn_delta = 0`
2. Check budget cap.
   `T-C3`: initiative budget `0 <= 3,000,000`, so the only applicable hard constraint passes.
3. Compute the contribution being given up.
   Line B revenue is `2,000,000/mo`.
   Line B contribution margin is `0.20`.
   Lost Line B contribution is `2,000,000 * 0.20 = 400,000/mo`.
4. Check the objective.
   The verifier cannot determine whether reallocating those resources to Line A produces more than `400,000/mo` of incremental contribution.
5. Therefore the verdict depends on the unquantified return from reallocation.

**Constraints Checked**

- `T-C3`: pass. Initiative budget `0 <= 3,000,000`.

**Load-Bearing Assumptions**

- `A1`: the incremental return Line A would generate from the reallocated resources is not quantified.

**Why It Is Undecidable**

- Pivotal assumption: reallocated Line A resources generate enough incremental contribution to exceed the lost Line B contribution.
- Flip threshold:
  `support_if: incremental_line_a_contribution_monthly > 400,000`
  `refute_if: incremental_line_a_contribution_monthly <= 400,000`
- Supported if: reallocated Line A contribution exceeds `400,000/mo`.
- Refuted if: reallocated Line A contribution is at or below `400,000/mo`.

**Refutation**

- Attempted: yes.
- Failure condition found: the objective depends on unquantified returns from reallocating Line B resources.

## D11

**Proposal:** Invest `$200,000` in a customer-success program projected to cut monthly churn from `2.5%` to `2.0%`.  
**Verdict:** `SUPPORTED`

**Derivation**

1. Compute action impact.
   `initiative_budget = 200,000`, `cash_outflow = 200,000`, `monthly_burn_delta = 0`
2. Check hard constraints.
   `L-C1`: post-action cash `3,000,000 >= 500,000`.
   `L-C2`: post-action runway `3,000,000 / 400,000 = 7.5` months.
   `L-C3`: initiative budget `200,000 <= 1,500,000`.
3. Check the objective.
   `LTV_before = 1,400 * 0.8 / 0.025 = 44,800`.
   `LTV_after = 1,400 * 0.8 / 0.020 = 56,000`.
   Churn improves from `0.025` to `0.020`.
   LTV improves from `44,800` to `56,000`.
4. Therefore the objective of improving retention and lifetime value is satisfied while constraints hold.

**Constraints Checked**

- `L-C1`: pass. Post-action cash `3,000,000 >= 500,000`.
- `L-C2`: pass. Post-action runway `7.5 >= 6`.
- `L-C3`: pass. Initiative budget `200,000 <= 1,500,000`.

**Load-Bearing Assumptions**

- None needed by the verifier for the final classification.

**Refutation**

- Attempted: yes.
- Failure condition found: none.

## D12

**Proposal:** Renegotiate the Line A supplier contract for a 2-point reduction in Line A COGS, at no cost; the supplier has verbally agreed.  
**Verdict:** `UNDECIDABLE`

**Derivation**

1. Compute action impact.
   `initiative_budget = 0`, `cash_outflow = 0`, `monthly_burn_delta = 0`
2. Check budget cap.
   `T-C3`: initiative budget `0 <= 3,000,000`.
3. Check the objective.
   Current Line A contribution margin is `0.40`.
   If fully executed, the projected Line A contribution margin would be `0.42`.
   But the supplier agreement is not signed, so the realized improvement is not pinned down by the facts.
4. Therefore the verdict depends on execution of the unsigned agreement.

**Constraints Checked**

- `T-C3`: pass. Initiative budget `0 <= 3,000,000`.

**Load-Bearing Assumptions**

- `A1`: the supplier has verbally agreed; the deal is not yet signed.

**Why It Is Undecidable**

- Pivotal assumption: the unsigned supplier agreement executes and yields a realized positive Line A margin improvement.
- Flip threshold:
  `support_if: realized_line_a_margin_improvement_fraction > 0`
  `refute_if: realized_line_a_margin_improvement_fraction <= 0`
- Supported if: the supplier agreement executes and Line A margin improves by more than `0`.
- Refuted if: the supplier agreement does not execute or yields no realized margin improvement.

**Refutation**

- Attempted: yes.
- Failure condition found: the objective depends on an unsigned supplier agreement and execution risk.
