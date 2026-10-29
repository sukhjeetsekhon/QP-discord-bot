# QP-discord-bot

A Discord bot built with Python and `discord.py` for the **UCSD IEEE Quarterly Projects (QP)** server.

---

## ✨ Features

### 1. 👥 Team Role Assignment
* Run `/setup-team-roles` in `#team-assignment` to post an interactive panel with a **"Join Team"** button.
* Prompts members to enter their team number (1–28).
* **Validation & Auto-Creation**: Checks range and automatically creates `Team <N>` if missing on the server.
* **Single-Team Rule**: Automatically removes any previous team roles when joining a new team.

### 2. 🛠️ Hardware Request Tickets & Budget Tracking ($50 Base + $11/IEEE Member)
* Run `/setup-tickets` to post an embed with a **"Request"** button.
* Creates private sequential ticket channels (`request-1`, `request-2`, etc.) under the `"Hardware Requests"` category.
* Accessible to the requester, their teammates, and `@QP Chair` / `@Mentor` / `@Officer` roles.
* **Budget Tracking & Adjustments**:
  * Approving requests opens a modal to specify the item name and approved amount.
  * Checks remaining team balance and warns if over budget.
  * Status buttons: **Approve Request**, **Reject Request**, **Mark Ordered 📦**, **Mark Arrived 📍**, and **Close Ticket 🔒**.
* Commands:
  * `/budget [team]`: Check remaining balance, total spent, and purchase history.
  * `/budget-adjust action: amount: [team:] [all_teams:] [reason:]`: Add (`+`), subtract (`-`), or set (`=`) budget for an individual team **OR all teams at once** (Leadership only).
  * `/budget-ieee-bonus team: num_ieee_members:`: Automatically calculates and sets budget with **$50 base + $11 per verified IEEE member** (Leadership only).
  * `/budget-summary`: Overview of all teams' budgets, total program spending, and remaining funds (Leadership only).

### 3. 📁 Automated Quarterly Team Workspaces (`<Season> <Year>` & `<Season> <Year> VC`)
* Run `/setup-team-workspaces season: year: num_teams:` (e.g. `season:Fall year:2026 num_teams:28`) to automatically generate:
  * **Text Category**: e.g. `Fall 2026` containing `team-1` through `team-n`.
  * **Voice Category**: e.g. `Fall 2026 VC` containing `Team 1 VC` through `Team n VC`.
  * **Permissions**: Strictly locked to the respective `Team X` role, plus full access for **`Mentor`**, **`QP Chair`**, and **`Officer`** roles.
  * Completely abides by Discord's 50-channels-per-category limit and allows instant 1-click reconfiguration each quarter.
* Commands:
  * `/my-team`: Check your team roster, remaining budget, borrowed lab equipment, and private channel link.
  * `/team-info team:<number>`: View directory status for any team.

### 4. 🙋 Mentor Help & Feedback Queue (Private Dynamic Help Channels)
* Run `/setup-mentor-queue` to post a persistent **"Request Mentor Help / Feedback"** panel in `#help-tickets`.
* **Auto-Detected Team**: Automatically identifies the requester's team number from their role—no manual team typing required.
* **Private Dynamic Help Channels (`help-1`, `help-2`, etc.)**:
  * Dynamically numbered starting from 1 under the `Help Requests` category.
  * Private channel visible exclusively to the requesting team, requester, and Leadership (`Mentor`, `QP Chair`, `Officer`).
* **In-Channel Ticket Controls**:
  * **Claim Request 🏃**: Mentors click to claim the request, updating status and notifying the team.
  * **Mark Resolved ✅**: Mentors or students mark the ticket resolved when help is complete.
  * **Close Channel 🔒**: Confirms and deletes the private channel with countdown once assistance wraps up.

