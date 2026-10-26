# Project form — paste-ready fields (R6.2)

Status: filled in against commit `fa42ee8` + the R6.2 red-team round. This file is a draft for the portal; nothing here is submitted automatically. Every sentence describes behaviour that runs today. Items that are **not** done are listed at the bottom instead of being written as done.

**Title** (limit 140):

```text
MatchLens AI — Football Intelligence You Can Challenge
```

**Tagline** (limit 300):

```text
A second agent tries to break every football claim before it reaches you. Every number carries the window it was measured over, off-ball guesswork is refused, and you can challenge the conclusion.
```

**Keywords:** Football; Explainable AI; Multi-Agent Systems; Synthetic Data; Sports Analytics; Broadcast.

**Open for others to join:** No (solo). Leave Skills Needed empty and Advanced off.

**Challenge:** The Synthetic Match Insights Engine for Premier League Studio.

**Writing Code:** Yes. Repository supplied by entrant: https://github.com/Leionel/MatchLens

**Description:**

```text
Does more possession really mean more danger? Usually the answer arrives as a confident sentence. MatchLens turns that sentence into something you can check.

The pipeline starts from recorded football events and computes every metric deterministically — the same events always produce the same numbers. Each number carries the window it was measured over, so a three-minute reading is never displayed as a match total.

An investigation works on one frozen moment. In the free deterministic mode, a typed tool registry produces the claim, its evidence and its counterevidence. With a model key configured, a Microsoft Agent Framework Analyst selects its own tools and proposes one claim, then hands it to a separate Verifier with its own tool budget, which re-reads the evidence, queries counterevidence, and returns a per-claim decision. A deterministic publication gate then checks refs, scope, numeric binding and unsupported language before anything is shown as approved.

The interface keeps the two honest: the agent panel shows which tools each stage actually called, or states plainly that no model was called. Approved claims can be challenged and read back as revisions, and they can be turned into a broadcast lower-third with their match time and evidence references attached.

Coverage: a continuous 12-minute synthetic match for the reproducible demo, and an 80-match StatsBomb open-data corpus (2010–2024, 302,638 events) for real-data generalisation.

What MatchLens refuses to do is part of the product: no off-ball shape, no pressing diagnosis, no calibrated xG, no causal claims. Those appear on screen as explicit limits next to the claim rather than as silence.
```

**What is not claimed (keep out of the portal copy):**

- No public hosted URL at submission time; the app runs locally with no key.
- No calibrated xG or fitted xT model.
- No measured single-agent vs. multi-agent quality comparison has been run.
- No off-ball / tracking data of any kind.
- The demo video is recorded and uploaded by the entrant; until that exists there is no video URL.

**Repository entry checklist:**

- [ ] Repository is public and the README renders the `evidence/r6.2/` screenshots
- [ ] `License: MIT` present (it is)
- [ ] No licensed StatsBomb payloads committed (they are git-ignored)
- [ ] No `.env`, key or token in history
- [ ] The three "what actually runs" rows in the README match what the recording shows
