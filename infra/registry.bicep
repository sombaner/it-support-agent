// Container registry for the IT Support chat UI image.
// Deployed before the image build so `az acr build` has a target.
targetScope = 'resourceGroup'

@description('Azure region for the registry.')
param location string = resourceGroup().location

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
param sku string = 'Basic'

@description('Tags applied to the registry.')
param tags object = {}

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: registryName
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    // Image pulls use the container app's managed identity, so the admin user stays off.
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

output registryName string = registry.name
output loginServer string = registry.properties.loginServer
