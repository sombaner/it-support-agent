---
name: container-app-deployment
description: 'Best practices for deploying a containerized UI/backend to Azure Container Apps via Bicep: user-assigned managed identity, ACR pull role assignment, Log Analytics-backed managed environment, and cross-resource-group role assignments. Use when deploying a Container App, building/pushing an image with `az acr build`, granting a container app''s identity access to a Foundry account in a different resource group, or wiring `az deployment group create` in a workflow.'
---

# Azure Container Apps Deployment

## When to Use
- Deploying a containerized web UI or backend service to Azure Container Apps.
- Granting a Container App's managed identity a role on a resource that lives in a *different* resource group.
- Wiring the "build image → deploy container app → verify health" sequence in a GitHub Actions job.

## Pattern (see `infra/ui.bicep`)
`targetScope = 'resourceGroup'`. Resources, in dependency order:
1. `logAnalytics` (Log Analytics workspace, `retentionInDays` param, default 30).
2. `identity` (`Microsoft.ManagedIdentity/userAssignedIdentities`) — the Container App's user-assigned identity.
3. `registry` — reference the **existing** ACR with `existing = true` only when it is co-located in the same resource group (no `scope:` needed).
4. `acrPullAssignment` (`Microsoft.Authorization/roleAssignments`, scoped to `registry`) — grants `identity` the AcrPull role (`7f951dda-4ed3-4680-a7ca-43fe172d538d`) so the Container App can pull its own image.
5. `managedEnvironment` (`Microsoft.App/managedEnvironments`) wired to `logAnalytics`.
6. `containerApp` (`Microsoft.App/containerApps`) with external ingress (e.g. port 8000), `identity.type: 'UserAssigned'` referencing `identity.id`, and the registry credential using the managed identity (not admin user/password).

Outputs: `containerAppName`, `fqdn`, `url`, `identityPrincipalId`, `identityClientId`.

## Cross-Resource-Group Role Assignments
If the Container App's identity needs a role on a resource in a **different** resource group (e.g. a shared Foundry account in `rg-sombaner-foundry` while the UI deploys into `rg-support-agent`):
- You **cannot** put `scope: resourceGroup(otherRgName)` on an inline resource inside a file whose `targetScope` is the current resource group — Bicep will fail to compile with *"A resource's scope must match the scope of the Bicep file for it to be deployable. You must use modules to deploy resources to a different scope."*
- Instead, extract the role assignment into its own module (see `infra/foundry-role-assignment.bicep`, `targetScope = 'resourceGroup'`, taking `foundryAccountName`/`principalId`/`roleDefinitionId` params and doing the `existing` lookup + role assignment internally), then call it from `ui.bicep`:
  ```bicep
  module inferenceAssignment 'foundry-role-assignment.bicep' = {
    name: 'inference-role-${uniqueString(resourceGroup().id, identityName, foundryAccountName)}'
    scope: resourceGroup(foundryResourceGroupName)
    params: {
      foundryAccountName: foundryAccountName
      principalId: identity.properties.principalId
      roleDefinitionId: inferenceRoleDefinitionId
    }
  }
  ```
- Add a `foundryResourceGroupName` param (default `resourceGroup().name`) so same-RG deployments keep working with no extra parameter.

## Workflow Sequence
0. Register the required resource providers (idempotent, must precede every `az deployment` call): `Microsoft.App`, `Microsoft.OperationalInsights`, `Microsoft.ContainerRegistry`, `Microsoft.ManagedIdentity`. See the `azure-resource-bootstrap` skill for the exact step.
1. Ensure RG + ACR exist (see `azure-resource-bootstrap` skill).
2. Build and push the image: `az acr build --registry "$ACR_NAME" --image "$REPO:$TAG" .` — tag with something traceable, e.g. `${GITHUB_SHA:0:7}-${{ github.run_number }}`.
3. Deploy the Container App: `az deployment group create --resource-group "$UI_RESOURCE_GROUP" --template-file infra/ui.bicep --parameters ... containerImage="$CONTAINER_IMAGE" ... --query properties.outputs.url.value -o tsv`.
4. Verify health with a curl loop against `${URL}/healthz` (or equivalent) before declaring the job successful.

## Regional Capacity Is the Most Likely Deployment Failure
Container Apps capacity is allocated **per region**, and busy regions (East US especially) reject new managed environments with:

```
ErrorCode: ManagedEnvironmentCapacityHeavyUsageError, Message: Creating a new managed
environment is unavailable at this time due to high demand in current region.
```

This is a platform-side constraint — it is not a quota you can raise, not an RBAC problem, and not a defect in your template. Design for it up front:

