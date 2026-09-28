---
name: azure-resource-bootstrap
description: 'Best practices for creating Azure resource groups and Azure Container Registries through idempotent Bicep modules instead of ad-hoc `az group create` / `az acr create` calls in CI, and for registering the resource providers those deployments require. Use when provisioning a new resource group, creating an ACR, building a subscription-scope orchestrator module, a GitHub Actions job needs "ensure resource group exists" / "create registry" logic, or a deployment fails with MissingSubscriptionRegistration / "subscription is not registered to use namespace".'
---

# Azure Resource Bootstrap (Resource Group + ACR)

## When to Use
- Adding a new resource group or container registry to a deployment pipeline.
- A GitHub Actions workflow currently calls `az group create` / `az acr create` directly and should call Bicep instead.
- Wiring a subscription-scope "orchestrator" module that composes smaller resource-group-scope modules.

## Core Principle
Never create a resource group or registry with an inline `run:` step in a workflow. Always deploy a Bicep template that does it idempotently, so re-running the pipeline is safe and the infrastructure is reviewable in source control.

## Pattern (see `infra/resource-group.bicep`, `infra/registry.bicep`, `infra/ui-stack.bicep`)

1. **`resource-group.bicep`** — `targetScope = 'subscription'`. Params: `resourceGroupName`, `location`, `tags` (default `{}`). One `Microsoft.Resources/resourceGroups` resource — deploying it again when the RG already exists is a no-op update, not an error. Outputs: `name`, `id`.
2. **`registry.bicep`** — `targetScope = 'resourceGroup'`. Params: `location` (default `resourceGroup().location`), `registryName` (`@minLength(5) @maxLength(50)`), `sku` (`@allowed(['Basic','Standard','Premium'])`, default `Basic`), `tags`. Set `adminUserEnabled: false`, `anonymousPullEnabled: false`. Outputs: `registryName`, `loginServer`.
3. **Orchestrator (`ui-stack.bicep`)** — `targetScope = 'subscription'`. Calls both modules:
   ```bicep
   module resourceGroupModule 'resource-group.bicep' = {
     name: 'rg-${uniqueString(subscription().id, resourceGroupName)}'
     params: { resourceGroupName: resourceGroupName, location: location, tags: tags }
   }
   module registryModule 'registry.bicep' = {
     name: 'acr-${uniqueString(subscription().id, resourceGroupName, registryName)}'
     scope: resourceGroup(resourceGroupName)
     params: { location: location, registryName: registryName, sku: registrySku, tags: tags }
     dependsOn: [ resourceGroupModule ]
   }
   ```
4. The workflow deploys only the orchestrator: `az deployment sub create --location "$LOCATION" --template-file infra/ui-stack.bicep --parameters resourceGroupName=... location=... registryName=...`.

## Register resource providers before the first deployment
A subscription that has never used a resource type fails the deployment with `MissingSubscriptionRegistration` ("The subscription is not registered to use namespace 'Microsoft.ContainerRegistry'").

**ARM/Bicep cannot register a resource provider.** There is no ARM resource type for registration, so no template edit can ever fix this error. Auto-registration on first use only happens when the calling principal already holds `<namespace>/register/action`, which is a **subscription-scope-only** permission — an RG-scoped Contributor assignment can never satisfy it.

Do it as a workflow step before any `az deployment` call. `az provider register` is idempotent, so this is a no-op on every subsequent run:

```yaml
env:
  # Keep in sync with the register/action list in infra/ci-rbac.bicep.
  UI_RESOURCE_PROVIDERS: Microsoft.ContainerRegistry Microsoft.App Microsoft.OperationalInsights Microsoft.ManagedIdentity

# ...
      - name: Register required resource providers
        run: |
          set -euo pipefail
          MISSING=""
          for NS in $UI_RESOURCE_PROVIDERS; do
            STATE=$(az provider show --namespace "$NS" --query registrationState -o tsv 2>/dev/null || echo "Unknown")
            if [ "$STATE" = "Registered" ]; then echo "$NS: already registered"; continue; fi
            echo "Registering $NS (current state: $STATE)"
            if ! az provider register --namespace "$NS" --wait; then MISSING="$MISSING $NS"; fi
          done
          if [ -n "$MISSING" ]; then
            echo "::error::Could not register:$MISSING — CI needs subscription-scope '<ns>/register/action'."
            exit 1
          fi
```

Grant CI the matching permission in the subscription-scope RBAC template (`infra/ci-rbac.bicep`), parameterized so the two lists stay in sync:

```bicep
@description('Resource provider namespaces CI must be able to register. Keep in sync with UI_RESOURCE_PROVIDERS in the deploy workflows.')
param resourceProviderNamespaces array = [
  'Microsoft.ContainerRegistry'
  'Microsoft.App'
  'Microsoft.OperationalInsights'
  'Microsoft.ManagedIdentity'
]
var registerActions = [for ns in resourceProviderNamespaces: '${ns}/register/action']
// ... permissions: [ { actions: union([ /* base actions */ 'Microsoft.Resources/providers/read' ], registerActions), notActions: [] } ]
```

Namespaces commonly needed: `Microsoft.ContainerRegistry` (ACR), `Microsoft.App` + `Microsoft.OperationalInsights` (Container Apps), `Microsoft.ManagedIdentity` (user-assigned identities), `Microsoft.CognitiveServices` (Foundry).

Check state before assuming: `az provider show --namespace <ns> --query registrationState -o tsv`.

## Gotchas
- Creating a **new** resource group via `az deployment sub create` is inherently subscription-scope. It requires `Microsoft.Resources/subscriptions/resourcegroups/write` and `Microsoft.Resources/deployments/*` at the **subscription**, not just Contributor on an already-existing resource group. If CI gets `AuthorizationFailed` on `Microsoft.Resources/deployments/validate/action` at subscription scope, this is almost always the cause — see the `codify-azure-fixes-into-iac` skill for how to grant it via Bicep.
- After changing which Bicep template a workflow directly invokes (e.g. merging two `run:` steps into one orchestrator module), update `scripts/check_infra_contract.py`'s `checks` list to reference the new template — it validates that a workflow's `--parameters`/`--query properties.outputs...` match the compiled template's declared parameters/outputs, and its marker-string extraction breaks if the workflow no longer contains that literal `--template-file <path>` string.
- Always compile every changed `infra/*.bicep` file with `az bicep build --file <file> --stdout` before considering the change done.
- The resource group's region does **not** constrain where its resources live, so a capacity-blocked region only forces the affected workload to move — not the whole stack. Keep the shared, location-immutable resources (resource group, registry) on one region parameter and give compute its own. See the `container-app-deployment` skill's "Regional Capacity Is the Most Likely Deployment Failure" section.
