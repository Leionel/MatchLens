# MatchLens AI — R3 Plan: Personalized Broadcast Studio

## 1. R3 阶段目标

在 R1（双队、多场景、空间与序列计算）和 R2（可质疑多 Agent 推理）的基础上，将 MatchLens AI 的输出层打造为**面向球迷、分析师与转播制作人的个性化转播工作台（Personalized Broadcast Studio）**。
**核心铁律**：个性化只改变**事件排序、关注焦点、信息密度与叙事编排**，绝不改变客观统计数字或放宽事实验证门控（One Verified Fact Set, Multiple Tailored Programs）。

---

## 2. 核心模块设计

### 2.1 Personalized Match Director (6.1)

将 R0.2 简单的 `Fan / Analyst` 双按钮切换扩展为完整的 **Director Context & Preferences**：
- **关注维度（Focus Scope）**：
  - `Follow Team`: `Harbor FC (H)` / `Northbridge United (N)` / `Neutral (Both)`
  - `Follow Player`: 可选特定球员（如 `H9 Kai Stone`、`N9 Alex West` 等）
  - `Preferred Insight Types`: `All` / `Tactical Divergence` / `Transitions & Recoveries` / `Goals & Scoring Chains`
- **三视图模式（Three Role Views）**：
  1. **Fan View**：突出比分影响、核心看点一句话结论、关注球队/球员的高光时刻与简洁可视化。
  2. **Analyst View**：展示完整双窗口/跨队对比表、分子/分母明细、传递网络与推进序列、Verifier 局限性声明及 Hypothesis Lab。
  3. **Broadcast View**：激活 **Broadcast Producer Workbench**，展示待审洞察队列、字幕预览与导出控制。

---

### 2.2 Personalized Match Story (6.2)

建立独立的比赛叙事编排引擎（`build_match_story`），告别“简单拼接已发布卡片”的粗糙做法：
- **五段式叙事结构（Five-Act Narrative Arc）**：
  1. **Opening Situation（开局态势，00:00–03:00）**：双方控球分配、早期进攻三区进入与首轮试探射门。
  2. **Early Patterns & Divergence（早期战术模式，03:00–06:00）**：识别控球与实际威胁是否背离（如高控球零射门或高效防反）。
  3. **Key Changes & Transitions（中段局势转折，06:00–09:00）**：聚焦高位球权夺回、10 秒内快速转换射门爆发或比赛节奏变化。
  4. **Turning Points & Scoring Sequences（胜负手与进球序列，09:00–12:00）**：完整还原打破僵局或逆转比分的连续有球控球序列（起点、参与球员、推进距离、终结位置）。
  5. **Evidence-Based Takeaways（基于证据的赛后总结）**：汇总经 Verifier 批准的核心结论、关键球员贡献及数据局限性说明。
- **动态裁剪与去重机制**：
  - 若比赛尚未进行到终场（如 `at = 400s`），自动生成截至当前时间的**阶段性报告（Segment Story）**，绝不剧透未来事件。
  - 若关注特定球队（如客队 `Northbridge United`）或特定球员，自动提升与该球队/球员相关的序列和转折权重，并在无足够事件时诚实输出简短报告。

---

### 2.3 Broadcast Producer Workbench (6.3)

面向赛事转播制作人设计专业的人机协同审校工作流（Human-in-the-Loop Editorial Workflow）：

```text
Detected Moment → AI Insight & Verifier Gate → Editorial Review Queue → Producer Approve / Reject / Defer → On-Air Lower-Third & Story Rundown
```

- **核心功能组件**：
  1. **Pending Insight Queue（待审洞察队列）**：展示所有已通过 Agent Verification Gate 的洞察卡片，附带时间戳 `as_of`、验证状态（`Verified` / `Qualified`）与关联收据数。
  2. **Evidence & Limit Quick-Check（证据快速预览）**：制作人无需离开工作台即可一键查看支撑该字幕的指标公式与 Verifier 风险提示（如“仅代表 3 分钟短期窗口”）。
  3. **Editorial Actions（人工编辑审校操作）**：
     - `Approve for Broadcast`：将卡片移入已批准转播单（Approved Rundown），可上屏展示或导出。
     - `Defer / Hold`：暂存观察，等待后续比赛窗口看趋势是否持续。
     - `Reject Editorial`：因转播叙事节奏原因人工弃用。
  4. **边界声明**：UI 明确区分 **`Agent Fact-Check Status`（机器事实与门控核验）** 与 **`Producer Editorial Status`（人工转播编排批准）**——人工点击 Approve 代表允许上屏播出，不代表将“短期关联”升级为“绝对因果真理”。

---

### 2.4 Broadcast Graphics & Export (6.4)

扩展现有 `BroadcastOverlay.tsx`，支持将已核验并经制作人批准的内容一键输出为标准转播交付物：
1. **SVG Broadcast Lower-Third Graphic**：生成自带比分牌、比赛时间 `as_of`、球队配色、核验徽章与洞察正文的独立矢量 `.svg` 文件，可直接导入 OBS / vMix 或设计软件。
2. **Structured JSON Overlay Payload**：输出包含 `match_id, snapshot_id, as_of, score_at_moment, headline, subline, verdict, metric_receipts, provenance` 的标准 JSON 载荷，供下游转播图文系统消费。
3. **Producer Rundown / Story Cards Markdown**：一键导出带时间戳与证据引用的解说提纲（Broadcast Narration Copy & Producer Notes）。
