import asyncio
import re
import discord
from discord import app_commands
from discord.ext import commands
import config
from cogs.team_assignment import TEAM_ROLE_PATTERN

REQUEST_CHANNEL_PATTERN = re.compile(r"^request-(\d+)$", re.IGNORECASE)


def is_staff_or_admin(member: discord.Member) -> bool:
    """Check if a member has the QP Chair / Staff role or Administrator permissions."""
    if member.guild_permissions.administrator:
        return True
    return any(
        role.name.lower() == config.STAFF_ROLE_NAME.lower()
        for role in member.roles
    )


class TicketCloseConfirmView(discord.ui.View):
    """View to confirm ticket channel deletion."""
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="Confirm Close & Delete",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
    )
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only members with the **{config.STAFF_ROLE_NAME}** role or Administrators can close this ticket.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "⏳ Closing and deleting this channel in 5 seconds..."
        )
        self.stop()
        await asyncio.sleep(5)
        try:
            if isinstance(interaction.channel, discord.TextChannel):
                await interaction.channel.delete(
                    reason=f"Ticket closed by {interaction.user.display_name}"
                )
        except discord.DiscordException as e:
            if interaction.channel:
                await interaction.channel.send(f"⚠️ Failed to delete channel: {e}")

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only members with the **{config.STAFF_ROLE_NAME}** role or Administrators can cancel this action.",
                ephemeral=True,
            )
            return

        await interaction.message.delete()
        self.stop()


class TicketControlView(discord.ui.View):
    """Persistent controls inside request-X channels for review & closure."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Approve Request",
        style=discord.ButtonStyle.success,
        custom_id="qp:ticket_approve_btn",
        emoji="✅",
    )
    async def approve_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only members with the **{config.STAFF_ROLE_NAME}** role or Administrators can approve requests.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="✅ Request Approved",
            description=f"This hardware request was **approved** by {interaction.user.mention}.",
            color=discord.Color.green(),
        )
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message(
            "Status updated to **Approved**.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Reject Request",
        style=discord.ButtonStyle.danger,
        custom_id="qp:ticket_reject_btn",
        emoji="❌",
    )
    async def reject_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only members with the **{config.STAFF_ROLE_NAME}** role or Administrators can reject requests.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="❌ Request Rejected",
            description=f"This hardware request was **rejected** by {interaction.user.mention}.",
            color=discord.Color.red(),
        )
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message(
            "Status updated to **Rejected**.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.secondary,
        custom_id="qp:ticket_close_btn",
        emoji="🔒",
    )
    async def close_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only members with the **{config.STAFF_ROLE_NAME}** role or Administrators can close this ticket.",
                ephemeral=True,
            )
            return

        confirm_view = TicketCloseConfirmView()
        await interaction.response.send_message(
            "⚠️ Are you sure you want to close and delete this ticket channel?",
            view=confirm_view,
            ephemeral=True,
        )


class TicketRequestView(discord.ui.View):
    """Persistent button view displayed in the request setup channel."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Request",
        style=discord.ButtonStyle.success,
        custom_id="qp:ticket_create_btn",
        emoji="📝",
    )
    async def create_ticket_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        guild = interaction.guild
        member = interaction.user

        if not guild or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ This action can only be performed in a server.",
                ephemeral=True,
            )
            return

        # Defer interaction to avoid timeouts during channel creation
        await interaction.response.defer(ephemeral=True)

        # 1. Determine next ticket number dynamically from existing request-X channels
        existing_numbers = []
        for channel in guild.text_channels:
            match = REQUEST_CHANNEL_PATTERN.match(channel.name.lower())
            if match:
                existing_numbers.append(int(match.group(1)))

        next_number = max(existing_numbers) + 1 if existing_numbers else 1
        channel_name = f"request-{next_number}"

        # 2. Locate or create category
        category = discord.utils.find(
            lambda c: c.name.lower() == config.TICKETS_CATEGORY_NAME.lower(),
            guild.categories,
        )

        try:
            if category is None:
                category = await guild.create_category(
                    name=config.TICKETS_CATEGORY_NAME,
                    reason="Auto-created hardware requests category by QP Bot",
                )

            # 3. Setup permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member: discord.PermissionOverwrite(
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

            # Check if requester has a Team role and grant access to teammates
            team_roles = [
                r for r in member.roles if TEAM_ROLE_PATTERN.match(r.name)
            ]
            for team_role in team_roles:
                overwrites[team_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                )

            # Locate QP Chair / Staff role and grant access
            staff_role = discord.utils.find(
                lambda r: r.name.lower() == config.STAFF_ROLE_NAME.lower(),
                guild.roles,
            )
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                    manage_messages=True,
                )

            # 4. Create the channel
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Hardware request for {member.display_name} ({', '.join(r.name for r in team_roles) if team_roles else 'No Team Role'})",
                reason=f"Created ticket channel for {member.display_name}",
            )

            # 5. Send initial welcome and instruction embed
            staff_mention = staff_role.mention if staff_role else f"@{config.STAFF_ROLE_NAME}"
            embed = discord.Embed(
                title=f"🛠️ Hardware Request #{next_number}",
                description=(
                    f"Welcome {member.mention}! Please provide the details of your hardware request below.\n\n"
                    "**Include the following information:**\n"
                    "• **Item Name & Description**\n"
                    "• **Product Link / URL**\n"
                    "• **Quantity & Estimated Total Cost**\n"
                    "• **Reason & Justification** (how it fits into your project)\n\n"
                    f"A member of {staff_mention} will review your request soon."
                ),
                color=discord.Color.gold(),
            )
            if team_roles:
                embed.add_field(
                    name="Team",
                    value=", ".join(r.name for r in team_roles),
                    inline=True,
                )
            embed.set_footer(text="QP Chair Review Panel • IEEE Quarterly Projects")

            controls = TicketControlView()
            await ticket_channel.send(
                content=f"{member.mention} {staff_mention}",
                embed=embed,
                view=controls,
            )

            await interaction.followup.send(
                f"✅ Your hardware request ticket has been created: {ticket_channel.mention}",
                ephemeral=True,
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "⚠️ Bot Permission Error: The bot does not have permissions to manage channels or categories. "
                "Please verify the bot has 'Manage Channels' permission.",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ An error occurred while creating your ticket channel: {e}",
                ephemeral=True,
            )


class HardwareTicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup-tickets",
        description="Post the interactive hardware request ticket panel in this channel.",
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛠️ IEEE QP Hardware Requests",
            description=(
                "Need hardware or components for your Quarterly Project?\n\n"
                "Click the **Request** button below to create a private review ticket channel. "
                "You and your team can discuss your purchase request directly with the **QP Chair** team!"
            ),
            color=discord.Color.green(),
        )
        embed.set_footer(text="IEEE Quarterly Projects • Hardware Procurement")

        view = TicketRequestView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            "✅ Hardware request panel posted successfully!",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(HardwareTicketsCog(bot))

