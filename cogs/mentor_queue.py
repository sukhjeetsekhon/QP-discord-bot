import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
import config
import database
from cogs.hardware_tickets import is_staff_or_admin
from cogs.team_assignment import TEAM_ROLE_PATTERN


class MentorCardView(discord.ui.View):
    """Buttons on individual mentor request cards (Claim / Resolve / Cancel)."""
    def __init__(self, request_id: int):
        super().__init__(timeout=None)
        self.request_id = request_id

        # Set dynamic custom IDs for persistence
        self.claim_btn.custom_id = f"qp:mentor_claim:{request_id}"
        self.resolve_btn.custom_id = f"qp:mentor_resolve:{request_id}"
        self.cancel_btn.custom_id = f"qp:mentor_cancel:{request_id}"

    @discord.ui.button(
        label="Claim Request",
        style=discord.ButtonStyle.success,
        emoji="🏃",
        row=0,
    )
    async def claim_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only members with the **{config.STAFF_ROLE_NAME}** role can claim mentor requests.",
                ephemeral=True,
            )
            return

        req = database.get_mentor_request(self.request_id)
        if not req or req["status"] != "waiting":
            await interaction.response.send_message(
                "⚠️ This request has already been claimed or resolved.", ephemeral=True
            )
            return

        database.claim_mentor_request(self.request_id, interaction.user.id)

        # Update embed
        embed = interaction.message.embeds[0]
        embed.title = f"🟢 Mentor Request #{self.request_id} — In Progress"
        embed.color = discord.Color.gold()
        embed.add_field(
            name="Mentor Assisting",
            value=f"{interaction.user.mention} is on their way!",
            inline=False,
        )

        # Update buttons: disable claim, show resolve
        self.claim_btn.disabled = True
        self.cancel_btn.disabled = True
        self.resolve_btn.disabled = False

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(
            f"🏃 **{interaction.user.mention}** claimed this request and is heading to **{req['location']}** for **Team {req['team_number']}**!",
        )

    @discord.ui.button(
        label="Mark Resolved",
        style=discord.ButtonStyle.primary,
        emoji="✅",
        disabled=True,
        row=0,
    )
    async def resolve_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only members with the **{config.STAFF_ROLE_NAME}** role can resolve mentor requests.",
                ephemeral=True,
            )
            return

        database.resolve_mentor_request(self.request_id)

        embed = interaction.message.embeds[0]
        embed.title = f"✅ Mentor Request #{self.request_id} — Resolved"
        embed.color = discord.Color.green()
        embed.set_footer(text=f"Resolved by {interaction.user.display_name} at {datetime.now().strftime('%I:%M %p')}")

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message("✅ Request marked as resolved!", ephemeral=True)
        self.stop()

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        emoji="❌",
        row=0,
    )
    async def cancel_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        req = database.get_mentor_request(self.request_id)
        if not req:
            await interaction.response.send_message("❌ Request not found.", ephemeral=True)
            return

        is_staff = isinstance(interaction.user, discord.Member) and is_staff_or_admin(interaction.user)
        is_requester = interaction.user.id == req["requester_id"]

        if not (is_staff or is_requester):
            await interaction.response.send_message(
                "❌ Only the original requester or a QP Chair can cancel this request.",
                ephemeral=True,
            )
            return

        database.cancel_mentor_request(self.request_id)

        embed = interaction.message.embeds[0]
        embed.title = f"❌ Mentor Request #{self.request_id} — Cancelled"
        embed.color = discord.Color.light_grey()

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message("Request cancelled.", ephemeral=True)
        self.stop()


