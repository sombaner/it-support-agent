// Resource-group-scoped half of the CI bootstrap RBAC fix (see infra/ci-rbac.bicep).
// fix done by copilot: grants the CI identity only what it needs inside the shared
// UI resource group, instead of Contributor/User Access Administrator at subscription scope.
targetScope = 'resourceGroup'

@description('Object id of the CI/CD service principal that deploys the UI stack.')
param ciServicePrincipalId string

@description('Built-in Contributor role definition id.')
param contributorRoleDefinitionId string

@description('Built-in User Access Administrator role definition id.')
param userAccessAdminRoleDefinitionId string

// fix done by copilot: lets CI create/update the ACR and Container App in this resource group.
resource contributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, ciServicePrincipalId, contributorRoleDefinitionId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', contributorRoleDefinitionId)
    principalId: ciServicePrincipalId
    principalType: 'ServicePrincipal'
  }
}

// fix done by copilot: lets CI assign the container app's managed identity the ACR-pull
// and Foundry-inference roles that infra/ui.bicep creates.
resource userAccessAdminAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, ciServicePrincipalId, userAccessAdminRoleDefinitionId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', userAccessAdminRoleDefinitionId)
    principalId: ciServicePrincipalId
    principalType: 'ServicePrincipal'
  }
}
