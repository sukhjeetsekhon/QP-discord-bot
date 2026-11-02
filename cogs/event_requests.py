import json
import re
from datetime import datetime
from typing import Dict, Any, Optional
import discord
from discord import app_commands
from discord.ext import commands
from google import genai
from google.genai import types

import config
from cogs.ai_help import get_gemini_client


def is_qp_chair_or_admin(member: discord.Member) -> bool:
    """Check if member has the QP Chair role or has Administrator permissions."""
    if member.guild_permissions.administrator:
        return True
    return any(role.name == config.STAFF_ROLE_NAME for role in member.roles)


EVENT_SYSTEM_INSTRUCTION = (
    "You are an assistant for the IEEE UCSD Quarterly Projects (QP) Chair.\n"
    "Your task is to take an informal event prompt from the QP Chair and generate a complete, structured event request package for the IEEE Vice Chair of Operations.\n\n"
    "CRITICAL RULES & FORMAT REQUIREMENTS:\n"
    "1. Event Type: Must ALWAYS be 'Projects'\n"
    "2. Department: Must ALWAYS be 'Projects'\n"
    "3. Event Code: MUST BE SHORT, UPPERCASE, AND QUICK TO TYPE (6 to 10 characters max, e.g. 'QP-SOLDER', 'QP-WORK1', 'QP-PCB', 'QP-DEMO', 'QP-KICK'). Hundreds of students will need to type this code in seconds on their phones for attendance.\n"
    "4. Event Description: Write an engaging, clear 2-3 sentence description suitable for marketing and operations approval.\n"
    "5. Location: Default to 'IEEE Project Space (Jacobs Hall 4309)' if not specified by the user.\n"
    "6. Event Date: Format clearly (e.g. 'Wednesday, November 12, 2026').\n"
    "7. Start Time & End Time: Standard format (e.g. '6:00 PM' and '8:00 PM').\n"
    "8. Flyers Needed: 'No' unless the user asks for physical posters/flyers.\n"
    "9. Graphics Needed: 'Yes (Digital graphics for Instagram, Discord banner, and website)' unless user specifies otherwise.\n"
    "10. Photography Needed: 'Yes' for major workshops/demos/showcase, otherwise 'No'.\n"
    "11. Required Logos: Must always include 'IEEE'. If food, pizza, snacks, boba, or funding is mentioned, 'AS' is strictly required (e.g. 'IEEE, AS'). Also include any co-hosts mentioned (e.g. HKN, TESC, PIB, TNT, SWE).\n"
    "12. Expected Attendance: Provide a reasonable attendee count estimate (e.g. '40 attendees').\n\n"
    "OUTPUT REQUIREMENT:\n"
    "Return ONLY a valid JSON object with the following exact keys:\n"
    "{\n"
    '  "event_name": "string",\n'
    '  "event_description": "string",\n'
    '  "event_type": "Projects",\n'
    '  "department": "Projects",\n'
    '  "location": "string",\n'
    '  "event_date": "string",\n'
    '  "start_time": "string",\n'
    '  "end_time": "string",\n'
    '  "event_code": "string",\n'
    '  "flyers_needed": "string",\n'
    '  "graphics_needed": "string",\n'
    '  "photography_needed": "string",\n'
    '  "required_logos": "string",\n'
    '  "expected_attendance": "string"\n'
    "}"
)


