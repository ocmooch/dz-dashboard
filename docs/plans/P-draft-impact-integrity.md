# P — Draft impact integrity and exploration

## Summary

Follow-up to `P-draft-impact-model`: repair identity-aware draft scoring, prevent raw
quarterback point scale from dominating weighted steals, and make the leaderboard and chart
share one Weighted/Points lens.

## Implementation

- Resolve scored/raw rows through `player_identity_links`, preferring the drafted id per week
  and falling back to linked members without double counting.
- Keep raw `value` as points over slot expectation. Weighted `impact` standardizes that value
  within QB/RB/WR/TE before applying draft-capital and bust carry weights; K/DEF remain in the
  board and points lens but are excluded from weighted rankings.
- Return up to nine weighted and points-only steals/busts. Normalize rounded negative zero.
- Use one frontend lens for both lists and chart; expand each list 3→6→9; filter the chart by
  position, round, and team; order by selected metric or draft order.
- Preserve dotted initial names and constrain long historical team labels without rewriting
  source data.

## Tests / done when

- Identity-cluster precedence, negative-zero, normalized weighting, ineligible positions, and
  dual ranking contract coverage.
- Component coverage for lens synchronization, expansion, filters, sorting controls, and
  dotted initials.
- Full backend/frontend gate and real-DB checks for 2019 Mike Williams, 2025 Elic Ayomanor,
  2019 A.J. Green, and 2025 weighted-vs-points ordering.
