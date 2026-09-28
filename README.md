# IT Support Agent

A Microsoft Foundry-hosted IT Support Agent built on the Microsoft Agent Framework. It helps employees triage common IT issues — network, VPN, Microsoft Teams call quality, account/password, printers, and endpoint health — using built-in diagnostic tools, and returns a structured support summary (issue, steps taken, resolution, follow-up).

Authentication uses `DefaultAzureCredential` (for example, an `az login` session or a hosted managed identity). No API keys are read from code or environment.

## Repository layout

- `src/agent.py` — builds the agent: loads the system prompt, registers the diagnostic tools, connects to the configured model deployment in a Foundry project, and returns a typed `SupportSummary`.
- `src/tools/` — the diagnostic tools: `diagnostics` (network), `vpn`, `teams` (call quality), `identity` (account status), `printing` (print queue), and `endpoint` (device health).
- `src/prompts/system.md` — the agent's system instructions.
- `main.py` — hosted-agent entry point; serves the agent over the Foundry Responses protocol.
- `web/` — responsive streaming chat client served by the FastAPI app.
- `tests/` — pytest tests for the agent and each tool.
- `evals/` — evaluation harness and dataset (`run_evals.py`, `it_support_evals.jsonl`).
- `.github/workflows/` — CI, security, and Foundry deploy workflows.
- `azure.yaml` / `foundry.yaml` — hosted Foundry agent configuration.

## Demo diagnostic data

The diagnostic tools currently use small in-memory placeholder datasets with sample users such as `alice` and `bob`. These records are intentionally hardcoded for local demos, tests, and evaluations only; they are not production data and do not contain secrets.

For production use, replace the placeholder dictionaries in `src/tools/` with real enterprise data sources, such as Microsoft Entra ID for account status, Intune or endpoint-management telemetry for device health, Teams call analytics for meeting quality, VPN gateway telemetry for VPN status, and a print-server or printer-management API for print queues.

## Local setup

1. Create and activate a Python virtual environment.
2. Install development dependencies with `pip install -r requirements-dev.txt`.
3. Copy `.env.example` to `.env` and fill in your Foundry project endpoint and model deployment.
4. Sign in with `az login`.
5. Run the agent against a sample request with `python -m src.agent`.
6. Run the chat UI with `uvicorn src.app:app --reload`, then open `http://127.0.0.1:8000`.
7. Run tests with `pytest`.
8. Run evaluations with `python -m evals.run_evals`.

## Environment variables

See `.env.example`. The agent reads the `FOUNDRY_*` names first, then falls back to the `AZURE_AI_*` names that the hosted Foundry runtime and azd inject, so the same code runs locally and when deployed.

- `FOUNDRY_PROJECT_ENDPOINT` — Microsoft Foundry project endpoint, e.g. `https://<account>.services.ai.azure.com/api/projects/<project>`. (Fallback: `AZURE_AI_PROJECT_ENDPOINT`.)
- `FOUNDRY_MODEL_DEPLOYMENT` — model deployment name (`claude-haiku-4-5` for this project). (Fallback: `AZURE_AI_MODEL_DEPLOYMENT_NAME`.)
- `APPLICATIONINSIGHTS_CONNECTION_STRING` — optional Application Insights tracing connection string.
- `IT_SUPPORT_KNOWLEDGE_BASE_PATH` — optional knowledge-base location.
- `TICKETING_API_BASE_URL` — optional ticketing-system API endpoint.

## Evaluations

`evals/run_evals.py` runs each ticket in `it_support_evals.jsonl` through the agent, then uses the same Foundry model as an LLM judge to score correctness, groundedness, safety, and relevance on a 1-5 scale. It prints a table and exits non-zero if any score falls below the threshold (default 3.0). The standalone `Run Agent Evaluations` workflow runs this quality gate for relevant pull requests and manual dispatches, then retains the report as a workflow artifact.

## Deployment

The agent deploys as a hosted Foundry agent via the Azure Developer CLI (azd), configured in `azure.yaml` (direct-code deploy, `python_3_13`, remote build from `requirements.txt`). The `.github/workflows/deploy-to-foundry.yml` workflow runs tests, deploys on push to `main` or manual dispatch, reports hosted-agent status, and performs a non-empty response smoke test. Authentication uses GitHub to Azure OIDC, and all Foundry configuration comes from repository variables rather than a committed azd environment. The workflow assumes the OIDC identity and hosted agent identity already have their required Foundry and model roles.
