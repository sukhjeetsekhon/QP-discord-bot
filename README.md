# QP-discord-bot

A Discord bot built with Python and `discord.py` for the **UCSD IEEE Quarterly Projects (QP)** server.

---

## ✨ Features

### 1. 👥 Team Role Assignment
* Run `/setup-team-roles` to post an interactive embed with a **"Join Team"** button in `#team-assignment`.
* Clicking the button opens a modal prompt where members enter their team number (1–28).
* **Validation & Auto-Creation**: Checks that the team number is within range. If the role `Team <N>` does not already exist on the server, the bot creates it automatically.
* **Single-Team Exclusivity**: If a member changes teams, any existing `Team <N>` role is removed before assigning the new one.
* **Persistent Button**: Survives bot restarts without needing to repost the embed.

### 2. 🛠️ Hardware Request Ticket System
* Run `/setup-tickets` to post an interactive embed with a **"Request"** button in your hardware channel.
* Clicking the button automatically creates a private temporary ticket channel named `request-1`, `request-2`, etc.
* **Dynamic Sequential Numbering**: Calculates the next number based on existing `request-X` channels.
* **Smart Access Control**:
  * Private channel organized under the **"Hardware Requests"** category (auto-created if missing).
  * Accessible only to the **requester**, their **teammates** (if they hold a `Team <N>` role), and members with the **"QP Chair"** role (or server administrators).
  * `@everyone` cannot view the channel.
* **Review Controls Inside Ticket**:
  * Pings the requester and `@QP Chair` with instructions on what details to provide (item name, product link, cost, justification).
  * Staff control buttons:
    * **Approve Request** (marks request as approved)
    * **Reject Request** (marks request as rejected)
    * **Close Ticket** (prompts confirmation and deletes the temporary channel)

---

## 🚀 Setup & Installation

### 1. Discord Developer Portal Setup
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a New Application.
2. Under the **Bot** tab:
   * Reset/Copy your **Bot Token**.
   * Under **Privileged Gateway Intents**, enable:
     * **Server Members Intent** (required to view and assign roles).
3. Under **OAuth2 > URL Generator**:
   * Scopes: `bot`, `applications.commands`
   * Bot Permissions:
     * `Manage Roles`
     * `Manage Channels`
     * `View Channels`
     * `Send Messages`
     * `Embed Links`
     * `Attach Files`
     * `Read Message History`
     * `Use Slash Commands`
   * Copy the generated URL and invite the bot to your server.
4. **Important Server Role Hierarchy**:
   * In your Discord Server Settings > Roles, ensure the **bot's role is positioned ABOVE the `Team` roles** and the `QP Chair` role so Discord allows the bot to assign and manage them.

---

### 2. Local Environment Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/QP-discord-bot.git
   cd QP-discord-bot
   ```

2. **Create a virtual environment** (optional but recommended):
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   * Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   * Open `.env` and fill in your values:
     ```env
     DISCORD_TOKEN=your_bot_token_here
     MAX_TEAMS=28
     STAFF_ROLE_NAME=QP Chair
     TICKETS_CATEGORY_NAME=Hardware Requests

     # Optional: your server ID for instant slash command testing
     # GUILD_ID=123456789012345678
     ```

---

## 🏃 Running the Bot

Start the bot with:

```bash
python bot.py
```

---

## 🛠️ Admin Commands

Both commands require **Administrator** permissions in the server:

* `/setup-team-roles`: Run in `#team-assignment` to post the interactive role selection panel.
* `/setup-tickets`: Run in your hardware announcements or requests channel to post the ticket creation panel.
