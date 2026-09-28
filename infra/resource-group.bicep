// Ensures the shared chat-UI resource group exists. Deploying an already-existing
// group is a no-op update, so this is safe to run before every dev/QA UI deployment.
targetScope = 'subscription'

@description('Name of the resource group to ensure exists.')
param resourceGroupName string

@description('Azure region for the resource group.')
param location string

@description('Tags applied to the resource group.')
param tags object = {}

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

output name string = rg.name
output id string = rg.id
