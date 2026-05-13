# Findings 241-270

## F241: H322 Keeps The H321 Cascade State As Offline Timing Evidence, Not An Additive Promotion (2026-04-09, Session 142)

Session 142 tested the immediate follow-up after the H321 pass:
- does `today_self_accel_high` add enough value over the frozen
  `S1 / C4 / C13` core to justify promotion?

The test reused:
- the saved H321 panel
- `xs_rl_signal_matrix.parquet`
- the same simple multiplicative core-overlay pattern used in H317

The H321 state stayed real as a sparse standalone timing cohort:
- state:
  - `today_self_accel_high`
- validation / confirmation binary-state IC:
  - `+0.0046 / +0.0072`
- validation / confirmation active lift:
  - `+0.0288 / +0.0570`
- pooled correlations with core ranks:
  - `S1`: `+0.0066`
  - `C4`: `+0.0068`
  - `C13`: `-0.0059`

So the state is nearly orthogonal and has a meaningful active-row response.
But the full-universe additive effect is tiny.

The best additive overlay was:
- variant:
  - `core_mul__today_self_accel_high__50`
- validation / confirmation IC delta vs frozen core:
  - `+0.00015 / +0.00005`
- validation / confirmation spread delta vs frozen core:
  - `+0.00018 / -0.00021`
- validation / confirmation IC delta vs matched H310 follow-up control:
  - `+0.00076 / +0.00044`
- validation / confirmation IC delta vs H310 novelty control:
  - `-0.00012 / +0.00017`

This fails the promotion bar. The result is not a contradiction of H321: it
says the cascade label is a useful sparse event-timing diagnostic, but too
sparse to materially improve the frozen daily ranker through a blunt overlay.

### Key finding
The self-exciting event-v2 cascade state is real but not promotable as a core
additive feature on the current representation. H322 repeats the H317 lesson:
event-v2 timing can produce strong cohorts, but the current frozen core does
not benefit enough from simple event overlays.

**Implication:** keep `today_self_accel_high` as offline timing evidence only.
Do not continue local event-v2 overlay tuning on the current core. Move the
next current-data creative queue item to `policy-beneficiary-graph`, while the
highest-value acquisition queue remains `historical-foreign-flow-source`.

## F242: H323 Finds A Usable CafeF Public-Investment Corpus But No Promotable Beneficiary Router (2026-04-09, Session 143)

Session 143 tested the first political-economy beneficiary branch:
- can raw CafeF public-investment / infrastructure policy news predict
  explicitly mapped listed beneficiaries?

The branch used a deliberately tiny manual map:
- direct beneficiaries:
  - `Xây dựng và Vật liệu`
  - `55` tickers
- second-order beneficiaries:
  - `Bất động sản`
  - `57` tickers
- rest basket:
  - `282` tickers

The local source was not the blocker. A predeclared title / summary keyword
scan of the raw CafeF archive found:
- unique policy articles:
  - `5,964`
- trading signal days:
  - `744`
- article assignment:
  - first trading day on or after publication
- evaluation window:
  - `2023-2025`

The best state was:
- `policy_total_5d_high`
- definition:
  - high combined public-investment / infrastructure article count over the
    trailing `5d`, using the dev `q80` threshold

It showed weak beneficiary-state structure:
- validation / confirmation active days:
  - `96 / 211`
- validation / confirmation direct public-works `fwd5` edge vs rest:
  - `+0.0010 / +0.0023`
- validation / confirmation `fwd5` diff-in-diff:
  - `+0.0032 / +0.0007`

But it failed the promotion bar:
- validation / confirmation actual diff-in-diff:
  - `+0.0027 / -0.0006`
- validation / confirmation direct-minus-real-estate `fwd5`:
  - `+0.0048 / -0.0012`

So the direct public-works basket does not cleanly own the policy response.
Real estate catches or beats the direct basket in confirmation, which is
consistent with the older H292 lesson that macro / policy themes behave more
like broad balance-sheet or property states than crisp sector routers.

### Key finding
The local CafeF corpus is sufficient for a public-investment policy pilot, but
the simple manual beneficiary graph is not strong enough to promote. The
political-economy channel remains interesting as a data / mapping problem, not
as a current direct-public-works router.

**Implication:** keep the raw policy corpus and H323 daily panel as offline
evidence. Do not expand the branch without a better policy-event source or a
more explicit beneficiary graph. Move the next honest queue item to
`historical-foreign-flow-source`.

## F243: H324 Confirms Real Historical Foreign Flow Is Still Source-Blocked Locally (2026-04-09, Session 144)

Session 144 tested the acquisition queue item after H323:
- is there any real historical per-ticker foreign buy/sell or foreign-room
  table available locally?

The answer is no.

The local source-gate scan found only two relevant maintained surfaces:
- `data/features/xs_foreign_demand_daily.parquet`
- `data/fx-commodities/fx_commodities_vnm_etf_1D.parquet`

The real-source counts were:
- real historical per-ticker foreign-flow candidates:
  - `0`
- schema fragments with foreign buy/sell/room fields:
  - `0`

The existing surfaces are proxies:
- `xs_foreign_demand_daily.parquet`
  - `826,404` rows
  - `394` tickers
  - `2015-01-05` to `2025-12-31`
  - VNM ETF affinity / premium proxy
  - archive-only after H110 failed
- `fx_commodities_vnm_etf_1D.parquet`
  - `4,182` rows
  - `2009-08-14` to `2026-03-31`
  - date-level ETF price surface
  - not per-ticker foreign flow

The live vnstock probe with network permission did not unblock the branch:
- installed package:
  - `vnstock 3.5.0`
- no available method:
  - `quote.history_foreign_ownership`
- current-day board fields:
  - available through `price_board`
  - not backtestable as historical daily data

So this remains the same scientific state as F59, but now with a fresh
source-gate artifact after the recent acquisition queue reopened the question.

### Key finding
Historical foreign flow is not falsified as a mechanism, but it is still not
testable in this workspace. The only local surfaces are the already-failed VNM
ETF proxy family.

**Implication:** do not retest H110-style proxies as the historical foreign-flow
branch. Keep H95 blocked until a real historical source is acquired, or start a
forward-only collector for current-day board foreign fields. Move the next
acquisition queue item to `queueing-open-fill-source`.

## F244: H325 Confirms Queue / Open-Fill Alpha Is Source-Blocked By Missing Microstructure History (2026-04-09, Session 145)

