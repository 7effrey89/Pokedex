targetScope = 'subscription'

@minLength(1)
@maxLength(64)
param environmentName string

@minLength(1)
param location string

@minLength(1)
param sessionId string

@minLength(1)
param deployedBy string

@minLength(1)
param createdAt string

@minLength(1)
param deployerObjectId string

@description('Container image name and tag within the existing registry.')
param containerImageName string = 'pokedex-app:latest'

@allowed([
  'key'
  'service_principal'
])
param azureAuthMode string = 'key'

param foundryProjectEndpoint string = ''
@minLength(1)
param azureOpenAiEndpoint string
@minLength(1)
param azureOpenAiDeployment string
param azureOpenAiApiVersion string = '2024-10-21'
param azureOpenAiRealtimeEndpoint string = ''
param azureOpenAiRealtimeDeployment string = 'gpt-realtime'
param azureOpenAiRealtimeApiVersion string = '2024-10-01-preview'
param azureAppRegistrationName string = ''
param azureClientId string = ''
param azureTenantId string = ''
param azureTokenScope string = 'https://cognitiveservices.azure.com/.default'
param pokemonApiUrl string = 'https://pokeapi.co/api/v2'

@secure()
param azureOpenAiApiKey string

@secure()
param azureClientSecret string

@secure()
param pokemonTcgApiKey string

@secure()
param appApiPassword string

@minValue(1)
@maxValue(250)
param tcgPageSize int = 250

var resourceGroupName = 'pokedex-rg'
var appServicePlanName = 'pokedex-chat-plan'
var appServiceName = 'app-pokedex-prod-0f50'
var containerRegistryName = 'pokedexacr2'
var keyVaultName = 'kv-pokedex-prod-0f50'
var logAnalyticsName = 'log-pokedex-prod-0f50'
var applicationInsightsName = 'appi-pokedex-prod-0f50'

var tags = {
  'app-onboard-skill': 'true'
  'app-onboard-session-id': sessionId
  'created-at': createdAt
  environment: environmentName
  'deployed-by': deployedBy
}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module appServicePlan './modules/app-service-plan.bicep' = {
  name: 'app-service-plan'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    appServicePlanName: appServicePlanName
  }
}

module containerRegistry './modules/container-registry.bicep' = {
  name: 'container-registry'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    containerRegistryName: containerRegistryName
  }
}

module keyVault './modules/key-vault.bicep' = {
  name: 'key-vault'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    keyVaultName: keyVaultName
  }
}

module logAnalytics './modules/log-analytics.bicep' = {
  name: 'log-analytics'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    logAnalyticsName: logAnalyticsName
  }
}

module applicationInsights './modules/application-insights.bicep' = {
  name: 'application-insights'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    applicationInsightsName: applicationInsightsName
    workspaceResourceId: logAnalytics.outputs.workspaceResourceId
  }
}

module appService './modules/app-service.bicep' = {
  name: 'app-service'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    appServiceName: appServiceName
    appServicePlanId: appServicePlan.outputs.appServicePlanId
    containerRegistryLoginServer: containerRegistry.outputs.loginServer
    containerImageName: containerImageName
    applicationInsightsConnectionString: applicationInsights.outputs.connectionString
    azureAuthMode: azureAuthMode
    foundryProjectEndpoint: foundryProjectEndpoint
    azureOpenAiEndpoint: azureOpenAiEndpoint
    azureOpenAiApiKey: azureOpenAiApiKey
    azureOpenAiDeployment: azureOpenAiDeployment
    azureOpenAiApiVersion: azureOpenAiApiVersion
    azureOpenAiRealtimeEndpoint: azureOpenAiRealtimeEndpoint
    azureOpenAiRealtimeDeployment: azureOpenAiRealtimeDeployment
    azureOpenAiRealtimeApiVersion: azureOpenAiRealtimeApiVersion
    azureAppRegistrationName: azureAppRegistrationName
    azureClientId: azureClientId
    azureTenantId: azureTenantId
    azureClientSecret: azureClientSecret
    azureTokenScope: azureTokenScope
    pokemonApiUrl: pokemonApiUrl
    pokemonTcgApiKey: pokemonTcgApiKey
    tcgPageSize: tcgPageSize
    appApiPassword: appApiPassword
  }
}

module roleAssignments './modules/role-assignments.bicep' = {
  name: 'role-assignments'
  scope: resourceGroup
  params: {
    keyVaultName: keyVaultName
    containerRegistryName: containerRegistryName
    appPrincipalId: appService.outputs.principalId
    deployerObjectId: deployerObjectId
  }
}

output resourceGroupName string = resourceGroup.name
output appServiceName string = appService.outputs.appServiceName
output appServiceDefaultHostName string = appService.outputs.defaultHostName
output containerRegistryLoginServer string = containerRegistry.outputs.loginServer
output keyVaultName string = keyVault.outputs.keyVaultName
output applicationInsightsName string = applicationInsights.outputs.applicationInsightsName
