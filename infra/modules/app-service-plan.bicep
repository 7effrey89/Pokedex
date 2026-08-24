param location string
param tags object
param appServicePlanName string

resource appServicePlan 'Microsoft.Web/serverFarms@2026-07-15' = {
  name: appServicePlanName
  location: location
  tags: tags
  kind: 'linux'
  sku: {
    name: 'S1'
    tier: 'Standard'
    size: 'S1'
    capacity: 1
  }
  properties: {
    reserved: true
  }
}

output appServicePlanId string = appServicePlan.id
output appServicePlanName string = appServicePlan.name