Session 145 tested the next acquisition queue item after H324:
- does the canonical warehouse contain any historical auction, order-book,
  opening-queue, or fine-minute source that can honestly test queue imbalance
  / open-fill pain?

The answer is no.

The source-gate scan found:
- source-looking paths:
  - `13,637`
- true historical queue / order-book candidates:
  - `0`
- true fine-minute candidates:
  - `0`

The local intraday estate is broad but reduced:
- CafeF hourly yearly parts:
  - `11,996`
- raw CafeF hourly files:
  - `404`
- adjusted CafeF hourly files:
  - `404`
- legacy shallow hourly files:
  - `9`
- adjustment factor files:
  - `810`
- derived daily intraday summaries:
  - `1`

Representative sampled hourly schemas were only:
- `time`
- `open`
- `high`
- `low`
- `close`
- `volume`

The sampled hourly shape confirms the resolution limit:
- median bars/day:
  - `4.0`
- max bars/day:
  - `5`

So the current source can support reduced-shape intraday research, but not the
microstructure question. It cannot measure bid/ask imbalance, queued buy/sell
pressure at the open, order-book depth, order arrival, or a fine-minute tape.

The first implementation pass also caught a useful failure mode: broad substring
matching can mistake `ticker`, ticker `BID`, `order_date`, `insider`, and
`barrier_depth` for microstructure evidence. H325 now uses stricter token-level
classification so the source gate does not promote false positives.

### Key finding
Queue / open-fill alpha is not falsified as a mechanism, but it is not testable
with the current local data. Hourly OHLCV and price-limit blocked-buy proxies
must not be relabeled as queue imbalance.

**Implication:** keep queue/open-fill research acquisition-blocked until a real
auction/order-book/fine-minute source is acquired. Move the next cheap data
unlock to `forward-foreign-flow-collector`, with explicit metadata that the
collector will be forward-only and not immediately backtestable.

## F245: H326 Starts A Forward-Only Foreign-Flow Archive From Current-Day VCI Board Fields (2026-04-09, Session 146)

Session 146 implemented the only cheap continuation after H324 confirmed real
historical foreign flow is unavailable:
- start collecting current-day board foreign fields forward-only
- keep the contract explicitly non-backtestable until enough future history
  accrues

The producer is:
- `data_tools/collect_forward_foreign_flow.py`

The canonical root is:
- `data/foreign_flow_forward/vci_price_board/`

The written surfaces are:
- `snapshots/YYYY-MM-DD/vci_price_board_foreign_flow_YYYYMMDDTHHMMSSZ.parquet`
- `latest_snapshot.parquet`
- `daily_latest.parquet`
- `manifest.json`

The contract keeps these normalized fields:
- `collected_at_utc`
- `ticker`
- `trading_date`
- `current_room`
- `total_room`
- `foreign_buy_volume`
- `foreign_sell_volume`
- `foreign_net_volume`
- `foreign_buy_value`
- `foreign_sell_value`
- `foreign_net_value`
- `foreign_room_used_ratio`

H326 validated two things:
- the normalizer correctly handles vnstock's MultiIndex `price_board` schema
- the live VCI board path can produce a full local-HOSE snapshot

The first full run captured:
- rows:
  - `404`
- tickers:
  - `404`
- board trading date:
  - `2026-04-09`
- failed chunks:
  - `0`

Example current-day extremes from the first snapshot:
- largest positive net foreign value:
  - `HPG +482.15B VND`
- largest negative net foreign value:
  - `VPL -3.284T VND`

This is not an alpha result. With one collected day, there is no honest
historical test. The value of H326 is that the workspace is no longer passively
blocked on this surface: every future run adds real forward evidence.

### Key finding
Current-day VCI board fields are sufficient to start a real per-ticker
foreign-flow archive, but only forward from collection time. This is a data
acquisition pass, not a predictive-signal promotion.

**Implication:** run the collector daily after market close. Do not build or
backtest foreign-flow features from this surface until enough forward days
exist and a source-quality audit passes.

## F246: CafeF GDKhoiNgoai Exposes Historical Daily Foreign Flow And Reopens H95 Source Acquisition (2026-04-09, Session 146)

The earlier H324 conclusion was too narrow. It correctly showed that vnstock /
VCI did not expose historical per-ticker foreign flow locally, but it did not
mean the broader source class was absent.

A direct CafeF page + endpoint probe found that the stock-history `Khối ngoại`
tab is backed by:
- `cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDKhoiNgoai.ashx`

The endpoint returns per-ticker daily rows including:
- `KLMua`
- `GtMua`
- `KLBan`
- `GtBan`
- `KLGDRong`
- `GTDGRong`
- `RoomConLai`
- `DangSoHuu`
- `ThayDoi`

Representative live probes confirmed real historical depth:
- `FPT`
  - returned rows:
    - `4,769`
  - oldest observed date:
    - `2006-12-13`
- `VCB`
  - oldest observed date:
    - `2009-06-30`
- `HPG`
  - oldest observed date:
    - `2007-03-01`
- `ACB`
  - oldest observed date:
    - `2007-01-02`

Session 146 then wired a raw historical fetcher:
- `data_tools/fetch_cafef_foreign_flow.py`

Its raw canonical outputs are:
- `data/foreign_flow/cafef/per_ticker/<TICKER>.parquet`
- `data/foreign_flow/cafef/foreign_flow_daily.parquet`
- `data/foreign_flow/cafef/manifest.json`

The first live validation pull covered:
- tickers:
  - `2`
- rows:
  - `5,604`
- window:
  - `2015-01-01` to `2026-04-09`
- failures:
  - `0`

### Key finding
Historical foreign flow is available after all, but via CafeF rather than
vnstock. The source question is now resolved; the remaining work is source
quality audit and honest signal testing.

**Implication:** unblock `H95` from acquisition-blocked status. The next honest
step is not another source search. It is:
- align CafeF foreign-flow rows to the local trading calendar
- quantify ticker/date coverage and missingness
- test the smallest honest raw and lagged foreign-flow features

## F247: H327 Source-Audits CafeF Foreign Flow As Usable But Rejects The First Raw Feature Screen (2026-04-09, Session 147)

Session 147 completed the first honest source-quality audit and raw feature
screen after the CafeF `GDKhoiNgoai` source was found.

The full local backfill contains:
- tickers:
  - `404`
- rows:
  - `1,353,462`
- date range:
  - `2001-04-02` to `2026-04-09`
- fetch failures:
  - `0`

The producer is:
- `data_tools/fetch_cafef_foreign_flow.py`

