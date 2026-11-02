# 📋 Operations Event Request Generator Guide

The **QP Helper Bot** includes a dedicated `/request-event` command specifically designed for the **QP Chair** to streamline submitting event requests to the **IEEE Vice Chair of Operations**.

---

## 🌟 Why Use `/request-event`?

For every workshop, workathon, kickoff, and showcase, the QP Chair must submit a comprehensive list of logistical and marketing requirements to Operations.

Instead of manually drafting descriptions, looking up required logos, formatting dates, and inventing event codes from scratch, the QP Chair can simply provide a brief, informal prompt in Discord (e.g. *"PCB Soldering Workshop on Nov 12 at 6-8pm in Jacobs Hall with pizza"*). 

The bot automatically drafts all 14 required fields, packages them into a clean copy-paste block, and lets you edit or publish it to `#event-requests` with a single click.

---

## 🔒 Permission & Security

- **Command:** `/request-event prompt:<details>`
- **Access:** Strictly restricted to the **`QP Chair`** role and **Server Administrators**. Other members cannot run this command.

---

## 📝 The 14 Event Information Fields

| # | Field Name | Description & Automation Rules |
|---|---|---|
| 1 | **Event Name** | Engaging, title-cased event title (e.g. *PCB Design & Soldering Workshop*). |
| 2 | **Event Description** | Formal, professional description outlining technical/educational purpose, hands-on student engineering activities, and room utilization for engineering department room reservation approval and official academic records. |
| 3 | **Event Type** | Automatically locked to **`Projects`**. |
| 4 | **Department** | Automatically locked to **`Projects`**. |
| 5 | **Location** | Extracted from prompt or defaults to *IEEE Project Space (Jacobs Hall 4309)*. |
| 6 | **Event Date** | Fully formatted date (e.g. *Wednesday, November 12, 2026*). |
| 7 | **Start Time** | Start time (e.g. *6:00 PM*). |
| 8 | **End Time** | End time (e.g. *8:00 PM*). |
| 9 | **Event Code** | Uppercase structured event code up to 25–30 characters (e.g. `QP-WINTER-KICKOFF-26`, `QP-PCB-SOLDER-26`, `QP-WORKATHON-W5-26`). Structured so quarter, year, and technical topic are clearly identified for attendance tracking and university records. |
| 10 | **Flyers Needed** | Defaults to `No` unless physical on-campus poster distribution is requested. |
| 11 | **Graphics Needed** | Defaults to `Yes (Instagram 1:1, Discord 16:9, Website)` for marketing. |
| 12 | **Photography Needed** | `Yes` (submits photos within 48 hrs) or `No`. |
| 13 | **Required Logos** | Always includes **`IEEE`**. If food/pizza/snacks/boba or AS funding was mentioned, **`AS`** (Associated Students) is strictly appended (e.g. `IEEE, AS`). Also includes any co-hosts (`HKN, TESC, PIB, TNT, SWE`). |
| 14 | **Expected Attendance** | Estimated attendee count to plan room capacity and catering. |

---

## 🖥️ How It Works (Step-by-Step)

### Step 1: Run the Command
In any staff channel (or in `#event-requests`), run:
```text
/request-event prompt: "Midterm PCB Soldering Workshop next Wednesday Nov 12 from 6 to 8 PM in Jacobs Hall 4309 with pizza from AS funding, expecting 45 people"
```

### Step 2: Private Preview
The bot immediately responds with an **ephemeral (private)** message visible only to you:
- **Embed Summary:** Visual card summarizing all logistics, media, and logo requirements.
- **Copy-Paste Block:** Monospace code block containing all 14 fields ready to copy directly into the Vice Chair's Google Form.

### Step 3: Interactive Controls
Below the preview, four action buttons are available:

1. **🚀 Publish to #event-requests**:
   - Posts the finalized event package to the designated `#event-requests` channel (creates the channel automatically if it doesn't exist yet).
   - Serves as a persistent historical record for you and the Vice Chair of Operations.
2. **✏️ Edit Details**:
   - Opens an interactive Discord popup modal allowing you to tweak the Event Name, Event Code (up to 30 characters), Location, Date/Time, and Attendance before publishing.
3. **🔄 Regenerate**:
   - Re-runs the AI generator if you want a fresh variation.
4. **🗑️ Dismiss**:
   - Discards the draft.
