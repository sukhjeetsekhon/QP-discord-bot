import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import config
import database
from cogs.hardware_tickets import is_staff_or_admin
from cogs.team_assignment import TEAM_ROLE_PATTERN


class TeamWorkspacesCog(commands.Cog):
    """Commands for generating private team workspaces and viewing team directories."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup-team-workspaces",
        description="Auto-generate private text & voice workspaces for all 28 teams (Admin only).",
    )
    @app_commands.describe(
        start_team="First team number to create (default: 1)",
        end_team=f"Last team number to create (default: {config.MAX_TEAMS})",
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_team_workspaces(
        self,
        interaction: discord.Interaction,
        start_team: int = 1,
        end_team: int = config.MAX_TEAMS,
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only members with the **{config.STAFF_ROLE_NAME}** role or Administrators can run this command.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ Must be run in a server.", ephemeral=True)
            return

        if start_team < 1 or end_team > config.MAX_TEAMS or start_team > end_team:
            await interaction.response.send_message(
                f"❌ Invalid team range. Must be between 1 and {config.MAX_TEAMS}.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        staff_role = discord.utils.find(
            lambda r: r.name.lower() == config.STAFF_ROLE_NAME.lower(),
            guild.roles,
        )

        created_count = 0

        # We partition teams into categories to respect Discord's 50-channels-per-category limit
        for team_num in range(start_team, end_team + 1):
            category_name = "IEEE QP Teams (1-14)" if team_num <= 14 else "IEEE QP Teams (15-28)"
            category = discord.utils.find(lambda c: c.name == category_name, guild.categories)
            if category is None:
                category = await guild.create_category(
                    name=category_name,
                    reason="Auto-created team workspace category by QP Bot",
                )

            # Ensure Team role exists
            role_name = f"Team {team_num}"
            team_role = discord.utils.find(lambda r: r.name.lower() == role_name.lower(), guild.roles)
            if team_role is None:
                team_role = await guild.create_role(name=role_name, reason="Auto-created team role")

            text_channel_name = f"team-{team_num}"
            voice_channel_name = f"🔊 Team {team_num} Lab"

            # Check if text channel already exists
            existing_text = discord.utils.find(
                lambda c: c.name == text_channel_name and c.category_id == category.id,
                guild.text_channels,
            )

            if existing_text is None:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    team_role: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        attach_files=True,
                        embed_links=True,
                    ),
                    guild.me: discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        manage_channels=True,
                        manage_messages=True,
                    ),
                }
                if staff_role:
                    overwrites[staff_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        attach_files=True,
                        embed_links=True,
                        manage_messages=True,
                    )

                text_chan = await guild.create_text_channel(
                    name=text_channel_name,
                    category=category,
                    overwrites=overwrites,
                    topic=f"Private workspace for {role_name}",
                )

                # Post welcome embed in text channel
                embed = discord.Embed(
                    title=f"🚀 Welcome to your Team {team_num} Workspace!",
                    description=(
                        f"This is the private channel for {team_role.mention} and the {config.STAFF_ROLE_NAME} team.\n\n"
                        "• Use this space to coordinate, share schematics, code, and project files.\n"
                        "• Check your remaining budget anytime with `/budget`.\n"
                        "• Check lab parts in stock with `/inventory`."
                    ),
                    color=discord.Color.blue(),
                )
                await text_chan.send(embed=embed)

                # Create voice channel
                voice_overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
                    team_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, manage_channels=True),
                }
                if staff_role:
                    voice_overwrites[staff_role] = discord.PermissionOverwrite(
                        view_channel=True, connect=True, speak=True
                    )

                await guild.create_voice_channel(
                    name=voice_channel_name,
                    category=category,
                    overwrites=voice_overwrites,
                )

                created_count += 1
                await asyncio.sleep(0.5)  # Avoid rate limiting

        await interaction.followup.send(
            f"✅ Successfully provisioned workspaces for **{created_count}** teams (Teams {start_team}–{end_team})!",
            ephemeral=True,
        )

    @app_commands.command(
        name="my-team",
        description="View your team roster, remaining budget, and borrowed lab items.",
    )
    async def my_team(self, interaction: discord.Interaction):
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ Must be run in a server.", ephemeral=True)
            return

        team_roles = [r for r in member.roles if TEAM_ROLE_PATTERN.match(r.name)]
        if not team_roles:
            await interaction.response.send_message(
                "❌ You do not have a Team role yet! Please select your team in `#team-assignment`.",
                ephemeral=True,
            )
            return

        team_role = team_roles[0]
        match = TEAM_ROLE_PATTERN.match(team_role.name)
        team_num = int(match.group(1))

        await self._render_team_info(interaction, team_num, team_role)

    @app_commands.command(
        name="team-info",
        description="Look up a team's roster, budget, and borrowed lab items.",
    )
    @app_commands.describe(team="Team number (1-28)")
    async def team_info(self, interaction: discord.Interaction, team: int):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ Must be run in a server.", ephemeral=True)
            return

        if team < 1 or team > config.MAX_TEAMS:
            await interaction.response.send_message(
                f"❌ Team number must be between 1 and {config.MAX_TEAMS}.", ephemeral=True
            )
            return

        team_role = discord.utils.find(lambda r: r.name.lower() == f"team {team}".lower(), guild.roles)
        await self._render_team_info(interaction, team, team_role)

    async def _render_team_info(
        self,
        interaction: discord.Interaction,
        team_num: int,
        team_role: discord.Role | None,
    ):
        guild = interaction.guild
        members = team_role.members if team_role else []
        roster_text = ", ".join(m.mention for m in members) if members else "No members assigned yet"

        budget = database.get_team_budget(team_num)
        loans = database.get_borrowed_items(team_number=team_num)

        embed = discord.Embed(
            title=f"👥 Team {team_num} Directory & Status",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Teammates", value=roster_text, inline=False)
        embed.add_field(
            name="💰 Hardware Budget",
            value=(
                f"• Allocation: **${budget['total_budget']:.2f}**\n"
                f"• Spent: **${budget['spent']:.2f}**\n"
                f"• Remaining: **${budget['remaining']:.2f}**"
            ),
            inline=True,
        )

        if loans:
            borrowed_text = "\n".join(
                f"• {loan['quantity']}x **{loan['item_name']}** (<@{loan['borrower_id']}>)"
                for loan in loans
            )
        else:
            borrowed_text = "No equipment currently borrowed"

        embed.add_field(name="📦 Borrowed Lab Inventory", value=borrowed_text, inline=True)

        text_chan = discord.utils.find(lambda c: c.name == f"team-{team_num}", guild.text_channels)
        if text_chan:
            embed.add_field(name="Workspace Channel", value=text_chan.mention, inline=False)

        embed.set_footer(text="IEEE Quarterly Projects • Team Directory")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(TeamWorkspacesCog(bot))
