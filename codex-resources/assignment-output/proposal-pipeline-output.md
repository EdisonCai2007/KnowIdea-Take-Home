# Proposal Pipeline Output

This file captures the pipeline output requested in the assignment for `P1` through `P6`: the interview transcript, the formal object produced by the current system, and the resulting verdict.

## P1

**Original Proposal**

> We're thinking about hiring some more salespeople to hit our growth targets next year. Can you tell us whether that's a sound move?

**Interview Transcript**

- `user` `proposal`: We're thinking about hiring some more salespeople to hit our growth targets next year. Can you tell us whether that's a sound move?
- `assistant` `question`: What is the target annual revenue growth rate for next year?
- `user` `answer`: 25% annual revenue growth
- `assistant` `question`: What is the current average annual revenue generated per salesperson?
- `assistant` `question`: What is the current total number of active salespeople?
- `user` `answer`: 200000 USD
- `user` `answer`: 20 salespeople
- `assistant` `question`: What is the average fully loaded annual cost (salary, benefits, overhead) for one salesperson?
- `user` `answer`: 100000 USD
- `assistant` `question`: What is the expected average annual revenue generated per new salesperson?
- `user` `answer`: 200000 USD
- `assistant` `question`: What is the current total annual revenue?
- `user` `answer`: 4000000 USD
- `assistant` `ready`: Stage 1 stopped after the 5-round clarification limit. Use the current decision brief with the unresolved notes below.

**Formal Object Produced By Current System**

Stage 1 decision kernel:

- Decision: Evaluate the soundness of hiring more salespeople.
- Objective: Achieve 25% annual revenue growth next year.
- Success criteria:
  - Hiring more salespeople is a sound move.
- Constraints mentioned: none
- What we know:
  - The company is Northstar CRM, a B2B SaaS company.
  - The proposal is to hire more salespeople.
  - The target annual revenue growth rate for next year is 25%.
  - The current average annual revenue generated per salesperson is 200000 USD.
  - The current total number of active salespeople is 20.
  - The average fully loaded annual cost for one salesperson is 100000 USD.
  - The expected average annual revenue generated per new salesperson is 200000 USD.
  - The current total annual revenue is 4000000 USD.
- Unresolved notes:
  - What is the expected return on investment from hiring more salespeople?
  - Are there alternative strategies to hit growth targets next year?

Stage 2 proof draft:

- Claim: Hiring more salespeople is a sound move to achieve the 25% annual revenue growth target.
- Premises:
  - Current total annual revenue is 4000000 USD.
  - Target annual revenue growth rate is 25% (0.25).
  - Expected average annual revenue generated per new salesperson is 200000 USD.
  - Average fully loaded annual cost for one salesperson is 100000 USD.
- Computations: none
- Comparisons: none
- Proposed verdict in draft: `SUPPORTED`
- Refutation attempt:
  - The calculation assumes that new salespeople will be immediately as productive as existing ones, without any ramp-up time.
  - It also assumes that the market can support this additional sales capacity without a decrease in price or an increase in customer acquisition cost.
- Unresolved gaps:
  - The analysis does not account for the ramp-up time for new salespeople to become fully productive.
  - The analysis does not consider potential market saturation or increased difficulty in acquiring new customers.

**Resulting Verdict**

`UNDECIDABLE`

## P2

**Original Proposal**

> Our biggest competitor just raised a huge round, so we need to do something big — I want to acquire one of the smaller players before they get scooped up. This is time-sensitive. Just tell me it's the right call.

**Interview Transcript**

