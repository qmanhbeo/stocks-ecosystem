# Session 335 Log — Transition Dynamics as Alpha (2026-05-17)

## Objective

Test the first Eureka hypothesis from the carry-branch completion:
- **H522: Transition Dynamics as Alpha**

Question:
- Do transition events (time-in-state, transition_to_X flags) capture info that static state labels lose?
- H507 found coherent transition flow (onset/amplified/router -> carry -> quiet) with self-transition probability 0.8692
- This tests whether the transitions themselves are the alpha, not just the static states

This session does not read `2026+`.
It does not optimize portfolio construction.

---

## What changed

Added one structural script:
- `analysis/h522_transition_dynamics_alpha.py`

### H522 - transition_dynamics_alpha

**Hypothesis:**
Transition events (time-in-state, transition_to_X flags) capture info that static state labels lose.

**Command / code:**
`python analysis/h522_transition_dynamics_alpha.py`

**Inputs:**
- Same panel as H507 (2015-2025, 826,404 rows)
- Latent state labels: quiet, onset, amplified, router, carry

**Transition features computed:**
- `just_transitioned`: any state change from previous day (108,053 rows)
- `transition_to_onset`: entered onset from another state (10,396 rows)
- `transition_to_amplified`: entered amplified from another state (15,150 rows)
- `transition_to_carry`: entered carry from another state (35,078 rows)
- `transition_to_router`: entered router from another state (11,890 rows)
- `enter_active`: quiet -> active (any) transition (27,383 rows)
- `return_to_quiet`: active -> quiet transition (27,015 rows)
- `days_in_state_q4`: long duration in current state (top 20%)
- `days_in_state_q1`: short duration in current state (bottom 20%)

**Saved artifact:**
`artifacts/run_summaries/20260517_140052_transition_dynamics_alpha_research_branch.json`

| State | IC | Rows | Positive Years |
|-------|----|------|----------------|
| state_router (static) | 0.2258 | 12,983 | 11/11 |
| transition_to_router | 0.2246 | 11,890 | 11/11 |
| state_onset (static) | 0.2222 | 35,103 | 11/11 |
| enter_active (transition) | 0.2221 | 27,383 | 11/11 |
| transition_to_onset | 0.2140 | 10,396 | 11/11 |
| just_transitioned | 0.2133 | 108,053 | 11/11 |
| transition_to_amplified | 0.2120 | 15,150 | 11/11 |
| return_to_quiet | 0.2072 | 27,015 | 11/11 |
| state_carry (static) | 0.2018 | 35,078 | 11/11 |
| transition_to_carry | 0.2018 | 35,078 | 11/11 |
| days_in_state_q1 | 0.1961 | 165,555 | 11/11 |
| all_rows (baseline) | 0.1302 | 826,404 | 11/11 |
| days_in_state_q4 | 0.0864 | 165,456 | 5/11 |

**Key comparisons:**
- Baseline IC: 0.1302
- Static best IC: 0.2258 (`state_router`)
- Transition best IC: 0.2246 (`transition_to_router`)
- **Transition vs Static lift: -0.0012** (essentially zero)
- Duration best IC: 0.1961 (`days_in_state_q1`)
- Long duration (`days_in_state_q4`) is anti-predictive (only 5/11 positive years!)

**Result:**
The transition features do **NOT** capture additional information beyond static states.
- Best transition (`transition_to_router` = 0.2246) is essentially identical to static (`state_router` = 0.2258)
- Transition vs static lift is -0.0012 (within noise)
- Duration features do not help: long duration is actually negative
- The coherent flow pattern H507 found is **structural, not predictive incremental**

**Verdict: FAILED**

---

## Branch decision

**H522 is a negative finding**: Transition events are NOT the alpha - the static states ARE the signal.

Key insight: The latent-state structure (quiet/onset/amplified/router/carry) is real and stable, but the transitions between states do not add predictive value beyond the static state labels themselves.

Next best action:
- Move to hypothesis 2 in the Eureka queue: **Cross-Sectional Relative State Encoding**
- Test if relative state (vs market, vs sector) beats absolute state encoding

---

## Validation

Completed during the pass:
- ran `python -m py_compile analysis/h522_transition_dynamics_alpha.py`
- ran `python analysis/h522_transition_dynamics_alpha.py`
- read saved run summary
- confirmed protocol guardrails: 2015-2025 only, no target-derived states
- verified all transition features have 11/11 positive years (stable)