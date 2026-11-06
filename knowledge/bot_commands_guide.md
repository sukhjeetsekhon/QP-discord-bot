# UCSD IEEE Quarterly Projects (QP) — Bot Commands Guide

Welcome to the official command guide for the UCSD IEEE Quarterly Projects Discord Bot! This guide is written specifically for **QP participants and teams** to help you navigate your team workspaces, check out lab components, request mentor help, and ask technical questions.

---

## 1. 🚀 Quick Start: How Commands Work

- **Slash Commands (`/`)**: Type `/` in any channel to open Discord's interactive command menu. Start typing the command name (e.g. `/my-team` or `/ask-ai`) and Discord will autocomplete the command and its parameters.
- **Auto-Detection**: Many commands (such as `/my-team`, `/budget`, and `/borrow-photo`) automatically detect your team number from your assigned `Team X` role—you don't have to type your team number manually!
- **Interactive UI Buttons**: Several workflows (joining your team, requesting a mentor, borrowing lab equipment, and requesting returns) use persistent interactive buttons on pinned panels in dedicated channels.

---

## 2. 👥 Team & Directory Commands

### `/my-team`
- **Target Audience:** All participants.
- **Description:** Your team's quick dashboard. Displays your team number, teammates (members with your team role), remaining hardware budget, and all actively borrowed lab items.
- **Parameters:** None (automatically detects your team from your role).
- **When to use:** Use this whenever you want to see who is on your team roster, verify your team status, or check what lab equipment your team currently has checked out.
- **Example:**
  ```text
  /my-team
  ```
- **Note:** If you don't have a team role yet, the bot will prompt you to join your team first in `#team-assignment`.

---

### `/team-info`
- **Target Audience:** All participants.
- **Description:** Look up any team's roster, budget status, and borrowed equipment across the competition.
- **Parameters:**
  - `team` *(Required, integer 1–28)*: The team number you wish to look up.
- **When to use:** Use this to see who is on another team, connect with fellow participants, or see what components other teams are working with.
- **Example:**
  ```text
  /team-info team: 5
  ```

---

## 3. 🤖 AI Help & Technical Support Commands

### `/ask-ai`
- **Target Audience:** All participants.
- **Description:** Ask the QP AI Assistant any question about competition rules, milestone deliverables, budgets, lab hours, or engineering topics.
- **What you can ask:**
  - **Competition Rules & Logistics:** Milestone expectations, showcase dates, Open Access Hours, battery rules, component policies.
  - **Hardware & Circuits:** Microcontroller pinouts (ESP32, Arduino, RP2040, STM32), sensor wiring (I2C, SPI, UART, ADC), motor drivers (L298N, DRV8825), voltage regulation, pull-up resistors.
  - **Firmware & Coding:** C/C++, Arduino libraries, MicroPython, Python scripts, debugging syntax or runtime errors.
- **Parameters:**
  - `question` *(Required, string)*: What you want to ask.
  - `private` *(Optional, boolean, default: False)*: Set to `True` if you want the answer to be visible only to you (ephemeral). Leave as `False` so your teammates can see the answer too!
- **Example:**
  ```text
  /ask-ai question: What are the SDA and SCL default pins on an ESP32-WROOM?
  /ask-ai question: What is expected for Milestone 1? private: True
  ```
- **Pro-Tip:** You can also ask questions without slash commands by simply typing in the **`#ai-qna-help`** channel. The bot will automatically reply in a dedicated thread!

---

### `/ai-status`
- **Target Audience:** All participants.
- **Description:** Check the operational health and status of the QP AI Assistant.
- **Parameters:** None.
- **What it shows:**
  - Operational model (e.g. Google Gemini 2.5 Flash).
  - Number of official knowledge documents loaded from `knowledge/`.
  - Number of historical Discord channel messages indexed.
  - Total grounded knowledge base size.
- **Example:**
  ```text
  /ai-status
  ```

---

## 4. 📦 Lab Inventory & Tool Checkouts

The IEEE Project Space stocks shared tools, development boards, sensors, and passive components. You can search inventory, check item locations, and log loans directly through the bot.

---

### `/inventory`
- **Target Audience:** All participants.
- **Description:** Search and browse components available in the IEEE Project Space inventory.
- **Parameters:**
  - `search` *(Optional, string)*: Search keyword for the item name (e.g. `servo`, `esp32`, `multimeter`, `oled`, `resistor`).
  - `category` *(Optional, string)*: Filter by category (e.g. `Microcontrollers`, `Sensors`, `Actuators`, `Power`, `Tools`).
- **What it shows:** Item name, category, quantity available in stock, total stock, and exact physical storage location (e.g., `Cabinet A - Bin 3`).
- **Examples:**
  ```text
  /inventory
  /inventory search: servo
  /inventory category: Microcontrollers
  ```