def fallback_event_parser(user_prompt: str) -> Dict[str, str]:
    """Fallback generator in case Gemini API is unreachable or not configured."""
    year = datetime.now().year
    prompt_lower = user_prompt.lower()

    # Determine event code
    code = f"QP-EVT-{year}"
    if "solder" in prompt_lower:
        code = f"QP-SOLDER"
    elif "workathon" in prompt_lower or "work" in prompt_lower:
        code = f"QP-WORK"
    elif "kickoff" in prompt_lower:
        code = f"QP-KICK"
    elif "showcase" in prompt_lower or "demo" in prompt_lower:
        code = f"QP-DEMO"
    elif "pcb" in prompt_lower:
        code = f"QP-PCB"

    # Check for food / AS logo requirement
    has_food = any(w in prompt_lower for w in ("food", "pizza", "snack", "boba", "as funding", "budget", "eat"))
    logos = "IEEE, AS" if has_food else "IEEE"

    # Extract location if mentioned
    loc = "IEEE Project Space (Jacobs Hall 4309)"
    if "jacobs" in prompt_lower:
        loc = "Jacobs Hall 4309"
    elif "ebu" in prompt_lower:
        loc = "EBU-1"
    elif "warren" in prompt_lower:
        loc = "Warren Mall"

    return {
        "event_name": user_prompt.split(",")[0].strip().title() or "QP Technical Event",
        "event_description": f"IEEE Quarterly Projects hands-on session: {user_prompt.strip()}",
        "event_type": "Projects",
        "department": "Projects",
        "location": loc,
        "event_date": datetime.now().strftime("%A, %B %d, %Y"),
        "start_time": "6:00 PM",
        "end_time": "8:00 PM",
        "event_code": code.upper()[:10],
        "flyers_needed": "No",
        "graphics_needed": "Yes (Instagram 1:1, Discord banner)",
        "photography_needed": "Yes" if "showcase" in prompt_lower or "kickoff" in prompt_lower else "No",
        "required_logos": logos,
        "expected_attendance": "35-45 attendees",
    }


async def generate_event_details(user_prompt: str) -> Dict[str, str]:
    """Generate event request data using Gemini model cascade with JSON parsing."""
    client = get_gemini_client()
    if not client:
        return fallback_event_parser(user_prompt)

    candidate_models = [config.GEMINI_MODEL, "gemini-3.5-flash-lite", "gemini-3.8-flash"]

    for model_name in candidate_models:
        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=[f"Event Brief from QP Chair:\n{user_prompt}"],
                config=types.GenerateContentConfig(
                    system_instruction=EVENT_SYSTEM_INSTRUCTION,
                    temperature=0.3,
                    response_mime_type="application/json",
                ),
            )
            if response.text:
                text = response.text.strip()
                # Strip markdown code blocks if present
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\n?", "", text)
                    text = re.sub(r"\n?```$", "", text)
                data = json.loads(text)
                # Ensure all required keys exist
                required_keys = [
                    "event_name", "event_description", "event_type", "department",
                    "location", "event_date", "start_time", "end_time", "event_code",
                    "flyers_needed", "graphics_needed", "photography_needed",
                    "required_logos", "expected_attendance",
                ]
                for k in required_keys:
                    if k not in data or not data[k]:
                        data[k] = "N/A"
                # Keep event code concise (max 10 chars, uppercase)
                data["event_code"] = re.sub(r"[^A-Z0-9-]", "", str(data["event_code"]).upper())[:10]
                return data
        except Exception as e:
            print(f"⚠️ Gemini event generation error on {model_name}: {e}")
            continue

    return fallback_event_parser(user_prompt)


def build_event_embed(data: Dict[str, str], submitter: discord.Member) -> discord.Embed:
    """Build a clean Discord embed displaying the event request."""
    embed = discord.Embed(
        title=f"📋 Event Request: {data.get('event_name', 'QP Event')}",
        description=data.get("event_description", ""),
        color=discord.Color.blue(),
        timestamp=datetime.now(),
    )
    embed.add_field(name="🏷️ Event Code", value=f"`{data.get('event_code', 'QP-EVENT')}`", inline=True)
    embed.add_field(name="📂 Department / Type", value=f"{data.get('department', 'Projects')} / {data.get('event_type', 'Projects')}", inline=True)
    embed.add_field(name="👥 Expected Attendance", value=data.get("expected_attendance", "N/A"), inline=True)

    time_str = f"{data.get('start_time', 'N/A')} – {data.get('end_time', 'N/A')}"
    embed.add_field(name="📅 Date & Time", value=f"{data.get('event_date', 'N/A')}\n⏰ {time_str}", inline=True)
    embed.add_field(name="📍 Location", value=data.get("location", "N/A"), inline=True)
    embed.add_field(name="🎨 Required Logos", value=f"`{data.get('required_logos', 'IEEE')}`", inline=True)

    marketing = (
        f"• **Flyers:** {data.get('flyers_needed', 'No')}\n"
        f"• **Graphics:** {data.get('graphics_needed', 'No')}\n"
        f"• **Photography:** {data.get('photography_needed', 'No')}"
    )
    embed.add_field(name="📢 Media & Marketing", value=marketing, inline=False)
    embed.set_footer(text=f"Requested by {submitter.display_name} • Operations Event Pipeline")
    return embed


