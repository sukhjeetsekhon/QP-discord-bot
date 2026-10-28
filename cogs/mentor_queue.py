import asyncio
import re
from datetime import datetime
from typing import List, Optional
import discord
from discord import app_commands
from discord.ext import commands
import config
import database
from cogs.hardware_tickets import is_staff_or_admin
from cogs.team_assignment import TEAM_ROLE_PATTERN

HELP_CHANNEL_PATTERN = re.compile(r"^help-(\d+)$", re.IGNORECASE)


class MentorCloseConfirmView(discord.ui.View):
    """Confirmation prompt before deleting a mentor help channel."""
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="Confirm Close & Delete",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        row=0,
    )
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_message(
            "🔒 Closing and deleting this channel in 3 seconds...", ephemeral=False
        )
        channel = interaction.channel
        if isinstance(channel, discord.TextChannel):
            req = database.get_mentor_request_by_channel(channel.id)
            if req and req["status"] in ("waiting", "claimed"):
                database.resolve_mentor_request(req["id"])

            await asyncio.sleep(3)
            try:
                await channel.delete(
                    reason=f"Mentor help ticket closed by {interaction.user.display_name}"
                )
            except Exception as e:
                print(f"Failed to delete channel: {e}")

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        emoji="❌",
        row=0,
    )
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        await interaction.delete_original_response()