### 5. 📦 Lab Inventory Location Tracking & Timestamped Borrowing
* Track which team borrowed what component and when, with exact timestamps on checkouts and returns.
* Commands:
  * `/inventory [search] [category]`: Search available parts in stock and their physical location in the lab.
  * `/inventory-add name: category: quantity: location:`: Add or restock components (Leadership only).
  * `/checkout team: item: quantity: [member]`: Check out tools or components to a team with an exact timestamp.
  * `/return team: item: quantity:`: Return borrowed components back to lab stock with an exact return timestamp.
  * `/whereis item:`: Pinpoint exactly where all units of a component are (how many in lab stock vs. which teams borrowed them).
  * `/borrowed [team]`: View all equipment currently checked out by a specific team or across all teams.
  * `/loan-history [team] [item] [limit]`: View a chronological audit log of all checkouts and returns with timestamps.

### 6. 🤖 AI Help Channel (`#ask-ai`) & Knowledge Base
* Powered by **Google Gemini API** (free tier from Google AI Studio).
* Students can ask questions directly in the `#ask-ai` channel located in the `Help Requests` category.
* **Grounding via Documents & Channel History**:
  * Loads static guides, rules, and schedules from the `knowledge/` directory.
  * Scrapes and indexes historical Discord messages via `/sync-ai-knowledge`.
  * Provides conversational answers with context memory for follow-up questions.
* Commands:
  * `/ask-ai question: [private:]`: Query the AI from any channel.
  * `/sync-ai-knowledge [channel:] [limit:]`: Index Discord channel messages into the knowledge base (Leadership only).
  * `/ai-status`: View API health, loaded documents, and synced channel counts.
* See the full **[AI Help Channel Guide](docs/AI_HELP_GUIDE.md)** for details.

---

## 🚀 Setup & Installation

### 1. Discord Developer Portal Setup
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and open your Application.
2. Under **Bot**:
   * Enable **Server Members Intent** under Privileged Gateway Intents.
   * Enable **Message Content Intent** under Privileged Gateway Intents (required for reading questions in `#ask-ai`).
3. Under **OAuth2 > URL Generator**:
   * Scopes: `bot`, `applications.commands`
   * Permissions: `Manage Roles`, `Manage Channels`, `View Channels`, `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`, `Use Slash Commands`.
4. **Server Role Hierarchy**:
   * In your Discord Server Settings > Roles, ensure the **bot's role is positioned ABOVE the `Team` roles** and the leadership roles.

---

### 2. Local Environment Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/sukhjeetsekhon/QP-discord-bot.git
   cd QP-discord-bot
   ```

2. **Set up virtual environment & install dependencies**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

3. **Configure `.env`**:
   ```bash
   cp .env.example .env
   ```
   Fill in your variables:
   ```env
   DISCORD_TOKEN=your_token_here
   MAX_TEAMS=28
   DEFAULT_TEAM_BUDGET=50.00
   IEEE_MEMBER_BONUS=11.00
   STAFF_ROLE_NAME=QP Chair
   TICKETS_CATEGORY_NAME=Hardware Requests
   MENTOR_CATEGORY_NAME=Help Requests
   AI_HELP_CHANNEL_NAME=ask-ai
   GEMINI_API_KEY=your_gemini_api_key_here
   DB_PATH=data/qp_bot.db
   ```

4. **Run the bot**:
   ```bash
   python bot.py
   ```

---

## 🛠️ Admin Setup Commands

* `/setup-team-roles`: Post the team role selection panel in `#team-assignment`.
* `/setup-tickets`: Post the hardware request button in your procurement channel.
* `/setup-team-workspaces`: Auto-provision separate text (`<Season> <Year>`) and voice (`<Season> <Year> VC`) categories and channels.
* `/setup-mentor-queue`: Post the help & feedback queue panel in `#mentor-help`.

---

## ☁️ Azure Cloud Hosting

For instructions on deploying and updating this bot on **Azure Container Apps (ACA)** to run 24/7, see our **[Azure Deployment Guide](docs/AZURE_DEPLOYMENT.md)**.

> **🚀 Continuous Deployment Enabled:**
> Every `git push` to `main` triggers a GitHub Actions workflow that automatically builds the container image and deploys a new revision directly to your Azure Container App.
>
> 💡 *Manual Fallback*: If you ever need to manually deploy a specific revision, you can update the image tag (`ghcr.io/sukhjeetsekhon/qp-discord-bot:<commit-sha>`) under **App** > **Containers** > **Edit and deploy** in the Azure Portal.


