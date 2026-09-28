// QA deployment entry point.
//
// Bicep cannot delete resources declaratively, so this template runs an Azure CLI
// deployment script that removes the existing QA project, then creates the account,
// project, and model deployment through the qa-foundry module.
//
// Deploy with:
//   az deployment group create -g <rg> -f infra/qa-deployment.bicep
targetScope = 'resourceGroup'

@description('Azure region for the QA Foundry account and project.')
param location string = 'eastus'

@description('Name of the Foundry (AIServices) account that hosts the QA project.')
param accountName string = 'sombaner-azure-foundry'

@description('Create the account. Leave false to reuse an existing shared account untouched.')
param createAccount bool = false

@description('Name of the QA Foundry project.')
param projectName string = 'sombaner-foundry-qa'

@description('Display name shown in the Foundry portal.')
param projectDisplayName string = 'IT Support Agent - QA'

@description('Delete the project before recreating it.')
param recreateProject bool = true

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

@description('Model deployment capacity.')
param modelCapacity string = '1'

@description('Optional principal id granted data-plane access for CI smoke tests.')
param deployerPrincipalId string = ''

@description('API version used to look up and delete the project.')
param cognitiveServicesApiVersion string = '2025-06-01'

@description('Forces the delete script to run on every deployment.')
param deploymentTimestamp string = utcNow()

@description('Tags applied to all resources.')
param tags object = {}

// Cognitive Services Contributor — least privilege needed to delete a Foundry project.
var cognitiveServicesContributorRoleId = '25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68'
var scriptIdentityName = 'id-qa-deploy-${projectName}'

resource scriptIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = if (recreateProject) {
  name: scriptIdentityName
  location: location
  tags: tags
}

resource scriptRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (recreateProject) {
  name: guid(resourceGroup().id, scriptIdentityName, cognitiveServicesContributorRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      cognitiveServicesContributorRoleId
    )
    principalId: scriptIdentity!.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource deleteProject 'Microsoft.Resources/deploymentScripts@2023-08-01' = if (recreateProject) {
  name: 'delete-${projectName}'
  location: location
  tags: tags
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${scriptIdentity!.id}': {}
    }
  }
  properties: {
    azCliVersion: '2.64.0'
    retentionInterval: 'PT1H'
    timeout: 'PT30M'
    cleanupPreference: 'OnSuccess'
    forceUpdateTag: deploymentTimestamp
    environmentVariables: [
      {
        name: 'SUBSCRIPTION_ID'
        value: subscription().subscriptionId
      }
      {
        name: 'RESOURCE_GROUP'
        value: resourceGroup().name
      }
      {
        name: 'ACCOUNT_NAME'
        value: accountName
      }
      {
        name: 'PROJECT_NAME'
        value: projectName
      }
      {
        name: 'API_VERSION'
        value: cognitiveServicesApiVersion
      }
    ]
    scriptContent: '''
set -euo pipefail

PROJECT_ID="/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${ACCOUNT_NAME}/projects/${PROJECT_NAME}"
DELETED=false

# Role assignments can take a moment to propagate to the script identity.
for attempt in 1 2 3 4 5 6; do
  if az account show >/dev/null 2>&1; then
    break
  fi
  echo "Waiting for identity to be ready (attempt ${attempt})..."
  sleep 10
done

az account set --subscription "${SUBSCRIPTION_ID}"

if az resource show --ids "${PROJECT_ID}" --api-version "${API_VERSION}" >/dev/null 2>&1; then
  echo "Deleting existing project ${PROJECT_NAME}..."
  az resource delete --ids "${PROJECT_ID}" --api-version "${API_VERSION}"
  DELETED=true
  echo "Deleted ${PROJECT_NAME}."
else
  echo "Project ${PROJECT_NAME} does not exist; nothing to delete."
fi

echo "{\"deleted\": ${DELETED}, \"projectName\": \"${PROJECT_NAME}\"}" > "${AZ_SCRIPTS_OUTPUT_PATH}"
'''
  }
  dependsOn: [
    scriptRoleAssignment
  ]
}

module qaFoundry 'qa-foundry.bicep' = {
  name: 'qa-foundry'
  params: {
    location: location
    accountName: accountName
    createAccount: createAccount
    projectName: projectName
    projectDisplayName: projectDisplayName
    modelDeploymentName: modelDeploymentName
    modelName: modelName
    modelFormat: modelFormat
    modelVersion: modelVersion
    modelSkuName: modelSkuName
    modelCapacity: modelCapacity
    deployerPrincipalId: deployerPrincipalId
    tags: tags
  }
  dependsOn: [
    deleteProject
  ]
}

output accountName string = qaFoundry.outputs.accountName
output projectName string = qaFoundry.outputs.projectName
output projectEndpoint string = qaFoundry.outputs.projectEndpoint
output projectId string = qaFoundry.outputs.projectId
output modelDeploymentName string = qaFoundry.outputs.modelDeploymentName
output projectDeleted bool = recreateProject ? deleteProject!.properties.outputs.deleted : false
