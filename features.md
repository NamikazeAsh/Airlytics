# Planned features

Backlog of features not yet built, kept here so the reasoning behind each isn't lost between sessions.

## 1. Personalized forecasting model (readiness / HRV) — DONE

Built as `app/forecasting/` (feature_builder, model, evaluation, forecast_service),
`POST /api/forecast/train` + `GET /api/forecast/{status,prediction}`, and a "Readiness
forecast" dashboard section. Real result against the actual synced data (n=54, since a bit
more synced since this was scoped): **model MAE 8.78 vs. naive-baseline MAE 10.41 — a 15.6%
improvement over predicting tomorrow = today**, walk-forward validated over 34 test folds.
Modest, as expected, and it's an honest number — no leakage (predicts a future day from
past-only features), correct time-series validation, explicit baseline comparison.

Original scoping notes below, kept for context.

Train a model on the user's own history to forecast **tomorrow's** readiness/HRV from
lag features (recent HRV, resting HR, sleep efficiency, active minutes), instead of the
current rule-based rolling averages/z-scores.

- **Leakage trap to avoid**: readiness is *computed* from today's HRV/RHR/sleep-efficiency
  (`analytics/readiness.py`). Predicting *today's* readiness from *today's* HRV/RHR/sleep
  would just re-derive the formula (~100% "accuracy", meaningless). The model must predict
  a future value from past values only.
- **Model**: start with a regularized linear model (Ridge/ElasticNet) — appropriate given
  ~100+ days of single-subject data (small n). Consider LightGBM only if linear underfits.
- **Validation**: walk-forward / expanding-window CV (never random k-fold on a time series).
  Report against a naive-persistence baseline (predict tomorrow = today, or = 7-day rolling
  average) — the honest resume claim is "beats naive baseline by X%," not a headline R².
- **Expected reality**: day-to-day HRV/RHR is noisy and driven by things not in the feature
  set (illness, alcohol, stress, travel), so expect only a modest improvement over baseline.
  That's fine — correctly framing/validating this is the actual resume value, not the number.
- **Follow-on**: feature importance (SHAP or permutation importance) on the trained model,
  fed into the coach's explanations ("your dip is mostly driven by declining sleep
  efficiency, not HRV").

## 2. LLM evaluation harness for the AI coach — DONE

Built as `backend/evals/` (seed_data, cases, scorer, runner) — run with
`python -m evals.runner`, hits the real Groq API against a fixed synthetic seeded dataset,
scores 8 curated cases for tool-call correctness and rule-based grounding.

**Real results, and a genuinely interesting debugging story**: the first run scored
tool-call accuracy 62% and grounding accuracy 12% — but inspecting the actual flagged
replies showed the low grounding score was mostly the *checker's* bug, not the model's: the
LLM renders dates and negative signs with a Unicode non-breaking hyphen (U+2011), not ASCII
`-`, so "2026‑08‑01" was mis-split into stray positive numbers and negative z-scores lost
their sign. Fixing date-stripping and dash normalization brought grounding accuracy to 50%
on a like-for-like re-run. One flagged case led further: the model was asked for "last
month's average steps," called `get_metric_series` (not `get_rolling_average` — a separate,
legitimate tool-call miss), then **correctly summed 31 real daily values by hand**
(266,593 ÷ 31 = 8,599.8, verified by hand against the seeded data) — a number that's
genuinely grounded but doesn't literally appear in any tool result, so the checker still
flags it. That's a real, named limitation (can't yet distinguish "correctly derived from
real data" from "fabricated"), documented in `evals/scorer.py`'s docstring rather than
glossed over, along with the remaining residual false-positive sources (numbered-list
markers, dash-separated ranges like "18-19°C" colliding with the negative-sign heuristic).
Tool-call accuracy also visibly varies run-to-run (the model isn't deterministic) — expected
and worth knowing before trusting any single eval run's score in isolation.

Original scoping notes below, kept for context.

A curated set of test questions with expected tool calls and/or expected grounded answers,
scored automatically for:

- **Tool-call correctness** — did the coach call the right analytics tool(s) for the
  question (e.g. "how has my HRV trended" → `get_trend`, not a guess)?
- **Grounding / hallucination rate** — does every number in the reply trace back to a tool
  result or the system prompt (per the grounding rule already in `context_builder.py`), or
  did the model state a figure it never retrieved?

Buildable on the existing test infra (`respx` mocks already used in
`tests/unit/ai_coach/`) — no new dependencies needed. Output: a small report/score
(e.g. % of eval questions correctly grounded) that can be re-run whenever the prompt,
tools, or model changes, to catch regressions.

## 3. Model comparison + feature importance for the readiness forecast — DONE

Extended `app/forecasting/` rather than adding a new module: `model.py` now holds a
`MODEL_CANDIDATES` registry (Ridge, ElasticNet, a deliberately small/regularized
`GradientBoostingRegressor`), `evaluation.py` gained `compare_models()` running the same
walk-forward validation across all three, and `forecast_service.get_feature_importance()`
uses `sklearn.inspection.permutation_importance` (no new dependency, and model-agnostic
unlike raw coefficients) on whichever candidate wins. Surfaced on the dashboard (model
comparison + top-drivers panel) and as a new coach tool, `get_readiness_drivers`.

**Real result against the actual synced data**: ElasticNet won (MAE 8.68, 16.6% improvement
over naive baseline), narrowly ahead of Ridge (8.78, 15.6%), with GradientBoosting
genuinely losing (9.11, 12.5%) — exactly the expected outcome given n≈54, not a rigged
comparison. Feature importance: resting heart rate dominates the prediction (63.7%), then
yesterday's readiness (15.2%), HRV (11.1%), sleep efficiency (10.0%). Verified live: asking
the coach "what's driving my readiness predictions" correctly triggered
`get_readiness_drivers` and cited these exact numbers back, not a guess.
