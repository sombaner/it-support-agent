---
name: foundry-project-model-provision
description: 'Best practices for provisioning a Microsoft Foundry (Cognitive Services AIServices) account, project, and model deployment via Bicep, plus granting inference/developer RBAC to callers. Use when creating a Foundry project, deploying a model (e.g. GlobalStandard SKU), granting Cognitive Services OpenAI User / Azure AI Developer roles, or wiring `az deployment group create` for a `qa-foundry.bicep`-style template.'
---

# Foundry Project + Model Provisioning

## When to Use
- Creating (or reusing) a Foundry `AIServices` account and a project underneath it.
- Deploying a model (e.g. `claude-haiku-4-5`, an OpenAI model) to that account.
- Granting a service principal, managed identity, or user data-plane access to call the deployed model.

## Pattern (see `infra/qa-foundry.bicep`)
`targetScope = 'resourceGroup'`.

1. **Account** — gate creation behind a `createAccount bool` param (default `false`) so environments that share one account across projects don't try to recreate it:
   ```bicep
   resource newAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = if (createAccount) {
     name: accountName
     kind: 'AIServices'
     sku: { name: 'S0' }
     identity: { type: 'SystemAssigned' }
     properties: {
       customSubDomainName: toLower(accountName)
       disableLocalAuth: true       // Entra-only; agent/UI authenticate with managed identity
       allowProjectManagement: true
     }
   }
   ```
2. Always declare a second `existing` reference to the **same name**, used for role-assignment `scope:` and to read `.id` regardless of whether this run created the account or it already existed:
   ```bicep
   resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = { name: accountName }
   ```
3. **Project** as a child resource (`Microsoft.CognitiveServices/accounts/projects`), `parent: account`, with `dependsOn: [ newAccount ]` (harmless even when `newAccount` was skipped by its `if`).
4. **Model deployment** as a child resource (`Microsoft.CognitiveServices/accounts/deployments`), `parent: account`. Build the `model` object conditionally so an empty `modelVersion` param omits the `version` field entirely (service picks the default) rather than sending an empty string. Pass `sku.capacity: int(modelCapacityParam)` — CLI/workflow parameters arrive as strings, so cast explicitly.
5. **RBAC for callers** — conditional role assignments scoped to the `account`, guarded by `if (!empty(deployerPrincipalId))` so the param can be safely left blank in environments that don't need CI/data-plane smoke-test access:
   - Cognitive Services OpenAI User: `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` (inference/data-plane calls).
   - Azure AI Developer: `64702f94-c441-49e6-a78b-ef80e0188fee` (project management).
6. Output `projectEndpoint` by string interpolation: `'https://${toLower(accountName)}.services.ai.azure.com/api/projects/${projectName}'` — don't try to read it off a resource property, the account/project resources don't expose it directly.

## Gotchas
- **Bicep cannot register resource providers.** Foundry needs `Microsoft.CognitiveServices`; if the subscription has never used it the deployment fails with `MissingSubscriptionRegistration` and no template edit can fix it. Register it in a workflow step (`az provider register --namespace Microsoft.CognitiveServices --wait`, idempotent) — see the `azure-resource-bootstrap` skill.
- **Bicep cannot delete resources.** If a workflow needs to replace a QA project on every run (rather than update it in place), the deletion (`az cognitiveservices account project delete` or equivalent) must happen as an explicit workflow step *before* the Bicep deployment — don't expect `az deployment group create` to remove a project that's no longer in the template.
- Keep the account/project/model names and the RBAC role-definition ids as parameters with sensible defaults — never hardcode a specific account or project name inline in resource bodies.
- Validate with `az bicep build --file infra/qa-foundry.bicep --stdout`, then a read-only `az deployment group what-if` before ever deploying live.