Two fetcher defects were fixed during the monitored backfill:
- partial probe caches were not enough to prove full requested coverage
  - per-ticker `.meta.json` coverage sidecars now record the requested window
- subset reruns could clobber the combined panel with only the requested names
  - the combined panel is now rebuilt from all per-ticker caches on disk

`H327` then audited the source against the local stock calendar over
`2015-2025`:
- row coverage:
  - `98.80%`
- tickers with any flow:
  - `399`
- tickers with at least `60%` coverage:
  - `399`
- duplicate ticker-day rows:
  - `0`
- net volume mismatches:
  - `0`
- net value mismatches:
  - `0`

Known source gaps remain:
- `AAA`
- `YBM`
- `YEG`

These names had local stock-history rows in the `2015-2025` audit window but no
CafeF foreign-flow rows in that window.

The first predictive screen used the frozen 2015-2025 protocol:
- dev:
  - `2015-2022`
- validation:
  - `2023-2024`
- confirmation:
  - `2025`
- no tuning:
  - `2026+`

The best raw feature was:
- `xs_ff_room_scarcity_rank`

It produced:
- dev IC:
  - `+0.0117`
- dev directional years:
  - `7 / 8`
- validation IC:
  - `+0.0074`
- confirmation IC:
  - `-0.0048`
- corr vs `S1`:
  - `-0.0028`

### Key finding
The CafeF foreign-flow source is research-usable, but the first raw buy/sell/net
flow and room-scarcity feature set is not promotable. The near-pass is
orthogonal to `S1`, but it fails 2025 confirmation.

**Implication:** `H95` is no longer source-blocked, but raw foreign-flow ranks
are not a signal-library candidate. Do not publish a feature from H327.

## F248: H328 Shows High Foreign Participation And Room Scarcity Do Not Rescue Raw CafeF Flow Ranks (2026-04-09, Session 147)

Session 147 ran one constrained follow-up after H327:
- test whether raw foreign-flow ranks only work inside high foreign
  participation states
- test whether raw foreign-flow ranks only work inside high room-scarcity states

The screen reused the same honest predictive protocol:
- dev:
  - `2015-2022`
- validation:
  - `2023-2024`
- confirmation:
  - `2025`
- no tuning:
  - `2026+`

The tested states were:
- `foreign_participation_top30`
- `foreign_participation_top20`
- `room_scarcity_top30`
- `room_scarcity_top20`

The tested raw flow feature families were small and predeclared:
- `xs_ff_net_vol_share_1d_rank`
- `xs_ff_net_vol_share_1d_lag1_rank`
- `xs_ff_net_vol_share_5d_rank`
- `xs_ff_net_vol_share_5d_lag1_rank`
- `xs_ff_buy_share_5d_rank`
- `xs_ff_sell_share_5d_rank`

The best row was:
- state:
  - `foreign_participation_top30`
- feature:
  - `xs_ff_buy_share_5d_rank`
- orientation:
  - negative
- dev IC:
  - `-0.0088`
- validation IC:
  - `-0.0147`
- confirmation IC:
  - `+0.0079`
- corr vs `S1`:
  - `-0.0398`

### Key finding
High foreign participation and high room scarcity do not rescue simple CafeF
foreign-flow ranks. The strongest conditioned row flips sign in 2025, and the
dev IC is below the standalone signal gate.

**Implication:** close the raw buy/sell/net-rank path. If `H95` continues, it
must be a materially different thesis such as:
- room-change events
- ownership-regime transitions
- near-limit foreign-room discontinuities
- sector-specific foreign ownership pressure

## F249: H329 Shows Title-Sequence Novelty Distillation Recovers Some Teacher Structure But Does Not Preserve The Short-Horizon Novelty Contract (2026-04-09, Session 148)

Session 148 ran the first honest cheap non-API continuation from the LLM-news
branch:
- do not retry the dead keyword-sentiment path
- do not claim a full deterministic replacement up front
- test whether deterministic title / summary / article-sequence rules can
  recover enough of the saved LLM novelty labels to preserve the novelty
  half-life evidence from `H290/H291`

The teacher surface was restricted to ticker-tagged cached rows with usable
novelty labels:
- teacher article rows:
  - `12,295`
- teacher cached days:
  - `728`
- teacher date range:
  - `2015-09-21` to `2018-01-03`
- holdout slice:
  - `2017`

The deterministic classifier did recover real novelty structure versus a naive
baseline:
- holdout macro-F1:
  - `0.3965`
- naive `always_new` macro-F1:
  - `0.3107`
- holdout macro-F1 delta:
  - `+0.0858`
- holdout balanced accuracy:
  - `0.3971`

But the hard short-horizon novelty state remained weak:
- holdout `follow_up` precision:
  - `0.1255`
- holdout `follow_up` recall:
  - `0.0673`
- holdout `follow_up` F1:
  - `0.0876`

The more important test was whether the reconstructed novelty labels preserved
the saved teacher-alpha directions:
- preserved key contracts:
  - `1 / 3`
- `1d follow_up` teacher / deterministic IC:
  - `+0.0023 / -0.0142`
- `5d follow_up_minus_new` teacher / deterministic IC:
  - `-0.0025 / +0.0053`
- `30d new` teacher / deterministic IC:
  - `+0.0108 / +0.0092`

### Key finding
Title-sequence novelty distillation is not a dead end, because it recovers
meaningful teacher-label structure above a naive baseline. But it is not strong
enough to replace the LLM novelty branch on its own: the key `follow_up`
bucket remains too lossy, and only one of the three key novelty contracts keeps
the teacher sign.

**Implication:** do not continue retuning novelty-only deterministic rules in
isolation. If the cheap branch continues, move to:
- hybrid deterministic-first routing with API only for ambiguous rows
- broader teacher-state distillation on more lexical fields such as
  `event_type`, `expectation_alignment`, `impact_scope`, and
  `source_authority`

## F250: H330 Shows A Hybrid Novelty Cascade Can Save Large API Share, But It Still Fails The `1d follow_up` Contract (2026-04-10, Session 149)

Session 149 ran the next honest cheap non-API continuation after `H329`:
- keep the novelty rules from `H329`
- use them only as a deterministic-first confidence screen
- route the ambiguous rows back to the teacher as an oracle fallback
- test whether that hybrid contract preserves the saved novelty-alpha evidence
  while reducing API demand materially

The audit used the same ticker-tagged teacher window:
- teacher article rows:
  - `12,295`
- teacher date range:
  - `2015-09-21` to `2018-01-03`
