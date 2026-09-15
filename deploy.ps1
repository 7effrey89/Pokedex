[CmdletBinding()]
param(
    [switch]$Plan,
    [switch]$Deploy,
    [string]$SubscriptionId = 'cc4deffa-8847-41c7-8872-b2bdc648e883',
    [string]$ResourceGroupName = 'pokedex-rg',
    [string]$Location = 'swedencentral',
    [string]$DeploymentName = 'pokedex-0f504b04',
    [string]$RegistryName = 'pokedexacr2',
    [string]$WebAppName = 'app-pokedex-prod-0f50',
    [string]$ImageName = 'pokedex-app:latest'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$deploymentScript = Join-Path $PSScriptRoot '.github\skills\deploy-pokedex\scripts\deploy.ps1'
if (-not (Test-Path $deploymentScript)) {
    throw "Deployment implementation not found: $deploymentScript"
}

& $deploymentScript @PSBoundParameters
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}