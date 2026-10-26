# MatchLens AI — Demo and Submission Plan (R6.2)

Baseline: 2026-10-26, commit `fa42ee8` + this round's changes. Target **112–115 s**, hard limit **< 120 s** (official rule). English interface, English narration, burned-in English captions.

> **The one rule for this video:** every frame is the running product. Nothing is re-typed, re-timed or narrated over a still that the app did not produce. If the two-agent run cannot be recorded live, the fallback in §3 is used and the on-screen label says so.

---

## 1. The single claim the video must land

> **A football explanation is only worth airing if someone can check it — and can argue with it.**

Everything else in the edit serves that sentence: one moment, one claim, one independent check, one gate decision, one piece of evidence you can open, one way to disagree.

Do **not** tour the feature set. Four surfaces, one story.

---

## 2. Shot list (112–115 s)

| # | Time | On screen (real UI) | Narration | Must be true in the frame |
| --- | --- | --- | --- | --- |
| 1 | 0–10 s | Match Detail, paused at 07:00. Insight card reading *"Harbor FC activity peaked in this spell"* with the **Cannot decide** line under it. | "Possession is up. The crowd is up. Does that mean the team is in control?" | Synthetic match; the `SYNTHETIC` provenance is visible somewhere in frame. |
| 2 | 10–20 s | Scroll the totals row and the live-window strip: `WHOLE MATCH` 8/5 shots, `Last 3 min window` 0/0. | "This is where most tools stop: a number without a scope. The last three minutes had no shots. The match had thirteen." | The strip must show its own bounds (`4020s–4200s`). |
| 3 | 20–30 s | Press **Investigate this change**. Studio opens on that exact moment; question pre-filled. | "So we ask the match — at this second, not about the whole game." | Clock in the panel reads the same second as the chart. |
| 4 | 30–55 s | **Agent collaboration panel.** Analyst row (tools it called, claim id), Verifier row (its own tools, verdict + reason), Gate row. | "The Analyst picks its own tools and proposes one claim. The Verifier gets its own tool budget, checks counterevidence, and decides whether that claim survives. This is the part a single model cannot do for itself." | See §3 — this is the only segment that depends on a model key. |
| 5 | 55–70 s | Open **Evidence**: findings with event ids; click one → the pitch jumps to that event. Then **What this cannot decide**. | "Every sentence points back to recorded events — and the claim is narrow on purpose: no off-ball shape, no tactical cause." | The event id in the finding equals the one selected on the pitch. |
| 6 | 70–82 s | Switch perspective **Fan → Coach → Media**. Same time, same claim: consequence → shot comparison → lower-third line. | "Same fact. A fan gets the consequence, an analyst gets the window comparison, a producer gets a line that can go on air." | The match time and claim id do **not** change between the three. |
| 7 | 82–93 s | **Broadcast preview** card under the result: provenance strip, score bug, headline, evidence refs. | "Approved claims become a lower-third with the match time and its evidence attached." | Provenance strip must read `SYNTHETIC SIMULATED REPLAY` for the synthetic match. |
| 8 | 93–104 s | Cut to Match Hub → open a `Real data` match → Match Detail → the same totals row and insight. | "The same pipeline runs on eighty real matches — provider event data, same receipts, same gate." | Hub card shows `Real data`, not `Demo`. |
| 9 | 104–112 s | Closing card: title, one-line claim, repo URL, "run locally in three minutes". | "MatchLens. Football intelligence you can challenge." | No invented URL, no "live at". |

### Optional 3 s if under time
60–63 s: open one **alternative explanation** row and show its `insufficient_evidence` status. This is the cheapest way to prove the system is willing to say "we cannot test this".

---

## 3. Segment 4 (30–55 s): the honesty fork

This is the segment that decides whether the submission is credible. Pick **one** of the following and never blend them.

### Variant A — live two-agent run (preferred, needs a key)

Requirements before recording:

- `DEEPSEEK_API_KEY` set server-side, ledger runway ≥ 6 requests (`$1.00` default ceiling).
- In Studio **Advanced → Engine** choose **Real Agent (uses model budget)**.
- Record the run id from the panel; keep the run receipt afterwards.

On screen the collaboration panel must show:

- mode chip = **Live model · deepseek-flash · N requests**
- Analyst row with `claim_id` and the tools it called
- Verifier row with its own tool list and a decision (`publish` / `qualify` / `withhold`)
- Gate row with the verdict

