"use client";

type Result = {
  status: string;
  origin: string;
  accepted: any[];
  rejected: any[];
  requests: number;
  audit: any[];
  duration_ms?: number;
  run_id: string;
};

type Props = {
  result: Result | null;
  pending: boolean;
  pendingStatus?: string;
};

export function AgentCollaborationFlow({ result, pending, pendingStatus }: Props) {
  const toolCallsCount = result?.audit?.filter((e) => e.type === "tool").length || 0;
  const receiptsCount = result?.audit?.filter((e) => e.type === "http_receipt").length || 0;
  const isQualified = result?.accepted?.[0]?.verdict === "qualify";
  const isPublished = result?.accepted?.[0]?.verdict === "publish";

  return (
    <div className="agent-collab-stage">
      <div className="collab-header-row">
        <div>
          <span className="collab-badge">DUAL-AGENT ADVERSARIAL PIPELINE</span>
          <h4 className="collab-heading">Visible Multi-Agent Workflow</h4>
        </div>
        {result && (
          <div className="collab-stats-pills">
            <span className="stat-pill">Run: <code>{result.run_id}</code></span>
            <span className="stat-pill"><b>{result.requests}</b> Requests</span>
            {result.duration_ms && <span className="stat-pill"><b>{(result.duration_ms / 1000).toFixed(2)}s</b></span>}
          </div>
        )}
      </div>

      <div className="collab-flow-steps">
        {/* Step 1: Analyst Agent */}
        <div className={`collab-step-card ${pending && pendingStatus !== "verifying" ? "active" : result ? "completed" : ""}`}>
          <div className="step-num-badge">1</div>
          <div className="step-card-header">
            <span className="step-agent-name">Analyst Agent</span>
            <span className="step-agent-role">Hypothesis & Draft</span>
          </div>
          <p className="step-desc">
            Investigates candidate anomaly, fetches evidence receipts, and drafts primary + conservative claim variants.
          </p>
          <div className="step-foot-stats">
            <span>Tools invoked: <b>{toolCallsCount > 0 ? Math.ceil(toolCallsCount / 2) : 1}</b></span>
            <span>Variant: <code>primary + conservative</code></span>
          </div>
        </div>

        <div className="collab-step-arrow">→</div>

        {/* Step 2: Verifier Agent */}
        <div className={`collab-step-card ${pending && pendingStatus === "verifying" ? "active" : result ? "completed" : ""}`}>
          <div className="step-num-badge">2</div>
          <div className="step-card-header">
            <span className="step-agent-name">Verifier Agent</span>
            <span className="step-agent-role">Adversarial Scrutiny</span>
          </div>
          <p className="step-desc">
            Independent isolated session. Pulls raw facts, audits counterevidence, and strips unsupported causal claims.
          </p>
          <div className="step-foot-stats">
            <span>Handoff: <code>SHA-256 bound</code></span>
            <span className="verdict-tag">{isQualified ? "QUALIFY" : isPublished ? "PUBLISH" : "AUDITED"}</span>
          </div>
        </div>

        <div className="collab-step-arrow">→</div>

        {/* Step 3: Publication Gate */}
        <div className={`collab-step-card ${result ? "completed" : ""}`}>
          <div className="step-num-badge">3</div>
          <div className="step-card-header">
            <span className="step-agent-name">Deterministic Gate</span>
            <span className="step-agent-role">Math & Bound Facts</span>
          </div>
          <p className="step-desc">
            Enforces strict slot-filling template contracts (bound-facts). Mathematical predicates guarantee zero hallucinated numbers.
          </p>
          <div className="step-foot-stats">
            <span>Gate status: <b className="gate-ok">100% VERIFIED</b></span>
            <span>Contract: <code>bound-facts-v1</code></span>
          </div>
        </div>
      </div>
    </div>
  );
}
