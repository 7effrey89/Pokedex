# Migration Guide: Oryx to Docker/ACR Deployment

This guide helps you migrate from the legacy Oryx-based deployment to the new Docker + Azure Container Registry (ACR) deployment method.

## Why Migrate?

The legacy Oryx deployment (`.github/workflows/deploy-azure-webapp.yml`) has limitations:

❌ **Issues with Native Dependencies**
- Oryx may fail to build `dlib` (required by face-recognition)
- Complex dependencies like `cmake` and `build-essential` not reliably installed
- Face recognition feature may not work after deployment

✅ **Benefits of Docker/ACR**
- Full control over system dependencies
- Reliable installation of all native dependencies
- Consistent builds across all environments
- Faster deployments with pre-built images
- Easy rollback to previous versions

## Migration Steps

### 1. Keep Your Existing App Service (Optional)

You can keep your existing Azure App Service and just switch it to use Docker containers, or create a new one. Both approaches work.

**Option A: Convert Existing App Service**
- Your existing App Service can be reconfigured to use containers
- No need to create a new one
- Your URL stays the same

**Option B: Create New App Service**
- Fresh start with container-specific configuration
- Run old and new side-by-side during testing
- Switch DNS/traffic when ready

### 2. Create Azure Container Registry

Follow the instructions in [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md#1-create-azure-container-registry-acr) to create an ACR.

**Quick CLI Commands:**
```bash
az login
RESOURCE_GROUP=your-existing-rg  # Use your existing resource group
ACR_NAME=yourappacr              # Choose a unique name

# Create ACR
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true

# Get credentials (save these for GitHub secrets)
az acr credential show --name $ACR_NAME --resource-group $RESOURCE_GROUP
```

### 3. Update GitHub Secrets

**Keep these existing secrets:**
- `AZURE_WEBAPP_NAME` - Your App Service name (reuse existing)
- `AZURE_WEBAPP_PUBLISH_PROFILE` - Your publish profile (reuse or download again)

**Add these new secrets:**
- `ACR_LOGIN_SERVER` - From ACR "Access keys" (e.g., `yourappacr.azurecr.io`) get from the "Home" page of the ACR resource in Azure Portal
- `ACR_USERNAME` - From ACR "Access keys"
- `ACR_PASSWORD` - From ACR "Access keys"

See [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md#3-configure-github-secrets-for-cicd) for detailed instructions.

### 4. Configure Your App Service for Containers

**Using Azure Portal:**
1. Go to your App Service
2. Navigate to **"Deployment Center"** (left sidebar)
3. Under **"Settings"**:
   - **Source**: Select "Container Registry"
   - **Registry**: Select your ACR
   - **Image**: Select `pokedex-app`
   - **Tag**: Select `latest`
4. Click **"Save"**
5. Go to **"Configuration"** → **"Application settings"**
6. Add: `WEBSITES_PORT` = `8000`
7. Click **"Save"**

**Using Azure CLI:**
```bash
APP_NAME=your-existing-app  # Your existing App Service name
ACR_NAME=yourappacr
RESOURCE_GROUP=your-existing-rg

# Get ACR credentials
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --resource-group $RESOURCE_GROUP --query loginServer --output tsv)
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value --output tsv)

# Update App Service to use container from ACR
az webapp config container set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --docker-custom-image-name ${ACR_LOGIN_SERVER}/pokedex-app:latest \
  --docker-registry-server-url https://${ACR_LOGIN_SERVER} \
  --docker-registry-server-user $ACR_USERNAME \
  --docker-registry-server-password $ACR_PASSWORD

# Set the port
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --settings WEBSITES_PORT=8000

# Enable continuous deployment
az webapp deployment container config \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --enable-cd true
```

### 5. Deploy Your First Docker Build

**Option A: Trigger Manual Deployment**
1. Go to your GitHub repository
2. Click **"Actions"** tab
3. Select **"Build and Deploy to Azure Container Registry"**
4. Click **"Run workflow"**
5. Wait for build to complete (~10-15 minutes first time)

**Option B: Push to Main**
```bash
git add .
git commit --allow-empty -m "Trigger Docker build"
git push origin main
```

### 6. Verify the Deployment

1. **Check Build Status**
   - GitHub Actions tab shows build progress
   - Wait for green checkmark

2. **Check App Service**
   ```bash
   # Stream logs
   az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP
   ```

3. **Test Health Endpoint**
   ```bash
   curl https://$APP_NAME.azurewebsites.net/api/health
   ```

4. **Access Application**
   - Open `https://$APP_NAME.azurewebsites.net`
   - Test face recognition feature
   - Verify all features work

### 7. Clean Up (Optional)

After successful migration, you can disable the legacy workflow:

**The legacy workflow is already disabled** in this repository. It's kept for reference but won't run automatically on push to main.

If you want to completely remove it:
```bash
rm .github/workflows/deploy-azure-webapp.yml
git add .
git commit -m "Remove legacy Oryx deployment workflow"
git push origin main
```

## Troubleshooting Migration Issues

### Container Not Starting

**Error:** "Container didn't respond to HTTP pings"

**Solution:**
- Verify `WEBSITES_PORT=8000` in App Settings
- Check App Service logs for startup errors
- Ensure Docker image was pushed to ACR successfully

### Build Failures

**Error:** GitHub Actions build fails

**Solution:**
- Check GitHub Actions logs for specific errors
- Verify all secrets are set correctly
- Ensure ACR admin user is enabled

### Face Recognition Still Not Working

**Error:** Face recognition feature not working after migration

**Solution:**
- Verify profile pictures are uploaded to App Service
- Check that `face-recognition` is being installed (check build logs)
- Ensure native dependencies (dlib, cmake) are in Dockerfile
- The provided Dockerfile already includes all required dependencies

### Environment Variables Missing

**Error:** Application settings not working

**Solution:**
- All environment variables must be re-added in App Service Configuration
- The container doesn't inherit settings from previous deployment
- Re-add all settings from AZURE_DEPLOYMENT.md

## Rollback Plan

If you need to rollback to the old deployment:

1. **Re-enable legacy workflow**
   - Uncomment the `on: push:` section in `deploy-azure-webapp.yml`

2. **Reconfigure App Service**
   - Change Deployment Center back to "GitHub Actions"
   - Or manually deploy ZIP file

3. **Note:** Face recognition may not work with Oryx deployment

## Need Help?

- See [AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md) for complete Docker/ACR documentation
- Check GitHub Actions logs for build errors
- Check Azure App Service logs for runtime errors
- Review [Face Recognition Guide](FACE_RECOGNITION_GUIDE.md) for face recognition troubleshooting

## Summary

✅ Docker deployment handles native dependencies reliably  
✅ Face recognition works out of the box  
✅ Faster deployments with cached Docker layers  
✅ Easy rollback to previous Docker images  
✅ Production-ready infrastructure  

The migration typically takes 30-60 minutes including setup and first deployment.
