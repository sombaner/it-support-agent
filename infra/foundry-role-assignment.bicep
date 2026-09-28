// Grants a principal an inference role on an existing Foundry account.
// Deployed as a module scoped to the Foundry account's own resource group,
// which may differ from the resource group the calling template targets.
targetScope = 'resourceGroup'

@description('Name of the existing Foundry (AIServices) account.')
param foundryAccountName string

@description('Principal id (managed identity) to grant the role to.')
param principalId string

@description('Role definition id to assign, for example Cognitive Services OpenAI User.')
param roleDefinitionId string

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource inferenceAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundryAccount
  name: guid(foundryAccount.id, principalId, roleDefinitionId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