---

### `/whereis`
- **Target Audience:** All participants.
- **Description:** Pinpoint where an item is located: see how many units are stored in the lab vs. which specific teams currently have units checked out.
- **Parameters:**
  - `item` *(Required, string)*: Component name or Item ID (e.g. `Arduino Uno`, `Soldering Iron`, `SG90 Servo`).
- **When to use:** Use this when you need a shared lab tool or component and want to see if it is in the lab cabinet or who has it.
- **Example:**
  ```text
  /whereis item: ESP32-WROOM
  ```

---

### `/borrow-photo`
- **Target Audience:** All participants.
- **Description:** Fast slash command to log a borrowed lab item with an attached photo.
- **Parameters:**
  - `image` *(Required, attachment)*: Attach a clear photo of the physical item(s) you are borrowing from the lab.
  - `item` *(Required, string)*: Item name/description and quantity (e.g. `2x SG90 Servos, 1x Breadboard`).
  - `team` *(Optional, integer 1–28)*: Your team number. Auto-detected from your team role if left blank!
- **What happens:**
  1. The bot publishes your active loan card in **`#borrowed-items`** (public board showing all active checkouts).
  2. The bot files an audit record in **`#inventory`** (leadership private log).
  3. You receive an immediate confirmation with a link to your active equipment card.
- **Example:**
  ```text
  /borrow-photo image: [uploaded_photo.jpg] item: 1x Arduino Uno, 1x USB Cable
  ```

---

### `/borrowed-items`
- **Target Audience:** All participants.
- **Description:** View visual photo cards of borrowed items for your team or across all teams.
- **Parameters:**
  - `team` *(Optional, integer 1–28)*: Filter by team number. Leave blank to view active loans across all teams.
  - `status` *(Optional, choice)*:
    - `Currently Borrowed (In Use)` (default)
    - `Return Pending Review`
    - `Returned`
    - `All Records`
- **When to use:** Use this to double-check what items your team is responsible for returning before the showcase.
- **Example:**
  ```text
  /borrowed-items team: 3
  /borrowed-items status: Currently Borrowed (In Use)
  ```

---

### `/borrowed`
- **Target Audience:** All participants.
- **Description:** View a clean text list of standard catalog items currently checked out by a specific team or across all teams.
- **Parameters:**
  - `team` *(Optional, integer 1–28)*: Team number. Auto-detected from your role if omitted.
- **Example:**
  ```text
  /borrowed
  /borrowed team: 12
  ```

---

### `/loan-history`
- **Target Audience:** All participants.
- **Description:** View the chronological history of all checkouts and returns with timestamps.
- **Parameters:**
  - `team` *(Optional, integer 1–28)*: Filter by team number.
  - `item` *(Optional, string)*: Filter by item name (e.g. `multimeter`).
  - `limit` *(Optional, integer, default: 15)*: Maximum number of log entries to retrieve.
- **Example:**
  ```text
  /loan-history team: 7 limit: 10
  ```

---

## 5. 💰 Budget Commands

### `/budget`
- **Target Audience:** All participants.
- **Description:** Check the remaining hardware budget, total spent, and purchase transaction history for your team or any team.
- **Parameters:**
  - `team` *(Optional, integer 1–28)*: Team number to inspect. Auto-detected from your role if omitted.
- **Fall 2026 Policy Context:**
  - For Fall 2026, teams do not receive an individual cash budget.
  - The QP Chair has allocated the budget upfront to purchase common components in bulk for all teams to share in the IEEE Project Space.
  - The `/budget` command reflects this status and logs any shared hardware distributions.
- **Example:**
  ```text
  /budget
  /budget team: 4
  ```

---

## 6. 🛠️ Interactive Self-Service Panels (Buttons & Modals)

In addition to slash commands, several key workflows are handled through interactive buttons in dedicated channels.

---

### Flow A: Joining Your Team Role (`#team-assignment`)
1. Go to the **`#team-assignment`** channel.
2. Click the **"Join Team"** button on the panel.
3. A pop-up modal will prompt you to enter your **Team Number** (1 through 28).
4. Click **Submit**.
5. You will instantly receive your `Team <N>` Discord role, granting access to:
   - Your private team text channel: `#team-<N>`.
   - Your private team voice channel: `Team <N> VC`.
6. *Note:* You can only belong to one team role at a time. Entering a new team number will automatically replace your old team role.

---

### Flow B: Requesting a Mentor (`#mentor-queue` or `#help-tickets`)
1. When you need help with schematics, soldering, coding, or debugging, go to **`#mentor-queue`**.
2. Click the **"🙋 Request Mentor"** button.
3. The modal will ask you for:
   - **Topic / Description:** Briefly describe what you need assistance with (e.g. `Motor driver smoking when powered by 12V`, `I2C scanner not detecting OLED display`, `Need help setting up PlatformIO`).
   - **Location / Channel:** Specify where the mentor can find you (e.g. `Project Space Bench 3`, `Team 4 VC`, `Jacobs Hall 2nd floor`).