- policy ladder:
  - `5` predeclared hybrid policies from strict to aggressive

The hybrid cascade did recover much more teacher-label structure than the pure
deterministic student:
- pure deterministic holdout macro-F1:
  - `0.3965`
- best hybrid holdout macro-F1:
  - `0.8840`
- pure deterministic holdout `follow_up` F1:
  - `0.0876`
- best hybrid holdout `follow_up` F1:
  - `0.8235`

It also showed that a large share of API traffic can be avoided:
- best cost / contract trade-off policy:
  - `aggressive_triple`
- best-policy API article share:
  - `0.2028`
- best-policy API text share:
  - `0.2035`
- best-policy preserved contracts:
  - `2 / 3`

But the more important result is what failed to recover:
- every tested hybrid policy preserved only:
  - `2 / 3`
- the failed contract in every policy was:
  - `1d follow_up`
- even the strict new-only cascade, which routed:
  - `58.9%` of articles
  - `60.2%` of article text
  back to the teacher, still left `1d follow_up` negative

### Key finding
The hybrid novelty cascade is real as a cost-reduction mechanism, but it still
does not preserve the short-horizon novelty contract that matters most. The
remaining information loss is concentrated in the `1d follow_up` line, and more
novelty-only cascade retuning is unlikely to change that.

**Implication:** do not continue the cheap branch with more novelty-only
distillation or cascade tuning. If the surrogate branch continues, move to:
- more lexical teacher fields such as `event_type`,
  `expectation_alignment`, `impact_scope`, and `source_authority`
- disagreement-residual tests that treat the teacher-fallback tail itself as a
  possible signal source

## F251: H331 Shows Direct Lexical Event-Family Routing Recovers Some Structure, But It Does Not Beat The Old Keyword Baseline Or Preserve The Key Authority State (2026-04-10, Session 150)

Session 150 ran the next honest cheap non-API continuation after `H330`:
- move off novelty-only routing
- test more lexical teacher fields directly from article text
- compare the rebuilt field routers with both teacher-state preservation and
  the old keyword-news baseline

The audited teacher surface stayed on the same ticker-tagged window:
- teacher article rows:
  - `12,378`
- teacher date range:
  - `2015-09-21` to `2018-01-03`
- tested field families:
  - `source_authority`
  - `expectation_alignment`
  - `impact_scope`
  - sparse focused `event_type`

The lexical router did recover meaningful article-level structure on several
fields:
- `source_authority` held-out macro-F1 delta vs train-majority:
  - `+0.1514`
- `impact_scope` held-out macro-F1 delta:
  - `+0.4364`
- sparse `event_type` held-out macro-F1 delta:
  - `+0.4458`
- preserved field champions:
  - `3 / 4`

But the broad branch still failed on the parts that mattered most:
- failed teacher champion:
  - `source_authority__rumor_source`
- teacher / deterministic mean IC:
  - `+0.0678 / -0.0848`
- weak field:
  - `expectation_alignment`
- its held-out macro-F1 delta:
  - `+0.0244`

The final bar was not cleared against the dead keyword path:
- best deterministic feature:
  - `source_authority__rumor_source`
  - abs IC `0.0848`
- best keyword baseline feature:
  - `sentiment_score`
  - abs IC `0.1303`
  - matched rows `609`

### Key finding
Direct lexical routing is not empty. It can recover real structure in
`impact_scope`, some authority buckets, and the densest event-type families.
But it still does not reopen the cheap branch as a broad replacement path: the
most important authority state flips sign, `expectation_alignment` stays weak,
and the best deterministic feature still trails the old keyword-news baseline
on the audited `5d` target.

**Implication:** close the direct lexical-router continuation on the current
contract. If the cheap branch continues, move to:
- disagreement-residual tests using student-teacher gaps or teacher-fallback
  rows themselves
- more selective narrow follow-ups only if a future branch needs one isolated
  lexical field rather than a broad replacement surface

## F252: H332 Shows The Surrogate Disagreement Tail Does Not Hold The Remaining News Reaction; Deterministic-Safe Rows Still React More Strongly (2026-04-10, Session 151)

Session 151 ran the last honest cheap non-API continuation after `H331`:
- take the best `H330` hybrid contract (`aggressive_triple`)
- merge it with the `H331` student-teacher field disagreements
- test whether the remaining short-horizon signal sits in:
  - teacher-fallback rows
  - novelty-disagreement rows
  - high lexical-disagreement rows
  - the combined hard tail

The residual audit built a ticker-day panel from the teacher window:
- panel rows:
  - `18,640`
- panel dates:
  - `728`
- panel tickers:
  - `2,073`
- deterministic-safe control rows:
  - `6,209`
- hard-tail rows:
  - `12,431`

The disagreement tail was not empty on signed means:
- `hard_tail_day` signed uplift vs `safe_only`:
  - `+0.00017 / +0.00093`
  - on `1d / 5d`
- best signed uplift state:
  - `lexical_2plus_day`
  - `+0.00025 / +0.00062`

But the more important result is that every residual state had weaker absolute
post-news reactions than the deterministic-safe control:
- `fallback_day` absolute uplift vs `safe_only`:
  - `-0.00104 / -0.00269`
- `novelty_disagree_day`:
  - `-0.00202 / -0.00417`
- `lexical_2plus_day`:
  - `-0.00011 / -0.00137`
- `hard_tail_day`:
  - `-0.00124 / -0.00303`

The daily ICs were not enough to rescue the line:
- `hard_tail_day` mean IC:
  - `+0.0049 / +0.0188`
- `lexical_2plus_day` mean IC:
  - `-0.0046 / -0.0021`

### Key finding
The teacher-fallback / disagreement tail is not where the remaining useful
reaction sits on the current teacher window. The residual rows have slightly
better signed means than deterministic-safe rows, but consistently weaker
absolute reactions. That points in the opposite direction from the desired
cheap-LLM continuation.

**Implication:** close the current cheap non-API surrogate branch on the
`2015-2017` teacher window. `H329/H330/H331/H332` together exhaust the obvious
deterministic continuations. Do not continue this branch without:
- more cache years
- new labels
- or a materially different contract

## F253: H333 Shows Foreign Room Residual Discontinuities Are Structured But Not Predictive Enough To Reopen H95 (2026-04-10, Session 153)

Session 153 ran the first distinct H95 continuation after `H327/H328` rejected
raw and conditioned CafeF foreign-flow ranks:
- compute the room-mechanics residual:
  - `delta(foreign_room_remaining) + foreign_net_volume`
