# MatchLens AI: Demo and Submission

Baseline: 2026-10-19. Target **115 seconds**, with a strict final file duration below 120 seconds. English interface, narration, captions, description and testing instructions. Final materials describe implemented behavior only; remove any planned feature that did not pass its gate.

## Story the judge should remember

**MatchLens shows when a football explanation deserves to be believed — and when the evidence says to narrow it.**

One story carries the demonstration: possession rises, but attacking threat may not. Show the difference between an appealing conclusion and what the event evidence actually supports. The agent trace substantiates that story; it is not the opening product screen.

Proposed English pitch, to finalize against the release:

> MatchLens turns a reproducible synthetic football match into explanations you can inspect. An Analyst investigates what changed; a separate Verifier checks the evidence and challenges overstatement. Fans get a clear consequence, analysts get the comparison and event trail, and both see the same approved facts. Built with Microsoft Agent Framework and DeepSeek, MatchLens keeps the match useful even when AI is unavailable.

The actual R0.1 local product path is recorded in R0.1_RESULTS; public access, final video and the comparative study remain release work. Do not claim Foundry, guaranteed truth or single-agent improvement. Use the final released stack in submission copy; see [TECH_SPIKE](TECH_SPIKE.md) and [PROJECT_FORM](PROJECT_FORM.md).

## Storyboard: 1 minute 55 seconds

| Time | On-screen action | Suggested English narration | Required real evidence |
| --- | --- | --- | --- |
| 0–9 s | MatchLens scoreboard and pitch; synthetic label visible; open possession chapter | “More possession sounds like more control. But is this team actually more dangerous?” | Real app, fictional teams and current scenario |
| 9–24 s | Start replay or seek to chapter cutoff; event feed and window bars change; request analysis | “This is a seeded synthetic match, with consistent possession, passes, recoveries and shots.” | Prefix reducer and real live request; visible pending status |
| 24–43 s | Keep Focus frozen at its as-of time while agents finish; show the actual decision | “The Analyst proposes an explanation. The Verifier checks opposing evidence before it reaches the screen.” | Both actual agent stages and tool calls; no inserted answer text |
| 43–64 s | Open evidence panel; compare possession with shots/pass entries; click a source event on pitch | “Here is the comparison behind the claim — the time window, the counts and the exact events. More possession alone is not enough.” | Cited receipts and source IDs from this run. Adapt narration to the actual verdict |
| 64–79 s | Switch Fan → Analyst → Fan | “One checked fact set, two useful views: a short consequence for fans, and the detail an analyst needs.” | Same claim IDs; different information density; no extra provider call |
| 79–94 s | Focus recovery chapter; show the actual recovery-to-shot discovery and linked IDs | “Here the system finds recoveries followed quickly by shots. Inspect the exact chains without claiming tactical causation.” | Actual framework stages, DeepSeek request/usage metadata and tool receipts; injected failure must be labeled |
| 94–107 s | Jump to final cutoff and display automatic match recap | “At full time, accepted moments become a linked recap. Every explanation stays attached to its evidence.” | Reconstruct full prefix; recap uses existing approved claims and score |
| 107–115 s | Repository/test URL closing card | “MatchLens: football intelligence you can challenge. Try the replay and inspect the evidence.” | Actual public URLs and released app |

Chapter seek is a deterministic replay shortcut. State clearly that match time is accelerated or skipped; label this continuous 12-minute demonstration match; do not imply a 90-minute match occurred. At full-time seek, only already generated/reviewed claims enter recap; any new pending analysis remains pending. An unfinished segment must say “segment recap.”

Record the central request→decision→evidence segment as an actual functioning screen capture. The agents may correctly agree or abstain; choose the relevant explanation from the real result. Do not force a disagreement, hardcode a rejection or substitute an anticipated script for a model response. The exact example sentence is illustrative until observed; avoid putting invented numbers in narration.

Prioritize the positive B-chapter discovery at79–94s. If the actual model takes longer, start that request earlier or disclose an edit/time skip; retain the raw capture/run receipt. Keep failure injection and longer traces in README unless they fit without losing the football story. The Spike's tiny samples are not a quality study or product p95 chart.

## Recording protocol

1. Freeze release commit, fixture, prompts, model configuration and deployment. Recheck that the endpoint is funded through Nov 10.
2. Open a fresh browser session; verify health without paid inference, then run the documented live smoke. Retain its run/trace IDs separately from the recording.
3. Record a fresh analysis in the product. Keep a raw capture and the run receipt. Captions may clarify window changes or shorten transitions, not manufacture behavior.
4. If the provider is down, a saved genuine run may be shown only with an explicit recorded-run label, timestamp and provenance. It is not a fresh run or evidence of current cloud availability. Resolve the live release gate before claiming live capability.
5. Use original SVG pitch, owned text and your own voice or properly licensed audio. No match footage, club crests, copyrighted music or borrowed broadcast graphics. Read the actual permission terms before adding any sponsor/league logo.
6. Capture at 1080p when practical; verify the score, evidence and uncertainty text at ordinary video viewing size. Keep cursor movement purposeful. English captions and narration agree with the visible result.
7. Inspect the exported video from start to end. Check actual duration via media metadata, audio intelligibility and UI readability; target 115 s to retain margin. Upload to a platform allowed by the official rules and test the public URL without login.

