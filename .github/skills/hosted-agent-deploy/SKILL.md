---
name: hosted-agent-deploy
description: 'Best practices for deploying a Microsoft Foundry hosted agent via azd (`host: azure.ai.agent`, `kind: hosted`) and validating it in CI: Foundry extension install, env config sourced from GitHub Variables, `azd deploy`, `azd ai agent show`, and a smoke-test `azd ai agent invoke`. Use when configuring `azure.yaml` for a hosted agent, wiring a GitHub Actions deploy job, or debugging an empty/failed agent invoke smoke test.'
---

# Hosted Foundry Agent Deployment

## When to Use
- Configuring `azure.yaml` to deploy a Python (or other) agent as a Microsoft Foundry **hosted agent**.
- Adding or debugging the GitHub Actions job that runs `azd deploy` for the agent.
- The CI smoke test (`azd ai agent invoke`) returns empty or errors.

## `azure.yaml` Pattern (see `azure.yaml`)
```yaml
infra:
    provider: microsoft.foundry
services:
    <service-name>:
        project: .
        host: azure.ai.agent
        kind: hosted
        name: <service-name>
        codeConfiguration:
            runtime: python_3_13
            entryPoint: main.py
            dependencyResolution: remote_build   # Foundry builds from requirements.txt; no local build step needed in CI
        container:
            resources: { cpu: "1", memory: 2Gi }
        environmentVariables:
            - name: AZURE_AI_PROJECT_ENDPOINT
              value: ${AZURE_AI_PROJECT_ENDPOINT}
            - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
              value: ${AZURE_AI_MODEL_DEPLOYMENT_NAME}
        protocols:
            - protocol: responses
              version: 1.0.0
```
The Foundry project itself is typically **provisioned separately** (see `foundry-project-model-provision` skill) and merely *reused* here — endpoint and model name are read from the active `azd` environment, not declared as an `ai-project` infra block.

## Workflow Sequence (see `.github/workflows/deploy-to-foundry.yml`)
1. Run the test suite **first**, before any Azure/azd calls — fail fast on a code bug rather than burning a deployment cycle.
2. Install and verify the Foundry `azd` extension:
   ```bash
   azd config set alpha.extensions on
   azd ext install microsoft.foundry
   azd ext list | grep -q "microsoft.foundry"
   azd ai agent --help > /dev/null
   ```
3. `azure/login@v2` with OIDC (`client-id`/`tenant-id`/`subscription-id` from `vars.*`, never hardcoded), then:
   ```bash
   azd config set auth.useAzCliAuth true
   azd config set defaults.subscription "${{ vars.AZURE_SUBSCRIPTION_ID }}"
   ```
4. Select or create the azd environment, then set every value **from GitHub Variables** — never inline a literal endpoint/model name in the workflow:
   ```bash
   azd env select "$AZD_ENV_NAME" || azd env new "$AZD_ENV_NAME" --no-prompt
   azd env set AZURE_AI_PROJECT_ENDPOINT "${{ vars.FOUNDRY_PROJECT_ENDPOINT }}"
   azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "${{ vars.FOUNDRY_MODEL_DEPLOYMENT }}"
   ```
5. `azd deploy --no-prompt`.
6. `azd ai agent show --no-prompt` — surfaces deployment/config problems immediately instead of only failing on invoke.
7. Smoke test:
   ```bash
   azd ai agent invoke "$AGENT_TEST_PROMPT" > "$RUNNER_TEMP/agent-response.txt" 2>&1
   cat "$RUNNER_TEMP/agent-response.txt"
   if [[ ! -s "$RUNNER_TEMP/agent-response.txt" ]]; then
     echo "::error::The agent returned an empty response."
     exit 1
   fi
   ```

## Gotchas
- An empty invoke response almost always traces back to a stale/incorrect `AZURE_AI_PROJECT_ENDPOINT` or `AZURE_AI_MODEL_DEPLOYMENT_NAME` in the azd env — verify against the live Foundry project (`az` / `azd ai agent show` output) before assuming the agent code is broken.
- Multiple environments (dev/QA) that authenticate with the **same** OIDC service principal (check `vars.AZURE_CLIENT_ID` across workflow files) can share one CI service-principal identity/config — don't provision a second app registration unnecessarily.
- **Never strict-parse model output.** Anthropic models (e.g. `claude-haiku-4-5`) served through Foundry's OpenAI-compatible `/openai/v1/` surface silently ignore the `json_schema` `response_format` contract. Passing `options={"response_format": SomeModel}` looks like it works until the model wraps its JSON in prose and a markdown fence, which surfaces as a `ChatClientException` with `Invalid JSON: expected value at line 1 column 1`. It is intermittent because nothing enforces the shape. Drop `response_format` and extract the JSON object tolerantly instead (`src/agent.py: extract_json_object` / `parse_json_model`), falling back to the raw text.
- **`azd env` state does not persist across GitHub Actions jobs.** It lives in `.azure/` on the runner's filesystem, so any job that calls `azd ai agent *` must re-run the full install/login/`azd env set` sequence, not just `needs:` the deploying job. See the `evaluate` job in `.github/workflows/evaluate-deployed-agent.yml`; extract a composite action if another job needs it.
- **A separate, approval-gated post-deploy eval, not an inline job.** `deploy-to-foundry.yml` only deploys — it does not run evals against the live agent. `deployed-agent-eval-approval.yml` chains off `Deploy to Foundry` via `workflow_run` and gates on a required reviewer for the `deployed-agent-eval-approval` environment; `evaluate-deployed-agent.yml` then chains off *that* workflow's success. Both `workflows:` names in the `workflow_run` triggers must exactly match the upstream workflow's `name:` field, or the chain silently never fires.
