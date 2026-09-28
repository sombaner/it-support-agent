// Orchestrates the chat UI's shared infrastructure prerequisites: ensures the
// resource group exists, then provisions the container registry inside it.
// GitHub Actions calls this single template instead of creating the resource
// group or registry itself.
targetScope = 'subscription'

@description('Name of the resource group to ensure exists for the chat UI stack.')
param resourceGroupName string

@description('Azure region for the resource group and its resources.')
param location string

@description('Globally unique registry name (alphanumeric only).')
@minLength(5)
@maxLength(50)
param registryName string

@description('Registry SKU.')
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param registrySku string = 'Basic'

@description('Tags applied to the resource group and registry.')
param tags object = {}

module resourceGroupModule 'resource-group.bicep' = {
  name: 'rg-${uniqueString(subscription().id, resourceGroupName)}'
  params: {
    resourceGroupName: resourceGroupName
    location: location
    tags: tags
  }
}

module registryModule 'registry.bicep' = {
  name: 'acr-${uniqueString(subscription().id, resourceGroupName, registryName)}'
  scope: resourceGroup(resourceGroupName)
  params: {
    location: location
    registryName: registryName
    sku: registrySku
    tags: tags
  }
  dependsOn: [
    resourceGroupModule
  ]
}

output resourceGroupName string = resourceGroupModule.outputs.name
output registryName string = registryModule.outputs.registryName
output registryLoginServer string = registryModule.outputs.loginServer
