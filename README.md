# QP-discord-bot

A Discord bot built with Python and `discord.py` for the **UCSD IEEE Quarterly Projects (QP)** server.

---

## ✨ Features

### 1. 👥 Team Role Assignment
* Run `/setup-team-roles` in `#team-assignment` to post an interactive panel with a **"Join Team"** button.
* Prompts members to enter their team number (1–28).
* **Validation & Auto-Creation**: Checks range and automatically creates `Team <N>` if missing on the server.
* **Single-Team Rule**: Automatically removes any previous team roles when joining a new team.

### 2. 🛠️ Hardware Request Tickets & Budget Tracking ($50 / Team)
* Run `/setup-tickets` to post an embed with a **"Request"** button.
* Creates private sequential ticket channels (`request-1`, `request-2`, etc.) under the `"Hardware Requests"` category.
* Accessible to the requester, their teammates, and `@QP Chair` / Admins.
* **$50 Budget Tracking**:
  * Approving requests opens a modal to specify the item name and approved amount.
  * Checks remaining team balance out of their $50 allocation and warns if over budget.
  * Status buttons: **Approve Request**, **Reject Request**, **Mark Ordered 📦**, **Mark Arrived 📍**, and **Close Ticket 🔒**.
* Commands:
  * `/budget [team]`: Check remaining balance and approved purchase history.
  * `/budget-summary`: Overview of all 28 teams' budgets and program spending (QP Chair only).

### 3. 📁 Automated Team Workspaces & Directory
* Run `/setup-team-workspaces` to auto-generate private text (`#team-X`) and voice (`🔊 Team X Lab`) channels for all 28 teams.
* Automatically splits into `IEEE QP Teams (1-14)` and `IEEE QP Teams (15-28)` to comply with Discord category limits.
* Commands:
  * `/my-team`: Check your team roster, remaining budget, borrowed lab equipment, and private channel link.
  * `/team-info team:<number>`: View directory status for any team.

### 4. 🙋 Lab Mentorship / "Call a Mentor" Queue
* Run `/setup-mentor-queue` to post a persistent **"Request Mentor / Help"** button.
* Students enter their team number, lab bench/location, and problem description.
* Notifies QP Chairs in real-time with action buttons:
  * **Claim Request 🏃**: Notifies the team that a mentor is heading over to their bench.
  * **Mark Resolved ✅**: Marks the ticket resolved and logs time.
  * **Cancel ❌**: Cancels the request.

### 5. 📦 Lab Inventory & Equipment Borrowing System
* Search and track parts available in the IEEE room drawer/cabinets.
* Track which teams borrowed what components and when.
* Commands:
  * `/inventory [search] [category]`: Search available parts in stock and their physical location in the lab.
  * `/inventory-add name: category: quantity: location:`: Add or restock components (QP Chair only).
  * `/checkout team: item: quantity: [member]`: Check out tools or components to a team.
  * `/return team: item: quantity:`: Return borrowed components back to lab stock.
  * `/borrowed [team]`: View all equipment currently checked out by a specific team or across all teams.

---

## 🚀 Setup & Installation

### 1. Discord Developer Portal Setup
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and open your Application.
2. Under **Bot**:
   * Enable **Server Members Intent** under Privileged Gateway Intents.
3. Under **OAuth2 > URL Generator**:
   * Scopes: `bot`, `applications.commands`
   * Permissions: `Manage Roles`, `Manage Channels`, `View Channels`, `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`, `Use Slash Commands`.
4. **Server Role Hierarchy**:
   * In your Discord Server Settings > Roles, ensure the **bot's role is positioned ABOVE the `Team` roles** and the `QP Chair` role.

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
   STAFF_ROLE_NAME=QP Chair
   TICKETS_CATEGORY_NAME=Hardware Requests
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
* `/setup-team-workspaces`: Auto-provision private channels for all teams.
* `/setup-mentor-queue`: Post the in-person help queue button in `#mentor-help`.

---

## ☁️ Azure Cloud Hosting

For instructions on deploying this bot to **Azure Container Apps (ACA)** to run 24/7 with zero maintenance, see our **[Azure Deployment Guide](docs/AZURE_DEPLOYMENT.md)**.
