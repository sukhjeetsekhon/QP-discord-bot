import re
import discord
from discord import app_commands
from discord.ext import commands
import config

TEAM_ROLE_PATTERN = re.compile(r"^Team\s+(\d+)$", re.IGNORECASE)


class TeamNumberModal(discord.ui.Modal, title="Select Your Team"):
    def __init__(self):
        super().__init__()
        self.team_input = discord.ui.TextInput(
            label=f"Team Number (1 - {config.MAX_TEAMS})",
            placeholder="e.g. 24",
            min_length=1,
            max_length=4,
            required=True,
        )
        self.add_item(self.team_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw_val = self.team_input.value.strip()

        # Validate integer
        if not raw_val.isdigit():
            await interaction.response.send_message(
                f"❌ Invalid input: `{raw_val}` is not a valid number. Please enter a number between 1 and {config.MAX_TEAMS}.",
                ephemeral=True,
            )
            return

        team_num = int(raw_val)
        if team_num < 1 or team_num > config.MAX_TEAMS:
            await interaction.response.send_message(
                f"❌ Team number `{team_num}` is out of range. Please enter a number between 1 and {config.MAX_TEAMS}.",
                ephemeral=True,
            )
            return

        target_role_name = f"Team {team_num}"
        member = interaction.user
        guild = interaction.guild

        if not isinstance(member, discord.Member) or guild is None:
            await interaction.response.send_message(
                "❌ This action can only be performed in a server.",
                ephemeral=True,
            )
            return

        # Find any current Team roles the member has
        current_team_roles = [
            role for role in member.roles if TEAM_ROLE_PATTERN.match(role.name)
        ]

        # Check if already in the target team
        if any(role.name.lower() == target_role_name.lower() for role in current_team_roles):
            await interaction.response.send_message(
                f"ℹ️ You already have the **{target_role_name}** role!",
                ephemeral=True,
            )
            return

        # Locate or auto-create target role
        target_role = discord.utils.find(
            lambda r: r.name.lower() == target_role_name.lower(),
            guild.roles,
        )

        try:
            if target_role is None:
                target_role = await guild.create_role(
                    name=target_role_name,
                    reason=f"Auto-created by QP Bot on request from {member.display_name}",
                )

            # Remove previous team roles (single team rule)
            removed_names = []
            if current_team_roles:
                for old_role in current_team_roles:
                    await member.remove_roles(
                        old_role,
                        reason="Swapped team via QP Bot team assignment",
                    )
                    removed_names.append(old_role.name)

            # Assign new team role
            await member.add_roles(
                target_role,
                reason="Assigned team via QP Bot team assignment",
            )

            if removed_names:
                msg = (
                    f"✅ You have been removed from **{', '.join(removed_names)}** "
                    f"and assigned the **{target_role.name}** role!"
                )
            else:
                msg = f"✅ You have been assigned the **{target_role.name}** role!"

            await interaction.response.send_message(msg, ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ Bot Permission Error: The bot does not have sufficient permissions to manage roles, "
                "or the bot's role is positioned below the team roles in the server role hierarchy. "
                "Please notify a QP Chair / Admin.",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.response.send_message(
                f"⚠️ An unexpected error occurred while assigning your role: {e}",
                ephemeral=True,
            )


class TeamAssignmentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Join Team",
        style=discord.ButtonStyle.primary,
        custom_id="qp:team_assignment_btn",
        emoji="👥",
    )
    async def join_team_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(TeamNumberModal())


class TeamAssignmentCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup-team-roles",
        description="Post the interactive team assignment panel in this channel.",
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_team_roles(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👥 IEEE QP Team Role Assignment",
            description=(
                "Welcome to IEEE Quarterly Projects!\n\n"
                f"Click the button below and enter your team number (**1 – {config.MAX_TEAMS}**) "
                "to receive your team role. \n\n"
                "• Members can only belong to **one team** at a time.\n"
                "• Entering a new team number will automatically replace your previous team role."
            ),
            color=discord.Color.blue(),
        )
        embed.set_footer(text="IEEE Quarterly Projects • Role Assignment")

        view = TeamAssignmentView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            "✅ Team assignment panel posted successfully!",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TeamAssignmentCog(bot))

