---
name: deploy-pokedex
description: "Deploy, redeploy, publish, release, or update this Pokédex Flask solution on Azure App Service. Use when asked to deploy the solution, push the app to Azure, rebuild the production container, update the live Web App, run an Azure what-if, or verify the production deployment. Reuses the existing Bicep, ACR, App Service plan, Web App, monitoring resources, and private-only Key Vault policy constraints."
argument-hint: "validate, plan, deploy, or verify the Pokédex Azure deployment"
user-invocable: true
disable-model-invocation: false
---

# Deploy Pokédex to Azure

Use the bundled [deployment script](./scripts/deploy.ps1) for this repository. Do not reconstruct the deployment with ad hoc `az webapp create` commands.

## Fixed Deployment

- Subscription: `cc4deffa-8847-41c7-8872-b2bdc648e883`
- Resource group: `pokedex-rg`
- Region: `swedencentral`
- Subscription deployment: `pokedex-0f504b04`
- Registry: `pokedexacr2`
- Image: `pokedex-app:latest`
- App Service plan: `pokedex-chat-plan`
- Web App: `app-pokedex-prod-0f50`
- Health endpoint: `https://app-pokedex-prod-0f50.azurewebsites.net/api/health`

Treat these names as existing resources. Never create parallel resources merely because a command reports that one already exists.

## Security Rules

- Never print, log, commit, or include secret values in chat responses.
- Load configuration from process environment or the ignored `.env` file.
- The script may reuse the ignored deployment-session secret file on the original deployment machine.
- On a fresh clone, require `APP_API_PASSWORD`, `AZURE_CLIENT_SECRET`, `POKEMON_TCG_API_KEY`, `AZURE_OPENAI_ENDPOINT`, and `AZURE_OPENAI_DEPLOYMENT`. Require `AZURE_OPENAI_API_KEY` when `AZURE_AUTH_MODE=key`.
- Keep `AZURE_OPENAI_ENDPOINT` and `FOUNDRY_PROJECT_ENDPOINT` as separate App Service settings. The former is the canonical chat endpoint; the latter remains a compatibility alias.
- Tenant policy `MCAPSGovDeployPolicies / KeyVault_PublicNetwork_Modify` forces Key Vault public network access to `Disabled`. Do not retry enabling it.
- The approved demo architecture uses encrypted App Service settings because no VNet integration or private endpoint is provisioned.
- Ask for explicit approval before adding paid resources, private networking, changing region/SKU, creating or deleting resources, or changing the secret-delivery architecture.
- Never deploy when what-if contains a `Delete` operation.
- Keep FTP and SCM basic publishing credentials disabled.

## Workflow

1. Read `infra/main.bicep`, `infra/main.parameters.json`, and the most recent `.copilot-azure/sessions/*/deployment-summary.md` when available.
2. Confirm Azure CLI authentication targets the fixed subscription. Do not display tokens or credentials.
3. Run local validation from the repository root:

   ```powershell
   & .\.github\skills\deploy-pokedex\scripts\deploy.ps1
   ```

4. For a requested deployment, run the read-only Azure plan:

   ```powershell
   & .\.github\skills\deploy-pokedex\scripts\deploy.ps1 -Plan
   ```

5. Report the what-if change counts. Stop on deletes. If the plan introduces resources, cost, or security changes, obtain explicit approval. A direct request to redeploy the existing approved architecture is sufficient when the plan contains only modifications and no deletes.
6. Deploy only after the gate is satisfied:

   ```powershell
   & .\.github\skills\deploy-pokedex\scripts\deploy.ps1 -Deploy
   ```

7. The script must complete all of these steps successfully:
   - Compile Bicep.
   - Run a second delete-free what-if immediately before deployment.
   - Apply the subscription deployment with secure parameters.
   - Build `pokedex-app:latest` using ACR Build.
   - Restart the existing Web App.
   - Verify `/api/health` reports `status: healthy`.
   - Verify `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT` are present and non-empty without printing their values.
   - Disable and verify SCM basic publishing credentials.
   - Verify the Web App state is `Running`.
8. Independently request the home page and health endpoint after the script completes. Reject Azure placeholder pages and non-200 responses.
9. Update the latest deployment session's `deploy-result.json`, `context.json`, `deployment-summary.md`, and audit log without recording secrets. Do not create a Git commit unless explicitly requested.

## Failure Handling

- A transient `503` immediately after restart can occur during image pull and cold start. Retry health checks and inspect App Service container startup logs before changing infrastructure.
- Historical `ImageNotFoundFailure` entries from before an ACR build are not current failures when later logs show the image pulled, Gunicorn listening on port 80, and the startup probe succeeding.
- For image-pull failures, verify the image manifest, App Service system identity, and `AcrPull` assignment.
- For startup failures, enable filesystem container logging, restart once, and inspect downloaded App Service logs for the first current exception.
- Do not claim success until both the application home page and `/api/health` return `HTTP 200` and the health payload is the application's payload.

## Modes

- No switch: local Bicep validation only; no Azure mutation.
- `-Plan`: Bicep validation plus Azure what-if; no Azure mutation.
- `-Deploy`: what-if, infrastructure update, image build, restart, health validation, and hardening.

Override fixed defaults only after the user explicitly approves the corresponding architecture change.