# Computational Evidence Status

## Active Package Classification

| Package | Classification | Evidential function |
|---|---|---|
| v35 | deterministic design-space prioritization matrix | ranks configured gas and sequence candidates |
| v35.1 | deterministic engineering design scoring | ranks configured channels, sequences, and a candidate protocol |
| v35.2 | Monte Carlo configuration screening | propagates configured coefficients and seeded perturbations through algebraic screening rules |
| v35.3 | theorem package with embedded corrected v35.2 screening evidence | preserves the theorem and its computational boundary |
| FINAL_THEOREM_PACKAGE_REBUILT_TRUE | publication core with corrected evidence classification | separates formal results from screening evidence |

## Corrected v35.2 Ranking

    em_only
    → hybrid_em_retention
    → hybrid_balanced
    → hybrid_soft
    → acoustic_only

This ranking is internal to the configured screening equations. It is not a measurement of physical channel superiority.

## Critical Scaling Synchronization

The corrected cubic specialization is:

```text
dC/dt = vtC − gC³
C_critical ~ g^(−1/2)v^(1/4)
t_delay ~ v^(−1/2)
```

The generalized linearly ramped class is:

```text
dC/dt = vtC − gC^n
C_critical ~ g^(−1/(n−1))v^(1/(2(n−1)))
t_delay ~ v^(−1/2)
```

for g > 0 and n > 1.

The amplitude exponent depends on the saturation order. The temporal exponent −1/2 does not: it is fixed by the derivative–ramp balance while the critical ramp retains the form vtC.

Under geometric dimensional closure, `V_coh,d ∝ C^d` and `n = d`. The full-volume three-dimensional specialization gives `V_coh,3 ∝ C³` and recovers the cubic amplitude exponent 1/4 without changing the delay exponent.

## Successor Dynamic Evidence Requirements

- explicit time integration of state variables
- matched `F_ext = 0` controls for every parameter point and seed
- coupling regimes near the applicable critical threshold
- one frequency convention throughout equations, code, and reports
- separate diagnostics for phase order, general coherence, and endogenous contribution
- post-drive comparison against control over a defined retention interval

## Public-Language Closure

The remaining public-facing evidence labels were synchronized after the first corrective pass.

Closed items:

- root repository sections now distinguish computational evidence, evaluation, scoring, screening, and independent dynamic evidence,

- the historical archive README now identifies preserved packages as computational history rather than current proof,

- v35 uses `legacy_reference_ratio` for the historical input coefficient without changing numerical rankings,

- the final theorem package identifies separate versioned packages as computational evidence packages,

- and obsolete one-time correction workflow files are removed after the closure run.