- separate idiosyncratic residual shocks from systemic reset days
- test both dense residual ranks and sparse top-tail discontinuity states
- evaluate both `T+1` (`actual`) and `T+5` (`fwd_rel_5d`) drift on
  `2015-2025`, with `2026+` excluded from the predictive decision

The room mechanics are structured:
- merged rows:
  - `817,074`
- residual exact-zero share:
  - `65.64%`
- systemic reset days:
  - `288`

But the dense residual ranks failed:
- best dense feature:
  - `xs_ff_room_residual_loosen_rank`
- dev / validation / confirmation IC:
  - `-0.0044 / -0.0109 / +0.0132`
- corr vs S1:
  - `-0.0226`

And the sparse event states failed:
- best event state:
  - `room_residual_systemic_abs_top5`
- validation / confirmation actual lift:
  - `-0.0724 / +0.0137`
- validation / confirmation `fwd5` lift:
  - `-0.0033 / +0.0090`
- passing dense features:
  - `0`
- passing event states:
  - `0`

### Key finding
The residual branch is real as source mechanics, but not as an alpha branch on
the current contract. Room residual discontinuities cluster and are not just
random scraper noise, but neither idiosyncratic nor systemic top-tail states
keep validation and confirmation signs together.

**Implication:** do not keep thresholding
`delta(foreign_room_remaining) + foreign_net_volume`. If H95 continues, move to
a materially different foreign-state thesis such as accumulation change-points,
foreign-friction interaction, or foreign-insider agreement.

## F254: H334 Shows A Constrained Legal-Exit Oracle Has Enough Upper-Bound Uplift To Justify One Smart-Exit Distillation Attempt (2026-04-10, Session 154)

Session 154 tested the first smart-exit ML gate before training any model:
- keep the frozen `full_library` top-5 / rebalance-5 backbone
- use actual executed buy entries from the simulated blotter
- allow only predeclared legal exits:
  - `3d`
  - `5d`
  - `10d`
  - `15d`
- if a scheduled exit is sell-blocked, use the first legal sell thereafter
- score utility as relative return minus a drawdown penalty:
  - `relative_return - 0.25 * open-path MAE`
- exclude `2026+` from the predictive decision

The audit covered:
- entries:
  - `2,578`
- horizon rows:
  - `10,295`
- tickers / entry dates:
  - `359 / 548`
- round-trip cost:
  - `0.30%`

The best fixed horizon was `3d` in every phase:
- dev fixed `3d` utility:
  - `-0.0003`
- validation fixed `3d` utility:
  - `-0.0018`
- confirmation fixed `3d` utility:
  - `-0.0068`

But the constrained oracle had material uplift:
- dev oracle utility / uplift:
  - `+0.0593 / +0.0596`
- validation oracle utility / uplift:
  - `+0.0382 / +0.0400`
- confirmation oracle utility / uplift:
  - `+0.0372 / +0.0440`

The oracle choice was not degenerate:
- validation non-best-fixed horizon choice rate:
  - `64.78%`
- confirmation non-best-fixed horizon choice rate:
  - `53.74%`

### Key finding
The current fixed-horizon exit contract is leaving a large upper-bound gap, but
the gap is not deployable by itself because the oracle uses future path
outcomes. This branch passes only as offline evidence that an exit target is
worth learning.

**Implication:** advance to `exit-mdp-lite` or `discrete-exit-hazard` before any
neural/offline-RL variant. The next model must use only information available
at entry or the current hold day and must recover a material share of oracle
uplift strictly walk-forward. Do not deploy or tune against the oracle directly.

## F255: H335 Fails To Distill The Legal-Exit Oracle With A Simple Hold/Sell MDP-Lite Policy (2026-04-10, Session 155)

Session 155 tested the first learned smart-exit distillation after `H334`:
- consume the H334 legal-horizon outcomes
- create decision rows at scheduled legal exits:
  - `3d`
  - `5d`
  - `10d`
- label a row as "hold" if a later legal horizon has higher H334 utility
- train a regularized logistic classifier on dev only
- run a sequential policy with fixed threshold `0.50`
- compare against the best fixed horizon and the H334 oracle
- exclude `2026+`

The panel covered:
- decision rows:
  - `7,717`
- policy entries:
  - `2,578`
- features:
  - `57`

The model had non-random classification signal:
- dev decision AUC:
  - `0.6299`
- validation decision AUC:
  - `0.5897`
- confirmation decision AUC:
  - `0.5746`

But the induced policy failed economically:
- best fixed horizon:
  - `3d`
- dev model uplift vs fixed `3d`:
  - `+0.00472`
- validation model uplift vs fixed `3d`:
  - `-0.00037`
- confirmation model uplift vs fixed `3d`:
  - `-0.00918`
- validation oracle uplift recovered:
  - `-0.93%`
- confirmation oracle uplift recovered:
  - `-20.88%`

The policy mostly held too long:
- validation model horizon choices:
  - `3d 7.97%`
  - `5d 50.52%`
  - `10d 39.83%`
  - `15d 1.68%`
- confirmation model horizon choices:
  - `3d 13.22%`
  - `5d 51.54%`
  - `10d 33.04%`
  - `15d 2.20%`

### Key finding
The H334 oracle gap is real, but the first simple hold/sell MDP-lite
distillation does not monetize it. The classifier can predict the hold label
better than random, yet the sequential policy loses to the fixed `3d` exit in
validation and confirmation.

**Implication:** do not integrate `exit-mdp-lite` and do not retune its
threshold against validation / confirmation. If continuing smart-exit work,
move to a materially different target such as `discrete-exit-hazard`; do not
jump to neural/offline RL from this failed distillation.

## F256: H336 Fails To Recover The Legal-Exit Oracle With Entry-Time Action-Value Horizon Routing (2026-04-10, Session 156)

Session 156 tested a second learned smart-exit distillation after `H334/H335`:
- consume the H334 executed-entry universe
- train one action-value regressor per legal exit horizon:
  - `3d`
  - `5d`
  - `10d`
  - `15d`
- use only entry-time daily state features
- select a non-`3d` horizon only when the predicted best horizon beats
  predicted `3d` by a dev-selected margin
- select the margin on dev only from:
  - `0.0000`
  - `0.0025`
  - `0.0050`
  - `0.0100`
  - `0.0150`
  - `0.0200`
  - `0.0300`
- compare against fixed `3d` and the H334 constrained oracle
- exclude `2026+`