class MentorTicketControlView(discord.ui.View):
    """Persistent controls inside help-X channels for claiming, resolving, and closing."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim Request",
        style=discord.ButtonStyle.success,
        custom_id="qp:mentor_ticket_claim",
        emoji="🏃",
        row=0,
    )
    async def claim_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only Leadership ({', '.join(config.STAFF_ROLES)}) can claim help requests.",
                ephemeral=True,
            )
            return

        req = database.get_mentor_request_by_channel(interaction.channel_id)
        if not req:
            await interaction.response.send_message(
                "⚠️ Could not find a request record associated with this channel.", ephemeral=True
            )
            return

        if req["status"] == "claimed":
            await interaction.response.send_message(
                "⚠️ This request has already been claimed.", ephemeral=True
            )
            return

        if req["status"] == "resolved":
            await interaction.response.send_message(
                "⚠️ This request has already been resolved.", ephemeral=True
            )
            return

        database.claim_mentor_request(req["id"], interaction.user.id)

        # Update the embed in the ticket channel
        if interaction.message and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.gold()
            for i, field in enumerate(embed.fields):
                if field.name == "Status":
                    embed.set_field_at(i, name="Status", value="🟢 In Progress", inline=True)
            if not any(f.name == "Mentor Assisting" for f in embed.fields):
                embed.add_field(name="Mentor Assisting", value=interaction.user.mention, inline=True)

            # Update buttons: claim disabled, resolve and close active
            view = MentorTicketControlView()
            for child in view.children:
                if isinstance(child, discord.ui.Button) and child.custom_id == "qp:mentor_ticket_claim":
                    child.disabled = True
            await interaction.message.edit(embed=embed, view=view)

        await interaction.channel.send(
            f"🏃 **{interaction.user.mention}** has claimed this help request and is now assisting **Team {req['team_number']}**!"
        )
        await interaction.response.send_message("✅ You have claimed this request!", ephemeral=True)

    @discord.ui.button(
        label="Mark Resolved",
        style=discord.ButtonStyle.primary,
        custom_id="qp:mentor_ticket_resolve",
        emoji="✅",
        row=0,
    )
    async def resolve_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        req = database.get_mentor_request_by_channel(interaction.channel_id)
        is_staff = isinstance(interaction.user, discord.Member) and is_staff_or_admin(interaction.user)
        is_requester = req and interaction.user.id == req["requester_id"]

        if not (is_staff or is_requester):
            await interaction.response.send_message(
                f"❌ Only Leadership ({', '.join(config.STAFF_ROLES)}) or the requester can resolve this help request.",
                ephemeral=True,
            )
            return

        if req and req["status"] == "resolved":
            await interaction.response.send_message(
                "⚠️ This request has already been marked as resolved.", ephemeral=True
            )
            return

        if req:
            database.resolve_mentor_request(req["id"])

        if interaction.message and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green()
            for i, field in enumerate(embed.fields):
                if field.name == "Status":
                    embed.set_field_at(i, name="Status", value="✅ Resolved", inline=True)
            embed.set_footer(
                text=f"Resolved by {interaction.user.display_name} at {datetime.now().strftime('%I:%M %p')}"
            )

            view = MentorTicketControlView()
            for child in view.children:
                if isinstance(child, discord.ui.Button):
                    if child.custom_id in ("qp:mentor_ticket_claim", "qp:mentor_ticket_resolve"):
                        child.disabled = True
            await interaction.message.edit(embed=embed, view=view)

        await interaction.channel.send(
            f"✅ This help request has been marked as **Resolved** by {interaction.user.mention}!\n"
            "When you are ready, click **Close Channel 🔒** below to delete this channel."
        )
        await interaction.response.send_message("✅ Request marked as resolved!", ephemeral=True)

    @discord.ui.button(
        label="Close Channel",
        style=discord.ButtonStyle.secondary,
        custom_id="qp:mentor_ticket_close",
        emoji="🔒",
        row=0,
    )
    async def close_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        req = database.get_mentor_request_by_channel(interaction.channel_id)
        is_staff = isinstance(interaction.user, discord.Member) and is_staff_or_admin(interaction.user)
        is_requester = req and interaction.user.id == req["requester_id"]

        is_teammate = False
        if req and isinstance(interaction.user, discord.Member):
            target_role = f"team {req['team_number']}"
            if any(r.name.lower() == target_role for r in interaction.user.roles):
                is_teammate = True

        if not (is_staff or is_requester or is_teammate):
            await interaction.response.send_message(
                "❌ Only Leadership or members of this team can close this channel.",
                ephemeral=True,
            )
            return

        confirm_view = MentorCloseConfirmView()
        await interaction.response.send_message(
            "⚠️ Are you sure you want to close and delete this help channel?",
            view=confirm_view,
            ephemeral=True,
        )


class MentorRequestModal(discord.ui.Modal, title="Request Mentor Help or Feedback"):
    """Modal that collects only the problem description (team number is auto-detected)."""
    def __init__(self, team_number: int, team_role: discord.Role):
        super().__init__()
        self.team_number = team_number
        self.team_role = team_role

        self.issue_input = discord.ui.TextInput(
            label="What do you need help or feedback with?",
            placeholder="Describe your issue, schematic, PCB review, or code debugging...",
            style=discord.TextStyle.paragraph,
            min_length=5,
            max_length=500,
            required=True,
        )
        self.add_item(self.issue_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        member = interaction.user
        if not guild or not isinstance(member, discord.Member):
            await interaction.followup.send(
                "❌ This action can only be performed in a server.", ephemeral=True
            )
            return

        issue = self.issue_input.value.strip()

        # 1. Determine next channel number dynamically starting from 1
        existing_numbers = []
        for channel in guild.text_channels:
            match = HELP_CHANNEL_PATTERN.match(channel.name.lower())
            if match:
                existing_numbers.append(int(match.group(1)))

        next_number = max(existing_numbers) + 1 if existing_numbers else 1
        channel_name = f"help-{next_number}"

        # 2. Locate or create category (default: 'Help Requests')
        category = discord.utils.find(
            lambda c: c.name.lower() == config.MENTOR_CATEGORY_NAME.lower(),
            guild.categories,
        )
        if category is None and isinstance(interaction.channel, discord.TextChannel):
            # If button was clicked inside an existing category, use it
            category = interaction.channel.category

        if category is None:
            try:
                category = await guild.create_category(
                    name=config.MENTOR_CATEGORY_NAME,
                    reason="Auto-created help requests category by QP Bot",
                )
            except Exception as e:
                print(f"Failed to create category {config.MENTOR_CATEGORY_NAME}: {e}")

        # 3. Setup permissions for private channel
        # Visible to: requesting team, requester member, staff roles, and bot
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            self.team_role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
                embed_links=True,
                attach_files=True,
            ),
        }

        staff_mentions: List[str] = []
        for role_name in config.STAFF_ROLES:
            role = discord.utils.find(lambda r: r.name.lower() == role_name.lower(), guild.roles)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                    manage_messages=True,
                )
                staff_mentions.append(role.mention)

        # 4. Create the private text channel
        try:
            help_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Mentor help request for Team {self.team_number} ({member.display_name})",
                reason=f"Created help channel for Team {self.team_number}",
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to create help channel: {e}", ephemeral=True
            )
            return

        # 5. Record request in database with channel_id
        req_id = database.create_mentor_request(
            team_number=self.team_number,
            requester_id=member.id,
            description=issue,
            channel_id=help_channel.id,
            location="Flexible / Remote",
        )

        # 6. Send initial embed and Claim controls inside the new private channel
        mention_str = " ".join(staff_mentions) if staff_mentions else f"@{config.STAFF_ROLE_NAME}"
        embed = discord.Embed(
            title=f"🟡 Mentor Help Request #{next_number} — Team {self.team_number}",
            description=(
                f"Welcome {member.mention} and {self.team_role.mention}!\n\n"
                "A mentor will be with you shortly. Please share any schematics, photos, or code snippets here."
            ),
            color=discord.Color.yellow(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="Team", value=f"Team {self.team_number}", inline=True)
        embed.add_field(name="Requested By", value=member.mention, inline=True)
        embed.add_field(name="Status", value="🟡 Waiting for Mentor", inline=True)
        embed.add_field(name="Help / Feedback Topic", value=issue, inline=False)
        embed.set_footer(text="Mentors & Officers: Click 'Claim Request' below to assist this team!")

        control_view = MentorTicketControlView()
        msg = await help_channel.send(
            content=f"{mention_str} — New help request from **Team {self.team_number}** ({member.mention})!",
            embed=embed,
            view=control_view,
        )
        database.set_mentor_request_message_id(req_id, msg.id)

        # 7. Notify requester ephemerally with link to the new private channel
        await interaction.followup.send(
            f"✅ Help channel created! Please head over to {help_channel.mention} to chat with mentors.",
            ephemeral=True,
        )


class MentorQueueSetupView(discord.ui.View):
    """Persistent button in the #help-tickets / #mentor-queue channel to call a mentor."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Request Mentor Help / Feedback",
        style=discord.ButtonStyle.primary,
        custom_id="qp:mentor_request_btn",
        emoji="🙋",
    )
    async def request_mentor_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        member = interaction.user
        if not isinstance(member, discord.Member) or not interaction.guild:
            await interaction.response.send_message(
                "❌ This action can only be performed in a server.", ephemeral=True
            )
            return

        # Auto-detect member's team role
        team_role = None
        team_num = None
        for role in member.roles:
            match = TEAM_ROLE_PATTERN.match(role.name)
            if match:
                team_num = int(match.group(1))
                team_role = role
                break

        if team_num is None or team_role is None:
            await interaction.response.send_message(
                "❌ You do not have a Team role assigned yet.\n"
                "Please join your team in the **#team-assignment** channel before requesting mentor help!",
                ephemeral=True,
            )
            return

        try:
            await interaction.response.send_modal(
                MentorRequestModal(team_number=team_num, team_role=team_role)
            )
        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"⚠️ Error opening modal: {e}", ephemeral=True)


class MentorQueueCog(commands.Cog):
    """Cog for managing the mentor help and feedback queue."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup-mentor-queue",
        description="Post the interactive 'Request Mentor' panel in this channel (Admin only).",
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_mentor_queue(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only Leadership ({', '.join(config.STAFF_ROLES)}) can run this command.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="🙋 IEEE QP Mentor Help & Feedback Queue",
            description=(
                "Need help or feedback from a mentor? \n\n"
                "• **Schematic & Hardware Reviews**: Get a second pair of eyes on your wiring, PCB, or components.\n"
                "• **Debugging Assistance**: Stuck on embedded firmware, sensor buses (I2C/SPI), or code logic?\n"
                "• **Project Guidance**: General questions on design, procurement, or manufacturing.\n\n"
                "Click **Request Mentor Help / Feedback** below to open a private help channel with our mentors!"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="IEEE Quarterly Projects • Mentorship Queue")

        view = MentorQueueSetupView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.followup.send("✅ Mentor queue panel posted!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MentorQueueCog(bot))
