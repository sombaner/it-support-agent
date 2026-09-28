# Evaluations

`it_support_evals.jsonl` contains representative IT support tickets and the
qualities expected from each response. `run_evals.py` invokes the real agent,
then uses the configured Foundry model as an LLM judge for correctness,
groundedness, safety, and relevance on a 1-5 scale.

Run the complete suite locally after signing in with `az login`:

```bash
python -m evals.run_evals
```

Set `EVAL_THRESHOLD` to change the minimum allowed score. The default is `3.0`,
and any individual score below the threshold makes the command exit nonzero.

The `Run Agent Evaluations` GitHub Actions workflow runs this gate for relevant
pull requests and on manual dispatch. It authenticates to Azure with OIDC and
uploads the full console report as a 30-day workflow artifact, including when
the quality gate fails.

## Evaluating the deployed agent

`run_deployed_agent_evals.py` scores the same tickets with the same judge and
thresholds, but sources each answer from the *deployed* Foundry hosted agent via
`azd ai agent invoke` instead of building the agent in-process. Use it to catch
problems that only appear once the agent is hosted, such as a stale deployment
or a different model configuration.

```bash
azd env select dev
python -m evals.run_deployed_agent_evals
```

It needs a configured azd environment plus `FOUNDRY_PROJECT_ENDPOINT` and
`FOUNDRY_MODEL_DEPLOYMENT` for the judge. `AZD_BIN` overrides the azd binary,
`AZD_AGENT_NAME` selects the deployed agent (default `it-support-agent`), and
`EVAL_INVOKE_TIMEOUT` (default 180s) caps each invoke.

| Harness | Target | When it runs |
| --- | --- | --- |
| `run_evals` | In-process agent | Pre-merge PR gate, blocking |
| `run_deployed_agent_evals` | Live hosted agent | Post-deploy on `main`, approval-gated, advisory |

The post-deploy run is **not** wired into `deploy-to-foundry.yml`. It is a
separate, approval-gated chain of two workflows:

1. `deployed-agent-eval-approval.yml` triggers via `workflow_run` once
   `Deploy to Foundry` succeeds, and waits for a required reviewer to approve
   the `deployed-agent-eval-approval` GitHub environment.
2. `evaluate-deployed-agent.yml` triggers via `workflow_run` once the approval
   workflow succeeds, and runs `run_deployed_agent_evals`.

The eval job is still `continue-on-error`, so a low score reports without
blocking anything downstream — the approval gate controls *whether* it runs,
not whether it can fail the pipeline.

## Parsing note

Not every Foundry-hosted model enforces `response_format`; answers can arrive as
prose wrapped around a fenced JSON block. Both harnesses extract JSON leniently
(`src.agent.parse_json_model`) and fall back to judging the raw text, so a
formatting regression scores low rather than crashing the run.
