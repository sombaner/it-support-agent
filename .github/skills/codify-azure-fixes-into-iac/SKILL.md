---
name: codify-azure-fixes-into-iac
description: 'Rule for turning any ad-hoc `az` CLI command run manually to unblock a deployment (role assignment, custom role, resource creation) into version-controlled Bicep plus a separate parameters/environment file, instead of leaving it as an undocumented one-off. Use whenever you run `az role assignment create`, `az role definition create`, `az group create`, or any other mutating Azure CLI command outside of a Bicep/GitHub Actions change, and after diagnosing a live CI `AuthorizationFailed`/permission error.'
---

# Codify Manual Azure Fixes Into IaC

## When to Use
- You (the agent) just ran a **mutating** `az` command directly in a terminal to unblock a live CI/deployment failure — e.g. a role assignment, a custom role definition, a manually created resource.
- You diagnosed a live `AuthorizationFailed` (or similar) error and are about to recommend or apply a fix.
- Anyone asks "why does this environment work when the Bicep/workflow doesn't show it" — that's a sign of undocumented drift this skill prevents.

## Core Principle
Any manual, live Azure change that isn't represented in `infra/*.bicep` or a GitHub Actions workflow is technical debt: an undocumented drift risk that the next deployment, teammate, or CI run won't know about. Every such fix must be codified back into source control before the task is considered done.

## Procedure
1. **Verify actual live state first.** Don't trust a narrative description of "what was done" — confirm it with read-only queries: `az role assignment list --assignee <id> --scope <scope>`, `az role definition list --custom-role-only true`, `az group show --name <rg>`, etc. Resolve any discrepancy (e.g. two different service-principal object ids floating around) against what's actually live before writing Bicep.
2. **Write Bicep that matches the verified live state**, one resource per manual action taken. Put a one-line comment containing the literal phrase `fix done by copilot` on every resource/module that codifies a manual remediation, so it stays traceable to "this wasn't part of the original design, it was a live fix":
   ```bicep
   // fix done by copilot: grants the CI identity the RBAC it was missing to
   // create new resource groups (see <error/PR reference> for context).
   resource bootstrapAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = { ... }
   ```
3. **No hardcoded values inside the `.bicep` file.** Every concrete value (service principal object id, resource group name, subscription-specific identifier) is a `param`; only generic defaults (well-known built-in role-definition ids, a sensible role name) belong as `param` defaults. Put the actual environment values in a separate `.bicepparam` file (`using 'file.bicep'` + `param x = '...'`) — this is the "separate environment file", not a copy of the template with values baked in.
4. **Validate without applying:**
   - `az bicep build --file infra/<file>.bicep --stdout`
   - `az bicep build-params --file infra/<file>.bicepparam --stdout`
   - `az deployment sub what-if` / `az deployment group what-if` — read-only, confirms the template's *intended* effect matches what's already live before anyone deploys it for real.
5. **Decide whether it belongs in CI.** If the fix grants permissions the CI identity is *currently missing* in order to do its normal job (e.g. subscription-scope RBAC needed to create a new resource group), do **not** wire the new template into the automated GitHub Actions workflow — the CI principal can't grant itself permissions it doesn't have. Instead, document at the top of the Bicep file that it must be deployed once by a privileged human identity, and leave it out of `.github/workflows/*.yml` entirely.
6. **Never apply a live, hard-to-reverse change without explicit user approval** — presenting the diagnosis + the codified Bicep + a `what-if` result is the deliverable; running `az deployment ... create` for real is a separate, explicitly-approved step.

## Gotcha: Find the *real* error before fixing anything
GitHub Actions shows only the outer `DeploymentFailed` / `The deployment failed with error code: DeploymentFailed`, which names the orchestrator deployment and truncates the actual cause. Never write a fix from the outer message. Drill into the inner deployment:

```bash
# Find the inner deployment name from the outer one, then:
az deployment operation group list \
  --resource-group <rg> --name <innerDeploymentName> \
  --query "[?properties.provisioningState=='Failed'].{res:properties.targetResource.id, code:properties.statusMessage.error.code, msg:properties.statusMessage.error.message}"
```

This is what turns a vague "deployment failed" into an actionable `MissingSubscriptionRegistration` / `AuthorizationFailed` / quota code.

**But deployment operations are not always enough.** Some resource providers — Container Apps in particular — never propagate their real error into the deployment record. The message degrades at every layer and the only place the truth exists is on the resource itself:

| Layer | Message |
| --- | --- |
| Outer deployment | `DeploymentFailed` — "At least one resource deployment operation failed" |
| `az deployment operation group list` | `ResourceDeploymentFailure` — "reached terminal provisioning state 'Failed'" |
| **`az containerapp env show ... --query properties.deploymentErrors`** | **`ManagedEnvironmentCapacityHeavyUsageError` + the real explanation** |

