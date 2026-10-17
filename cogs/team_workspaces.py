import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from typing import List
import config
import database
from cogs.hardware_tickets import is_staff_or_admin
from cogs.team_assignment import TEAM_ROLE_PATTERN


class TeamWorkspacesCog(commands.Cog):
    """Commands for generating quarterly team workspaces and viewing team directories."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup-team-workspaces",
        description="Auto-configure text and voice categories and channels for a new quarter (Admin only).",
    )
    @app_commands.describe(
        season="Quarter season (Fall, Winter, Spring, Summer)",
        year="Year of the quarter (e.g. 2026)",
        num_teams="Total number of teams to configure (e.g. 28)",
    )
    @app_commands.choices(
        season=[
            app_commands.Choice(name="Fall", value="Fall"),
            app_commands.Choice(name="Winter", value="Winter"),
            app_commands.Choice(name="Spring", value="Spring"),
            app_commands.Choice(name="Summer", value="Summer"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_team_workspaces(
        self,
        interaction: discord.Interaction,
        season: app_commands.Choice[str],
        year: int,
        num_teams: int = 28,
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only Administrators or Leadership roles ({', '.join(config.STAFF_ROLES)}) can run this command.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ Must be run in a server.", ephemeral=True)
            return

        if num_teams < 1 or num_teams > 50:
            await interaction.response.send_message(
                "❌ Number of teams must be between 1 and 50 (Discord limits categories to 50 channels).",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        season_name = season.value
        text_category_name = f"{season_name} {year}"
        voice_category_name = f"{season_name} {year} VC"

        # 1. Locate or create Text category
        text_category = discord.utils.find(lambda c: c.name == text_category_name, guild.categories)
        if text_category is None:
            text_category = await guild.create_category(
                name=text_category_name,
                reason=f"Quarterly setup for {text_category_name}",
            )

        # 2. Locate or create Voice category
        voice_category = discord.utils.find(lambda c: c.name == voice_category_name, guild.categories)
        if voice_category is None:
            voice_category = await guild.create_category(
                name=voice_category_name,
                reason=f"Quarterly setup for {voice_category_name}",
            )

        # 3. Locate Leadership Roles (Mentor, QP Chair, Officer)
        leadership_roles: List[discord.Role] = []
        for role_name in config.STAFF_ROLES:
            found = discord.utils.find(lambda r: r.name.lower() == role_name.lower(), guild.roles)
            if found:
                leadership_roles.append(found)

        created_text = 0
        created_voice = 0

        # 4. Generate channels for Teams 1 to num_teams
        for team_num in range(1, num_teams + 1):
            role_name = f"Team {team_num}"
            team_role = discord.utils.find(lambda r: r.name.lower() == role_name.lower(), guild.roles)
            if team_role is None:
                team_role = await guild.create_role(
                    name=role_name,
                    reason=f"Auto-created {role_name} for {season_name} {year}",
                )

            # Build permission overwrites for Text Channel
            text_overwrites = {
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
            for leader_role in leadership_roles:
                text_overwrites[leader_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                    manage_messages=True,
                )

            # Check if text channel already exists in this category
            text_channel_name = f"team-{team_num}"
            existing_text = discord.utils.find(
                lambda c: c.name == text_channel_name and c.category_id == text_category.id,
                guild.text_channels,
            )

            if existing_text is None:
                text_chan = await guild.create_text_channel(
                    name=text_channel_name,
                    category=text_category,
                    overwrites=text_overwrites,
                    topic=f"{season_name} {year} private workspace for Team {team_num}",
                )

                embed = discord.Embed(
                    title=f"🚀 Welcome to your Team {team_num} Workspace!",
                    description=(
                        f"Welcome {team_role.mention} to **IEEE Quarterly Projects ({season_name} {year})**!\n\n"
                        f"This private channel is accessible to your team and the **{', '.join(r.name for r in leadership_roles) or 'Leadership'}** staff.\n\n"
                        "**Quick Commands:**\n"
                        "• `/budget`: Check your remaining hardware budget ($50 base + $11/IEEE member).\n"
                        "• `/inventory`: Browse parts and tools currently in stock in the IEEE Lab.\n"
                        "• `/whereis`: Check where components are or which team borrowed them."
                    ),
                    color=discord.Color.blue(),
                )
                embed.set_footer(text=f"IEEE Quarterly Projects • {season_name} {year}")
                await text_chan.send(embed=embed)
                created_text += 1

            # Build permission overwrites for Voice Channel
            voice_channel_name = f"Team {team_num} VC"
            existing_voice = discord.utils.find(
                lambda c: c.name == voice_channel_name and c.category_id == voice_category.id,
                guild.voice_channels,
            )

            if existing_voice is None:
                voice_overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
                    team_role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, manage_channels=True),
                }
                for leader_role in leadership_roles:
                    voice_overwrites[leader_role] = discord.PermissionOverwrite(
                        view_channel=True, connect=True, speak=True
                    )

                await guild.create_voice_channel(
                    name=voice_channel_name,
                    category=voice_category,
                    overwrites=voice_overwrites,
                )
                created_voice += 1

            await asyncio.sleep(0.3)  # Rate limit safety

        leadership_names = ", ".join(r.name for r in leadership_roles) or "None configured"
        await interaction.followup.send(
            f"✅ **{season_name} {year} Setup Complete!**\n\n"
            f"• **Text Category**: `{text_category_name}` ({created_text} text channels created)\n"
            f"• **Voice Category**: `{voice_category_name}` ({created_voice} voice channels created)\n"
            f"• **Access Granted To**: Respective `Team X` roles, plus `{leadership_names}`.",
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
                f"• {loan['quantity']}x **{loan['item_name']}** (<@{loan['borrower_id']}> on `{loan['borrowed_at']}`)"
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