- `user` `proposal`: Our biggest competitor just raised a huge round, so we need to do something big — I want to acquire one of the smaller players before they get scooped up. This is time-sensitive. Just tell me it's the right call.
- `assistant` `question`: What is the maximum acquisition budget in USD for this transaction?
- `user` `answer`: 5000000 USD
- `assistant` `question`: What is the latest date by which this acquisition must be completed to be considered 'time-sensitive' and effective against the competitor's move?
- `user` `answer`: 2024-07-01
- `assistant` `question`: What is the minimum annual revenue threshold in USD that a target company must have to be considered a 'smaller player' and a viable acquisition target?
- `assistant` `question`: What is the minimum number of active customers a target company must have to be considered a 'smaller player' and a viable acquisition target?
- `assistant` `question`: What is the maximum number of employees a target company can have to be considered a 'smaller player' and a viable acquisition target?
- `user` `answer`: 1000000 USD
- `user` `answer`: 1000 customers
- `user` `answer`: 50 employees
- `assistant` `question`: What is the minimum acceptable annual growth rate percentage for a target company's revenue to be considered a viable acquisition target?
- `assistant` `question`: What is the minimum acceptable gross profit margin percentage for a target company to be considered a viable acquisition target?
- `assistant` `question`: What is the maximum acceptable customer churn rate percentage for a target company to be considered a viable acquisition target?
- `user` `answer`: 20%
- `user` `answer`: 60%
- `user` `answer`: 5%
- `assistant` `question`: What is the minimum acceptable customer lifetime value (CLTV) in USD for a target company's average customer to be considered a viable acquisition target?
- `assistant` `question`: What is the maximum acceptable customer acquisition cost (CAC) in USD for a target company to be considered a viable acquisition target?
- `assistant` `question`: What is the minimum acceptable ratio of Customer Lifetime Value (CLTV) to Customer Acquisition Cost (CAC) for a target company to be considered a viable acquisition target?
- `user` `answer`: 2000 USD
- `user` `answer`: 100 USD
- `user` `answer`: 3:1
- `assistant` `ready`: Stage 1 stopped after the 5-round clarification limit. Use the current decision brief with the unresolved notes below.

**Formal Object Produced By Current System**

Stage 1 decision kernel:

- Decision: Acquire a smaller player in the market.
- Objective: Respond to a competitor's recent funding round by making a significant strategic move.
- Success criteria:
  - Acquire one of the smaller players before they get scooped up.
- Constraints mentioned:
  - This is time-sensitive.
  - Maximum acquisition budget is 5,000,000 USD.
  - Acquisition must be completed by 2024-07-01.
- What we know:
  - A biggest competitor recently raised a huge round.
  - The proposer wants to do "something big".
  - The proposer wants to acquire one of the smaller players.
  - The maximum acquisition budget is 5,000,000 USD.
  - The acquisition must be completed by 2024-07-01 to be considered time-sensitive and effective.
  - A "smaller player" is defined as a company with a minimum annual revenue of 1,000,000 USD.
  - A "smaller player" is defined as a company with a minimum of 1,000 active customers.
  - A "smaller player" is defined as a company with a maximum of 50 employees.
  - A viable acquisition target must have a minimum acceptable annual revenue growth rate of 20%.
  - A viable acquisition target must have a minimum acceptable gross profit margin of 60%.
  - A viable acquisition target must have a maximum acceptable customer churn rate of 5%.
  - A viable acquisition target must have a minimum acceptable customer lifetime value of 2000 USD.
  - A viable acquisition target must have a maximum acceptable customer acquisition cost of 100 USD.
  - A viable acquisition target must have a minimum acceptable CLTV:CAC ratio of 3:1.
- Unresolved notes:
  - Which specific "smaller players" are candidates for acquisition?

Stage 2 proof draft:

- Claim: Acquiring a smaller player is a viable strategic move, provided a target company can be found that meets the specified financial and operational criteria.
- Premises:
  - Maximum acquisition budget is 5000000 USD.
  - Viable target minimum annual revenue is 1000000 USD.
  - Viable target minimum active customers is 1000.
  - Viable target maximum employees is 50.
  - Viable target minimum annual revenue growth rate is 0.20.
  - Viable target minimum gross profit margin is 0.60.
  - Viable target maximum customer churn rate is 0.05.
  - Viable target minimum CLTV is 2000 USD.
  - Viable target maximum CAC is 100 USD.
  - Viable target minimum CLTV:CAC ratio is 3.
- Computations:
  - `c_implied_ratio = p_min_cltv / p_max_cac = 20`
- Comparisons:
  - `c_implied_ratio >= p_min_ratio`
- Proposed verdict in draft: `SUPPORTED`
- Refutation attempt:
  - The argument is supported only if a target company that meets all specified criteria actually exists and is available for acquisition within the budget.
  - Without a specific candidate, the decision is purely theoretical and its real-world viability is unproven.
