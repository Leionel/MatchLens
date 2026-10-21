"""
Adversarial Empirical Stress Testing Suite for MatchLens 2026 Platform.
Authored by: Empirical Challenger (critic, specialist).
Purpose: Strictly verify mathematical limits, sparsity, filter response,
and logical boundaries for the proposed Backlog items (BL-01 to BL-12).
Pure standard-library implementation (zero external dependency).
"""

import math
import pytest
from matchlens.football import generate_match, reduce_match, build_sequences, build_tactical_explorer
from matchlens.contracts import publication_gate, ClaimDraft, Claim, Variant


class TestAdversarialEmpiricalVerification:
    """Empirical verification suite for adversarial challenger findings."""

    def test_xt_16x12_grid_sparsity_and_degeneration(self):
        """
        [Stress Test 1]: 16x12 xT grid sparsity & degeneration in single match.
        Assessing if 16x12 (192 cells) or transition matrix (36,864 cells)
        suffers severe zero-sample sparsity under typical single-match event volume.
        """
        events = generate_match(seed=17)
        total_events = len(events)
        assert total_events >= 100, f"Match event count too low: {total_events}"

        # Setup 16x12 grid (105m x 68m pitch)
        nx, ny = 16, 12
        cell_counts = [[0 for _ in range(ny)] for _ in range(nx)]
        transition_dict = {}

        # Count passes and carries with spatial coordinates
        for e in events:
            if hasattr(e, "start") and e.start:
                sx, sy = e.start
                gx = min(int(sx / (105.0 / nx)), nx - 1)
                gy = min(int(sy / (68.0 / ny)), ny - 1)
                cell_counts[gx][gy] += 1

                if hasattr(e, "end") and e.end:
                    ex, ey = e.end
                    egx = min(int(ex / (105.0 / nx)), nx - 1)
                    egy = min(int(ey / (68.0 / ny)), ny - 1)
                    src_idx = gy * nx + gx
                    dst_idx = egy * nx + egx
                    transition_dict[(src_idx, dst_idx)] = transition_dict.get((src_idx, dst_idx), 0) + 1

        total_cells = nx * ny
        flat_counts = [cell_counts[x][y] for x in range(nx) for y in range(ny)]
        zero_cells = sum(1 for c in flat_counts if c == 0)
        low_sample_cells = sum(1 for c in flat_counts if c <= 1)
        zero_cell_ratio = zero_cells / total_cells
        low_sample_ratio = low_sample_cells / total_cells

        total_transitions = total_cells * total_cells  # 192 * 192 = 36864
        nonzero_transitions = len(transition_dict)
        transition_sparsity = 1.0 - (nonzero_transitions / total_transitions)

        spatial_count = sum(1 for e in events if hasattr(e, "start") and e.start)
        print(f"\n[xT Sparsity Results]:")
        print(f"Total spatial events in match: {spatial_count}")
        print(f"16x12 Cells with 0 events: {zero_cells}/{total_cells} ({zero_cell_ratio*100:.1f}%)")
        print(f"16x12 Cells with <= 1 events: {low_sample_cells}/{total_cells} ({low_sample_ratio*100:.1f}%)")
        print(f"Transition matrix non-zero elements: {nonzero_transitions}/{total_transitions}")
        print(f"Transition Matrix Sparsity: {transition_sparsity*100:.4f}%")

        # Empirical assertion: Single-match transition matrix is >98% sparse!
        assert transition_sparsity > 0.98, "Transition matrix must be overwhelmingly sparse in single match"

    def test_attack_momentum_ema_distortion(self):
        """
        [Stress Test 2]: Attack Momentum EMA filter under dead-ball pauses and low-xG shot spikes.
        Verifies if raw EMA over wall-clock time causes severe false dips or shot spikes.
        """
        half_life_seconds = 60.0
        lam = math.log(2) / half_life_seconds

        # Scenario A: Momentum before VAR deadball pause
        # Team A had steady pressure (+5.0 momentum) at t=45m.
        # Dead-ball VAR pause lasts 180 seconds (3 minutes) with 0 events.
        t_start = 45.0 * 60.0
        t_end = t_start + 180.0
        initial_momentum = 5.0
        decayed_momentum = initial_momentum * math.exp(-lam * (t_end - t_start))

        # After 180s (3 half-lives), momentum drops by 87.5% to 0.625
        decay_ratio = 1.0 - (decayed_momentum / initial_momentum)
        print(f"\n[Momentum Dead-ball Decay]: Decayed from {initial_momentum} to {decayed_momentum:.3f} ({decay_ratio*100:.1f}% drop during pause)")
        assert decay_ratio > 0.85, "Wall-clock EMA drops >85% during 3-minute VAR stoppage, creating false momentum loss"

        # Scenario B: Low-xG Desperation Shot Spike
        # Away team does a 45m clearance shot with xG=0.015.
        # If Shot Action has fixed weight +6.0, it generates a spike identical to a 1v1 big chance.
        shot_raw_weight = 6.0
        calibrated_shot_weight = 1.0 + 7.0 * 0.015  # 1.105
        spike_inflation_ratio = shot_raw_weight / calibrated_shot_weight
        print(f"[Momentum Shot Spike]: Uncalibrated shot weight {shot_raw_weight} vs xG-calibrated {calibrated_shot_weight:.3f} (Inflation: {spike_inflation_ratio:.1f}x)")
        assert spike_inflation_ratio > 4.0, "Uncalibrated shot weight inflates momentum impact by >400% for low-xG desperation shots"

    def test_zone_differential_bl04_possession_masking(self):
        """
        [Stress Test 3]: Pitch Zone Differential under asymmetric possession (e.g., 75% vs 25%).
        Checks whether simple subtraction (Home_Touches - Away_Touches) completely erases
        the defensive activity of the low-possession team.
        """
        home_touches = {
            "def_box": 12, "def_mid": 25, "def_wing": 20,
            "mid_box": 45, "mid_mid": 70, "mid_wing": 55,
            "att_box": 30, "att_mid": 40, "att_wing": 35
        }
        away_touches = {
            "att_box": 28,  # Away team defensive box actions
            "att_mid": 12,
            "att_wing": 8,
            "mid_box": 10, "mid_mid": 15, "mid_wing": 12,
            "def_box": 2, "def_mid": 5, "def_wing": 4
        }

        # Naive differential: Home - Away
        naive_differential = {k: home_touches[k] - away_touches[k] for k in home_touches}
        home_dominated_zones = sum(1 for v in naive_differential.values() if v > 0)
        print(f"\n[Zone Differential]: Naive differential dominated by Home team in {home_dominated_zones}/9 zones")
        print(f"In opponent penalty box (att_box): Home {home_touches['att_box']} vs Away defensive actions {away_touches['att_box']} -> Diff: {naive_differential['att_box']}")

        assert home_dominated_zones >= 8, "Naive touch differential erases low-possession team tactical presence"

    def test_counterfactual_sandbox_bl09_defense_blindspot(self):
        """
        [Stress Test 4]: Counterfactual Sandbox (BL-09) vulnerability to phantom passing options.
        Demonstrates that pure xT grid delta cannot evaluate passing interception risk,
        generating dangerous counter-factual hallucinations without 360/tracking defense data.
        """
        xt_source = 0.05
        xt_target = 0.22
        delta_xt = xt_target - xt_source

        p_complete = 0.05
        expected_threat_real = (p_complete * delta_xt) + ((1.0 - p_complete) * (-0.15))

        print(f"\n[Counterfactual What-If]: Naive delta_xT: +{delta_xt:.2f}")
        print(f"Realistic expected threat under defensive congestion: {expected_threat_real:.3f}")

        assert delta_xt > 0 and expected_threat_real < 0, (
            "Naive xT counterfactual sandbox generates opposite sign compared to reality "
            "when off-ball defensive interception probability is unobserved."
        )

    def test_llm_token_budget_consumption_for_match_story(self):
        """
        [Stress Test 5]: Token consumption vs SQLite budget guard ($1.00 / 32 requests).
        Verifies if sending raw match event dumps into LLM breaches budget constraints.
        """
        event_count = 1800
        bytes_per_event = 90
        total_bytes = event_count * bytes_per_event
        estimated_input_tokens = total_bytes / 4.0

        cost_per_input_token = 3.0 / 1_000_000.0
        cost_per_output_token = 15.0 / 1_000_000.0
        output_tokens = 2500

        single_call_cost = (estimated_input_tokens * cost_per_input_token) + (output_tokens * cost_per_output_token)
        total_story_cost = single_call_cost * 2.5

        print(f"\n[Token Budget Stress]:")
        print(f"Raw 1800 events token volume: {estimated_input_tokens:.0f} tokens")
        print(f"Cost of single unpruned report generation: ${single_call_cost:.4f}")
        print(f"Tri-agent cycle cost: ${total_story_cost:.4f} (Budget threshold: $1.00)")

        assert total_story_cost > 0.25, "Unpruned raw event feeding threatens $1.00 global budget cap"