def build_copy_paste_block(data: Dict[str, str]) -> str:
    """Format key-value text ready to copy-paste into the Vice Chair's Google Form."""
    return (
        "```text\n"
        f"Event Name: {data.get('event_name', '')}\n"
        f"Event Description: {data.get('event_description', '')}\n"
        f"Event Type: {data.get('event_type', 'Projects')}\n"
        f"Department: {data.get('department', 'Projects')}\n"
        f"Location: {data.get('location', '')}\n"
        f"Event Date: {data.get('event_date', '')}\n"
        f"Start time: {data.get('start_time', '')}\n"
        f"End time: {data.get('end_time', '')}\n"
        f"Event code: {data.get('event_code', '')}\n"
        f"Flyers Needed: {data.get('flyers_needed', 'No')}\n"
        f"Graphics Needed: {data.get('graphics_needed', 'No')}\n"
        f"Photography Needed: {data.get('photography_needed', 'No')}\n"
        f"Required Logos: {data.get('required_logos', 'IEEE')}\n"
        f"Expected Attendance: {data.get('expected_attendance', '')}\n"
        "```"
    )


class EventRequestEditModal(discord.ui.Modal, title="Edit Event Request Details"):
    """Modal to let the QP Chair quickly tweak primary fields."""
    def __init__(self, data: Dict[str, str], view: "EventRequestPreviewView"):
        super().__init__()
        self.data = data
        self.preview_view = view

        self.name_input = discord.ui.TextInput(
            label="Event Name",
            default=data.get("event_name", ""),
            max_length=100,
            required=True,
        )
        self.code_input = discord.ui.TextInput(
            label="Event Code (Short & Quick to Type)",
            default=data.get("event_code", ""),
            max_length=12,
            required=True,
        )
        self.loc_input = discord.ui.TextInput(
            label="Location",
            default=data.get("location", ""),
            max_length=100,
            required=True,
        )
        self.time_input = discord.ui.TextInput(
            label="Date & Time (e.g. Nov 12 | 6:00 PM - 8:00 PM)",
            default=f"{data.get('event_date', '')} | {data.get('start_time', '')} - {data.get('end_time', '')}",
            max_length=100,
            required=True,
        )
        self.att_input = discord.ui.TextInput(
            label="Expected Attendance",
            default=data.get("expected_attendance", ""),
            max_length=40,
            required=True,
        )

        self.add_item(self.name_input)
        self.add_item(self.code_input)
        self.add_item(self.loc_input)
        self.add_item(self.time_input)
        self.add_item(self.att_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.data["event_name"] = self.name_input.value.strip()
        self.data["event_code"] = self.code_input.value.strip().upper()[:10]
        self.data["location"] = self.loc_input.value.strip()
        self.data["expected_attendance"] = self.att_input.value.strip()

        # Parse date and times if pipe is present
        time_val = self.time_input.value.strip()
        if "|" in time_val:
            parts = time_val.split("|", 1)
            self.data["event_date"] = parts[0].strip()
            if "-" in parts[1]:
                t_parts = parts[1].split("-", 1)
                self.data["start_time"] = t_parts[0].strip()
                self.data["end_time"] = t_parts[1].strip()

        embed = build_event_embed(self.data, interaction.user)
        copy_text = build_copy_paste_block(self.data)
        content = (
            "📋 **Event Request Draft (Updated)**\n"
            "Review the generated details below. You can copy the code block directly into the Operations form, or click **Publish to #event-requests**."
        )

        await interaction.response.edit_message(
            content=f"{content}\n\n**Copy-Paste Block for Google Form:**\n{copy_text}",
            embed=embed,
            view=self.preview_view,
        )


class EventRequestPreviewView(discord.ui.View):
    """Interactive preview allowing the QP Chair to review, edit, or publish the event request."""
    def __init__(self, data: Dict[str, str], submitter: discord.Member, prompt: str):
        super().__init__(timeout=600)
        self.data = data
        self.submitter = submitter
        self.prompt = prompt

    @discord.ui.button(
        label="Publish to #event-requests",
        style=discord.ButtonStyle.success,
        emoji="🚀",
        row=0,
    )
    async def publish_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ Guild not found.", ephemeral=True)
            return

        target_channel_name = config.EVENT_REQUESTS_CHANNEL_NAME.lower()
        target_channel = discord.utils.get(guild.text_channels, name=target_channel_name)

        # If channel doesn't exist, try to create it
        if not target_channel:
            try:
                target_channel = await guild.create_text_channel(
                    name=target_channel_name,
                    topic="Official event requests pipeline for IEEE Vice Chair of Operations.",
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"⚠️ Could not find or create `#{target_channel_name}`: {e}",
                    ephemeral=True,
                )
                return

        embed = build_event_embed(self.data, self.submitter)
        copy_text = build_copy_paste_block(self.data)

        # Send public record to #event-requests
        posted_msg = await target_channel.send(
            content=(
                f"📌 **New Event Request Submitted by {self.submitter.mention}**\n\n"
                f"**Copy-Paste Block for Vice Chair of Operations:**\n{copy_text}"
            ),
            embed=embed,
        )

        # Disable buttons on ephemeral message
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=f"✅ **Event request published successfully to {target_channel.mention}!**\n[Jump to Request]({posted_msg.jump_url})",
            embed=embed,
            view=self,
        )

    @discord.ui.button(
        label="Edit Details",
        style=discord.ButtonStyle.primary,
        emoji="✏️",
        row=0,
    )
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EventRequestEditModal(self.data, self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Regenerate",
        style=discord.ButtonStyle.secondary,
        emoji="🔄",
        row=0,
    )
    async def regenerate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.data = await generate_event_details(self.prompt)
        embed = build_event_embed(self.data, self.submitter)
        copy_text = build_copy_paste_block(self.data)
        content = (
            "📋 **Event Request Draft (Regenerated)**\n"
            "Review the generated details below. You can copy the code block directly into the Operations form, or click **Publish to #event-requests**."
        )
        await interaction.edit_original_response(
            content=f"{content}\n\n**Copy-Paste Block for Google Form:**\n{copy_text}",
            embed=embed,
            view=self,
        )

    @discord.ui.button(
        label="Dismiss",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        row=0,
    )
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="🗑️ *Event request draft dismissed.*",
            embed=None,
            view=None,
        )


