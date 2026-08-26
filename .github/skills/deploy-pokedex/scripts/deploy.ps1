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

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$templateFile = Join-Path $repoRoot 'infra\main.bicep'
$parameterFile = Join-Path $repoRoot 'infra\main.parameters.json'
$envFile = Join-Path $repoRoot '.env'
$sessionSecretFile = Join-Path $repoRoot '.copilot-azure\sessions\0f504b04-fbcf-46fc-9937-70e8055afde6\deploy-secrets.env'

function Read-DotEnv {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#') -or -not $trimmed.Contains('=')) {
            continue
        }

        $parts = $trimmed.Split('=', 2)
        $value = $parts[1].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $values[$parts[0].Trim()] = $value
    }

    return $values
}

function Get-DeploymentValue {
    param(
        [hashtable]$DotEnv,
        [string]$Name,
        [string]$Default = ''
    )

    $environmentValue = [Environment]::GetEnvironmentVariable($Name)
    if (-not [string]::IsNullOrWhiteSpace($environmentValue)) {
        return $environmentValue
    }
    if ($DotEnv.ContainsKey($Name) -and -not [string]::IsNullOrWhiteSpace($DotEnv[$Name])) {
        return $DotEnv[$Name]
    }
    return $Default
}

function Invoke-Az {
    param([string[]]$Arguments)

    $output = & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI failed: az $($Arguments[0..([Math]::Min(2, $Arguments.Count - 1))] -join ' ')"
    }
    return $output
}

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw 'Azure CLI (az) is required.'
}
if (-not (Test-Path $templateFile) -or -not (Test-Path $parameterFile)) {
    throw 'Run this script from the checked-out Pokédex repository.'
}