The panel covered:
- entries:
  - `2,578`
- features:
  - `32`
- selected margin:
  - `0.0000`
- model:
  - `GradientBoostingRegressor(max_depth=2, n_estimators=80, min_samples_leaf=30)`

The model appeared useful on dev:
- dev model utility:
  - `+0.02045`
- dev model uplift vs fixed `3d`:
  - `+0.02075`
- dev oracle uplift recovered:
  - `34.81%`

But it failed out of sample:
- validation model utility:
  - `-0.00586`
- validation model uplift vs fixed `3d`:
  - `-0.00406`
- validation oracle uplift recovered:
  - `-10.16%`
- confirmation model utility:
  - `-0.01642`
- confirmation model uplift vs fixed `3d`:
  - `-0.00960`
- confirmation oracle uplift recovered:
  - `-21.84%`

The router overrode fixed `3d` too aggressively:
- validation override rate:
  - `86.37%`
- confirmation override rate:
  - `82.82%`
- validation model / oracle horizon match:
  - `22.85%`
- confirmation model / oracle horizon match:
  - `25.11%`

Per-horizon rank quality was weak in the held-out phases:
- validation Spearman:
  - `h3 0.1048`
  - `h5 0.0686`
  - `h10 0.0303`
  - `h15 0.0641`
- confirmation Spearman:
  - `h3 0.0777`
  - `h5 -0.0739`
  - `h10 0.0932`
  - `h15 0.0543`

### Key finding
The H334 oracle gap is not recovered by entry-time action-value horizon routing
on the current daily feature state. The model can fit useful-looking dev
utility, but the out-of-sample policy pushes too many entries into longer
horizons and loses to fixed `3d`.

**Implication:** close entry-time horizon routing for now. Do not integrate the
policy, and do not retune its margin on validation / confirmation. If the
smart-exit branch continues, use a materially different target such as
`discrete-exit-hazard` with post-entry state, or park the branch until better
state/data exists.

## F257: H337 Fixes The H336 Long-Hold Bias But Only Delivers Mixed Smart-Exit Evidence (2026-04-10, Session 157)

Session 157 tested the next honest smart-exit continuation after `H335/H336`:
- keep the H334 legal-horizon oracle as the offline target surface
- create held-position decision rows only at legal step boundaries:
  - `3d`
  - `5d`
  - `10d`
- label each row by whether waiting exactly one more legal step has higher
  utility than exiting now
- use only current hold-day state at the decision date:
  - path state
  - score decay
  - current signal state
  - activation state
  - tradability
  - event surface v1
  - a 2015-compatible replacement-pressure proxy from the full score surface
- train a dev-only logistic hazard with fixed threshold `0.50`
- compare against fixed `3d`, the H334 oracle, and a local H211
  strength-exhaustion path on the same H334 entry universe
- exclude `2026+`

The panel covered:
- step rows:
  - `7,717`
- policy entries:
  - `2,578`
- features:
  - `79`
- event features:
  - `15`

The branch improved materially versus `H335/H336`:
- validation decision AUC:
  - `0.5107`
- confirmation decision AUC:
  - `0.5587`
- validation model uplift vs fixed `3d`:
  - `+0.00245`
- confirmation model uplift vs fixed `3d`:
  - `+0.00253`
- validation delta vs local H211:
  - `+0.00742`
- confirmation delta vs local H211:
  - `+0.03246`

But the recovered oracle share stayed small:
- validation oracle uplift recovered:
  - `6.14%`
- confirmation oracle uplift recovered:
  - `5.75%`

The shape of the failure changed in a useful way:
- `H336` validation / confirmation non-best-fixed horizon choice rate:
  - `86.37%`
  - `82.82%`
- `H337` validation / confirmation non-best-fixed horizon choice rate:
  - `36.69%`
  - `26.87%`

So the new hazard no longer hallucinates long holds. It became conservative:
- validation model horizon choices:
  - `3d 63.31%`
  - `15d 16.98%`
- confirmation model horizon choices:
  - `3d 73.13%`
  - `15d 11.01%`

### Key finding
Changing both the label and the state helped. A one-step current-state hazard
is better than entry-time horizon routing and better than the local H211 rule
on the H334 entry universe. But on the current daily stack, the gain is still
too small to claim that smart-exit ML is solved or integration-ready.

**Implication:** keep `H337` as mixed offline evidence only. If the branch
continues, stay inside the one-step current-state hazard family and narrow to a
stronger replacement-relative label or a smaller state family. Do not reopen
`H335/H336`, and do not jump to neural/offline RL from this result.

## F258: H338 Shows H337 Fails Mainly Because Current Daily State Does Not Rank Continuation Utility Well Enough, With A Smaller Skip-Over Ceiling Behind It (2026-04-10, Session 158)

Session 158 audited the exact blocker behind `H337` by testing four competing
failure explanations:
- the one-step label family is itself too weak
- the fixed `0.50` threshold is wrong
- one simple feature family is missing
- the current daily state does not localize continuation utility well enough

The audit ruled out threshold tuning as the main explanation:
- tested thresholds:
  - `0.35`
  - `0.40`
  - `0.45`
  - `0.50`
  - `0.55`
  - `0.60`
  - `0.65`
- dev-selected threshold:
  - `0.50`
- validation / confirmation uplift vs fixed `3d` at `0.50`:
  - `+0.00245`
  - `+0.00253`
- lower thresholds turned strongly negative out of sample
- higher thresholds collapsed back toward fixed `3d`

The audit also ruled out "one-step hazard is impossible" as the main ceiling:
- a perfect H337-style step oracle recovered:
  - validation `72.56%` of H334 oracle uplift
  - confirmation `68.48%` of H334 oracle uplift

So the current label family is usable enough that a much better learner could
still recover materially more than `H337`.

No simple feature-family rescue appeared:
- `core_only`:
  - validation / confirmation uplift `+0.00020 / -0.00337`
- `core_plus_replacement`:
  - `+0.00230 / +0.00253`
- `full_no_event`:
  - `-0.00109 / +0.00283`
- `full_no_replacement`:
  - `+0.00282 / +0.00248`
- `full`:
  - `+0.00208 / +0.00154`

The dominant blocker was weak out-of-sample utility ranking:
- overall probability-to-utility Spearman:
  - validation `0.0296`
  - confirmation `0.1174`
- mean step delta utility stayed negative in every held-out horizon:
  - validation:
    - `3d -> 5d: -0.0010`
    - `5d -> 10d: -0.0043`
    - `10d -> 15d: -0.0014`
  - confirmation:
    - `3d -> 5d: -0.0063`
    - `5d -> 10d: -0.0095`
    - `10d -> 15d: -0.0092`

