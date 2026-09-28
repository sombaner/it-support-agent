// Environment configuration for infra/ci-rbac.bicep — the actual identifiers live here,
// not inline in the template, so the bootstrap fix can be re-applied or adapted per
// environment without editing Bicep code.
using 'ci-rbac.bicep'

// GitHub Actions OIDC app (used by both deploy-to-foundry.yml and deploy-qa.yml)
// object id, i.e. `az ad sp show --id <AZURE_CLIENT_ID> --query id -o tsv`.
param ciServicePrincipalId = '17fd38bc-eed7-420b-a35d-0e1a50794cd6'

// Shared UI resource group used by both dev and QA (must match UI_RESOURCE_GROUP
// in .github/workflows/deploy-to-foundry.yml and deploy-qa.yml).
param uiResourceGroupName = 'rg-support-agent'

// Must match UI_LOCATION in both workflows.
param location = 'eastus'

// fix done by copilot: resource provider namespaces the UI stack needs. ARM cannot register
// a provider, so this list only drives the '<namespace>/register/action' grant in the custom
// role; the registration itself is done by the "Register required resource providers" step
// in both workflows. Must match UI_RESOURCE_PROVIDERS in
// .github/workflows/deploy-to-foundry.yml and .github/workflows/deploy-qa.yml.
param resourceProviderNamespaces = [
  'Microsoft.ContainerRegistry'
  'Microsoft.App'
  'Microsoft.OperationalInsights'
  'Microsoft.ManagedIdentity'
]