- **Give the Container Apps resources their own region parameter.** Do not reuse the one region parameter for everything. The registry, Log Analytics workspace and managed identity **cannot change location in place**, so a single shared `location` param makes the stack impossible to move. Use a separate `appLocation` (defaulting to `location`) consumed only by `managedEnvironment` and `containerApp`, driven by a `UI_APP_LOCATION` workflow variable. Log Analytics works fine cross-region — `appLogsConfiguration` only needs a customer ID and shared key.
- **Put the region in the managed environment's name**, e.g. `cae-${appName}-${environmentName}-${appLocation}`. Redeploying the same name into a new region fails with `InvalidResourceLocation: The resource 'x' already exists in location 'eastus' ... A resource with the same name cannot be created in location 'eastus2'`. A region-qualified name lets you abandon a capacity-blocked region without first deleting anything.
- **A failed managed environment never self-heals.** It persists in terminal `provisioningState: Failed` and every re-run of the same workflow fails identically. Retrying in the same region requires deleting it first: `az containerapp env delete -n <env> -g <rg> --yes`. Check for dependents first with `az resource list -g <rg> --resource-type Microsoft.App/containerApps -o table`.
- **Pick an alternate region** from https://aka.ms/acaregions rather than waiting out the capacity shortage — it can persist for days.

## Diagnosing a Failed Deployment
ARM does **not** propagate the resource provider's error text into the deployment record. For a Container Apps capacity failure the message degrades at every layer, so the workflow log alone is useless:

| Layer | Command | Message you get |
| --- | --- | --- |
| Outer deployment | workflow log | `DeploymentFailed` — "At least one resource deployment operation failed" |
| Deployment operation | `az deployment operation group list -g <rg> -n <deployment>` | `ResourceDeploymentFailure` — "reached terminal provisioning state 'Failed'" |
| **The resource itself** | `az containerapp env show -n <env> -g <rg> --query properties.deploymentErrors -o tsv` | **the actual error code and message** |

`az deployment operation group list` is **not** sufficient for Container Apps. Always read `properties.deploymentErrors` off the managed environment.

Build this into the workflow so the next failure is self-diagnosing instead of requiring a manual Azure investigation:

```yaml
if ! URL=$(az deployment group create ... --query properties.outputs.url.value -o tsv); then
  ENV_NAME="cae-${UI_APP_NAME}-dev-${UI_APP_LOCATION}"
  ERRORS=$(az containerapp env show --name "$ENV_NAME" --resource-group "$UI_RESOURCE_GROUP" \
    --query properties.deploymentErrors -o tsv 2>/dev/null || true)
  if [ -n "$ERRORS" ]; then
    echo "::error::Managed environment '$ENV_NAME' failed: $ERRORS"
  fi
  case "$ERRORS" in
    *CapacityHeavyUsage*)
      echo "::error::'$UI_APP_LOCATION' has no Container Apps capacity. Set UI_APP_LOCATION to"
      echo "::error::another region (https://aka.ms/acaregions) and re-run."
      ;;
  esac
  exit 1
fi
```

## Gotchas
- A Container App stack pulls in **four** resource providers, and a subscription that has never used them fails with `MissingSubscriptionRegistration`. `Microsoft.App` and `Microsoft.OperationalInsights` are needed for the managed environment, `Microsoft.ContainerRegistry` for the ACR, `Microsoft.ManagedIdentity` for the user-assigned identity. Bicep cannot register them — see `azure-resource-bootstrap`.
- Compile after every change: `az bicep build --file infra/ui.bicep --stdout`.
- Keep `scripts/check_infra_contract.py` in sync — any new/renamed parameter passed by the workflow must exist in the Bicep template's declared parameters, and vice versa.
- **Reproduce the deployment locally before touching CI.** The same `az deployment group create` the workflow runs can be run by hand with an existing image tag (`az acr repository show-tags --name <acr> --repository <repo> --orderby time_desc --top 3`) and the workflow's variables (`gh variable list`). It turns a 3-minute CI round trip into a seconds-long feedback loop and proves the template rather than the pipeline.
- **Nothing in the diagnostic path should be hardcoded.** The failure handler has to rebuild the managed environment's name to query it, so drive the app name and region from workflow `env:` variables (`UI_APP_NAME`, `UI_APP_LOCATION`) and pass them as Bicep parameters, rather than duplicating literals between the template and the workflow.
- Always finish with the health check. A successful `az deployment group create` only means ARM accepted the resources — the container can still crash-loop on a bad image or a missing environment variable.
