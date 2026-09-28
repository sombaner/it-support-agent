// fix done by copilot: one-time bootstrap that grants the CI/CD service principal the
// least-privilege RBAC it needs to run `infra/ui-stack.bicep` (which creates the shared
// UI resource group via `az deployment sub create`). Resolves:
//   AuthorizationFailed ... does not have authorization to perform action
//   'Microsoft.Resources/deployments/validate/action' over scope '/subscriptions/...'
// seen in the "Deploy resource group and container registry" workflow step, and:
//   MissingSubscriptionRegistration ... The subscription is not registered to use
//   namespace 'Microsoft.ContainerRegistry'.
// seen deploying infra/registry.bicep. Bicep/ARM cannot register a resource provider,
// so the workflow does that with `az provider register`; this template only grants the
// subscription-scope <namespace>/register/action permission that call requires.
//
// IMPORTANT: this template must be deployed by a privileged identity (subscription
// Owner/Contributor), not by the CI service principal itself — CI cannot grant itself
// the permissions this template exists to create. Deploy once (or whenever the CI
// principal or target resource group changes) with:
//   az deployment sub create --location <location> --template-file infra/ci-rbac.bicep \
//     --parameters infra/ci-rbac.bicepparam
//
// fix done by copilot: until this template is deployed, the CI principal has no
// register/action permission and the workflow's registration step fails with
// AuthorizationFailed. The namespaces in `resourceProviderNamespaces` were therefore
// registered once by a subscription Owner with (idempotent, safe to re-run):
//   for NS in $(...namespaces...); do az provider register --namespace "$NS" --wait; done
// Registration is a one-time, subscription-wide operation, so the workflow step now
// short-circuits with "already registered" for every namespace.
targetScope = 'subscription'

@description('Object id of the CI/CD service principal (GitHub Actions OIDC app) that deploys the UI stack.')
param ciServicePrincipalId string

@description('Name of the shared UI resource group the CI service principal deploys into.')
param uiResourceGroupName string

@description('Azure region for the UI resource group (must match infra/resource-group.bicep parameters used by CI).')
param location string

@description('Display name for the custom role that lets CI create/verify the UI resource group.')
param bootstrapRoleName string = 'CI Resource Group Bootstrap'

@description('Built-in Contributor role definition id, granted scoped to the UI resource group only.')
param contributorRoleDefinitionId string = 'b24988ac-6180-42a0-ab88-20f7382dd24c'

@description('Built-in User Access Administrator role definition id, granted scoped to the UI resource group only.')
param userAccessAdminRoleDefinitionId string = '18d7d88d-d35e-4fb5-a5c3-7773c20a72d9'

@description('Tags applied to the UI resource group.')
param tags object = {}

@description('Resource provider namespaces CI must be able to register. Keep in sync with UI_RESOURCE_PROVIDERS in the deploy workflows.')
param resourceProviderNamespaces array = [
  'Microsoft.ContainerRegistry'
  'Microsoft.App'
  'Microsoft.OperationalInsights'
  'Microsoft.ManagedIdentity'
]

var registerActions = [for ns in resourceProviderNamespaces: '${ns}/register/action']

// fix done by copilot: minimal subscription-scope permissions — read/create resource groups,
// run deployments, and register the resource providers this stack deploys into — instead of
// subscription-wide Contributor. Resource-provider registration is only ever a
// subscription-scope permission, so it must live here (not in ci-rbac-scope.bicep, which is
// RG-scoped and cannot register providers no matter what role it grants).
resource bootstrapRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(subscription().id, bootstrapRoleName)
  properties: {
    roleName: bootstrapRoleName
    description: 'Lets the CI identity check for and create the shared UI resource group, run subscription-scope deployments, and register the resource providers those deployments require.'
    type: 'CustomRole'
    assignableScopes: [
      subscription().id
    ]
    permissions: [
      {
        actions: union(
          [
            'Microsoft.Resources/subscriptions/resourcegroups/read'
            'Microsoft.Resources/subscriptions/resourcegroups/write'
            'Microsoft.Resources/deployments/*'
            'Microsoft.Resources/providers/read'
          ],
          registerActions
        )
        notActions: []
      }
    ]
  }
}

// fix done by copilot: subscription-scope assignment of the bootstrap role above.
resource bootstrapAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().id, ciServicePrincipalId, bootstrapRole.id)
  properties: {
    roleDefinitionId: bootstrapRole.id
    principalId: ciServicePrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Ensures the resource group exists before granting RG-scoped roles on it.
module resourceGroupModule 'resource-group.bicep' = {
  name: 'rg-${uniqueString(subscription().id, uiResourceGroupName)}'
  params: {
    resourceGroupName: uiResourceGroupName
    location: location
    tags: tags
  }
}

// fix done by copilot: RG-scoped Contributor + User Access Administrator, so CI can deploy
// the ACR/Container App and assign roles without subscription-wide access.
module uiResourceGroupRbac 'ci-rbac-scope.bicep' = {
  name: 'ui-rg-rbac-${uniqueString(subscription().id, uiResourceGroupName, ciServicePrincipalId)}'
  scope: resourceGroup(uiResourceGroupName)
  params: {
    ciServicePrincipalId: ciServicePrincipalId
    contributorRoleDefinitionId: contributorRoleDefinitionId
    userAccessAdminRoleDefinitionId: userAccessAdminRoleDefinitionId
  }
  dependsOn: [
    resourceGroupModule
  ]
}

output bootstrapRoleId string = bootstrapRole.id
output resourceGroupName string = resourceGroupModule.outputs.name
