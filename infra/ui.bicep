// Chat UI (FastAPI + web/index.html) hosted on Azure Container Apps.
// Authentication to Foundry uses a user-assigned managed identity — no API keys.
targetScope = 'resourceGroup'

@description('Azure region for the UI resources.')
param location string = resourceGroup().location

// fix done by copilot: Container Apps capacity is allocated per region and East US returns
// ManagedEnvironmentCapacityHeavyUsageError. The managed environment and container app get
// their own region so they can move without relocating the registry, workspace or identity
// (those cannot change location in place). Configured via UI_APP_LOCATION in the workflows.
@description('Azure region for the Container Apps environment and container app. Defaults to location; override when the primary region has no Container Apps capacity.')
param appLocation string = location

@description('Environment discriminator used in resource names, for example dev or qa.')
@minLength(2)
@maxLength(10)
param environmentName string

@description('Base name for the UI workload.')
param appName string = 'it-support-ui'

@description('Name of an existing container registry that holds the UI image.')
param registryName string

@description('Fully qualified image reference, for example myacr.azurecr.io/it-support-ui:abc123.')
param containerImage string

@description('Name of the existing Foundry (AIServices) account the UI calls.')
param foundryAccountName string

@description('Resource group containing the existing Foundry account, if different from this deployment\'s resource group.')
param foundryResourceGroupName string = resourceGroup().name

@description('Foundry project endpoint the agent connects to.')
param foundryProjectEndpoint string

@description('Model deployment name used by the agent.')
param modelDeploymentName string

@description('Default user id applied to chat requests that omit one.')
param demoUserId string = 'alice'

@description('vCPU allocated to the container.')
param cpu string = '0.5'

@description('Memory allocated to the container.')
param memory string = '1Gi'

@description('Minimum replica count.')
@minValue(0)
param minReplicas int = 1

@description('Maximum replica count.')
@minValue(1)
param maxReplicas int = 3

@description('Log Analytics retention in days.')
param retentionInDays int = 30

@description('Role granting the UI identity inference access to Foundry. Defaults to Cognitive Services OpenAI User.')
param inferenceRoleDefinitionId string = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

@description('Tags applied to all resources.')
param tags object = {}

var acrPullRoleDefinitionId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var containerAppName = '${appName}-${environmentName}'
var identityName = 'id-${appName}-${environmentName}'
// fix done by copilot: the region is part of the name because a managed environment cannot
// change location in place — ARM rejects a redeploy of the same name in a new region with
// InvalidResourceLocation. Naming it per region lets a capacity-blocked region be abandoned.
var managedEnvironmentName = 'cae-${appName}-${environmentName}-${appLocation}'
var logAnalyticsName = 'log-${appName}-${environmentName}'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2025-07-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: identityName
  location: location
  tags: tags
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: registryName
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: guid(registry.id, identity.id, acrPullRoleDefinitionId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleDefinitionId)
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// The Foundry account may live in a different resource group than this deployment,
// so the role assignment on it is deployed as a module scoped to that resource group.
module inferenceAssignment 'foundry-role-assignment.bicep' = {
  name: 'inference-role-${uniqueString(resourceGroup().id, identityName, foundryAccountName)}'
  scope: resourceGroup(foundryResourceGroupName)
  params: {
    foundryAccountName: foundryAccountName
    principalId: identity.properties.principalId
    roleDefinitionId: inferenceRoleDefinitionId
  }
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2025-07-01' = {
  name: managedEnvironmentName
  location: appLocation
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2025-07-01' = {
  name: containerAppName
  location: appLocation
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: appName
          image: containerImage
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: [
            {
              name: 'FOUNDRY_PROJECT_ENDPOINT'
              value: foundryProjectEndpoint
            }
            {
              name: 'FOUNDRY_MODEL_DEPLOYMENT'
              value: modelDeploymentName
            }
            {
              // Tells DefaultAzureCredential which user-assigned identity to use.
              name: 'AZURE_CLIENT_ID'
              value: identity.properties.clientId
            }
            {
              name: 'DEMO_USER_ID'
              value: demoUserId
            }
          ]
          probes: [
            {
              type: 'Readiness'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 10
              failureThreshold: 3
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/healthz'
                port: 8000
              }
              initialDelaySeconds: 15
              periodSeconds: 30
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
  dependsOn: [
    acrPullAssignment
    inferenceAssignment
  ]
}

output containerAppName string = containerApp.name
output fqdn string = containerApp.properties.configuration.ingress.fqdn
output url string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output identityPrincipalId string = identity.properties.principalId
output identityClientId string = identity.properties.clientId