class EventRequestsCog(commands.Cog):
    """Cog providing the /request-event command for the QP Chair."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="request-event",
        description="Draft and generate an IEEE event request package for the Vice Chair of Operations.",
    )
    @app_commands.describe(
        prompt="Brief details about the event (e.g. 'Soldering workshop next Wednesday 6-8pm in Jacobs Hall with pizza')"
    )
    async def request_event_command(self, interaction: discord.Interaction, prompt: str):
        # Enforce QP Chair role or Administrator permission
        if not isinstance(interaction.user, discord.Member) or not is_qp_chair_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only the **{config.STAFF_ROLE_NAME}** or Server Administrators can use `/request-event`.",
                ephemeral=True,
            )
            return

        # Defer ephemerally while Gemini drafts the fields
        await interaction.response.defer(ephemeral=True)

        data = await generate_event_details(prompt.strip())
        embed = build_event_embed(data, interaction.user)
        copy_text = build_copy_paste_block(data)

        view = EventRequestPreviewView(data, interaction.user, prompt.strip())
        content = (
            "📋 **Event Request Draft Generated!**\n"
            "Review the generated fields below. You can copy the code block directly into the Vice Chair's Google Form, "
            "edit any field using **Edit Details**, or click **Publish to #event-requests**."
        )

        await interaction.followup.send(
            content=f"{content}\n\n**Copy-Paste Block for Google Form:**\n{copy_text}",
            embed=embed,
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(EventRequestsCog(bot))
