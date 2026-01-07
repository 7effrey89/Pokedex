# Azure Web App Deployment Guide

The repository ships with the workflow `.github/workflows/deploy-azure-webapp.yml`, which zips the Flask application and deploys it to an Azure Web App using the official `azure/webapps-deploy` action. The deployment relies on Azure's Oryx build system to automatically create a virtual environment and install dependencies from `requirements.txt`. Follow these steps to provision Azure resources, configure secrets, and trigger the pipeline.

## 1. Provision the Azure Web App

1. Create an **App Service** (Linux) in your preferred resource group.
2. Select at least a **Standard (S1) App Service Plan** so WebSockets stay enabled for the realtime voice WebSocket connection. Basic and Free SKUs disable WebSockets and will break the voice client.
3. Choose a **Python 3.11** runtime stack. The workflow packages the code with `requirements.txt` and Oryx automatically builds the virtual environment during deployment.
4. In **Configuration → Application settings**, add the environment variables used locally (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_REALTIME_DEPLOYMENT`, `POKEMON_API_URL`, `POKEMON_TCG_API_KEY`, `APP_API_PASSWORD`, etc.). These map 1:1 with the values you enter in the Settings panel of the UI.

## 2. Configure GitHub Secrets

Add the following repository secrets (Settings → Secrets and variables → Actions → New repository secret):

| Secret Name | Description |
|-------------|-------------|
| `AZURE_WEBAPP_NAME` | The exact name of the App Service you just created. e.g pokedex-chat|
| `AZURE_WEBAPP_PUBLISH_PROFILE` | The entire contents of the downloaded publish profile XML file. |

To get the publish profile:
1. Go to your Azure Portal
2. Navigate to your App Service
3. Click "Get publish profile" in the Overview section
4. Open the downloaded XML file and copy its entire contents
5. Paste it as the value for the `AZURE_WEBAPP_PUBLISH_PROFILE` secret

Optionally, you can also add `APP_API_PASSWORD` to the Web App settings if you want a password other than the default `Password1`.

## 3. How the Workflow Runs

- **Triggers**: pushes to `main` and the manual "Run workflow" button (`workflow_dispatch`).
- **Steps**:
  1. Check out the repository.
  2. Create a deployment archive including `app.py`, `src/`, `static/`, `templates/`, `data/`, `tcg-cache/`, helper scripts, and **`requirements.txt`**.
  3. Deploy the archive to the Azure Web App using the publish profile.
  4. Azure's Oryx build system automatically detects `requirements.txt`, creates a virtual environment (`antenv`), and runs `pip install -r requirements.txt`.
  5. Gunicorn starts automatically to serve the Flask application.

### How the Automated Deployment Works

The workflow uses Azure's **Oryx build system** following Microsoft best practices:

1. **Package Phase**: The workflow zips the application code along with `requirements.txt`.
2. **Deployment Phase**: The ZIP is uploaded to Azure App Service.
3. **Build Phase**: Oryx automatically detects the Python app, creates a virtual environment at `/home/site/wwwroot/antenv`, and installs all dependencies from `requirements.txt`.
4. **Startup Phase**: Azure automatically launches gunicorn to serve the Flask application.

This approach ensures:
- ✅ No manual dependency management required
- ✅ Consistent with Microsoft Azure best practices
- ✅ Automatic handling of native dependencies (like dlib for face-recognition)
- ✅ Simplified workflow and deployment process
- ✅ Fully automated process with GitHub Actions

You can watch deployment logs under the repository's **Actions** tab. Azure-side logs are available in the App Service "Deployment Center."


## 4. Post-Deployment Checklist

1. Visit `https://<YOUR_APP>.azurewebsites.net/api/health` to verify the service is up.
2. Open the main UI and enter either your own Azure OpenAI credentials or the password-protected defaults.
3. Whenever you update code, merge it into `main` (or run the workflow manually) to redeploy.

With these steps, your Pokédex assistant can be promoted to a managed Azure Web App with repeatable, auditable deployments.