4. Click **Submit**.
5. The bot opens a private dynamic help channel (`#help-X`) for you, your team, and mentors.
6. When an IEEE mentor clicks **Claim Request 🏃**, you will be notified. Once your question is resolved, click **Mark Resolved ✅** to close the ticket.

---

### Flow C: Borrowing Lab Items via Photo (`#borrow-items`)
1. Head to the **`#borrow-items`** channel in the Project Space.
2. Click the **"📸 Borrow Lab Item"** button on the panel.
3. The bot creates a private 24-hour checkout thread for your team.
4. In that thread:
   - Upload a clear **photo** of the physical item(s) you are borrowing.
   - Type the **item name / description & quantity** (e.g. `2x SG90 Servos, 1x Breadboard`).
5. The bot publishes your active loan card in **`#borrowed-items`** and archives a private record in **`#inventory`**.
6. You receive a direct receipt link in your thread!

---

### Flow D: Returning Lab Items (`#borrowed-items`)
1. Bring the borrowed item(s) to the **IEEE Project Space (Jacobs Hall 4309)** during **Open Access Hours (OAH)**.
2. Open the **`#borrowed-items`** channel on Discord.
3. Locate your team's active loan card and click the **"Request Return 📦"** button.
4. The card status changes to `⏳ Return Pending Review`, and an alert pings `@QP Chair` in `#inventory`.
5. Hand the item to the on-duty IEEE officer. The officer inspects the hardware and clicks **"Confirm Return ✅"** on the private card.
6. The public card in `#borrowed-items` is automatically removed from the active board!

---

### Flow E: Requesting Custom Hardware Review (`#tickets`)
1. If your team requires special hardware evaluation, head to **`#tickets`**.
2. Click the **"Request"** button on the panel.
3. A private ticket channel (`request-<N>`) is created between your team and the `@QP Chair`.
4. Discuss your hardware requirements or component questions directly with leadership.

---

## 7. 🔒 Leadership & Admin Commands (Reference for Participants)

The following commands are strictly restricted to the **`QP Chair`**, **`Officers`**, and **Server Administrators**. Participants will receive a permission error if they attempt to run them, but they are documented here so you understand how leadership operates the bot on your behalf:

- **`/inventory-add name: category: quantity: location:`**: Adds new components or restocks units in the lab inventory database.
- **`/checkout team: item: quantity: [member:]`**: Manually records a component checkout to a team.
- **`/return team: item: quantity:`**: Manually logs a component return back to lab stock.
- **`/setup-borrow-panel [channel:]`**: Deploys or updates the borrowing button panel in `#borrow-items`.
- **`/setup-team-roles`**: Deploys the team role assignment button panel in `#team-assignment`.
- **`/setup-mentor-queue`**: Deploys the mentor help queue button panel in `#mentor-queue`.
- **`/setup-tickets`**: Deploys the hardware tickets button panel in `#tickets`.
- **`/setup-team-workspaces season: year: num_teams:`**: Automatically configures all quarterly text and voice categories and channels.
- **`/budget-adjust action: amount: [team:] [all_teams:] [reason:]`**: Adjusts or overrides a team's budget balance.
- **`/budget-ieee-bonus team: num_ieee_members:`**: Applies the $11/verified member bonus calculation.
- **`/budget-summary`**: Displays an aggregate spending report across all 28 teams.
- **`/sync-ai-knowledge [channel:] [message_limit:]`**: Indexes past Discord announcements into the AI knowledge base.
- **`/request-event prompt:`**: Uses AI to draft formal event and room reservation proposals for the Vice Chair of Operations.

---

## 8. 💡 Tips & Frequently Encountered Issues

- **"You do not have a Team role yet!"**:
  - Solution: Head to `#team-assignment`, click "Join Team", and enter your team number (1–28).
- **"Only Leadership can run this command"**:
  - Explanation: This command is reserved for officers (such as adding inventory stock or modifying budgets). Check the list in Section 7 above!
- **Can my teammate return an item that I checked out?**:
  - Yes! Any member with the same `Team <N>` role can click **"Request Return 📦"** on the team's card in `#borrowed-items`.
- **Where can I see what parts are available right now?**:
  - Run `/inventory` in any channel, or visit the IEEE Project Space during Open Access Hours.
- **Can I ask the bot technical coding questions?**:
  - Yes! The `/ask-ai` assistant is trained on embedded engineering, microcontrollers, circuits, and Python/C++ debugging in addition to QP competition rules.
