# Azure Web App Deployment Guide

The repository now ships with the workflow `.github/workflows/deploy-azure-webapp.yml`, which zips the Flask application and deploys it to an Azure Web App using the official `azure/webapps-deploy` action. Follow these steps to provision Azure resources, configure secrets, and trigger the pipeline.

## 1. Provision the Azure Web App

1. Create an **App Service** (Linux) in your preferred resource group.
2. Select at least a **Standard (S1) App Service Plan** so WebSockets stay enabled for the realtime voice WebSocket connection. Basic and Free SKUs disable WebSockets and will break the voice client.
3. Choose a **Python 3.11** runtime stack. The workflow packages the code with pre-bundled dependencies and automatically configures the startup command, so no Docker image or manual configuration is required.
4. In **Configuration → Application settings**, add the environment variables used locally (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_REALTIME_DEPLOYMENT`, `POKEMON_API_URL`, `POKEMON_TCG_API_KEY`, `APP_API_PASSWORD`, etc.). These map 1:1 with the values you enter in the Settings panel of the UI.
5. Download the **Publish profile** for the web app (Portal → Overview → Get publish profile). This XML file will be stored as a GitHub secret.

## 2. Configure GitHub Secrets

Add the following repository secrets (Settings → Secrets and variables → Actions → New repository secret):

| Secret Name | Description |
|-------------|-------------|
| `AZURE_WEBAPP_NAME` | The exact name of the App Service you just created. e.g pokedex-chat|
| `AZURE_WEBAPP_PUBLISH_PROFILE` | The entire contents of the downloaded publish profile XML file. |
| `AZURE_RESOURCE_GROUP` | The name of the Azure resource group containing your App Service (e.g., `pokedex-rg`). Required for automated startup command configuration. |
| `AZURE_CREDENTIALS` | Azure service principal credentials in JSON format (see below for setup). Required for automated startup command configuration. |

### Creating Azure Service Principal Credentials

To enable automated startup command configuration, create a service principal with contributor access to your resource group:

```bash
az ad sp create-for-rbac \
  --name "github-pokedex-deploy" \
  --role contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/<RESOURCE_GROUP_NAME> \
  --sdk-auth
```

Copy the entire JSON output (including the curly braces) and paste it as the value for the `AZURE_CREDENTIALS` secret.

**Note:** You can find your subscription ID by running `az account show --query id -o tsv`.

Optionally, you can also add `APP_API_PASSWORD` to the Web App settings if you want a password other than the default `Password1`.

## 3. How the Workflow Runs

- **Triggers**: pushes to `main` and the manual "Run workflow" button (`workflow_dispatch`).
- **Steps**:
  1. Check out the repository.
  2. Install Python 3.11 and CMake (system-wide to avoid build issues).
  3. Install all dependencies from `requirements.txt` into `.python_packages/lib/site-packages` (pre-bundled approach).
  4. Create a deployment archive including `startup.sh` and the pre-bundled dependencies.
  5. Deploy the archive to the Azure Web App using the publish profile.
  6. Configure the startup command to use `/home/site/wwwroot/startup.sh` (copies bundled dependencies into Oryx virtualenv and launches gunicorn).

### How the Automated Deployment Works

The workflow uses a **pre-bundled dependencies** approach to eliminate CMake/DD build issues on Azure:

1. **Build Phase**: Dependencies are installed locally in GitHub Actions with proper build tools (CMake, gcc) into `.python_packages/lib/site-packages`.
2. **Deployment Phase**: The entire `.python_packages` directory is included in the deployment ZIP.
3. **Startup Phase**: The `startup.sh` script copies all bundled dependencies from `.python_packages` into the Oryx-created virtualenv at runtime, then launches gunicorn.

This approach ensures:
- ✅ No CMake/build tools required on Azure App Service
- ✅ No manual configuration of startup commands
- ✅ Consistent deployments across environments
- ✅ Fully automated process with GitHub Actions

You can watch deployment logs under the repository's **Actions** tab. Azure-side logs are available in the App Service "Deployment Center."


## 4. Post-Deployment Checklist

1. Visit `https://<YOUR_APP>.azurewebsites.net/api/health` to verify the service is up.
2. Open the main UI and enter either your own Azure OpenAI credentials or the password-protected defaults.
3. Whenever you update code, merge it into `main` (or run the workflow manually) to redeploy.

With these steps, your Pokédex assistant can be promoted to a managed Azure Web App with repeatable, auditable deployments.