## Judge reproduction path

Target instructions to place in the English README after implementation:

1. Open the public test URL in a normal desktop browser. No account or payment required.
2. Select **Possession without penetration** to Focus at 06:00, then **Analyse this moment**. The UI identifies synthetic data and replay speed.
3. Wait for the analysis state to finish, or select the chapter's analysis control. A reused result says “saved model analysis”; its original run remains inspectable. The documented live route must also work without a judge buying API credits.
4. Open **Evidence**, compare the two windows and select an event to highlight it on the pitch.
5. Switch **Fan / Analyst** and verify that the claim/evidence IDs are unchanged.
6. Select the recovery chapter, then the final cutoff; read the scope-labeled recap and source links.
7. Inspect **View run trace** for provider/model, time, agent decisions and token/latency information. Test failure/recovery through the documented safe reproduction procedure if desired.

Provide local reproduction for environments where the public endpoint is inaccessible: pinned prerequisites, `.env.example`, fixture generation/validation, offline start, real-model start and expected visible states. No key may be shipped in a test build. A paid user-supplied key is not the only free judging path; maintain the funded hosted route or an equivalent authorized test service. State CPU/platform requirements and known restrictions honestly.

## English README structure

| Section | Required contents |
| --- | --- |
| Opening | One-sentence problem/outcome, actual screenshot, test URL and <2 min video URL |
| Quick judge path | The concrete sequence above, including fresh/cached/fallback labels and expected timings |
| Run locally | Tested OS/prerequisites, package locks, exact commands, ports and safe example config |
| Why two agents | Distinct objectives, immutable handoff, counterevidence, failure behavior; link architecture |
| Microsoft technology | Actual Agent Framework graph/tools and handoff; exact DeepSeek model/options; real run receipts and chosen hosting service. No Foundry dependency or Copilot runtime claim |
| Synthetic football data | Seed/version/hash, state invariants, coordinate/time model, supported metrics and limitations |
| Evaluation | Protocol, actual report/denominators, single-rater or missing-study limits; separate deterministic and live gates |
| Architecture | Mermaid diagram from ARCHITECTURE and an explanation of the request/evidence path |
| Reliability and cost | Deadlines, fallback, saved-run provenance, API budget assumptions and judging availability |
| Reproduce / contribute | Validation commands, clear module boundaries, license, third-party notices and evidence artifacts |
| Hackathon provenance | Development dates, release commit, original work and truthful tool-use disclosure |

Do not claim GitHub Copilot was used if coding was done with Codex. Category rules mention several supported orchestration approaches; actual runtime Agent Framework collaboration is the relevant evidence here. Do not list services merely because they appear in an architecture wish list.

## Final submission checklist

Rules source: [OFFICIAL RULES.md](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md). User screenshots establish the displayed challenge and basic fields. The agent has not operated/saved/submitted the form; remaining portal requirements still need checking. Copyable draft text is in [PROJECT_FORM](PROJECT_FORM.md).

- [ ] Registration receipt retained; entrant checks age/residence/conflicts and any applicable preferential-support restriction.
- [ ] Project creation history is after Sep 29, 2026, 09:00 PT; repository history and dependencies reflect the actual work.
- [ ] Actual submission form inspected: deadline/timezone, category options, required fields, URLs and any additional technical conditions.
- [ ] Category label uses the real form wording; understand only one category prize can be won.
- [ ] Public GitHub repository URL works signed out; English README, setup, license and third-party notices complete.
- [ ] Architecture diagram matches the release. Planned/unused services are removed from pitch and README.
- [ ] Real test URL/build works freely for judges, with any required test login supplied; funded access retained through **Nov 10, 2026, 23:59 PT**.
- [ ] G0–G5 evidence recorded; actual provider calls, both roles, tool use, references, failure handling and browser journey distinguishable from offline tests.
- [ ] No secret in current files, client bundle, released artifacts or Git history; synthetic identities and assets have clear provenance.
- [ ] Metrics and uncertainty match available event data. No xG, speed, formations or causal claims without new validated inputs.
- [ ] Evaluation report contains measured values or explicit NOT RUN; no invented uplift, latency, user study or availability claim.
- [ ] Video duration **<120 seconds**; target 115. English audio/captions, real operation and public allowed-platform URL verified.
- [ ] Every visible sample is labeled fresh, saved or deterministic as appropriate; injected failure is disclosed if shown.
- [ ] Pitch states problem, outcome and technologies actually used; no SDK/service laundry list.
- [ ] Final rules rechecked for changes; any material ambiguity sent to organizer by entrant as required, without guessed eligibility promises.
- [ ] Submit by internal target **Oct 27, 18:00 PT**; retain received confirmation, submission URLs and released commit SHA.
- [ ] Keep the submitted revision stable after the deadline; restrict changes to what the rules/organizer permit. Preserve the working deployment and logs through judging.

## Completion evidence to retain

`release commit + image/revision identifier + fixture hash + package locks + prompt versions + live run receipts + actual evaluation report + public test/video/repository URLs + raw recording + final media duration + submission receipt`.

Missing entries are outstanding work. A storyboard, passing unit suite or saved screenshot alone does not complete delivery.
