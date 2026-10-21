export type Locale = "zh" | "en";

export const translations = {
  zh: {
    // Brand & Header
    brandTitle: "MATCHLENS",
    brandSubtitle: "AI 战术智能工作台",
    cockpitVersion: "COCKPIT 4.0",
    matchLabel: "比赛场次",
    liveStatusConnected: "已连接",
    liveStatusConnecting: "连接中...",
    themeLight: "日间模式",
    themeDark: "黑曜石暗夜",
    tacticalGuide: "战术指南与释义",
    languageToggle: "中 / EN",
    inspectorDrawer: "详情抽屉",

    // Workspaces
    workspaceMatchCenter: "比赛中心",
    workspaceTacticalLab: "战术与空间实验室",
    workspaceStoryAgent: "战报与智能体研报",
    workspaceValidationLab: "科研与模型验证",

    // Perspectives
    perspectiveCoach: "教练/战术分析",
    perspectiveCoachDesc: "聚焦通道推进、禁区触球转化率与 6s 反抢恢复",
    perspectiveMedia: "转播/媒体故事",
    perspectiveMediaDesc: "聚焦 OAAI 攻防动量潮汐、胜负转折点与自动战报",
    perspectiveFan: "深度球迷视角",
    perspectiveFanDesc: "聚焦球星个人触球热区、精彩团队连续传控与射门预期",

    // Scoreboard & Global Controls
    possession: "控球率",
    xgEstimated: "预计进球 (xG)",
    eventsLogged: "已记录事件",
    playbackSpeed: "倍速",
    restartKickoff: "重置比赛",
    playMatch: "播放",
    pauseMatch: "暂停",

    // OAAI
    oaaiTitle: "进攻活动指数 (OAAI)",
    oaaiSubtitle: "基于三层因果架构聚合，度量记录事件反映的攻防推进强度（非心理动量或胜率预测）",
    causalSmoothing: "实时因果滤波 (Causal)",
    bilateralSmoothing: "赛后双边平滑 (Bilateral)",
    homeAdvantage: "Harbor FC 进攻优势区 (+)",
    awayAdvantage: "Northbridge United 进攻优势区 (-)",
    currentMomentum: "当前攻防动量",
    peakWave: "全场峰值动量",
    changePointsDetected: "检测到胜负拐点",
    decayHalfLife: "滤波半衰期",
    oaaiHelpTip: "点击波形任意位置跳转比赛时钟 · 点击圆圈图标查看拐点归因 (Level 2)",

    // Event Feed
    eventLogTitle: "实时触球事件流",
    eventLogSubtitle: "全场逐动作高精度事件记录，支持筛选与一键跳转球场复盘",
    filterAll: "全部事件",
    filterShots: "射门与进球 ⚽",
    filterPasses: "推进传球 ↗",
    filterRecoveries: "球权夺回 ⚡",
    filterTurnovers: "失误丢球 ✕",
    searchEventsPlaceholder: "搜索球员姓名、事件编号...",
    noEventsFound: "未找到符合条件的事件",
    eventTotalSuffix: "条记录",
    goalBadge: "进球 GOAL!",
    shotBadge: "射门 SHOT",
    passBadge: "传球 PASS",
    recoveryBadge: "反抢恢复 RECOVERY",
    turnoverBadge: "失去球权 TURNOVER",
    outcomeSaved: "被扑出",
    outcomeBlocked: "被封堵",
    outcomeComplete: "到位",
    outcomeIncomplete: "未到位",

    // Attacking Channels (BL-08)
    corridorTitle: "进攻通道渗透度与禁区转化率",
    corridorSubtitle: "区分左路、中路、右路走廊向前推进渗透度与禁区触球转化率（严格以进攻球队视角划分）",
    leftFlank: "左路走廊",
    centralCore: "中路主轴",
    rightFlank: "右路走廊",
    attacksInitiated: "次进攻发起",
    finalThirdPenetration: "前场三区渗透度",
    boxConversionRate: "禁区触球转化率",
    progressiveGainMeters: "推进净增米数",
    channelDefinitionNote: "通道定义：左右方向严格以该进攻队伍的球门向对方球门视角划分，渗透度与转化率按已记录有效事件归纳。",

    // Highlight Locator (BL-12)
    highlightLocatorTitle: "核心攻防波次定位 (Highlight Locator)",
    highlightLocatorSubtitle: "与 OAAI 变化点检测及 S2 控球序列联动，自动定位比赛关键攻防高光与胜负波次",
    jumpToReplay: "一键复盘波次 →",
    surgeScore: "波次影响力得分",
    dominantTeam: "主导球队",
    waveCategorySurge: "进攻浪潮",
    waveCategoryGoal: "进球高光",
    waveCategoryShot: "危险射门",

    // Action Density Differential (BL-04)
    densityTitle: "场区行动占比差分 (Action Density Differential)",
    densitySubtitle: "计算公式：ΔD(z) = n_home(z)/N_home - n_away(z)/N_away。标注高密度重叠与优势争夺区",
    overlapZonesCount: "高密度重叠争夺区",
    defensiveThird: "防守三区",
    middleThird: "中场三区",
    attackingThird: "进攻三区",

    // Quick Recovery Analysis (BL-03)
    recoveryAnalysisTitle: "失去球权后快速恢复分析 (Quick Recovery)",
    recoveryAnalysisSubtitle: "统计失去球权后指定时间窗口内的球权重新夺回发生率与场区分布",
    recoveryWindowSlider: "统计观察窗口",
    quickRecoveryRate: "秒内快速反抢率",
    totalPossessionLosses: "次失球",
    highPressRecoveries: "前场高位反抢",
    spatialDistributionThirds: "纵向三区恢复分布",
    spatialDistributionChannels: "横向走廊恢复分布",
  },
  en: {
    // Brand & Header
    brandTitle: "MATCHLENS",
    brandSubtitle: "AI Tactical Intelligence Cockpit",
    cockpitVersion: "COCKPIT 4.0",
    matchLabel: "Match",
    liveStatusConnected: "Connected",
    liveStatusConnecting: "Connecting...",
    themeLight: "Light Mode",
    themeDark: "Obsidian Dark",
    tacticalGuide: "Tactical Guide & Glossary",
    languageToggle: "中 / EN",
    inspectorDrawer: "Inspector",

    // Workspaces
    workspaceMatchCenter: "Match Center",
    workspaceTacticalLab: "Tactical & Spatial Lab",
    workspaceStoryAgent: "Story & Agent Workbench",
    workspaceValidationLab: "Validation & Research Lab",

    // Perspectives
    perspectiveCoach: "Coach / Tactics",
    perspectiveCoachDesc: "Focus: Corridor penetration, box conversion & 6s recovery rate",
    perspectiveMedia: "Broadcast / Media",
    perspectiveMediaDesc: "Focus: OAAI momentum waves, turning points & automated narratives",
    perspectiveFan: "Deep Fan",
    perspectiveFanDesc: "Focus: Star player heatmaps, continuous possession & xG thrills",

    // Scoreboard & Global Controls
    possession: "Possession",
    xgEstimated: "Est. xG",
    eventsLogged: "Events Logged",
    playbackSpeed: "Speed",
    restartKickoff: "Restart Replay",
    playMatch: "Play",
    pauseMatch: "Pause",

    // OAAI
    oaaiTitle: "Observed Attacking Activity Index (OAAI)",
    oaaiSubtitle: "Three-tier causal aggregation quantifying recorded event attacking pressure (not psychological momentum)",
    causalSmoothing: "Causal Real-time Filter",
    bilateralSmoothing: "Bilateral Post-match Smoothing",
    homeAdvantage: "Harbor FC Attacking Advantage (+)",
    awayAdvantage: "Northbridge United Attacking Advantage (-)",
    currentMomentum: "Current Momentum",
    peakWave: "Peak Wave Amplitude",
    changePointsDetected: "Change-Points Detected",
    decayHalfLife: "Filter Half-life",
    oaaiHelpTip: "Click anywhere on the wave to seek · Click circle icons to examine Level 2 inflection attribution",

    // Event Feed
    eventLogTitle: "On-Ball Action Stream",
    eventLogSubtitle: "High-precision on-ball event log with instant filtering and pitch playback seek",
    filterAll: "All Events",
    filterShots: "Shots & Goals ⚽",
    filterPasses: "Progressive Passes ↗",
    filterRecoveries: "Ball Recoveries ⚡",
    filterTurnovers: "Turnovers ✕",
    searchEventsPlaceholder: "Search player or event ID...",
    noEventsFound: "No events matching your filter",
    eventTotalSuffix: "events",
    goalBadge: "GOAL!",
    shotBadge: "SHOT",
    passBadge: "PASS",
    recoveryBadge: "RECOVERY",
    turnoverBadge: "TURNOVER",
    outcomeSaved: "Saved",
    outcomeBlocked: "Blocked",
    outcomeComplete: "Complete",
    outcomeIncomplete: "Incomplete",

    // Attacking Channels (BL-08)
    corridorTitle: "Attacking Channel Penetration & Box Conversion",
    corridorSubtitle: "Differentiates Left, Central, and Right corridor progression and box conversion (team perspective)",
    leftFlank: "Left Flank",
    centralCore: "Central Core",
    rightFlank: "Right Flank",
    attacksInitiated: "attacks initiated",
    finalThirdPenetration: "Final 3rd Penetration",
    boxConversionRate: "Box Conversion Rate",
    progressiveGainMeters: "Progressive Gain",
    channelDefinitionNote: "Channel definition: Left/Right defined strictly relative to the attacking team's orientation.",

    // Highlight Locator (BL-12)
    highlightLocatorTitle: "Highlight Locator (Key Tactical Surges)",
    highlightLocatorSubtitle: "Linked with OAAI change-points and S2 sequences to index pivotal match surges",
    jumpToReplay: "Replay Tactical Surge →",
    surgeScore: "Surge Impact Score",
    dominantTeam: "Dominant Team",
    waveCategorySurge: "Attacking Surge",
    waveCategoryGoal: "Goal Highlight",
    waveCategoryShot: "Dangerous Shot",

    // Action Density Differential (BL-04)
    densityTitle: "Team Action Density Differential (ΔD(z))",
    densitySubtitle: "Formula: ΔD(z) = n_home(z)/N_home - n_away(z)/N_away. Highlights contest overlap zones",
    overlapZonesCount: "High-density overlap zones",
    defensiveThird: "Defensive Third",
    middleThird: "Middle Third",
    attackingThird: "Attacking Third",

    // Quick Recovery Analysis (BL-03)
    recoveryAnalysisTitle: "Post-Turnover Quick Recovery Analysis",
    recoveryAnalysisSubtitle: "Monitors ball re-gain rate and pitch distribution within the configured post-loss window",
    recoveryWindowSlider: "Observation Window",
    quickRecoveryRate: "s Quick Recovery Rate",
    totalPossessionLosses: "possession losses",
    highPressRecoveries: "High Press Recoveries",
    spatialDistributionThirds: "Thirds Spatial Distribution",
    spatialDistributionChannels: "Corridor Spatial Distribution",
  },
};

export function getTranslation(locale: Locale) {
  return translations[locale] || translations.zh;
}
