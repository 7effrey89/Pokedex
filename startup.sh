#!/bin/bash
# Azure App Service startup script
# Copies pre-bundled dependencies from .python_packages into the Oryx-created virtualenv (antenv)
# Then launches gunicorn to serve the Flask application

set -e

echo "Starting Azure App Service startup script..."

# Oryx creates a virtualenv at /home/site/wwwroot/antenv
ANTENV_PATH="/home/site/wwwroot/antenv"
BUNDLED_PACKAGES="/home/site/wwwroot/.python_packages/lib/site-packages"

if [ -d "$BUNDLED_PACKAGES" ]; then
    echo "Found bundled packages at $BUNDLED_PACKAGES"
    
    if [ -d "$ANTENV_PATH" ]; then
        echo "Found Oryx virtualenv at $ANTENV_PATH"
        
        # Determine the site-packages directory in the virtualenv
        SITE_PACKAGES=$(find "$ANTENV_PATH/lib" -type d -name "site-packages" | head -n 1)
        
        if [ -n "$SITE_PACKAGES" ]; then
            echo "Copying bundled packages to $SITE_PACKAGES..."
            cp -r "$BUNDLED_PACKAGES"/* "$SITE_PACKAGES/"
            echo "Successfully copied bundled packages"
        else
            echo "Warning: Could not find site-packages in virtualenv"
        fi
    else
        echo "Warning: Oryx virtualenv not found at $ANTENV_PATH"
    fi
else
    echo "Warning: Bundled packages not found at $BUNDLED_PACKAGES"
fi

# Activate the virtualenv if it exists
if [ -d "$ANTENV_PATH" ]; then
    echo "Activating virtualenv..."
    source "$ANTENV_PATH/bin/activate"
fi

# Launch gunicorn
echo "Starting gunicorn..."
cd /home/site/wwwroot
gunicorn --bind=0.0.0.0:${PORT:-8000} --timeout 600 app:app
