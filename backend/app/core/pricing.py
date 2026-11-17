"""
Token prices used to estimate what each investigation would cost at the
provider's published on-demand rates.

Prices are USD per one million tokens, separately for input (prompt) and
output (completion) tokens. On a free tier the actual charge is $0; the
estimate shows what the same usage would cost on a paid plan.

Override for any model with environment variables, e.g.
  LLM_PRICE_INPUT_PER_M=0.80  LLM_PRICE_OUTPUT_PER_M=4.00
(applies to the primary model when set).
"""

import os

# model -> (input $/1M tokens, output $/1M tokens, source)
MODEL_PRICES = {
    "groq/qwen/qwen3.8-27b": (
        0.80,
        4.00,
        "GroqCloud models documentation (Preview model), checked November 2026",
    ),
}


def price_for(model: str, primary_model: str | None = None) -> tuple[float, float, str] | None:
    """Return (input, output, source) prices per 1M tokens, or None if unknown."""
    if primary_model and model == primary_model:
        price_in = os.getenv("LLM_PRICE_INPUT_PER_M", "").strip()
        price_out = os.getenv("LLM_PRICE_OUTPUT_PER_M", "").strip()
        if price_in and price_out:
            try:
                return float(price_in), float(price_out), "configured prices"
            except ValueError:
                pass
    return MODEL_PRICES.get(model)


def estimate_cost(usage: dict[str, dict[str, int]], primary_model: str | None = None) -> dict:
    """
    Price per-model token usage. Returns total cost (USD), the token totals,
    a per-model breakdown, and any models without a known price.
    """
    total = 0.0
    breakdown = []
    unpriced = []
    prompt_total = completion_total = 0

    for model, values in usage.items():
        prompt = values.get("prompt_tokens", 0)
        completion = values.get("completion_tokens", 0)
        prompt_total += prompt
        completion_total += completion

        price = price_for(model, primary_model)
        if price is None:
            unpriced.append(model)
            continue

        price_in, price_out, source = price
        cost = prompt / 1_000_000 * price_in + completion / 1_000_000 * price_out
        total += cost
        breakdown.append({
            "model": model,
            "calls": values.get("calls", 0),
            "input_tokens": prompt,
            "output_tokens": completion,
            "input_price_per_million": price_in,
            "output_price_per_million": price_out,
            "cost_usd": round(cost, 6),
            "price_source": source,
        })

    return {
        "cost_usd": round(total, 6),
        "input_tokens": prompt_total,
        "output_tokens": completion_total,
        "by_model": breakdown,
        "unpriced_models": unpriced,
    }
