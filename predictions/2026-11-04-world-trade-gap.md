# A small dated bet on the world economy: the trade gap of 2025

**Written on 4 November 2026.** Anthony Charretier and Claude, computed by `grm_world.py`.

World exports and world imports of goods and services must be equal: everything sold is bought. In the IMF World
Economic Outlook (October 2026) the world exports more than it imports, by a gap that grew from about zero around
2000 to 1117 billion dollars in 2024 (3.4 % of world exports).

The GRM network writes this as a hidden node proportional to world exports, whose share drifts in time
(2.27 % in 2010, +0.061 point a year; the drift beats a constant share by 63 in the Bayesian information criterion).
Of the three carriers fixed in advance (world GDP, world exports, the oil price), world GDP and world exports explain
the year-to-year changes of the gap better than chance (permutation p = 0.0002 and 0.002) and better than 165 of the
170 placebo series; nothing explains the income part, and the network refuses to invent a carrier for it.

**The bet**, with the IMF's own projected exports for 2025:

| | world trade gap 2025 (billions of USD) |
|---|---|
| GRM node with drift | **+1107** |
| GRM node, constant share | +920 |
| IMF projection (WEO October 2026) | +1170 |

Decided when the IMF publishes the 2025 balance of payments as measured (World Economic Outlook, probably April or
October 2027): the GRM node wins if the measured gap is closer to 1107 than to 1170. This is a modest bet (the two
values are close, and the IMF projection is made by people who see far more data); it is written down so that it can
be checked, not because it is likely to be decisive.