class MentorRequestModal(discord.ui.Modal, title="Call a Mentor / Help"):
    def __init__(self, default_team: str = ""):
        super().__init__()
        self.team_input = discord.ui.TextInput(
            label=f"Team Number (1 - {config.MAX_TEAMS})",
            placeholder="e.g. 14",
            default=default_team,
            min_length=1,
            max_length=3,
            required=True,
        )
        self.location_input = discord.ui.TextInput(
            label="Lab Bench / Location",
            placeholder="e.g. Bench 4, Soldering Station, 3D Printer Area",
            min_length=2,
            max_length=50,
            required=True,
        )
        self.issue_input = discord.ui.TextInput(
            label="What do you need help with?",
            placeholder="e.g. ESP32 I2C sensor communication failing, oscilloscope debugging, code compile error",
            style=discord.TextStyle.paragraph,
            min_length=5,
            max_length=400,
            required=True,
        )
        self.add_item(self.team_input)
        self.add_item(self.location_input)
        self.add_item(self.issue_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw_team = self.team_input.value.strip()
        if not raw_team.isdigit() or int(raw_team) < 1 or int(raw_team) > config.MAX_TEAMS:
            await interaction.response.send_message(
                f"❌ Invalid team number. Please enter a number between 1 and {config.MAX_TEAMS}.",
                ephemeral=True,
            )
            return

        team_num = int(raw_team)
        location = self.location_input.value.strip()
        issue = self.issue_input.value.strip()

        req_id = database.create_mentor_request(
            team_number=team_num,
            requester_id=interaction.user.id,
            location=location,
            description=issue,
        )

        guild = interaction.guild
        staff_role = discord.utils.find(lambda r: r.name.lower() == config.STAFF_ROLE_NAME.lower(), guild.roles)
        staff_mention = staff_role.mention if staff_role else f"@{config.STAFF_ROLE_NAME}"

        embed = discord.Embed(
            title=f"🟡 Mentor Request #{req_id} — Waiting for Mentor",
            color=discord.Color.yellow(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="Team", value=f"Team {team_num}", inline=True)
        embed.add_field(name="Requester", value=interaction.user.mention, inline=True)
        embed.add_field(name="Location", value=f"📍 `{location}`", inline=True)
        embed.add_field(name="Issue Description", value=issue, inline=False)
        embed.set_footer(text="QP Chairs: Click 'Claim Request' when heading over")

        view = MentorCardView(req_id)
        msg = await interaction.channel.send(
            content=f"{staff_mention} — New help request for **Team {team_num}**!",
            embed=embed,
            view=view,
        )
        database.set_mentor_request_message_id(req_id, msg.id)

        await interaction.response.send_message(
            f"✅ Mentor request #{req_id} submitted! A mentor has been notified.",
            ephemeral=True,
        )


class MentorQueueSetupView(discord.ui.View):
    """Persistent button in the #mentor-queue channel to call a mentor."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Request Mentor / Help",
        style=discord.ButtonStyle.primary,
        custom_id="qp:mentor_request_btn",
        emoji="🙋",
    )
    async def request_mentor_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        member = interaction.user
        default_team = ""
        if isinstance(member, discord.Member):
            for role in member.roles:
                match = TEAM_ROLE_PATTERN.match(role.name)
                if match:
                    default_team = match.group(1)
                    break

        await interaction.response.send_modal(MentorRequestModal(default_team=default_team))


class MentorQueueCog(commands.Cog):
    """Cog for managing the lab mentor/help queue."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup-mentor-queue",
        description="Post the interactive 'Call a Mentor' panel in this channel (Admin only).",
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_mentor_queue(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only members with the **{config.STAFF_ROLE_NAME}** role or Administrators can run this command.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🙋 IEEE QP Lab Mentor Queue",
            description=(
                "Stuck on an issue in the lab? Need in-person help with debugging, circuits, code, or tools?\n\n"
                "Click **Request Mentor / Help** below, specify your bench location, and a **QP Chair / Mentor** "
                "will head over to assist your team!"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="IEEE Quarterly Projects • Mentorship Queue")

        view = MentorQueueSetupView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Mentor queue panel posted!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MentorQueueCog(bot))
