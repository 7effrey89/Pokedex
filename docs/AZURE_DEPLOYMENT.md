# Azure Web App Deployment Guide (Docker + Azure Container Registry)

This guide covers deploying the Pokédex app to Azure App Service using **Docker containers** and **Azure Container Registry (ACR)**. This approach is required for applications with native dependencies like `dlib` (used by face-recognition) that need custom build environments.

The repository includes two deployment workflows:
- **`.github/workflows/build-and-deploy-acr.yml`** - Docker-based deployment using Azure Container Registry (RECOMMENDED)
- **`.github/workflows/deploy-azure-webapp.yml`** - Legacy Oryx-based deployment (kept for reference, not suitable for native dependencies)

## Why Docker + ACR?

Native Python dependencies like `face-recognition` (which requires `dlib`, `cmake`, and build tools) often fail with Azure's default Oryx build system. Using Docker containers gives you full control over the build environment and ensures consistent, reproducible deployments.

**Benefits:**
- ✅ Full control over system dependencies (cmake, build-essential, etc.)
- ✅ Handles native dependencies (dlib, face-recognition) reliably
- ✅ Consistent builds across development and production
- ✅ Faster deployments (pre-built images)
- ✅ Easy rollback to previous image versions

## 1. Create Azure Container Registry (ACR)

You can create an ACR using either the Azure Portal (GUI) or Azure CLI (command line).

### Option A: Using Azure Portal (Beginner-Friendly)