So the drill-down does not stop at the deployment operation. When an operation reports a resource "reached terminal provisioning state 'Failed'", go read that resource's own error field (`properties.deploymentErrors`, `properties.statusMessage`, or the provider's equivalent) before concluding anything. And once you find it, wire that lookup into the workflow's failure path so the next run diagnoses itself.

## Gotcha: A fix in a CI-excluded file is inert
Step 5 above deliberately keeps privileged bootstrap templates (e.g. `infra/ci-rbac.bicep`) out of the workflows. The consequence: **editing that file does not fix a live CI failure.** It stays inert until a privileged identity deploys it. If a recurring CI error "was already fixed" but keeps happening, check whether the fix landed only in a template nothing runs.

Whenever you put a fix in a CI-excluded file, you must do one of:
- state explicitly that it needs a one-time manual privileged apply, **and** give the exact command; or
- pair it with a change that actually executes in CI (a workflow step, or a template a workflow invokes).

## Gotcha: Some fixes cannot be Bicep at all
Not every remediation has an ARM representation. **Resource provider registration is the canonical example** — there is no ARM resource type for it, so `MissingSubscriptionRegistration` can never be fixed by a template edit. It has to be an `az provider register --namespace <ns> --wait` workflow step (idempotent) plus a subscription-scope `<namespace>/register/action` grant in the RBAC template. Before writing Bicep for a fix, confirm the operation is actually expressible in ARM. See the `azure-resource-bootstrap` skill.

Related: `<namespace>/register/action` is subscription-scope-only. It cannot be granted from a resource-group-scoped template no matter which role you use.

## Gotcha: Not every failure is a defect in your code
Some failures are platform-side and no template edit will fix them — regional capacity exhaustion (`...CapacityHeavyUsageError`), service outages, and temporary provider throttling. The tell is that everything upstream succeeded (provider registration, RBAC, resource group, image build) and the resource got far enough to be assigned real properties before failing. Before changing the template, confirm the failure is yours to fix. The correct "fix" for a capacity error is a configuration change (another region) plus a parameter that makes that change easy next time — not a rewrite.

## Gotcha: Some properties are immutable, so design for mobility
A resource's `location` cannot be changed in place; ARM rejects the redeploy with `InvalidResourceLocation`. If a resource may ever need to move (because its region can run out of capacity), it needs (a) its own region parameter rather than sharing one with resources that can't move, and (b) a name that includes the region, so the new region is a create rather than an illegal update. Retrofitting this after the fact costs a deletion; designing for it costs one parameter.

## Gotcha: Destructive remediation is not yours to run
Deleting a resource to unblock a retry (a failed managed environment, a stale role assignment) is irreversible and will be refused by the agent safety gate. Do not work around it. Either hand the user the exact command with the pre-checks you already ran (e.g. "`az resource list -g <rg> --resource-type <type>` returned nothing, so there are no dependents"), or find a non-destructive path — renaming the resource so the old one is simply abandoned is usually available and unblocks immediately.

## Gotcha: Deterministic Names vs. Ad-hoc Names
Bicep role assignments are typically named with `guid(scope, principalId, roleDefinitionId)` for idempotency. A role assignment created ad hoc via `az role assignment create` gets a **random** GUID name instead. Deploying the new deterministic-name template will **not** be recognized by ARM as "the same assignment" — a `what-if` will show it as a new "Create" rather than "No change", and actually deploying it would create a functionally redundant duplicate. Flag this explicitly to the user (leave as documentation-only vs. reconcile/delete-and-recreate) rather than silently deploying duplicates.

## Gotcha: Local validation can fail for environmental reasons
Scripts that shell out to `az` (e.g. `scripts/check_infra_contract.py`, which runs `az bicep build`) can fail inside a sandboxed terminal because the CLI needs write access to caches outside the workspace. Before treating such a failure as a repo defect, re-run the same underlying command directly. If it passes, the failure is environmental — do not "fix" working templates to chase it. Corroborate with `git status --short` to see what actually changed.

## Reference Example
`infra/ci-rbac.bicep` + `infra/ci-rbac-scope.bicep` + `infra/ci-rbac.bicepparam` in this repo codify exactly this pattern: a subscription-scope custom role + assignment (the part CI itself can't self-grant, documented as a one-time privileged bootstrap, not wired into any workflow) plus a resource-group-scope module for the day-to-day Contributor/User Access Administrator grants, with concrete ids/names isolated in the `.bicepparam` file.
