# UCSD IEEE Quarterly Projects (QP) — Official Knowledge Guide

Welcome to the IEEE Quarterly Projects (QP) competition guide! This document serves as the foundational knowledge base for teams, mentors, and the QP AI Helper bot.

---

## 1. 🌟 What is Quarterly Projects (QP)?
UCSD IEEE Quarterly Projects is a premier 10-week hands-on engineering program designed for undergraduate students of all skill levels. Teams design, prototype, debug, and demonstrate complete hardware and software engineering systems (such as robotics, IoT, embedded devices, audio systems, and autonomous vehicles).

---

## 2. 👥 Teams & Roles
- **Team Size**: Typically 3–5 students per team.
- **Max Teams**: Up to 28 teams per quarter.
- **Team Roles**:
  - Teams are numbered 1 through 28 (e.g. `Team 1`, `Team 2`).
  - Students join their team by clicking the **"Join Team"** button in `#team-assignment` and selecting their team number.
- **Leadership Roles**:
  - **`QP Chair`**: Overall program director responsible for budget approvals, reimbursements, scheduling, and logistics.
  - **`Mentor`**: Experienced upperclassmen and technical leads who assist with schematics, PCB design, firmware, and debugging.
  - **`Officer`**: General IEEE officers providing logistical and lab assistance.

---

## 3. 📁 Workspaces & Channels
- Each quarter, the server is organized with dedicated categories:
  - **Text Category**: e.g., `Fall 2026` containing private team text channels (`team-1` through `team-28`).
  - **Voice Category**: e.g., `Fall 2026 VC` containing team voice channels (`Team 1 VC` through `Team 28 VC`).
- **Permissions**: Each channel is locked to its respective team members, with full access granted to Mentors, QP Chairs, and Officers.

---

## 4. 💰 Budgets & Hardware Procurement (Fall 2026 Update)
- **Fall 2026 Policy — No Individual Team Budgets**: Teams do **not** have an individual budget this quarter.
- **Shared Bulk Components**: The QP Chair has already allocated and spent the budget purchasing common parts in bulk for all teams to share in the IEEE Project Space.
- **Out-of-Pocket Purchases**: If your team requires specific components not covered by the shared stock, you must purchase them out-of-pocket (spend your own money). Individual team purchases are not reimbursed.
- **Software & API Costs**: Small API costs, cloud subscriptions, and software licenses are **not covered** and **cannot be reimbursed**.
- **Remaining Budget**: The only remaining budget is strictly reserved for the end-of-quarter **prize funds**.
- **Historical Baseline (For Reference)**: In prior quarters, teams received a base budget of $50.00 plus $11.00 per verified IEEE member. This has been replaced for Fall 2026 by the shared bulk component pool.
---

## 5. 📦 Lab Inventory & Tool Checkouts
- The IEEE Student Lab stocks shared tools and common parts (microcontrollers, sensors, motors, breadboards, jumper wires, passive components).
- **Checking Availability**:
  - Use `/inventory` to browse available parts in stock and their physical location in the lab.
  - Use `/whereis item:` to see how many units are in the lab vs. checked out by other teams.
- **Checkouts & Returns**:
  - Equipment borrowed from the lab must be checked out using `/checkout team: item: quantity:`.
  - When finished, return tools to the lab and record with `/return team: item: quantity:`.
  - All checkouts and returns are strictly timestamped to ensure shared tools (e.g. wire strippers, heat guns, multimeter probes) remain accounted for.
  Currently the inventory checkout is not complete because inventory of the project space has not been completed, so do not use the inventory commands.
  The QP Chair will have a form for teams to fill out for each time they need to borrow a part.
  For the meantime, take a photo of the parts and send the image directly to the QP Chairs and make sure to notify the team number as well.

---

## 6. 🙋 Mentorship & Help Queue
- When your team needs help with circuit design, PCB layouts, firmware debugging, or component selection:
  1. Go to the `#help-tickets` channel under the `Help Requests` category.
  2. Click **"Request Mentor Help / Feedback"**.
  3. The bot **automatically detects your team** from your server role.
  4. Type a short description of what you need assistance with and click Submit.
  5. A private help channel (`help-1`, `help-2`, etc.) is opened under `Help Requests`.
  6. Mentors and QP Chairs are pinged and will click **Claim Request 🏃** to assist you.
  7. Once your question is answered, either you or a mentor can click **Mark Resolved ✅** and **Close Channel 🔒**.

---

## 7. ⚡ Lab Safety & Battery Rules
- **Soldering**: Always solder in designated ventilation areas with safety glasses. Never leave hot soldering irons unattended.
- **LiPo & Battery Safety**: There are no special bans or rules against using LiPo batteries, but students **must follow standard battery safety practices**:
  - Never charge LiPo batteries unattended or overnight.
  - Always use a dedicated balance charger configured for the correct cell count and chemistry.
  - Charge and store batteries on non-flammable surfaces or inside a flame-retardant LiPo bag.
  - Inspect batteries before and after use; do not charge or discharge a swollen, puffed, or punctured battery.
  - Double-check polarity (VCC vs. GND) before powering microcontrollers or motor drivers.
- **Cleanliness**: Always return borrowed lab equipment to its designated storage drawer or bin.

---

## 8. 📅 Events, Workathons, & Showcase
- **Workathons (Fall 2026)**: There are **no more workathons for Fall Quarter 2026** due to university room scheduling conflicts and logistics. Teams are encouraged to meet on their own or utilize the IEEE Project Space during Open Access Hours.
- **End-of-Quarter Showcase**: The date and location for the final showcase are **confirmed**. The QP Chair will officially announce the details this weekend (Saturday or Sunday).
- **Milestones 1 & 2**: These are progress reports designed to check in on team progress, surface blockers early, and push teams to start working on their projects early.