There is a secondary label ceiling from skip-over states:
- entries with skip-over conflicts:
  - validation `24.32%`
  - confirmation `21.15%`
- these are rows where the immediate next legal step is worse, but a later
  legal horizon is still better than exiting now

### Key finding
`H337` is not mainly failing because of threshold choice, and not mainly
because the branch forgot one obvious feature family. It is mainly failing
because the current daily state does not rank the sparse profitable
continuation pockets strongly enough out of sample. A secondary but real cap is
that one-step labels still miss skip-over states on about one-fifth to
one-quarter of entries.

**Implication:** the next honest smart-exit continuation is not more threshold
tuning. It is a skip-aware, utility-weighted, replacement-relative target
inside the current-state hazard family. If that still fails, the branch is
probably blocked by missing post-entry data rather than local model design.

## F259: H339 Shows The Skip-Aware Label Ceiling Is Solved, But The Current Daily State Still Cannot Learn The Right Exit Pockets (2026-04-10, Session 159)

Session 159 tested the exact continuation implied by `H338`:
- reuse the saved `H337` legal-step rows unchanged
- replace the immediate-next-step sign label with a skip-aware continuous
  target:
  - `max(later_legal_utility) - current_utility`
- train only a dev-only regularized linear value model:
  - `Ridge(alpha=10.0)`
- choose the hold margin only on dev from:
  - `-0.005`
  - `0.000`
  - `0.0025`
  - `0.0050`
  - `0.0100`
  - `0.0150`
  - `0.0200`
- compare directly against fixed `3d`, the `H334` oracle, and saved `H337`

The new target fully solved the skip-over label ceiling in principle:
- perfect skip-aware oracle recovered:
  - validation `100.00%` of `H334` oracle uplift
  - confirmation `100.00%`

So the target itself was not the problem anymore.

But the learned policy failed badly out of sample:
- dev-selected margin:
  - `0.0200`
- validation / confirmation uplift vs fixed `3d`:
  - `-0.00430 / -0.01109`
- validation / confirmation uplift delta vs `H337`:
  - `-0.00676 / -0.01362`
- validation / confirmation non-best-fixed rate:
  - `95.60% / 96.04%`

The failure mode was a return of long-hold bias:
- validation horizon choices:
  - `3d 4.40%`
  - `10d 49.90%`
- confirmation horizon choices:
  - `3d 3.96%`
  - `10d 54.19%`

The value model overpredicted positive continuation on holdout:
- overall predicted mean skip value vs true mean:
  - validation `0.0273 vs 0.0147`
  - confirmation `0.0270 vs 0.0105`
- per-horizon utility Spearman stayed weak where the decision mattered:
  - validation `3d 0.0462`, `5d 0.0379`, `10d -0.0068`
  - confirmation `3d 0.1916`, `5d -0.0100`, `10d 0.1372`

### Key finding
`H339` proves that fixing the skip-aware label ceiling is not enough on the
current daily state. The target can reproduce the oracle exactly, but the
learned model still cannot localize the rare bad continuation pockets well
enough, so it smooths toward positive hold values and recreates an aggressive
long-hold policy.

**Implication:** park current-state daily smart-exit label tinkering. If this
branch is reopened, the next honest change must be richer post-entry state/data
or a materially different nonlinear / replacement-relative model, not another
margin retune or small target rewrite.

## F260: CafeF Order-Stats And Proprietary-Trading Surfaces Reopen Daily Pressure / Flow Side Channels But Do Not Reopen Queue / Open-Fill Research (2026-04-10, Session 160)

Session 160 followed through on the CafeF stock-history page probe after page 2
(`ThongKeDL`) and page 4 (`GDTuDoanh`) were found.

Two new raw historical producers were wired:
- `data_tools/fetch_cafef_order_stats.py`
- `data_tools/fetch_cafef_proprietary_trading.py`

The fetchers now share one resumable history helper:
- `data_tools/cafef_history_common.py`

The monitored live backfill found and fixed two real operator bugs:
- manifests originally only wrote at the end of a run
  - they now update incrementally with `running / completed /
    completed_with_errors / interrupted`
- resumed runs misclassified cached tickers as failures because cached-path
  logging used an invalid DataFrame truthiness shortcut
  - cached resumes now work cleanly again

The acquisition result split by surface:

1. proprietary trading:
- first full-universe run status:
  - `completed_with_errors`
- requested:
  - `404` tickers
- fetched:
  - `350`
- cached:
  - `25`
- failed:
  - `29`
- combined panel:
  - `50,918` rows
  - `343` tickers
- direct endpoint probes reproduced CafeF `Success=false` formatting failures on
  names such as:
  - `ANV`
  - `BVH`
  - `DGC`
  - `GVR`
  - `HDB`
  - `HPG`

2. order statistics:
- live backfill is in progress with durable checkpointing
- note-promotion snapshot:
  - `143 / 404` processed
  - `134` fetched
  - `9` cached
  - `0` failed

Scientifically, this changes the branch state in a narrow but important way.
The workspace now owns real daily summary data for:
- posted buy / sell order counts
- posted buy / sell volume
- average order size
- buy-sell imbalance
- proprietary buy / sell / net volume
- proprietary buy / sell / net value

So earlier **daily** execution-friction / crowding ideas are no longer
source-blocked. The lab can now honestly test:
- daily order-pressure / implementation-pain side channels
- daily proprietary-flow regime states
- foreign-flow vs proprietary-flow vs posted-order conflict states

But the older `H325` blockage still stands in the microstructure sense.
These new surfaces do **not** provide:
- order-book ladders
- opening-auction queues
- actual fill position
- fine-minute sequence data
- bid / ask depth

### Key finding
CafeF page 2 and page 4 are a real acquisition win, but at **daily summary**
granularity only. They reopen lower-resolution pressure / flow-state research,
not the true queue/open-fill branch.

**Implication:** keep queue/open-fill research acquisition-blocked until a real
auction / order-book / fine-minute source exists. Move the next honest
low-cost follow-through to daily order-pressure, proprietary-flow, and
cross-flow divergence audits instead of pretending the microstructure question
is solved.

## F261: The Current Open Stack Now Maxes Out At Daily Side Channels Plus Reduced-Shape Intraday; True Historical Queue / Depth Likely Requires Either Forward Collection Or A Paid Vendor (2026-04-10, Session 161)