Narration must not invent a disagreement. If the Verifier publishes, say so: *"here it agreed — and you can see exactly what it checked before agreeing."*

### Variant B — no key: deterministic run, labelled on camera

- Leave **Engine** on **Deterministic (free)**.
- The collaboration panel will render: *"No model called · deterministic tools"* and *"no Analyst/Verifier exchange exists"*.
- Narration: *"This run is deterministic — no model was called, so there is no agent debate to show. What you can still check is the gate, the evidence and the counterevidence."*
- Then spend the saved time on segment 5 (evidence + limits), which is the part that survives without a key.

**Never** show Variant B while narrating a two-agent discussion. That is the one thing that would make the whole submission untrustworthy.

### Variant C — historical recorded run (only if A and B both fail)

`evidence/r0.2/runs/` contains genuine recorded model runs, including a **rejection**:

| Run | Verdict | Why it is useful on camera |
| --- | --- | --- |
| `run-14e303594906f796` | published `possession_without_penetration` | a supported claim |
| `run-c-verify-a359468b` | published `goal_sequence` | a supported claim after correction |
| `run-c-verify-29254a79` | **rejected** — `unbound_spelled_number` | the gate refusing a claim the verifier thought was in-bounds |

If used, it must carry the UI's **Historical real analysis** label and the narration must say "recorded earlier", with the run id visible. This is evidence, not a live demo.

---

## 4. Recording protocol

1. Freeze the commit. `git tag demo-<date>`; do not edit during recording.
2. `NODE_OPTIONS= npm --prefix apps/web run build`, start one Uvicorn worker, open a fresh browser at 1920×1080, zoom 100%.
3. Set locale **English**, theme **dark** (dim room) or **light** (bright room) — pick one and keep it.
4. Record at 1080p60 if available; 1080p30 is fine. Cursor: hide when idle, no shaking.
5. One continuous take per segment; cut only on segment boundaries to keep the clock honest.
6. Burn in captions that match narration exactly. No caption may assert something not visible.
7. Export, then **check duration with media metadata** (`ffprobe`). If ≥ 120 s, cut segment 2 or 8, not the honesty lines.
8. Watch the export at 50% size: the score, the window bounds and the *Cannot decide* line must still be legible.

### Pre-flight checklist

- [ ] Hub shows `Real data` badges and `Demo · Synthetic` on synthetic cards
- [ ] Match Detail totals read `WHOLE MATCH`; the live strip shows its own seconds
- [ ] Investigating lands on the same second as the chart
- [ ] Collaboration panel matches the engine actually selected
- [ ] Evidence click moves the pitch/time to that event
- [ ] Fan/Coach/Media keep the same clock and claim id
- [ ] Broadcast preview shows the correct provenance strip
- [ ] No visible console error, no `localhost` banner, no dev overlay
- [ ] Repo URL in the closing card resolves

---

## 5. Submission copy (paste-ready)

**Title:** MatchLens — Football Intelligence You Can Challenge

**One line:** MatchLens turns recorded football events into claims a second agent can verify, a gate can withhold, and you can challenge — with every number tied to the window it was measured over.

**Description:** MatchLens runs a full claim lifecycle on real football event data. A deterministic engine computes every metric from the event log; optionally, a Microsoft Agent Framework Analyst proposes a claim with tools it selects itself, and a separate Verifier re-checks it with its own tool budget and counterevidence query before a publication gate decides. Off-ball shape and tactical cause are explicitly out of scope, and the UI says so next to the claim. Works on a continuous synthetic match and on an 80-match StatsBomb open-data corpus. Runs locally with no key and no account.

**Built with:** Microsoft Agent Framework, FastAPI, Next.js, DeepSeek (optional live agent mode).

**What is intentionally not claimed:** no calibrated xG, no off-ball tracking, no measured multi-agent uplift, no public deployment at submission time.

---

## 6. Release tasks that need a human

| Task | Owner | Blocking? |
| --- | --- | --- |
| Record and upload the < 120 s video | user | **yes** — submission requires a URL |
| Decide on public hosting (funded key + rate limits) | user | no — local path is documented and honest |
| Replace the `Live demo` line in README with the real URL if hosting happens | user | no |
| Final read of submission text against the recorded footage | user | **yes** |

Nothing in this plan requires new product code. If hosting is approved, the only change is the README line and the closing card.