Push-Location $repoRoot
try {
    if ($Plan -and $Deploy) {
        throw 'Choose either -Plan or -Deploy, not both.'
    }

    Invoke-Az @('bicep', 'build', '--file', $templateFile, '--stdout') | Out-Null
    if (-not $Plan -and -not $Deploy) {
        [pscustomobject]@{
            mode = 'validation-only'
            bicepCompiled = $true
            nextStep = 'Run again with -Plan to inspect Azure changes.'
        }
        return
    }

    Invoke-Az @('account', 'show', '--subscription', $SubscriptionId, '--output', 'none') | Out-Null
    $dotEnv = Read-DotEnv $envFile
    $sessionSecrets = Read-DotEnv $sessionSecretFile
    foreach ($name in $sessionSecrets.Keys) {
        if (-not $dotEnv.ContainsKey($name)) {
            $dotEnv[$name] = $sessionSecrets[$name]
        }
    }
    $azureAuthMode = Get-DeploymentValue $dotEnv 'AZURE_AUTH_MODE' 'service_principal'
    $azureOpenAiApiKey = Get-DeploymentValue $dotEnv 'AZURE_OPENAI_API_KEY'
    $azureClientSecret = Get-DeploymentValue $dotEnv 'AZURE_CLIENT_SECRET'
    $pokemonTcgApiKey = Get-DeploymentValue $dotEnv 'POKEMON_TCG_API_KEY'
    $appApiPassword = Get-DeploymentValue $dotEnv 'APP_API_PASSWORD'
    $azureOpenAiEndpoint = Get-DeploymentValue $dotEnv 'AZURE_OPENAI_ENDPOINT'
    $azureOpenAiDeployment = Get-DeploymentValue $dotEnv 'AZURE_OPENAI_DEPLOYMENT'
    $azureOpenAiRealtimeEndpoint = Get-DeploymentValue $dotEnv 'AZURE_OPENAI_REALTIME_ENDPOINT' $azureOpenAiEndpoint

    if ($azureAuthMode -eq 'service_principal' -and [string]::IsNullOrWhiteSpace($azureOpenAiApiKey)) {
        $azureOpenAiApiKey = 'not-used-service-principal-auth'
    }

    $required = @{
        AZURE_CLIENT_SECRET = $azureClientSecret
        POKEMON_TCG_API_KEY = $pokemonTcgApiKey
        APP_API_PASSWORD = $appApiPassword
        AZURE_OPENAI_ENDPOINT = $azureOpenAiEndpoint
        AZURE_OPENAI_DEPLOYMENT = $azureOpenAiDeployment
    }
    if ($azureAuthMode -eq 'key') {
        $required.AZURE_OPENAI_API_KEY = $azureOpenAiApiKey
    }
    $missing = @($required.Keys | Where-Object { [string]::IsNullOrWhiteSpace($required[$_]) })
    if ($missing.Count -gt 0) {
        throw "Missing required values in the process environment or .env: $($missing -join ', ')"
    }

    $secureParameters = @(
        "azureAuthMode=$azureAuthMode"
        "azureOpenAiApiKey=$azureOpenAiApiKey"
        "azureClientSecret=$azureClientSecret"
        "pokemonTcgApiKey=$pokemonTcgApiKey"
        "appApiPassword=$appApiPassword"
        "containerImageName=$ImageName"
    )

    $optionalParameters = @{
        foundryProjectEndpoint = Get-DeploymentValue $dotEnv 'FOUNDRY_PROJECT_ENDPOINT' $azureOpenAiEndpoint
        azureOpenAiEndpoint = $azureOpenAiEndpoint
        azureOpenAiDeployment = $azureOpenAiDeployment
        azureOpenAiApiVersion = Get-DeploymentValue $dotEnv 'AZURE_OPENAI_API_VERSION'
        azureOpenAiRealtimeEndpoint = $azureOpenAiRealtimeEndpoint
        azureOpenAiRealtimeDeployment = Get-DeploymentValue $dotEnv 'AZURE_OPENAI_REALTIME_DEPLOYMENT'
        azureOpenAiRealtimeApiVersion = Get-DeploymentValue $dotEnv 'AZURE_OPENAI_REALTIME_API_VERSION'
        azureAppRegistrationName = Get-DeploymentValue $dotEnv 'AZURE_APP_REGISTRATION_NAME'
        azureClientId = Get-DeploymentValue $dotEnv 'AZURE_CLIENT_ID'
        azureTenantId = Get-DeploymentValue $dotEnv 'AZURE_TENANT_ID'
        azureTokenScope = Get-DeploymentValue $dotEnv 'AZURE_TOKEN_SCOPE'
        pokemonApiUrl = Get-DeploymentValue $dotEnv 'POKEMON_API_URL'
        tcgPageSize = Get-DeploymentValue $dotEnv 'TCG_PAGE_SIZE'
    }
    foreach ($parameterName in $optionalParameters.Keys) {
        if (-not [string]::IsNullOrWhiteSpace($optionalParameters[$parameterName])) {
            $secureParameters += "$parameterName=$($optionalParameters[$parameterName])"
        }
    }

    $whatIfArguments = @(
        'deployment', 'sub', 'what-if',
        '--name', $DeploymentName,
        '--location', $Location,
        '--subscription', $SubscriptionId,
        '--template-file', $templateFile,
        '--parameters', "@$parameterFile"
    ) + $secureParameters + @('--result-format', 'FullResourcePayloads', '--no-pretty-print', '--output', 'json')

    $whatIf = (Invoke-Az $whatIfArguments | Out-String) | ConvertFrom-Json
    if ($whatIf.changes.changeType -contains 'Delete') {
        throw 'Deployment stopped because what-if contains a Delete operation.'
    }
    $changeCounts = @($whatIf.changes | Group-Object changeType | ForEach-Object {
        [pscustomobject]@{
            changeType = $_.Name
            count = $_.Count
        }
    })
    if ($Plan) {
        [pscustomobject]@{
            mode = 'plan'
            hasDeletes = $false
            changeCounts = $changeCounts
            nextStep = 'Review the plan and obtain explicit approval before running with -Deploy.'
        }
        return
    }

    $deploymentArguments = @(
        'deployment', 'sub', 'create',
        '--name', $DeploymentName,
        '--location', $Location,
        '--subscription', $SubscriptionId,
        '--template-file', $templateFile,
        '--parameters', "@$parameterFile"
    ) + $secureParameters + @('--output', 'none')
    Invoke-Az $deploymentArguments | Out-Null

    Invoke-Az @(
        'acr', 'build',
        '--subscription', $SubscriptionId,
        '--registry', $RegistryName,
        '--image', $ImageName,
        '.', '--no-logs'
    ) | Out-Null

    Invoke-Az @(
        'webapp', 'restart',
        '--subscription', $SubscriptionId,
        '--resource-group', $ResourceGroupName,
        '--name', $WebAppName
    ) | Out-Null

    $healthUrl = "https://$WebAppName.azurewebsites.net/api/health"
    $health = $null
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 240
            if ($health.status -eq 'healthy') {
                break
            }
        }
        catch {
            if ($attempt -eq 3) {
                throw
            }
            Start-Sleep -Seconds (20 * $attempt)
        }
    }
    if ($null -eq $health -or $health.status -ne 'healthy') {
        throw 'The Web App health endpoint did not report healthy.'
    }

    $scmPolicyId = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName/providers/Microsoft.Web/sites/$WebAppName/basicPublishingCredentialsPolicies/scm"
    Invoke-Az @(
        'resource', 'update', '--ids', $scmPolicyId,
        '--api-version', '2023-12-01', '--set', 'properties.allow=false', '--output', 'none'
    ) | Out-Null
    $scmAllowed = (Invoke-Az @(
        'resource', 'show', '--ids', $scmPolicyId,
        '--api-version', '2023-12-01', '--query', 'properties.allow', '--output', 'tsv'
    )).Trim()
    if ($scmAllowed -ne 'false') {
        throw 'SCM basic publishing credentials were not disabled.'
    }

    $state = (Invoke-Az @(
        'webapp', 'show', '--subscription', $SubscriptionId,
        '--resource-group', $ResourceGroupName, '--name', $WebAppName,
        '--query', 'state', '--output', 'tsv'
    )).Trim()
    if ($state -ne 'Running') {
        throw "Web App state is $state."
    }

    $configuredOpenAiSettings = @(Invoke-Az @(
        'webapp', 'config', 'appsettings', 'list',
        '--subscription', $SubscriptionId,
        '--resource-group', $ResourceGroupName,
        '--name', $WebAppName,
        '--query', "[?value!='' && (name=='AZURE_OPENAI_ENDPOINT' || name=='AZURE_OPENAI_DEPLOYMENT')].name",
        '--output', 'tsv'
    ))
    $missingOpenAiSettings = @(
        'AZURE_OPENAI_ENDPOINT', 'AZURE_OPENAI_DEPLOYMENT' |
            Where-Object { $_ -notin $configuredOpenAiSettings }
    )
    if ($missingOpenAiSettings.Count -gt 0) {
        throw "Web App is missing required Azure OpenAI settings: $($missingOpenAiSettings -join ', ')"
    }

    [pscustomobject]@{
        mode = 'deployment'
        status = 'succeeded'
        webApp = $WebAppName
        url = "https://$WebAppName.azurewebsites.net"
        healthStatus = $health.status
        azureOpenAiSettingsConfigured = $true
        scmBasicPublishingAllowed = $false
    }
}
finally {
    Pop-Location
}