Session 161 closed the full `2026-04-10` timing-data acquisition pass with a
clean source-feasibility split.

What is now clearly in hand:
- CafeF historical foreign flow
- CafeF page 2 daily order statistics
- CafeF page 4 daily proprietary trading
- CafeF page 5 reduced-shape matched-trade intraday
- CafeF raw company news archive

What is therefore honestly collectable from the current open stack:
- daily order-pressure / implementation-pain side channels
- daily proprietary-flow regime states
- daily foreign-vs-proprietary-vs-posted-order divergence states
- reduced-shape intraday state from the existing CafeF `1H` path

What is only collectable if the lab starts recording from now:
- liveboard depth snapshots
- live board-state snapshots near open / close / ATC
- any current-board state that only exists on a live feed

What remains structurally unavailable from the current open/local surfaces:
- historical order-book ladders
- historical queue position
- historical auction-book state
- actual fill-position / open-fill pain
- reconstructed past liveboard history for dates never recorded

The vendor audit also sharpened the escalation path:
- `FiinQuant` appears promising for historical intraday plus foreign-flow-like
  fields and live order-book access
- `SSI FastConnect` remains a credentialed intraday / live-board fallback
- `ICE` is the first strong evidence that true historical HOSE depth may exist
  commercially, but likely only as an enterprise-cost path

### Key finding
The missing timing data problem is no longer ambiguous.
The open-data branch now appears to max out at:
- daily side channels
- reduced-shape intraday

If the lab needs true historical queue / depth / auction state, the next honest
paths are:
- start forward collection now, or
- pay for a vendor that can actually deliver historical depth

### Implication
Do not keep hand-waving the queue/open-fill branch as “almost solved.”
Keep the next steps explicit:
- first test the newly unlocked daily side channels
- if that still is not enough, escalate the vendor question directly

## F262: H340 Shows Same-Day Buy-Volume Pressure Is A Strong Positive-Side Rewrite Of C5, While Count-Only Pressure Fails Confirmation (2026-04-22, Session 162)

Session 162 took the first honest research pass on the newly unlocked
CafeF page-2 order-statistics surface:
- keep the original `H108` `fwd_rel_5d` contract
- keep the `2015-2022 / 2023-2024 / 2025` split from `H306`
- test only a small predeclared set of positive-side `C5` rewrites using
  same-day or lagged posted-order pressure ratios

Raw `C5` stayed the baseline:
- avg IC:
  - `+0.0374`
- positive years:
  - `10 / 11`
- validation / confirmation pooled IC:
  - `+0.0808 / +0.0028`

But same-day posted buy-volume pressure was a much stronger conditioner than
the original raw signal:
- best row:
  - `c5_scale_pos_buy_vol_ratio_cap_dev_median`
- dev support threshold:
  - `0.1149`
- avg IC:
  - `+0.0693`
- positive years:
  - `11 / 11`
- validation / confirmation pooled IC:
  - `+0.0980 / +0.0576`
- confirmation uplift vs raw `C5`:
  - `+0.0548`

Other bounded follow-through rows support the same mechanism:
- `c5_gate_pos_buy_vol_ratio_gt_0` also passed:
  - avg IC `+0.0688`
  - confirmation pooled IC `+0.0565`
- `c5_gate_pos_dual_buy_pressure_gt_0` also passed:
  - avg IC `+0.0626`
  - confirmation pooled IC `+0.0474`
- lagged buy-volume support also stayed positive but weaker:
  - avg IC `+0.0503`
  - confirmation pooled IC `+0.0283`

The non-surviving line was count-only pressure:
- `c5_gate_pos_buy_count_ratio_gt_0`
  - validation / confirmation pooled IC:
    - `+0.0930 / -0.0212`

### Key finding
The useful side channel is not generic “more buy orders.”
It is same-day **buy-volume** pressure alongside bullish insider conviction.
That makes `H340` a stronger positive-side robustness rewrite of `C5` than the
earlier `H306` exec-rate conditioner on the current daily contract.

### Implication
Do not reopen a broad queue/open-fill story from this result.
Keep it where it belongs:
- a daily side-channel rewrite of bullish `C5`
- next honest continuation:
  - test whether `H340` and `H306` stack additively or mostly duplicate the
    same positive-side quality mechanism

## F263: H341 Shows The H340 Buy-Volume Rewrite Already Captures The Usable Daily-State Quality, So Stacking H306 Exec-Rate Does Not Help (2026-04-22, Session 163)

Session 163 took the exact narrow follow-through earned by `H340`:
- keep the original `H108` `fwd_rel_5d` contract
- keep the `2015-2022 / 2023-2024 / 2025` split
- use the `H340` best row as the branch baseline
- test only:
  - the old `H306` best rewrite for context
  - one soft stacked rewrite
  - one conservative intersection gate

The `H340` baseline stayed the leader:
- baseline:
  - `c5_scale_pos_buy_vol_ratio_cap_dev_median`
- avg IC:
  - `+0.0693`
- validation / confirmation pooled IC:
  - `+0.0980 / +0.0576`

The best stacked row was close, but still worse:
- best stacked row:
  - `c5_scale_pos_exec_x_buy_vol_min_cap_dev_medians`
- avg IC:
  - `+0.0654`
- avg IC retention vs baseline:
  - `94.3%`
- validation / confirmation pooled IC:
  - `+0.0935 / +0.0548`
- validation / confirmation uplift vs baseline:
  - `-0.0045 / -0.0028`

The conservative hard intersection gate also missed:
- `c5_gate_pos_buy_vol_gt_0_exec_gt_0`
  - avg IC:
    - `+0.0649`
  - validation / confirmation pooled IC:
    - `+0.0931 / +0.0545`

And the old exec-rate rewrite was far weaker once compared directly against the
new buy-volume baseline:
- `c5_scale_pos_exec_cap_dev_median`
  - avg IC:
    - `+0.0379`
  - validation / confirmation pooled IC:
    - `+0.0740 / +0.0119`

### Key finding
The new page-2 buy-volume rewrite already captures the usable daily-state
quality on the current `C5` contract.
Exec-rate does not add another clean layer on top of it.
`H306` and `H340` are not independent enough to justify a default stacked
rewrite.

### Implication
Close the `c5-pressure-exec-stack` branch on the current daily contract.
Keep:
- `H340` as the preferred daily-state rewrite of bullish `C5`
- `H306` as the fallback when order-stats data is unavailable

Do not spend more cycles stacking the same two daily filters.
