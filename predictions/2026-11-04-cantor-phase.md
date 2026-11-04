# A second dated bet: the phase of the neutrinos on the Cantor cascade

**Written on 4 November 2026**, before looking at any neutrino measurement newer than the PDG 2024 tables.
Anthony Charretier and Claude, with `grm_loop.py`.

## The rule, fixed before the test

The Cantor cascade removes 1/3, then 2/9, then 4/27, 8/81… : each term is the previous one times 2/3, which is the
loop itself (Koide's Q = 2/3), and all the terms together make the whole (their sum is 1).

The charged leptons sit on it: their phase is 2/9 to 8 parts in 10 million (with Q = 2/3 exact, from the electron and
the muon: 0.222222047). The candidate phases for the neutrinos were fixed as the Cantor terms t_n = (1/3)(2/3)^(n-1),
their partial sums, and the lepton phase plus a later term (n <= 6): 16 values.

## What the existing data say (and what that is worth)

With the loop (Q = 2/3, one amplitude in opposition), the measured ratio Δm²₂₁ / Δm²₃₂ = 0.0307 ± 0.0008 (PDG 2024)
allows a neutrino phase between 0.4754 and 0.4825 rad (or its mirror image). One candidate falls inside:
**1/3 + 4/27 = 13/27 = 0.48148** (the first term plus the third). With 16 candidates, a hit like this would happen by
chance about one time in ten: **on its own, not significant.** It was also seen before the rule was written (the phase
0.479 had been computed), which is why only new data can decide.

## The bet

If the neutrino phase is exactly 13/27, the ratio is fixed: Δm²₂₁ / Δm²₃₂ = 0.031230. With Δm²₃₂ = 2.455 × 10⁻³ eV²:

- **Δm²₂₁ = (7.667 ± 0.087) × 10⁻⁵ eV²** (the uncertainty is that of Δm²₃₂);
- masses 0.372, 8.764, 50.32 meV, **sum 59.45 meV**, normal order.

A precise new measurement of Δm²₂₁ (JUNO, by reactor neutrinos) and of Δm²₃₂ will decide: a ratio outside
0.03123 ± 0.0002 once both are known to the per-mille would refute it.

## First check, the same evening, after the bet was written

The first JUNO measurement (arXiv:2511.14593, published after the PDG 2024 tables, looked up only once the bet above was
written): **Δm²₂₁ = (7.50 ± 0.12) × 10⁻⁵ eV²** (normal ordering). The bet said (7.667 ± 0.087) × 10⁻⁵: a difference of
1.1 combined sigma. **Neither confirmed nor refuted**; the measurement leans slightly below. JUNO's precision will
improve several-fold over its next years of data, and Δm²₃₂ will be measured better too: the ratio will then decide.