- Unresolved gaps:
  - Data for a specific acquisition target is needed to verify its price, revenue, customer count, employee count, growth rate, profit margin, churn rate, CLTV, and CAC against the established criteria.

**Resulting Verdict**

`SUPPORTED`

## P3

**Original Proposal**

> We've got $2M in the bank and we're burning $250k a month. Our board requires us to keep at least six months of runway at all times, no exceptions. I want to put $1M upfront into a brand-marketing campaign. Good idea?

**Interview Transcript**

- `user` `proposal`: We've got $2M in the bank and we're burning $250k a month. Our board requires us to keep at least six months of runway at all times, no exceptions. I want to put $1M upfront into a brand-marketing campaign. Good idea?
- `assistant` `question`: What is the expected monthly burn rate after the $1M brand-marketing campaign is executed?
- `user` `answer`: 300000 USD/month
- `assistant` `ready`: Stage 1 is ready because no additional proof-critical clarification questions remain.

**Formal Object Produced By Current System**

Stage 1 decision kernel:

- Decision: Approve or reject a $1M upfront investment in a brand-marketing campaign.
- Objective: Determine if investing $1M upfront in a brand-marketing campaign is a good idea given current financials and board requirements.
- Success criteria:
  - Maintain at least six months of runway after the $1M investment.
- Constraints mentioned:
  - Board requires at least six months of runway at all times, no exceptions.
- What we know:
  - Current cash in bank: $2M
  - Current monthly burn rate: $250k
  - Proposed upfront investment for brand-marketing campaign: $1M
  - Expected monthly burn rate after the $1M brand-marketing campaign is executed: 300000 USD/month
- Unresolved notes:
  - Expected return or benefits of the brand-marketing campaign.

Stage 2 proof draft:

- Claim: The proposed $1M brand-marketing campaign will leave the company with at least six months of runway, satisfying the board's requirement.
- Premises:
  - Current cash in bank is $2,000,000.
  - Proposed upfront investment is $1,000,000.
  - Expected monthly burn rate after the investment is $300,000.
  - Required runway is at least 6 months.
- Computations:
  - `c1 = p1 - p2 = 1000000`
  - `c2 = c1 / p3 = 3.3333333333333335`
- Comparisons:
  - `c2 >= p4`
- Proposed verdict in draft: `REFUTED`
- Refutation attempt:
  - The investment would leave the company with $1M in cash.
  - With a new burn rate of $300k/month, the resulting runway is approximately 3.33 months, which is less than the required 6 months.
- Unresolved gaps: none

**Resulting Verdict**

`REFUTED`

## P4

**Original Proposal**

> We sell a subscription product — ARPU is $80 a month, gross margin is 75%, monthly churn is 4%. We found a new acquisition channel with a CAC of $400. Our standing policy is that we only scale a channel if its LTV/CAC is at least 3. Should we scale this one? (Also, we just redesigned our logo and the team loves it.)

**Interview Transcript**

- `user` `proposal`: We sell a subscription product — ARPU is $80 a month, gross margin is 75%, monthly churn is 4%. We found a new acquisition channel with a CAC of $400. Our standing policy is that we only scale a channel if its LTV/CAC is at least 3. Should we scale this one? (Also, we just redesigned our logo and the team loves it.)
- `assistant` `question`: What is the average customer lifetime in months for your subscription product?
- `user` `answer`: 25 months
- `assistant` `ready`: Stage 1 is ready because no additional proof-critical clarification questions remain.

**Formal Object Produced By Current System**

Stage 1 decision kernel:

- Decision: Decide whether to scale a newly identified acquisition channel.
- Objective: Scale acquisition channels that meet the company's LTV/CAC policy.
- Success criteria:
  - The new acquisition channel's LTV/CAC is at least 3.
- Constraints mentioned:
  - Only scale a channel if its LTV/CAC is at least 3.
- What we know:
  - ARPU is $80 a month.
  - Gross margin is 75%.
  - Monthly churn is 4%.
  - New acquisition channel CAC is $400.
  - Standing policy requires LTV/CAC of at least 3 to scale a channel.
  - Average customer lifetime is 25 months.
