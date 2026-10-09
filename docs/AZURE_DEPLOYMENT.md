# Hosting QP Discord Bot on Microsoft Azure

This guide walks you through deploying your Discord bot to **Azure Container Apps (ACA)**. 

Azure Container Apps is a modern, fully-managed serverless container service that is cost-effective, easy to monitor, and keeps your bot online 24/7.

---

## 🔑 Crucial Concepts for Discord Bots on Azure

1. **Ingress should be DISABLED**: Discord bots establish an outbound WebSocket connection to Discord's Gateway. They do **not** accept incoming HTTP web requests. Disabling Ingress avoids HTTP timeouts and saves resources.
2. **Min Replicas = 1 (Always-On)**: By default, serverless containers scale down to 0 when there's no HTTP traffic. For a Discord bot, you **must set Min Replicas to 1** so the bot stays connected 24/7.

---

## Method 1: Azure Portal Setup (No CLI Required)

### Step 1: Create a Container App
1. Go to the [Azure Portal](https://portal.azure.com/).
2. In the top search bar, search for **Container Apps** and click **Create**.
3. Fill in the **Basics** tab:
   * **Subscription**: Your Azure subscription.
   * **Resource Group**: Create new (e.g. `rg-qp-bot`).
   * **Container App Name**: `qp-discord-bot`.
   * **Region**: Choose the closest region (e.g., `West US 2` or `East US`).
   * **Container Apps Environment**: Click *Create new* and choose default settings.

### Step 2: Configure the Container
In the **Container** tab:
* **Image Source**: Docker Hub or other registries (or Azure Container Registry if you created one).
* If you pushed your image to GitHub Container Registry (`ghcr.io`):
  * **Image type**: Other registry
  * **Image and tag**: `ghcr.io/<your-github-username>/qp-discord-bot:latest`
* **CPU and Memory**: `0.25 vCPU, 0.5 GiB` (more than enough for a Discord bot and very cheap / practically free).

### Step 3: Add Environment Variables & Secrets
Under the container configuration, add:
* `DISCORD_TOKEN`: Add as a **Secret**, then reference it.
* `MAX_TEAMS`: `28`
* `STAFF_ROLE_NAME`: `QP Chair`
* `TICKETS_CATEGORY_NAME`: `Hardware Requests`

### Step 4: Ingress & Scale Configuration
* **Ingress tab**:
  * Uncheck / Disable **Enable Ingress** (Discord bots do not listen for incoming HTTP traffic).
* **Scale tab** (or after creation under Settings > Scale):
  * **Min replicas**: `1` *(CRITICAL: prevents bot from sleeping)*
  * **Max replicas**: `1`

Click **Review + create** and deploy!

---

## Method 2: Azure Cloud Shell / CLI (One-Liner Script)

You can also open [Azure Cloud Shell](https://shell.azure.com/) directly in your browser and run:

```bash
# 1. Variables
RESOURCE_GROUP="rg-qp-bot"
LOCATION="westus2"
ENVIRONMENT="env-qp-bot"
APP_NAME="qp-discord-bot"

# 2. Create Resource Group
az group create --name $RESOURCE_GROUP --location $LOCATION

# 3. Create Container Apps Environment
az containerapp env create \
  --name $ENVIRONMENT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# 4. Create and Deploy Container App (with min-replicas 1 and ingress disabled)
az containerapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENVIRONMENT \
  --image ghcr.io/<your-github-username>/qp-discord-bot:latest \
  --cpu 0.25 --memory 0.5Gi \
  --min-replicas 1 \
  --max-replicas 1 \
  --ingress disabled \
  --env-vars \
    DISCORD_TOKEN="<your_discord_token>" \
    MAX_TEAMS="28" \
    STAFF_ROLE_NAME="QP Chair" \
    TICKETS_CATEGORY_NAME="Hardware Requests"
```

---

## 📊 Viewing Bot Logs in Azure

To check that your bot is running and view live logs:
1. In the Azure Portal, open your `qp-discord-bot` Container App.
2. In the left navigation bar under **Monitoring**, click **Log stream**.
3. You will see the bot login output:
   ```
   ==================================================
   🤖 QP Discord Bot logged in as: QP Bot#1234
    Connected to 1 server(s)
    Max Teams: 28
    Staff Role: QP Chair
    Tickets Category: Hardware Requests
   ==================================================
   ```

---

## 🔄 Automated CI/CD with GitHub Actions

The repository includes [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml).

Every time you push code to `main`:
1. GitHub Actions builds the Docker image.
2. It pushes the image to GitHub Packages (`ghcr.io`).
3. You can configure Azure credentials in your repository's GitHub Secrets to automatically roll out updates to Azure!
