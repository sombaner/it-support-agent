// QA Foundry environment: AIServices account, the QA project, and the model deployment.
// Deleting a pre-existing project is handled by the workflow — Bicep cannot delete resources.
targetScope = 'resourceGroup'

@description('Azure region for the QA Foundry account and project.')
param location string = 'eastus'

@description('Name of the Foundry (AIServices) account that hosts the QA project.')
@minLength(3)
@maxLength(60)
param accountName string

@description('Create the account. Leave false to reuse an existing shared account untouched.')
param createAccount bool = false

@description('Name of the QA Foundry project.')
param projectName string = 'sombaner-foundry-qa'

@description('Display name shown in the Foundry portal.')
param projectDisplayName string = 'IT Support Agent - QA'

@description('Model deployment name the agent and UI call.')
param modelDeploymentName string = 'claude-haiku-4-5'

@description('Underlying model name.')
param modelName string = 'claude-haiku-4-5'

@description('Model publisher format, for example Anthropic or OpenAI.')
param modelFormat string = 'Anthropic'

@description('Model version. Leave empty to use the service default.')
param modelVersion string = ''

@description('Model deployment SKU.')
param modelSkuName string = 'GlobalStandard'

@description('Model deployment capacity. Passed as a string so CLI env values map cleanly.')
param modelCapacity string = '1'

@description('Optional principal id granted data-plane access for CI smoke tests. Leave empty to skip.')
param deployerPrincipalId string = ''

@description('Cognitive Services OpenAI User role definition id.')
param inferenceRoleDefinitionId string = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

@description('Azure AI Developer role definition id.')
param developerRoleDefinitionId string = '64702f94-c441-49e6-a78b-ef80e0188fee'

@description('Tags applied to all resources.')
param tags object = {}

var modelDefinition = empty(modelVersion)
  ? {
      format: modelFormat
      name: modelName
    }
  : {
      format: modelFormat
      name: modelName
      version: modelVersion
    }

resource newAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = if (createAccount) {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: toLower(accountName)
    publicNetworkAccess: 'Enabled'
    // Entra-only access; the agent and UI authenticate with managed identity.
    disableLocalAuth: true
    allowProjectManagement: true
  }
}

// Used for role-assignment scope and outputs whether or not this run created the account.
resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: accountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: projectDisplayName
    description: 'QA environment for the IT Support Agent.'
  }
  dependsOn: [
    newAccount
  ]
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: modelDeploymentName
  sku: {
    name: modelSkuName
    capacity: int(modelCapacity)
  }
  properties: {
    model: modelDefinition
  }
  dependsOn: [
    newAccount
    project
  ]
}

resource deployerInference 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  scope: account
  name: guid(account.id, deployerPrincipalId, inferenceRoleDefinitionId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', inferenceRoleDefinitionId)
    principalId: deployerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource deployerDeveloper 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  scope: account
  name: guid(account.id, deployerPrincipalId, developerRoleDefinitionId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', developerRoleDefinitionId)
    principalId: deployerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output accountName string = accountName
output projectName string = projectName
output projectEndpoint string = 'https://${toLower(accountName)}.services.ai.azure.com/api/projects/${projectName}'
output modelDeploymentName string = modelDeploymentName
output accountId string = account.id
output projectId string = project.id
