param location string
param tags object
param appServiceName string
param appServicePlanId string
param containerRegistryLoginServer string
param containerImageName string
param applicationInsightsConnectionString string
param azureAuthMode string
param foundryProjectEndpoint string
@secure()
param azureOpenAiApiKey string
param azureOpenAiDeployment string
param azureOpenAiApiVersion string
param azureOpenAiRealtimeDeployment string
param azureOpenAiRealtimeApiVersion string
param azureAppRegistrationName string
param azureClientId string
param azureTenantId string
@secure()
param azureClientSecret string
param azureTokenScope string
param pokemonApiUrl string
@secure()
param pokemonTcgApiKey string
param tcgPageSize int
@secure()
param appApiPassword string

resource appService 'Microsoft.Web/sites@2026-07-15' = {
  name: appServiceName
  location: location
  tags: tags
  kind: 'app,linux,container'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlanId
    httpsOnly: true
    clientAffinityEnabled: false
    publicNetworkAccess: 'Enabled'
    siteConfig: {
      linuxFxVersion: 'DOCKER|${containerRegistryLoginServer}/${containerImageName}'
      acrUseManagedIdentityCreds: true
      alwaysOn: true
      webSocketsEnabled: true
      healthCheckPath: '/api/health'
      http20Enabled: true
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        {
          name: 'FLASK_DEBUG'
          value: 'False'
        }
        {
          name: 'PORT'
          value: '80'
        }
        {
          name: 'WEBSITES_PORT'
          value: '80'
        }
        {
          name: 'WEBSITES_CONTAINER_START_TIME_LIMIT'
          value: '1800'
        }
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://${containerRegistryLoginServer}'
        }
        {
          name: 'GUNICORN_WORKERS'
          value: '4'
        }
        {
          name: 'AZURE_AUTH_MODE'
          value: azureAuthMode
        }
        {
          name: 'FOUNDRY_PROJECT_ENDPOINT'
          value: foundryProjectEndpoint
        }
        {
          name: 'AZURE_OPENAI_API_KEY'
          value: azureOpenAiApiKey
        }
        {
          name: 'AZURE_OPENAI_DEPLOYMENT'
          value: azureOpenAiDeployment
        }
        {
          name: 'AZURE_OPENAI_API_VERSION'
          value: azureOpenAiApiVersion
        }
        {
          name: 'AZURE_OPENAI_REALTIME_DEPLOYMENT'
          value: azureOpenAiRealtimeDeployment
        }
        {
          name: 'AZURE_OPENAI_REALTIME_API_VERSION'
          value: azureOpenAiRealtimeApiVersion
        }
        {
          name: 'AZURE_APP_REGISTRATION_NAME'
          value: azureAppRegistrationName
        }
        {
          name: 'AZURE_CLIENT_ID'
          value: azureClientId
        }
        {
          name: 'AZURE_TENANT_ID'
          value: azureTenantId
        }
        {
          name: 'AZURE_CLIENT_SECRET'
          value: azureClientSecret
        }
        {
          name: 'AZURE_TOKEN_SCOPE'
          value: azureTokenScope
        }
        {
          name: 'POKEMON_API_URL'
          value: pokemonApiUrl
        }
        {
          name: 'POKEMON_TCG_API_KEY'
          value: pokemonTcgApiKey
        }
        {
          name: 'TCG_PAGE_SIZE'
          value: string(tcgPageSize)
        }
        {
          name: 'APP_API_PASSWORD'
          value: appApiPassword
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: applicationInsightsConnectionString
        }
      ]
    }
  }
}

resource scmAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2023-12-01' = {
  parent: appService
  name: 'scm'
  properties: {
    allow: false
  }
}

resource ftpAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2023-12-01' = {
  parent: appService
  name: 'ftp'
  properties: {
    allow: false
  }
}

output appServiceId string = appService.id
output appServiceName string = appService.name
output defaultHostName string = appService.properties.defaultHostName
output principalId string = appService.identity.principalId
