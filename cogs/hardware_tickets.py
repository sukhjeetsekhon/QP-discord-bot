import asyncio
import re
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
import config
import database
from cogs.team_assignment import TEAM_ROLE_PATTERN

REQUEST_CHANNEL_PATTERN = re.compile(r"^request-(\d+)$", re.IGNORECASE)


def is_staff_or_admin(member: discord.Member) -> bool:
    """Check if a member has Mentor, QP Chair, or Officer role, or Administrator permissions."""
    if member.guild_permissions.administrator:
        return True
    staff_names = {r.lower() for r in config.STAFF_ROLES}
    staff_names.add(config.STAFF_ROLE_NAME.lower())
    return any(role.name.lower() in staff_names for role in member.roles)



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

        # Dismiss the ephemeral confirmation prompt first
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass

        self.stop()

        # Send public notice in the channel before deleting
        if interaction.channel:
            await interaction.channel.send("⏳ Closing and deleting this channel in 5 seconds...")

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

        # Acknowledge the interaction and delete the ephemeral confirmation message
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except discord.HTTPException:
            try:
                await interaction.edit_original_response(content="❌ Action cancelled.", view=None)
            except discord.HTTPException:
                pass

        self.stop()


class ApproveHardwareModal(discord.ui.Modal, title="Approve Hardware Request"):
    def __init__(self, default_team: str = ""):
        super().__init__()
        self.item_input = discord.ui.TextInput(
            label="Item Name / Summary",
            placeholder="e.g. ESP32-S3 Dev Board + OLED Display",
            min_length=2,
            max_length=100,
            required=True,
        )
        self.cost_input = discord.ui.TextInput(
            label="Approved Cost in USD ($)",
            placeholder="e.g. 18.50",
            min_length=1,
            max_length=10,
            required=True,
        )
        self.team_input = discord.ui.TextInput(
            label=f"Team Number (1 - {config.MAX_TEAMS})",
            placeholder="e.g. 14",
            default=default_team,
            min_length=1,
            max_length=3,
            required=True,
        )
        self.add_item(self.item_input)
        self.add_item(self.cost_input)
        self.add_item(self.team_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw_cost = self.cost_input.value.strip().replace("$", "")
        try:
            cost = float(raw_cost)
            if cost <= 0:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message(
                f"❌ Invalid cost amount `{self.cost_input.value}`. Please enter a positive dollar amount (e.g. 15.00).",
                ephemeral=True,
            )
            return

        raw_team = self.team_input.value.strip()
        if not raw_team.isdigit() or int(raw_team) < 1 or int(raw_team) > config.MAX_TEAMS:
            await interaction.response.send_message(
                f"❌ Invalid team number `{raw_team}`. Must be between 1 and {config.MAX_TEAMS}.",
                ephemeral=True,
            )
            return

        team_num = int(raw_team)
        item_name = self.item_input.value.strip()

        # Check existing budget
        budget = database.get_team_budget(team_num)
        new_spent = budget["spent"] + cost
        remaining = budget["total_budget"] - new_spent

        # Record in database
        database.add_hardware_purchase(
            ticket_channel_id=interaction.channel_id,
            team_number=team_num,
            requester_id=interaction.user.id,
            item_name=item_name,
            cost=cost,
            approved_by_id=interaction.user.id,
        )

        warning_note = ""
        if remaining < 0:
            warning_note = f"\n⚠️ **Budget Alert**: Team {team_num} is over budget by **${abs(remaining):.2f}**!"

        embed = discord.Embed(
            title="✅ Hardware Request Approved",
            color=discord.Color.green(),
        )
        embed.add_field(name="Item Approved", value=item_name, inline=True)
        embed.add_field(name="Approved Cost", value=f"${cost:.2f}", inline=True)
        embed.add_field(
            name=f"Team {team_num} Budget Summary",
            value=(
                f"• Allocation: **${budget['total_budget']:.2f}**\n"
                f"• Total Spent: **${new_spent:.2f}**\n"
                f"• Remaining: **${remaining:.2f}**{warning_note}"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Approved by {interaction.user.display_name}")

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Request approved and recorded in budget!", ephemeral=True)


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

        # Try to infer team number from channel topic or overwrites
        default_team = ""
        if isinstance(interaction.channel, discord.TextChannel) and interaction.channel.topic:
            match = re.search(r"Team\s+(\d+)", interaction.channel.topic, re.IGNORECASE)
            if match:
                default_team = match.group(1)

        await interaction.response.send_modal(ApproveHardwareModal(default_team=default_team))

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

        database.update_purchase_status(interaction.channel_id, "rejected")

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
        label="Mark Ordered",
        style=discord.ButtonStyle.primary,
        custom_id="qp:ticket_order_btn",
        emoji="📦",
    )
    async def order_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only members with the **{config.STAFF_ROLE_NAME}** role or Administrators can update order status.",
                ephemeral=True,
            )
            return

        database.update_purchase_status(interaction.channel_id, "ordered")

        embed = discord.Embed(
            title="📦 Order Placed",
            description=f"The requested items have been ordered by {interaction.user.mention} and are on the way!",
            color=discord.Color.blue(),
        )
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("Status updated to **Ordered**.", ephemeral=True)

    @discord.ui.button(
        label="Mark Arrived",
        style=discord.ButtonStyle.secondary,
        custom_id="qp:ticket_arrived_btn",
        emoji="📍",
    )
    async def arrived_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only members with the **{config.STAFF_ROLE_NAME}** role or Administrators can update arrival status.",
                ephemeral=True,
            )
            return

        database.update_purchase_status(interaction.channel_id, "arrived")

        embed = discord.Embed(
            title="📍 Parts Arrived — Ready for Pickup!",
            description=(
                "Your hardware has arrived and is ready for pickup in the **IEEE Lab**!\n"
                "Please coordinate with a QP Chair when picking up your components."
            ),
            color=discord.Color.purple(),
        )
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("Status updated to **Arrived**.", ephemeral=True)

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
                match = TEAM_ROLE_PATTERN.match(team_roles[0].name)
                if match:
                    team_num = int(match.group(1))
                    b = database.get_team_budget(team_num)
                    embed.add_field(
                        name="Team Budget",
                        value=f"• Remaining: **${b['remaining']:.2f} / ${b['total_budget']:.2f}**",
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

    @app_commands.command(
        name="budget",
        description="Check remaining hardware budget and purchase history for your team or any team.",
    )
    @app_commands.describe(team="Optional team number (1-28). Leave blank to check your own team.")
    async def budget_cmd(self, interaction: discord.Interaction, team: Optional[int] = None):
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ Must be run in a server.", ephemeral=True)
            return

        # If team not provided, check user's team role
        if team is None:
            team_roles = [r for r in member.roles if TEAM_ROLE_PATTERN.match(r.name)]
            if team_roles:
                match = TEAM_ROLE_PATTERN.match(team_roles[0].name)
                team = int(match.group(1))
            else:
                await interaction.response.send_message(
                    "❌ You are not assigned to a team yet! Please specify a team number (e.g. `/budget team:14`).",
                    ephemeral=True,
                )
                return

        if team < 1 or team > config.MAX_TEAMS:
            await interaction.response.send_message(
                f"❌ Team number must be between 1 and {config.MAX_TEAMS}.", ephemeral=True
            )
            return

        b = database.get_team_budget(team)
        embed = discord.Embed(
            title=f"💰 Team {team} Hardware Budget",
            color=discord.Color.green() if b["remaining"] >= 0 else discord.Color.red(),
        )
        embed.add_field(name="Total Allocation", value=f"${b['total_budget']:.2f}", inline=True)
        embed.add_field(name="Total Spent", value=f"${b['spent']:.2f}", inline=True)
        embed.add_field(name="Remaining Balance", value=f"${b['remaining']:.2f}", inline=True)

        if b["purchases"]:
            history = []
            for p in b["purchases"][:10]:
                status_emoji = {"approved": "✅", "ordered": "📦", "arrived": "📍", "rejected": "❌"}.get(p["status"], "•")
                date_str = p["created_at"][:10] if p["created_at"] else ""
                history.append(f"{status_emoji} **${p['cost']:.2f}** — {p['item_name']} *({p['status'].title()}, {date_str})*")
            embed.add_field(name="Recent Approved Purchases", value="\n".join(history), inline=False)
        else:
            embed.add_field(name="Purchases", value="No hardware purchases approved yet.", inline=False)

        embed.set_footer(text="IEEE Quarterly Projects • Budget Tracking")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="budget-summary",
        description="View an overview of all 28 teams' budgets and program spending (QP Chair only).",
    )
    @app_commands.default_permissions(administrator=True)
    async def budget_summary(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only members with the **{config.STAFF_ROLE_NAME}** role or Administrators can view budget summaries.",
                ephemeral=True,
            )
            return

        summary = database.get_all_budgets_summary()
        total_allocated = sum(r["total_budget"] for r in summary)
        total_spent = sum(r["spent"] for r in summary)
        total_remaining = total_allocated - total_spent

        embed = discord.Embed(
            title="📊 IEEE QP Master Budget Summary",
            description=(
                f"• Total Program Budget: **${total_allocated:.2f}**\n"
                f"• Total Spent Across All Teams: **${total_spent:.2f}**\n"
                f"• Total Remaining: **${total_remaining:.2f}**\n\n"
                "**Team Breakdown:**"
            ),
            color=discord.Color.blue(),
        )

        lines = []
        for r in summary:
            status_indicator = "🔴" if r["remaining"] < 0 else ("🟡" if r["spent"] > 0 else "⚪")
            lines.append(f"{status_indicator} **Team {r['team_number']}**: Spent ${r['spent']:.2f} | Left **${r['remaining']:.2f}**")

        # Split into fields if necessary
        chunk_size = 14
        for i in range(0, len(lines), chunk_size):
            chunk = lines[i:i + chunk_size]
            embed.add_field(
                name=f"Teams {i + 1}–{min(i + chunk_size, len(lines))}",
                value="\n".join(chunk),
                inline=True,
            )

        embed.set_footer(text="IEEE Quarterly Projects • Finance Oversight")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="budget-adjust",
        description="Add, subtract, or set a team's total budget allocation (QP Chair / Leadership only).",
    )
    @app_commands.describe(
        team=f"Team number (1-{config.MAX_TEAMS})",
        action="Action to perform (add, subtract, set)",
        amount="Dollar amount in USD (e.g. 11.00 or 25.00)",
        reason="Optional explanation for adjustment",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Add to budget (+)", value="add"),
            app_commands.Choice(name="Subtract from budget (-)", value="subtract"),
            app_commands.Choice(name="Set exact total budget (=)", value="set"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def budget_adjust(
        self,
        interaction: discord.Interaction,
        team: int,
        action: app_commands.Choice[str],
        amount: float,
        reason: Optional[str] = "Manual adjustment by leadership",
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only Leadership ({', '.join(config.STAFF_ROLES)}) can adjust budgets.",
                ephemeral=True,
            )
            return

        if team < 1 or team > config.MAX_TEAMS:
            await interaction.response.send_message(
                f"❌ Team number must be between 1 and {config.MAX_TEAMS}.", ephemeral=True
            )
            return

        if amount < 0:
            await interaction.response.send_message(
                "❌ Amount must be a positive number. Use the 'Subtract' action to reduce budget.",
                ephemeral=True,
            )
            return

        action_val = action.value
        old_budget = database.get_team_budget(team)

        if action_val == "add":
            updated = database.adjust_team_budget(team, amount)
            action_desc = f"Added **+${amount:.2f}** to budget"
        elif action_val == "subtract":
            updated = database.adjust_team_budget(team, -amount)
            action_desc = f"Subtracted **-${amount:.2f}** from budget"
        else:  # set
            updated = database.set_team_budget(team, amount)
            action_desc = f"Set total budget to **${amount:.2f}**"

        embed = discord.Embed(
            title=f"💵 Team {team} Budget Adjusted",
            description=action_desc,
            color=discord.Color.blue(),
        )
        embed.add_field(name="Previous Allocation", value=f"${old_budget['total_budget']:.2f}", inline=True)
        embed.add_field(name="New Total Allocation", value=f"**${updated['total_budget']:.2f}**", inline=True)
        embed.add_field(name="Remaining Balance", value=f"**${updated['remaining']:.2f}**", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Adjusted by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="budget-ieee-bonus",
        description="Apply $11 bonus per verified IEEE member for a team ($55 base + $11/member).",
    )
    @app_commands.describe(
        team=f"Team number (1-{config.MAX_TEAMS})",
        num_ieee_members="Number of verified IEEE members on this team",
    )
    @app_commands.default_permissions(administrator=True)
    async def budget_ieee_bonus(
        self,
        interaction: discord.Interaction,
        team: int,
        num_ieee_members: int,
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only Leadership ({', '.join(config.STAFF_ROLES)}) can apply IEEE member bonuses.",
                ephemeral=True,
            )
            return

        if team < 1 or team > config.MAX_TEAMS:
            await interaction.response.send_message(
                f"❌ Team number must be between 1 and {config.MAX_TEAMS}.", ephemeral=True
            )
            return

        if num_ieee_members < 0:
            await interaction.response.send_message(
                "❌ Number of IEEE members cannot be negative.", ephemeral=True
            )
            return

        bonus_total = num_ieee_members * config.IEEE_MEMBER_BONUS
        new_total = config.DEFAULT_TEAM_BUDGET + bonus_total
        updated = database.set_team_budget(team, new_total)

        embed = discord.Embed(
            title=f"🎉 IEEE Member Budget Updated — Team {team}",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Verified IEEE Members", value=str(num_ieee_members), inline=True)
        embed.add_field(name="Base Allocation", value=f"${config.DEFAULT_TEAM_BUDGET:.2f}", inline=True)
        embed.add_field(name="IEEE Bonus Added", value=f"+${bonus_total:.2f} (${config.IEEE_MEMBER_BONUS:.2f}/ea)", inline=True)
        embed.add_field(name="New Total Budget", value=f"**${updated['total_budget']:.2f}**", inline=True)
        embed.add_field(name="Spent", value=f"${updated['spent']:.2f}", inline=True)
        embed.add_field(name="Remaining", value=f"**${updated['remaining']:.2f}**", inline=True)
        embed.set_footer(text=f"Verified & applied by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(HardwareTicketsCog(bot))

