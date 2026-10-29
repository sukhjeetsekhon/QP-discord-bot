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

## 4. 💰 Budgets & Hardware Procurement
- **Base Budget**: Every team starts with a baseline budget of **$50.00**.
- **IEEE Member Bonus**: Teams receive an additional **+$11.00** for each verified IEEE student member on the team.
  - 0 IEEE members: $50.00 total budget
  - 1 IEEE member: $61.00 total budget
  - 2 IEEE members: $72.00 total budget
  - 3 IEEE members: $83.00 total budget
  - 4 IEEE members: $94.00 total budget
  - The QP Chair verifies active IEEE membership and sets the bonus via `/budget-ieee-bonus`.
- **How to Order Hardware**:
  1. Go to the `#hardware-requests` (or tickets) channel.
  2. Click the **"Request"** button.
  3. A private ticket channel (`request-1`, `request-2`, etc.) is generated for your team.
  4. Post the links, part numbers, quantity, and total cost of the components your team needs.
  5. A QP Chair or Mentor reviews the request and clicks **Approve Request** (deducting the amount from your team's budget), **Mark Ordered 📦**, and **Mark Arrived 📍**.
  6. When parts arrive, pick them up in the **IEEE Student Lab**.

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

## 7. ⚡ Lab Safety Rules
- **Soldering**: Always solder in designated ventilation areas with safety glasses. Never leave hot soldering irons unattended.
- **Power & Batteries**: Double-check polarity (VCC vs GND) before powering circuits. Do not short-circuit or charge LiPo batteries unattended.
- **Cleanliness**: Always return borrowed lab equipment to its designated storage drawer or bin.

