# Azure Web App Deployment Guide

The repository now ships with the workflow `.github/workflows/deploy-azure-webapp.yml`, which zips the Flask application and deploys it to an Azure Web App using the official `azure/webapps-deploy` action. Follow these steps to provision Azure resources, configure secrets, and trigger the pipeline.

## 1. Provision the Azure Web App

1. Create an **App Service** (Linux) in your preferred resource group.
2. Select at least a **Standard (S1) App Service Plan** so WebSockets stay enabled for the realtime voice WebSocket connection. Basic and Free SKUs disable WebSockets and will break the voice client.
3. Choose a **Python 3.11** runtime stack. The workflow packages the code without additional build steps, so no Docker image is required.
4. After the app is created, go to **Configuration → General settings** and set:
   - `Startup Command`: `gunicorn --bind=0.0.0.0:$PORT --timeout 600 app:app`
   - `WEBSITES_PORT`: `5000` (matches the default `PORT` expected by `app.py`).
5. In **Configuration → Application settings**, add the environment variables used locally (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_REALTIME_DEPLOYMENT`, `POKEMON_API_URL`, `POKEMON_TCG_API_KEY`, `APP_API_PASSWORD`, etc.). These map 1:1 with the values you enter in the Settings panel of the UI.
6. Download the **Publish profile** for the web app (Portal → Overview → Get publish profile). This XML file will be stored as a GitHub secret.

## 2. Configure GitHub Secrets

Add the following repository secrets (Settings → Secrets and variables → Actions → New repository secret):

| Secret Name | Description |
|-------------|-------------|
| `AZURE_WEBAPP_NAME` | The exact name of the App Service you just created. |
| `AZURE_WEBAPP_PUBLISH_PROFILE` | The entire contents of the downloaded publish profile XML file. |

Optionally, you can also add `APP_API_PASSWORD` to the Web App settings if you want a password other than the default `Password1`.

## 3. How the Workflow Runs

- **Triggers**: pushes to `main` and the manual “Run workflow” button (`workflow_dispatch`).
- **Steps**:
  1. Check out the repository.
  2. Install Python 3.11 and all dependencies from `requirements.txt`.
  3. Zip the repository (excluding caches, virtual environments, and git metadata).
  4. Deploy the archive to the Azure Web App using the publish profile.

You can watch deployment logs under the repository’s **Actions** tab. Azure-side logs are available in the App Service “Deployment Center.”

## 4. Post-Deployment Checklist

1. Visit `https://<YOUR_APP>.azurewebsites.net/api/health` to verify the service is up.
2. Open the main UI and enter either your own Azure OpenAI credentials or the password-protected defaults.
3. Whenever you update code, merge it into `main` (or run the workflow manually) to redeploy.

With these steps, your Pokédex assistant can be promoted to a managed Azure Web App with repeatable, auditable deployments.
