# ruff: noqa: E501
import json
from typing import override

from alpha_quant.ports.llm import LLM

_FIXTURES: dict[str, dict] = {
    "positive_stage": {
        "headline": "Strong technical setup confirmed",
        "summary": "Trend, momentum, and volume all support entry. The stock is in a confirmed uptrend with healthy participation.",
        "recommended_action": "consider_entry",
        "confidence_label": "high",
        "interpretation": "All technical indicators align bullishly — score reflects broad agreement across trend, momentum, and volume.",
        "key_reasons": [
            "Trend score 85/100 — price above both 50 and 200 day MAs",
            "Momentum confirmed by positive MACD cross",
            "Relative volume at 1.2x average — healthy participation",
        ],
        "key_evidence": [
            "Trend regime bullish 60+ days",
            "RSI at 55 — room to run",
            "Volume above 20d avg",
        ],
        "key_caveats": ["Volatility elevated (ATR 2.8%) — use wider stop"],
        "main_risks": ["Mean reversion after 5 consecutive up days"],
        "data_quality_notes": "Technical readouts all within 2h of as_of",
        "decision_context": "Top-ranked candidate at 82/100 — strong broad agreement, no hard gates triggered",
        "educational_context": "M3 Technical State aggregates trend, momentum, volatility, volume, and relative strength into a single 0-100 score. Scores above 65 indicate broad technical support.",
        "override_guidance": [],
    },
    "cautionary_stage": {
        "headline": "Fundamental quality is weak",
        "summary": "High debt-to-equity and negative earnings yield signal fundamental fragility. The deterministic score is depressed as a result.",
        "recommended_action": "watch",
        "confidence_label": "low",
        "interpretation": "Fundamental gate flags debt and earnings concerns — score reflects this risk.",
        "key_reasons": [
            "Debt/equity ratio 6.2x — above 5x warning threshold",
            "Earnings yield negative at -5%",
            "Gross margin negative — operating losses continue",
        ],
        "key_evidence": ["Financial health metrics from latest filing"],
        "key_caveats": ["Fundamental data from annual filing — may be up to 9 months stale"],
        "main_risks": ["Further deterioration before next filing", "Covenant breach risk"],
        "data_quality_notes": "Fundamental data as-of last quarterly filing (3 months ago)",
        "decision_context": "M4 Fundamental Resilience gate downgrades from neutral to cautionary — high debt and negative earnings are structural concerns",
        "educational_context": "M4 Fundamental Resilience checks debt/equity, gross margin, and earnings yield as binary pass/fail gates. A fail here means the company has weak financial health regardless of technical setup.",
        "override_guidance": [],
    },
    "blocking_stage": {
        "headline": "Earnings blackout blocks entry",
        "summary": "This candidate is inside the 14-day earnings blackout window. The deterministic engine blocks entry regardless of other scores.",
        "recommended_action": "do_nothing",
        "confidence_label": "high",
        "interpretation": "Hard gate triggered — entry is blocked until the earnings event passes.",
        "key_reasons": [
            "Earnings report within 14-day blackout window",
            "High event risk — gap potential exceeds normal stop distance",
        ],
        "key_evidence": ["Earnings event confirmed on 2026-01-15 — 8 days from as_of"],
        "key_caveats": [],
        "main_risks": ["Gap-through on earnings — normal stops may not protect"],
        "data_quality_notes": "Earnings date confirmed via company guidance",
        "decision_context": "M7 Known Event Risk gate blocks entry. The blackout window runs until 2026-01-22.",
        "educational_context": "M7 Known Event Risk enforces a 14-day blackout window around earnings. Stocks in this window cannot be entered because gap risk exceeds normal stop controls.",
        "override_guidance": "Override to enter despite blackout only if you accept gap risk and have out-of-hours stop capability.",
    },
    "missing_data": {
        "headline": "Insufficient data for complete assessment",
        "summary": "Several expected readouts are missing. The deterministic engine uses fallback values for missing indicators.",
        "recommended_action": "watch",
        "confidence_label": "low",
        "interpretation": "Score is less reliable than normal due to missing inputs.",
        "key_reasons": [
            "Only 4 of 7 expected technical readouts available",
            "RSI and MACD data missing — fallback assumptions used",
            "Fundamental data absent — neutral assumption applied",
        ],
        "key_evidence": ["Available readouts: last price, ATR, volume"],
        "key_caveats": [
            "Missing RSI and MACD reduces trend confidence",
            "Fundamental score uses neutral 50 assumption",
        ],
        "main_risks": ["Score may change materially when missing data arrives"],
        "data_quality_notes": "Data quality score 42/100 — values missing for RSI_14, MACD_cross, and PE_ratio",
        "decision_context": "Final score includes data-quality attenuation: score reduced by 30% due to poor data quality",
        "educational_context": "The Data Quality gate checks what percentage of expected readouts are present. Below 50% availability triggers score attenuation — the engine reduces confidence rather than blocking.",
        "override_guidance": [],
    },
    "stale_data": {
        "headline": "Market data is stale",
        "summary": "The most recent data for this symbol is 45 minutes old. The stale-data gate has downgraded the recommendation to blocked.",
        "recommended_action": "blocked",
        "confidence_label": "low",
        "interpretation": "Result is blocked because data freshness requirement is not met.",
        "key_reasons": [
            "Last market data 45 minutes ago — exceeds 30-minute threshold",
            "Freshness gate blocks trading on stale data by policy",
        ],
        "key_evidence": ["Freshness check: age=45m, threshold=30m, stale=true"],
        "key_caveats": ["Data may recover when next Alpha-Lake readout arrives"],
        "main_risks": ["Trading on stale data risks mispriced entry"],
        "data_quality_notes": "Stale flag set by FreshnessService — data age 45m > 30m threshold",
        "decision_context": "Stale gate forces recommendation to blocked regardless of score",
        "educational_context": "The Freshness Gate checks that market data is within a configurable staleness threshold (default 30 minutes). When data exceeds this age, the system blocks recommendations to prevent trading on stale conditions.",
        "override_guidance": "If you have confirmed current pricing from another source, override to force the original recommendation.",
    },
    "risk_warning": {
        "headline": "Portfolio concentration approaching limit",
        "summary": "This position would bring single-name concentration to 19%, approaching the 20% policy cap. The risk engine flags this as a warning.",
        "recommended_action": "reduce",
        "confidence_label": "medium",
        "interpretation": "Adding would push concentration very close to the hard cap — the engine recommends caution.",
        "key_reasons": [
            "Current allocation: 14% of equity",
            "Proposed addition: +5% → 19% total",
            "Hard cap: 20% single-name concentration limit",
        ],
        "key_evidence": ["Concentration report: current=14%, proposed=19%, cap=20%"],
        "key_caveats": ["No alert below 15% — warning only above 15% utilization"],
        "main_risks": [
            "Further appreciation would push past the hard cap",
            "No room for additional positions in this name",
        ],
        "data_quality_notes": "",
        "decision_context": "Risk posture shifts from 'all limits within policy' to 'elevated' — warn at 95% utilization of concentration cap",
        "educational_context": "The concentration cap ensures no single position exceeds 20% of portfolio equity. At 95% utilization (19/20%), the risk engine issues a warning but does not block — the operator can choose to proceed or resize.",
        "override_guidance": "Override to proceed if you accept near-limit concentration, or resize position to stay under 20%.",
    },
    "risk_resizing": {
        "headline": "Trade resized by risk policy constraints",
        "summary": "The proposed quantity exceeds the per-trade risk cap. The risk engine resizes the position to align with policy.",
        "recommended_action": "reduce",
        "confidence_label": "medium",
        "interpretation": "Engine reduces size to comply with per-trade risk limit.",
        "key_reasons": [
            "Risk at stop for proposed 300 shares: $2,100 (1.2% of equity)",
            "Per-trade risk cap: 1.0% of equity ($1,750)",
            "Resized to 250 shares → risk at stop $1,750 (1.0% of equity)",
        ],
        "key_evidence": [
            "Risk calculation: 300sh × $7.00 stop = $2,100",
            "Cap: 1.0% × $175,000 equity = $1,750",
        ],
        "key_caveats": [
            "Resizing uses the selected stop method — changing method may change the resized quantity"
        ],
        "main_risks": ["Resized position may not meet minimum economic value for the strategy"],
        "data_quality_notes": "",
        "decision_context": "RiskAction.ALLOW with quantity=250 (was 300). Per-trade risk cap REDUCE triggered at 120% utilization.",
        "educational_context": "The per-trade risk cap limits the dollars at risk (quantity × stop distance) to a percentage of equity. When the proposed quantity exceeds this cap, the engine resizes down to the maximum compliant quantity rather than blocking the trade entirely.",
        "override_guidance": "Override to accept higher risk if you have a strong conviction — the cap is a policy guideline, not a hard block.",
    },
    "risk_hard_block": {
        "headline": "Risk engine blocks trade — buying power exceeded",
        "summary": "The proposed notional exceeds available buying power. The risk engine blocks the trade.",
        "recommended_action": "do_nothing",
        "confidence_label": "high",
        "interpretation": "Hard risk violation — cannot execute as proposed.",
        "key_reasons": [
            "Proposed notional: $47,500",
            "Available buying power: $32,000",
            "Shortfall: $15,500 (48% over limit)",
        ],
        "key_evidence": ["Buying power check: $47,500 > $32,000"],
        "key_caveats": ["Free up buying power by reducing other positions or adding capital"],
        "main_risks": [],
        "data_quality_notes": "",
        "decision_context": "RiskAction.BLOCK — buying power exceeded at 148% utilization. Hard limit breach, not subject to override.",
        "educational_context": "Buying power is calculated as equity × buying_power_pct (default 18%). When the notional of the proposed trade exceeds available buying power, the risk engine issues a hard block. This is a policy constraint that cannot be overridden through the normal sizing flow.",
        "override_guidance": "Cannot be overridden via sizing. Reduce position size or free up buying power by selling other positions.",
    },
    "overall_scorecard": {
        "headline": "Moderately positive — technical strength offsets fundamental weakness",
        "summary": "The stock shows strong technical momentum and trend-following characteristics, but elevated debt and negative earnings temper the overall score. The deterministic engine recommends watch with a score of 62/100.",
        "recommended_action": "watch",
        "confidence_label": "medium",
        "interpretation": "Broadly average score with conflicting signals across stages.",
        "key_reasons": [
            "Technical trend and momentum are the strongest contributors (82 and 78)",
            "Fundamental quality drags the score (32 — high debt, negative earnings)",
            "No hard gates triggered, but no stage strongly supports immediate entry",
        ],
        "key_caveats": [
            "Fundamental data is 3 months stale",
            "Regime is RISK_ON which amplifies scores",
        ],
        "main_risks": ["Fundamentals could deteriorate further before next filing"],
        "data_quality_notes": "Data quality pass — 92% of expected readouts available",
        "decision_context": "Final score 62/100 under RISK_ON (no regime attenuation). Recommendation: watch. Top-3 positions are not filled — discovery portfolio.",
        "educational_context": "Scorecards aggregate 13 component scores into a 0-100 composite. 62/100 falls in the 'below investable threshold but above do-nothing' band. The system watches for fundamental improvement or technical deterioration to trigger a change.",
        "override_guidance": [],
    },
    "overall_risk": {
        "headline": "Portfolio risk is elevated — concentration and VaR warnings active",
        "summary": "The portfolio shows elevated single-name concentration near limits. VaR is within budget but approaching the warn threshold. No hard limits breached — posture is 'elevated'.",
        "recommended_action": "reduce",
        "confidence_label": "medium",
        "interpretation": "Current risk posture allows trading but with constraints. Incremental risk from new positions is limited.",
        "key_reasons": [
            "Single-name concentration at 18% (cap 20%) — near-limit warning",
            "Sector concentration at 55% (cap 70%) — within limits",
            "1-day 99% VaR at 3.2% (budget 4%) — within budget",
            "Max drawdown at -8% (limit -10%) — above floor",
        ],
        "key_evidence": [
            "Concentration: effective bets = 5.2",
            "VaR: p95=1.8%, p99=3.2%, ES975=4.1%",
            "Stress scenario: −12% market shock portfolio loss",
        ],
        "key_caveats": [
            "VaR uses synthetic returns (v1 methodology)",
            "Stress scenarios are historical lookback only",
        ],
        "main_risks": [
            "Market shock could push VaR over budget",
            "Additional positions increase concentration risk",
        ],
        "data_quality_notes": "Risk engine uses synthetic returns for VaR — approximations only until Alpha-Lake returns arrive",
        "decision_context": "RiskAction.ALLOW — all limits within policy. Posture: elevated (warnings active). No hard blocks, but operator should monitor concentration.",
        "educational_context": "The Risk Engine checks 5 limits: gross exposure, VaR budget, max drawdown, sector concentration, and single-name concentration. When any limit exceeds 85% utilization, a warning is issued (elevated posture). Above 100% causes a hard block.",
        "override_guidance": [],
    },
}


class CannedLLM(LLM):
    def __init__(self, response_template: str = "", fixture_key: str = "") -> None:
        if fixture_key:
            self._template = json.dumps(_FIXTURES[fixture_key])
        elif response_template:
            self._template = response_template
        else:
            self._template = json.dumps(
                {
                    "headline": "Deterministic canned recommendation",
                    "summary": "CannedLLM output for testing.",
                    "recommended_action": "hold",
                    "confidence_label": "medium",
                    "interpretation": "Canned interpretation for testing.",
                    "key_reasons": ["Canned test reason 1", "Canned test reason 2"],
                    "key_evidence": [],
                    "key_caveats": [],
                    "main_risks": ["Canned test risk"],
                    "what_changed_since_previous_run": [],
                    "what_could_change": [],
                    "override_guidance": [],
                }
            )

    @override
    def explain(self, context: str) -> str:
        return self._template

    @override
    def generate_card(self, symbol: str, data: str) -> str:
        return json.dumps(
            {
                "symbol": symbol,
                "headline": f"Canned card for {symbol}",
                "summary": data,
            }
        )
