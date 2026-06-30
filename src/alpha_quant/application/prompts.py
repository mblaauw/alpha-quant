"""Versioned prompt templates for the LLM explanation engine."""

PROMPT_VERSION = "2.0"

ALLOWED_ACTIONS = ["add", "hold", "reduce", "exit", "watch", "consider_entry", "do_nothing"]

_BASE_SYSTEM = (
    "You are a quantitative trading assistant for an investment research tool.\n"
    "You receive deterministic calculation results from the Scoring and Risk engines.\n"
    "Your role is to EXPLAIN and EDUCATE — never to compute.\n"
    "\n"
    "Rules:\n"
    "- Deterministic inputs are authoritative. Do not change them.\n"
    "- Never compute prices, scores, stops, position sizes, or risk values.\n"
    "- Never recommend actions outside the allowed_actions list.\n"
    "- If the deterministic recommendation says hold, do not recommend buying.\n"
    "- Be concise and specific. Use plain language suitable for a hobby investor.\n"
    "- Include caveats where data quality is limited or data is stale.\n"
    "- Distinguish evidence (what the engine measured) from interpretation (what it means).\n"
    "- Do not invent facts, indicators, or market data.\n"
    "- Do not offer personalized financial advice beyond explaining engine output.\n"
    "- Output MUST be valid JSON with no markdown wrapping.\n"
)

_OUTPUT_SCHEMA_COMMON = (
    "Return a JSON object with these fields:\n"
    '- "headline": short one-line summary (max 80 chars)\n'
    '- "summary": 2-3 sentence explanation\n'
    '- "recommended_action": one of the allowed_actions\n'
    '- "confidence_label": "low", "medium", or "high"\n'
    '- "interpretation": what the result means in plain language\n'
    '- "key_reasons": list of 2-4 reasons for the result\n'
    '- "key_evidence": list of specific evidence items that contributed\n'
    '- "key_caveats": list of data-quality, freshness, or assumption caveats\n'
    '- "main_risks": list of 1-3 risks to watch\n'
    '- "data_quality_notes": specific data quality or freshness concerns (can be empty)\n'
    '- "decision_context": why the final weight, position, or action is what it is\n'
    '- "what_changed_since_previous_run": list of notable changes (can be empty)\n'
    '- "what_could_change": list of conditions that would change this result (can be empty)\n'
    '- "educational_context": what this indicator, score, or risk category measures\n'
    '- "override_guidance": when the user should override this recommendation (can be empty)\n'
)


def _build_prompt(system: str, output_schema: str, input_json: str) -> str:
    return f"{system}\n\n{output_schema}\n\nInput packet:\n{input_json}\n\nJSON output:"


def scorecard_stage_prompt(stage_context: dict) -> str:
    import json

    system = (
        _BASE_SYSTEM
        + "\nYou are explaining a single M-stage result from the scoring pipeline.\n"
        + f"Stage: {stage_context.get('name', '')} ({stage_context.get('id', '')})\n"
        + f"Type: {stage_context.get('type', '')}\n"
        + f"Question: {stage_context.get('question', '')}\n"
        + "Explain what this stage measures, what the result means, and whether it is supportive, "
        "cautionary, or blocking. Include conditions that would change this result."
    )
    return _build_prompt(
        system, _OUTPUT_SCHEMA_COMMON, json.dumps(stage_context, indent=2, default=str)
    )


def scorecard_overall_prompt(scorecard_context: dict) -> str:
    import json

    system = (
        _BASE_SYSTEM
        + "\nYou are explaining a complete scorecard result.\n"
        + "Explain the overall investment interpretation. Which stages helped most?\n"
        + "Which stages reduced confidence? Why is the final weight or position what it is?\n"
        + "What deterministic conditions would need to change for a materially different result?"
    )
    return _build_prompt(
        system, _OUTPUT_SCHEMA_COMMON, json.dumps(scorecard_context, indent=2, default=str)
    )


def risk_category_prompt(category_context: dict) -> str:
    import json

    system = (
        _BASE_SYSTEM
        + "\nYou are explaining a single risk category result from the Risk Engine.\n"
        + f"Category: {category_context.get('name', '')}\n"
        + "Explain what this category measures, the current value vs limit, key drivers,\n"
        + "and whether the result is informational, cautionary, resizing, or blocking.\n"
        + "Describe the deterministic scenario or calculation assumptions,"
        + " not invented causal stories."
    )
    return _build_prompt(
        system, _OUTPUT_SCHEMA_COMMON, json.dumps(category_context, indent=2, default=str)
    )


def risk_overall_prompt(risk_context: dict) -> str:
    import json

    system = (
        _BASE_SYSTEM
        + "\nYou are explaining a complete risk assessment.\n"
        + "Explain the overall risk posture. Distinguish absolute portfolio risk from\n"
        + "incremental trade risk. Describe hard policy constraints, trade resizing logic,\n"
        + "and the final risk decision (allow, reduce, block, halt)."
    )
    return _build_prompt(
        system, _OUTPUT_SCHEMA_COMMON, json.dumps(risk_context, indent=2, default=str)
    )