- Unresolved notes: none

Stage 2 proof draft:

- Claim: The new acquisition channel should be scaled.
- Premises:
  - ARPU is $80 per month.
  - Gross margin is 0.75.
  - New channel CAC is $400.
  - Average customer lifetime is 25 months.
  - LTV/CAC ratio must be at least 3.
- Computations: none
- Comparisons: none
- Proposed verdict in draft: `SUPPORTED`
- Refutation attempt:
  - The proposal is refuted if the true CAC exceeds $500, as this would push the LTV/CAC ratio below the required threshold of 3.
- Unresolved gaps: none

**Resulting Verdict**

`UNDECIDABLE`

## P5

**Original Proposal**

> We want to raise our prices by 20%. We think it'll boost revenue, and our finance team is fine with it. Should we go ahead?

**Interview Transcript**

- `user` `proposal`: We want to raise our prices by 20%. We think it'll boost revenue, and our finance team is fine with it. Should we go ahead?
- `assistant` `question`: What is the current average monthly revenue in USD?
- `assistant` `question`: What is the current average monthly customer churn rate?
- `assistant` `question`: What is the current average monthly sales volume in units?
- `user` `answer`: 1000000 USD
- `user` `answer`: 2.0%
- `user` `answer`: 50000 units
- `assistant` `question`: What is the maximum acceptable percentage increase in customer churn rate that would still result in a net revenue gain after a 20% price increase?
- `assistant` `question`: What is the maximum acceptable percentage decrease in sales volume (units) that would still result in a net revenue gain after a 20% price increase?
- `user` `answer`: 8.0%
- `user` `answer`: 8.0%
- `assistant` `ready`: Stage 1 is ready because no additional proof-critical clarification questions remain.

**Formal Object Produced By Current System**

Stage 1 decision kernel:

- Decision: Approve or reject a 20% price increase.
- Objective: Boost revenue through a price increase.
- Success criteria:
  - The finance team is fine with the price increase.
  - A net revenue gain is achieved after a 20% price increase, even with a maximum 8.0% increase in customer churn rate.
  - A net revenue gain is achieved after a 20% price increase, even with a maximum 8.0% decrease in sales volume.
- Constraints mentioned: none
- What we know:
  - Proposed price increase is 20%.
  - Finance team has no objections to the price increase.
  - Current average monthly revenue is 1000000 USD.
  - Current average monthly customer churn rate is 2.0%.
  - Current average monthly sales volume is 50000 units.
  - Maximum acceptable increase in churn that still preserves net revenue gain is 8.0%.
  - Maximum acceptable decrease in sales volume that still preserves net revenue gain is 8.0%.
- Unresolved notes:
  - The specific revenue boost expected.
  - Any potential negative impacts on market share or brand perception.

Stage 2 proof draft:

- Claim: A 20% price increase will result in a net revenue gain, assuming a sales volume decrease no greater than 8.0%.
- Premises:
  - Current average monthly revenue is 1000000 USD.
  - Current average monthly sales volume is 50000 units.
  - Proposed price increase is 20%.
  - Assumed sales volume decrease is 8.0%.
  - Net revenue gain after a 20% price increase with at most an 8.0% volume decrease is the success criterion.
- Computations: none
- Comparisons: none
- Proposed verdict in draft: `SUPPORTED`
- Refutation attempt:
  - The claim is refuted if the calculated new revenue, under the assumption of an 8% sales volume decrease, is not greater than the current revenue.
- Unresolved gaps:
  - The actual projected decrease in sales volume following the price increase is not specified, only the maximum acceptable decrease which is used as an assumption in this proof.

**Resulting Verdict**

`UNDECIDABLE`

## P6

**Original Proposal**

> Huge opportunity — a distributor wants to place a $5M order, the biggest deal in our company's history. We currently make 30 units a month and they want 1,000 units delivered in four months. Obviously we take it, right?

**Interview Transcript**

