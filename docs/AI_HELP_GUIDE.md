# 🤖 QP AI Help Channel & Knowledge Base Guide

The **QP Helper Bot** includes an integrated AI assistant powered by **Google Gemini API** (via the modern `google-genai` SDK).

The AI can read static documentation files (such as rules, schedules, BOM guides, and lab safety protocols) and scrape historical Discord channel messages (such as past announcements, FAQs, and hardware advice) to provide accurate, grounded answers to students in a dedicated `#ask-ai` channel.

---

## 🌟 Key Features

1. **Dedicated AI Channel (`#ask-ai`)**:
   - Students can ask questions directly in the `#ask-ai` text channel (placed under the `Help Requests` category).
   - The bot displays a live typing indicator (`...is typing`) and responds within seconds.
   - Preserves short-term conversational context so follow-up questions work naturally.
2. **Document Grounding (`knowledge/` folder)**:
   - Place any `.md` or `.txt` files inside the `knowledge/` folder.
   - The bot automatically loads and feeds these documents to Gemini's 1,000,000-token context window.
   - A comprehensive starter guide (`knowledge/qp_guidelines.md`) is included out-of-the-box.
3. **Channel History Ingestion (`/sync-ai-knowledge`)**:
   - Leadership can run `/sync-ai-knowledge` to scrape and index historical messages from `#announcements`, `#faq`, `#resources`, or any specific channel.
   - Strips out bot commands and spam, storing clean transcripts in SQLite.
4. **Slash Command (`/ask-ai`)**:
   - Students can also query the AI using `/ask-ai question:` with an option for private (ephemeral) replies. The command is strictly restricted to the `#ask-ai` channel to keep other channels free of bot clutter.
5. **Completely Free Tier**:
   - Google AI Studio provides a free Gemini API key with no credit card required.
   - Rate limit: 15 requests per minute and 1,500 requests per day (more than enough for a university competition).

---

## 🔑 Step 1: Get a Free Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Sign in with your Google account.
3. Click **Get API key** (or **Create API key**).
4. Click **Create API key in new project** and copy the generated key.

---

## ⚙️ Step 2: Configure Environment Variables

### Local Development (`.env`)
In your local `.env` file, add:
```env
# Google Gemini API Key
GEMINI_API_KEY=AIzaSy...your_actual_key_here

# Optional: customize model (default: gemini-3.5-flash-lite)
GEMINI_MODEL=gemini-3.5-flash-lite

# Channel name for AI Q&A (default: ask-ai)
AI_HELP_CHANNEL_NAME=ask-ai
```

### Production on Azure Container Apps
To add your API key to your running Container App in Azure:

#### Option A: Azure Portal
1. Open the [Azure Portal](https://portal.azure.com/) and navigate to your `qp-discord-bot` Container App.
2. In the left navigation menu under **Application** (or **Settings**), click **Containers**.
3. Click **Edit and deploy** at the top.
4. Click on your container row (`qp-discord-bot`).
5. Scroll down to **Environment variables** and click **Add**:
   - **Name**: `GEMINI_API_KEY`
   - **Value**: *(paste your Gemini API key)*
6. Click **Save** at the bottom of the drawer, then click **Create** at the bottom of the page.

#### Option B: Azure CLI / Cloud Shell
Run this single command in Azure Cloud Shell:
```bash
az containerapp update \
  --name qp-discord-bot \
  --resource-group rg-qp-bot \
  --set-env-vars GEMINI_API_KEY="AIzaSy...your_actual_key_here"
```

---

## 💬 Step 3: Discord Server Setup

### 1. Enable Message Content Intent
For the bot to read messages sent in the `#ask-ai` channel:
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click your bot application > **Bot** tab.
3. Under **Privileged Gateway Intents**, ensure **Message Content Intent** is toggled **ON**.
4. Click **Save Changes**.

### 2. Create the `#ask-ai` Channel
1. In your Discord server, right-click the **`Help Requests`** category.
2. Click **Create Channel**.
3. Set Channel Type to **Text Channel**.
4. Name the channel **`ask-ai`**.
5. Set Channel Topic:
   ```text
   Ask any question about IEEE Quarterly Projects (QP) rules, budgets, hardware requests, or lab inventory!
   ```

---

## 📚 Step 4: Adding Custom Knowledge & Syncing Channels

### Adding Documents
You can drop any markdown or text files into the `knowledge/` directory:
- `knowledge/rules.md`: Specific competition rules, deliverables, and judging rubrics.
- `knowledge/schedule.md`: Milestone deadlines, showcase dates, and workshop schedules.
- `knowledge/approved_parts.md`: Recommended vendors, approved microcontroller lists, and battery policies.

The bot automatically reloads these documents into memory.

### Indexing Channel Messages
To feed past announcements or Q&A into the bot's memory:
1. In Discord, run:
   ```text
   /sync-ai-knowledge
   ```
2. To index a specific channel:
   ```text
   /sync-ai-knowledge channel:#announcements message_limit:200
   ```
3. The bot will scan the messages, strip out bot commands, format the conversation, and save it to the SQLite database.

---

## 🛠️ Slash Commands Reference

| Command | Permission | Description |
|---|---|---|
| `/ask-ai question: [private:]` | Everyone | Ask the QP AI assistant a question directly in `#ask-ai`. |
| `/ai-status` | Everyone | Check whether the Gemini API is active, loaded document count, and synced channels. |
| `/sync-ai-knowledge [channel:] [limit:]` | Leadership (`QP Chair`, `Mentor`, `Officer`) | Scrapes and indexes Discord channel messages into the AI knowledge cache. |