1. **Sign in to Azure Portal**
   - Go to [https://portal.azure.com](https://portal.azure.com)
   - Sign in with your Azure account

2. **Create a Container Registry**
   - Click **"Create a resource"** (+ icon in top-left)
   - Search for **"Container Registry"** and select it
   - Click **"Create"**

3. **Configure the Registry**
   - **Subscription**: Select your Azure subscription
   - **Resource Group**: Create new or select existing (e.g., `pokedex-rg`)
   - **Registry name**: Enter a unique name (e.g., `pokedexacr` - must be globally unique)
   - **Location**: Choose a region close to you (e.g., `East US`, `West Europe`)
   - **SKU**: Select **Basic** (sufficient for most use cases, $5/month)
   - Click **"Review + create"**, then **"Create"**

4. **Get Registry Credentials**
   - After creation, navigate to your Container Registry
   - In the left menu, click **"Access keys"** under Settings
   - **Enable "Admin user"** (toggle to ON)
   - Note down these three values (you'll need them for GitHub secrets):
     - **Login server**: `<your-registry>.azurecr.io`
     - **Username**: (shown on this page)
     - **Password**: (shown on this page - use password or password2)

### Option B: Using Azure CLI (For Automation)

If you prefer command-line or want to automate the process:

1. **Install Azure CLI**
   - Download from: [https://learn.microsoft.com/cli/azure/install-azure-cli](https://learn.microsoft.com/cli/azure/install-azure-cli)
   - Or use Azure Cloud Shell (already has CLI installed)

2. **Log in and Create ACR**
   ```bash
   # Login to Azure
   az login

   # Set variables (customize these)
   RESOURCE_GROUP=pokedex-rg
   LOCATION=eastus
   ACR_NAME=pokedexacr  # Must be globally unique, lowercase, 5-50 characters

   # Create resource group (if you don't have one)
   az group create --name $RESOURCE_GROUP --location $LOCATION

   # Create Azure Container Registry
   az acr create \
     --resource-group $RESOURCE_GROUP \
     --name $ACR_NAME \
     --sku Basic \
     --admin-enabled true

   # Get ACR credentials (save these for GitHub secrets)
   az acr credential show --name $ACR_NAME --resource-group $RESOURCE_GROUP
   ```

3. **Save the Output**
   - The command will output `username` and `password` values
   - Your login server is: `<ACR_NAME>.azurecr.io`
   - Keep these credentials secure - you'll add them to GitHub secrets next

## 2. Create Azure App Service for Containers

Now create an App Service that will run your Docker container from ACR.

### Using Azure Portal

1. **Create App Service**
   - In Azure Portal, click **"Create a resource"**
   - Search for **"Web App"** and select it
   - Click **"Create"**

2. **Configure Basic Settings**
   - **Subscription**: Select your Azure subscription
   - **Resource Group**: Use same as ACR (e.g., `pokedex-rg`)
   - **Name**: Enter a unique name (e.g., `pokedex-chat`)
   - **Publish**: Select **"Docker Container"**
   - **Operating System**: Select **"Linux"**
   - **Region**: Same as your ACR (e.g., `East US`)
   - **Pricing Plan**: Select at least **Standard S1** (required for WebSockets)
     - Basic and Free tiers disable WebSockets (breaks voice features)

3. **Configure Docker Settings**
   - **Options**: Select **"Single Container"**
   - **Image Source**: Select **"Azure Container Registry"**
   - **Registry**: Select your ACR (e.g., `pokedexacr`)
   - **Image**: Select `pokedex-app` (will be created by GitHub Actions)
   - **Tag**: Select `latest`
   - Click **"Review + create"**, then **"Create"**

4. **Configure App Settings (Environment Variables)**
   - After creation, go to your App Service
   - Click **"Configuration"** → **"Application settings"**
   - Add these settings (click **"+ New application setting"** for each):
   
   | Name | Value | Description |
   |------|-------|-------------|
   | `WEBSITES_PORT` | `8000` | Port your Docker container listens on |
   | `GUNICORN_WORKERS` | `4` | Number of gunicorn worker processes (optional, default: 4) |
   | `AZURE_OPENAI_ENDPOINT` | `https://<your-resource>.openai.azure.com/` | Your Azure OpenAI endpoint |
   | `AZURE_OPENAI_API_KEY` | `your-api-key` | Your Azure OpenAI API key |
   | `AZURE_OPENAI_DEPLOYMENT` | `gpt-4` | Your chat deployment name |
   | `AZURE_OPENAI_REALTIME_DEPLOYMENT` | `gpt-4o-realtime-preview` | Your realtime deployment name |
   | `AZURE_OPENAI_REALTIME_API_VERSION` | `2024-10-01-preview` | API version |
   | `POKEMON_API_URL` | `https://pokeapi.co/api/v2` | PokeAPI base URL |
   | `POKEMON_TCG_API_KEY` | `your-tcg-api-key` | Pokemon TCG API key |
   | `APP_API_PASSWORD` | `YourSecurePassword` | App authentication password |
   | `USE_NATIVE_MCP` | `false` | MCP mode (false for client-side) |
   
   **Note:** For production workloads, consider adjusting `GUNICORN_WORKERS` based on your App Service tier:
   - S1 (1 core): 2-4 workers recommended
   - S2 (2 cores): 4-8 workers recommended
   - S3 (4 cores): 8-16 workers recommended
   
   - Click **"Save"** at the top when done

5. **Enable Continuous Deployment (Optional)**
   - In App Service, go to **"Deployment Center"**
   - Under **"Settings"**, enable **"Continuous deployment"**
   - This automatically pulls new images when GitHub Actions pushes to ACR

### Using Azure CLI

```bash
# Set variables (use same RESOURCE_GROUP and ACR_NAME from ACR setup)
APP_NAME=pokedex-chat  # Your desired app service name
APP_PLAN=${APP_NAME}-plan
ACR_NAME=pokedexacr  # Your ACR name from earlier

# Get ACR credentials
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer --output tsv)
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value --output tsv)

# Create App Service Plan (Standard S1 for WebSockets)
az appservice plan create \
  --name $APP_PLAN \
  --resource-group $RESOURCE_GROUP \
  --is-linux \
  --sku S1

# Create Web App with Docker container
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_PLAN \
  --name $APP_NAME \
  --deployment-container-image-name ${ACR_LOGIN_SERVER}/pokedex-app:latest

# Configure ACR credentials for the Web App
az webapp config container set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name ${ACR_LOGIN_SERVER}/pokedex-app:latest \
  --docker-registry-server-url https://${ACR_LOGIN_SERVER} \
  --docker-registry-server-user $ACR_USERNAME \
  --docker-registry-server-password $ACR_PASSWORD

# Set application settings (environment variables)
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --settings \
    WEBSITES_PORT=8000 \
    GUNICORN_WORKERS=4 \
    FLASK_ENV=production \
    FLASK_DEBUG=False \
    AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/" \
    AZURE_OPENAI_API_KEY="<your-key>" \
    AZURE_OPENAI_DEPLOYMENT="gpt-4" \
    AZURE_OPENAI_REALTIME_DEPLOYMENT="gpt-4o-realtime-preview" \
    AZURE_OPENAI_REALTIME_API_VERSION="2024-10-01-preview" \
    POKEMON_API_URL="https://pokeapi.co/api/v2" \
    POKEMON_TCG_API_KEY="<your-key>" \
    APP_API_PASSWORD="YourSecurePassword" \
    USE_NATIVE_MCP=false

# Enable continuous deployment
az webapp deployment container config \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --enable-cd true
```

## 3. Configure GitHub Secrets for CI/CD

To enable automated Docker builds and deployments via GitHub Actions, you need to add these secrets to your GitHub repository.

### How to Add GitHub Secrets

1. **Go to your GitHub repository**
   - Navigate to `https://github.com/your-username/Pokedex`

2. **Open Settings**
   - Click **"Settings"** tab (top right)
   - In the left sidebar, click **"Secrets and variables"** → **"Actions"**

3. **Add Repository Secrets**
   - Click **"New repository secret"** button
   - Add each secret below (one at a time)

### Required Secrets

| Secret Name | Description | How to Get It |
|-------------|-------------|---------------|
| `ACR_LOGIN_SERVER` | Your ACR login server URL | From ACR "Access keys" page (e.g., `pokedexacr.azurecr.io`) |
| `ACR_USERNAME` | ACR username | From ACR "Access keys" page (after enabling Admin user) |
| `ACR_PASSWORD` | ACR password | From ACR "Access keys" page (use password or password2) |
| `AZURE_WEBAPP_NAME` | Your App Service name | The name you chose when creating the App Service (e.g., `pokedex-chat`) |
| `AZURE_WEBAPP_PUBLISH_PROFILE` | App Service publish profile XML | Download from App Service "Overview" → "Get publish profile" button |

### Getting the Publish Profile

1. Go to Azure Portal
2. Navigate to your **App Service** (not ACR)
3. In the **Overview** page, click **"Get publish profile"** button (top toolbar)
4. A `.PublishSettings` file will download
5. Open the file in a text editor
6. Copy the **entire XML content**
7. Paste it as the value for `AZURE_WEBAPP_PUBLISH_PROFILE` secret in GitHub

### Example Values

```bash
ACR_LOGIN_SERVER=pokedexacr.azurecr.io
ACR_USERNAME=pokedexacr
ACR_PASSWORD=abc123...xyz  # Long random string from Azure
AZURE_WEBAPP_NAME=pokedex-chat
AZURE_WEBAPP_PUBLISH_PROFILE=<publishData>...</publishData>  # Full XML
```

### Security Notes

- ⚠️ **Never commit these secrets to your repository**
- ⚠️ **Never share these secrets publicly**
- ✅ Always use GitHub Secrets for sensitive values
- ✅ Rotate credentials periodically for security


## 4. Deploy Using GitHub Actions

Once your secrets are configured, GitHub Actions will automatically build and deploy your Docker container.

### How the Workflow Works

The workflow (`.github/workflows/build-and-deploy-acr.yml`) performs these steps:

1. **Checkout Code**: Gets the latest code from your repository
2. **Login to ACR**: Authenticates with Azure Container Registry using your secrets
3. **Build Docker Image**: Builds a Docker image with all dependencies
   - Installs system packages (cmake, build-essential, etc.)
   - Installs Python dependencies (face-recognition, dlib, Flask, etc.)
   - Configures gunicorn to run the application
4. **Push to ACR**: Uploads the built image to your Container Registry
5. **Deploy to App Service**: Updates your Azure App Service to use the new image

### Triggering a Deployment

**Automatic Deployment (Recommended)**
- Push code to the `main` branch
- GitHub Actions automatically triggers
- New Docker image is built and deployed

```bash
git add .
git commit -m "Update application"
git push origin main
```

**Manual Deployment**
1. Go to your GitHub repository
2. Click **"Actions"** tab
3. Select **"Build and Deploy to Azure Container Registry"** workflow
4. Click **"Run workflow"** dropdown
5. Select branch and optional environment tag
6. Click **"Run workflow"** button

### Monitoring Deployments

**GitHub Actions Logs**
1. Go to **Actions** tab in your repository
2. Click on the latest workflow run
3. Expand each step to see detailed logs
4. Look for any errors in red

**Azure App Service Logs**
```bash
# Stream live logs from Azure
az webapp log tail --name pokedex-chat --resource-group pokedex-rg

# Or download logs
az webapp log download --name pokedex-chat --resource-group pokedex-rg --log-file app-logs.zip
```

**Azure Portal Logs**
1. Go to your App Service in Azure Portal
2. Click **"Deployment Center"** (left sidebar)
3. View deployment history and status
4. Click **"Log stream"** (left sidebar) for live logs

### Troubleshooting Failed Deployments

**Build Fails**
- Check GitHub Actions logs for errors
- Verify Dockerfile syntax
- Ensure all dependencies are in `requirements.txt`

**Image Push Fails**
- Verify ACR secrets are correct in GitHub
- Check ACR has space (Basic tier has limits)
- Ensure ACR admin user is enabled

**App Service Fails to Start**
- Check App Service logs: `az webapp log tail ...`
- Verify `WEBSITES_PORT=8000` is set in App Settings
- Ensure Docker image was pushed successfully to ACR
- Check environment variables are set correctly

## 5. Post-Deployment Verification

After deployment completes, verify your application is running correctly.

### Test the Health Endpoint

```bash
# Using curl
curl https://<YOUR_APP>.azurewebsites.net/api/health

# Expected response
{"status": "healthy", "service": "Pokemon Chat Demo"}
```

### Access the Application

1. Open your browser
2. Navigate to `https://<YOUR_APP>.azurewebsites.net`
3. You should see the Pokédex chat interface
4. Try the voice feature (requires Azure OpenAI setup)
5. Test face recognition (if enabled and profile pictures configured)

### Verify Environment Variables

Check that all settings are applied:

```bash
az webapp config appsettings list \
  --name pokedex-chat \
  --resource-group pokedex-rg \
  --output table
```

### Common Issues

**"Container didn't respond to HTTP pings"**
- Ensure `WEBSITES_PORT=8000` is set in App Settings
- Verify Dockerfile exposes port 8000
- Check gunicorn is binding to `0.0.0.0:8000`

**"Face recognition not working"**
- Native dependencies (dlib) are now handled by Docker ✅
- Verify profile pictures are uploaded (or add via App Service FTP)
- Check Face Identification is enabled in Tools settings

**"Voice feature not working"**
- Verify S1 or higher plan (Free/Basic disable WebSockets)
- Check Azure OpenAI credentials in App Settings
- Ensure realtime deployment is configured

## 6. Updating Your Application

When you make code changes:

1. **Commit and push to main**
   ```bash
   git add .
   git commit -m "Update feature"
   git push origin main
   ```

2. **GitHub Actions automatically**:
   - Builds new Docker image
   - Pushes to ACR
   - Deploys to App Service

3. **Monitor deployment**:
   - GitHub Actions tab shows build progress
   - Azure Portal shows deployment status

4. **Verify changes**:
   - Visit your app URL
   - Test updated features

## Summary

✅ **Docker-based deployment** handles native dependencies (dlib, face-recognition)  
✅ **Azure Container Registry** stores your Docker images  
✅ **GitHub Actions** automates build and deployment  
✅ **Azure App Service** runs your containerized app  
✅ **WebSockets enabled** for realtime voice features  
✅ **Scalable and maintainable** infrastructure  

For questions or issues, check:
- GitHub Actions logs (build errors)
- Azure App Service logs (runtime errors)
- Azure Portal Deployment Center (deployment status)

## Legacy Deployment (Not Recommended)

The repository still includes `.github/workflows/deploy-azure-webapp.yml` for Oryx-based deployment, but this is **not recommended for apps with native dependencies**. The Oryx build system may fail to install `dlib` and other complex dependencies.

**Use the Docker + ACR approach described above for reliable deployments.**