- `user` `proposal`: Huge opportunity — a distributor wants to place a $5M order, the biggest deal in our company's history. We currently make 30 units a month and they want 1,000 units delivered in four months. Obviously we take it, right?
- `assistant` `question`: What is the maximum number of units ForgeLine can produce per month if production capacity is fully utilized?
- `user` `answer`: 50 units/month
- `assistant` `question`: What is the maximum number of additional units ForgeLine can produce per month beyond its current 50 units/month capacity, assuming a temporary increase in resources (e.g., overtime, temporary staff, or minor equipment rental) without major capital expenditure?
- `assistant` `question`: What is the lead time required to procure and install new equipment that would permanently increase ForgeLine's production capacity?
- `assistant` `question`: What is the cost per unit to produce the additional units beyond the current 50 units/month capacity, considering any temporary resource increases?
- `user` `answer`: 10 units/month
- `user` `answer`: 6 months
- `user` `answer`: $1,500/unit
- `assistant` `question`: What is the current standard cost per unit for the first 50 units produced per month?
- `user` `answer`: $1,000/unit
- `assistant` `question`: What is the total cost of materials required per unit for the first 50 units produced per month?
- `assistant` `question`: What is the total cost of materials required per unit for the additional 10 units produced per month beyond the first 50 units?
- `user` `answer`: $600/unit
- `user` `answer`: $900/unit
- `assistant` `question`: What is the total labor cost per unit for the first 50 units produced per month?
- `assistant` `question`: What is the total labor cost per unit for the additional 10 units produced per month beyond the first 50 units?
- `user` `answer`: $400/unit
- `user` `answer`: $600/unit
- `assistant` `ready`: Stage 1 stopped after the 5-round clarification limit. Use the current decision brief with the unresolved notes below.

**Formal Object Produced By Current System**

Stage 1 decision kernel:

- Decision: Decide whether to accept a $5M order for 1,000 units to be delivered in four months.
- Objective: Secure the largest deal in company history while ensuring operational feasibility.
- Success criteria:
  - Deliver 1,000 units within four months.
  - Fulfill the $5M order.
- Constraints mentioned:
  - 1,000 units delivered in four months.
- What we know:
  - A distributor wants to place a $5,000,000 order.
  - This would be the biggest deal in the company's history.
  - The company currently makes 30 units a month.
  - The distributor wants 1,000 units.
  - The delivery deadline is four months.
  - ForgeLine's maximum production capacity is 50 units/month if fully utilized.
  - ForgeLine can produce an additional 10 units/month beyond its 50 units/month capacity using temporary resources.
  - Lead time to procure and install new equipment for permanent capacity increase is 6 months.
  - Cost per unit for additional units beyond 50 units/month is $1,500/unit.
  - Current standard cost per unit for the first 50 units produced per month is $1,000/unit.
  - Total materials cost per unit for the first 50 units is $600/unit.
  - Total materials cost per unit for the additional 10 units is $900/unit.
  - Total labor cost per unit for the first 50 units is $400/unit.
  - Total labor cost per unit for the additional 10 units is $600/unit.
- Unresolved notes:
  - What are the financial implications and profitability of this order?
  - What resources are needed to scale production?
  - What are the risks associated with taking on such a large order?
  - What are the terms and conditions of the distributor's order?

Stage 2 proof draft:

- Claim: ForgeLine can meet the delivery requirement of 1,000 units within the specified four-month timeframe.
- Premises:
  - Order requires 1,000 units to be delivered.
  - Delivery timeframe is 4 months.
  - Maximum standard production capacity is 50 units per month.
  - Additional 10 units per month can be produced with temporary resources.
  - Lead time to install new equipment for permanent capacity increase is 6 months.
- Computations:
  - `c_total_monthly_capacity = p_max_capacity + p_surge_capacity = 60`
  - `c_total_production_in_period = c_total_monthly_capacity * p_delivery_period = 240`
- Comparisons:
  - `c_total_production_in_period >= p_required_units`
- Proposed verdict in draft: `REFUTED`
- Refutation attempt:
  - The calculation assumes that the only sources of production are the standard and temporary surge capacities.
  - The verdict could be overturned if there is existing inventory or if outsourcing production is a viable, unmentioned option.
- Unresolved gaps: none

**Resulting Verdict**

`REFUTED`
