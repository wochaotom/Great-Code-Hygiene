# Source Pack: Agent Evaluation Methodology

- Source ID: `agent-eval-methodology`
- Activation: training loop
- Primary links:
  - OpenAI eval best practices: https://developers.openai.com/api/docs/guides/evaluation-best-practices
  - Anthropic empirical evals: https://docs.anthropic.com/en/docs/test-and-evaluate/develop-tests
  - Agent GPA paper: https://arxiv.org/abs/2510.08847
  - Snowflake Agent GPA engineering write-up: https://www.snowflake.com/en/blog/engineering/ai-agent-evaluation-gpa-framework/

## Distilled Checks

- Make evals representative of the target task and include hard cases, edge cases, and realistic task distributions.
- Use clear success criteria, consistent grading, automated judges where reliable, and human calibration for ambiguous or high-impact cases.
- Log inputs, outputs, scores, judge reasoning, run type, and comparable regression history.
- Keep eval design, grader criteria, and prompt or skill changes separated enough to avoid leakage.
- For agent traces, evaluate goal fulfillment, plan quality, plan adherence, tool-call validity and completeness, logical consistency, and execution efficiency.
- Localize failures to the final answer, plan step, tool choice, tool call, or action output when evidence allows.
- Do not treat a successful final answer as sufficient proof when the trace shows skipped requirements, fabricated support, inefficient loops, or invalid tool use.
- Label evidence honestly as script-only, audit-backed, or model-execution before using it for promotion.

## PASS-100 Focus

`agent_process`, `tests`, `correctness`
