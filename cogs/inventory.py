import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import config
import database
from cogs.hardware_tickets import is_staff_or_admin
from cogs.team_assignment import TEAM_ROLE_PATTERN


class InventoryCog(commands.Cog):
    """Commands for managing IEEE QP lab inventory, tracking item locations, and timestamped checkouts/returns."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="inventory-add",
        description="Add a new item to lab inventory or increase stock (Leadership only).",
    )
    @app_commands.describe(
        name="Name of the component or tool (e.g. ESP32-WROOM, SG90 Servo)",
        category="Category (e.g. Microcontrollers, Sensors, Actuators, Tools, Power)",
        quantity="Number of units to add to stock",
        location="Physical location in lab (e.g. Cabinet A - Bin 3)",
    )
    @app_commands.default_permissions(administrator=True)
    async def inventory_add(
        self,
        interaction: discord.Interaction,
        name: str,
        category: str,
        quantity: int = 1,
        location: str = "IEEE Lab",
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only Leadership ({', '.join(config.STAFF_ROLES)}) can manage inventory.",
                ephemeral=True,
            )
            return

        if quantity <= 0:
            await interaction.response.send_message(
                "❌ Quantity must be at least 1.", ephemeral=True
            )
            return

        item = database.add_or_update_inventory_item(name, category, quantity, location)
        embed = discord.Embed(
            title="📦 Inventory Updated",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Item", value=item["name"], inline=True)
        embed.add_field(name="Category", value=item["category"], inline=True)
        embed.add_field(name="Location", value=item["location"], inline=True)
        embed.add_field(
            name="Stock Status",
            value=f"**{item['available_qty']}** available / **{item['total_qty']}** total",
            inline=False,
        )
        embed.set_footer(text=f"Updated by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="inventory",
        description="Search and view components available in the IEEE lab inventory.",
    )
    @app_commands.describe(
        search="Search query for item name (e.g. servo, sensor, esp32)",
        category="Filter by category (e.g. Sensors, Microcontrollers, Tools)",
    )
    async def inventory_list(
        self,
        interaction: discord.Interaction,
        search: Optional[str] = None,
        category: Optional[str] = None,
    ):
        items = database.search_inventory(search_query=search, category=category)

        if not items:
            query_str = f" matching `{search}`" if search else ""
            cat_str = f" in category `{category}`" if category else ""
            await interaction.response.send_message(
                f"🔍 No items found{query_str}{cat_str}.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="📦 IEEE QP Lab Inventory",
            description=f"Showing **{len(items)}** component(s) in lab stock.",
            color=discord.Color.green(),
        )

        for item in items[:25]:  # Discord embed field limit
            status_emoji = "🟢" if item["available_qty"] > 0 else "🔴"
            field_name = f"{status_emoji} {item['name']} (ID: {item['id']})"
            field_val = (
                f"• Category: **{item['category']}**\n"
                f"• Available in Lab: **{item['available_qty']} / {item['total_qty']}**\n"
                f"• Location: `{item['location']}`"
            )
            embed.add_field(name=field_name, value=field_val, inline=True)

        if len(items) > 25:
            embed.set_footer(text=f"Showing first 25 of {len(items)} items. Use search to narrow results.")
        else:
            embed.set_footer(text="IEEE Quarterly Projects • Lab Inventory")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="checkout",
        description="Check out a lab component to a team with an exact timestamp (Leadership only).",
    )
    @app_commands.describe(
        team=f"Team number (1-{config.MAX_TEAMS})",
        item="Item name or Item ID from /inventory",
        quantity="Number of units being borrowed",
        member="Optional member receiving the item (defaults to command runner)",
    )
    @app_commands.default_permissions(administrator=True)
    async def checkout(
        self,
        interaction: discord.Interaction,
        team: int,
        item: str,
        quantity: int = 1,
        member: Optional[discord.Member] = None,
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only Leadership ({', '.join(config.STAFF_ROLES)}) can check out items.",
                ephemeral=True,
            )
            return

        if team < 1 or team > config.MAX_TEAMS:
            await interaction.response.send_message(
                f"❌ Team number must be between 1 and {config.MAX_TEAMS}.", ephemeral=True
            )
            return

        borrower = member or interaction.user
        success, msg = database.checkout_inventory_item(
            item_id_or_name=item,
            team_number=team,
            borrower_id=borrower.id,
            quantity=quantity,
        )

        if not success:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        embed = discord.Embed(
            title="📤 Lab Checkout Logged",
            description=msg,
            color=discord.Color.gold(),
        )
        embed.add_field(name="Team", value=f"Team {team}", inline=True)
        embed.add_field(name="Borrower", value=borrower.mention, inline=True)
        embed.add_field(name="Logged By", value=interaction.user.mention, inline=True)
        embed.set_footer(text="Please return components upon project completion.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="return",
        description="Check an item back into lab inventory with an exact timestamp (Leadership only).",
    )
    @app_commands.describe(
        team=f"Team number returning the item (1-{config.MAX_TEAMS})",
        item="Item name or Item ID",
        quantity="Number of units being returned",
    )
    @app_commands.default_permissions(administrator=True)
    async def return_item_cmd(
        self,
        interaction: discord.Interaction,
        team: int,
        item: str,
        quantity: int = 1,
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only Leadership ({', '.join(config.STAFF_ROLES)}) can process returns.",
                ephemeral=True,
            )
            return

        success, msg = database.return_inventory_item(
            item_id_or_name=item,
            team_number=team,
            quantity=quantity,
        )

        if not success:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        embed = discord.Embed(
            title="📥 Component Return Logged",
            description=msg,
            color=discord.Color.green(),
        )
        embed.add_field(name="Team", value=f"Team {team}", inline=True)
        embed.add_field(name="Processed By", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="whereis",
        description="Locate where an item is: how many are in lab storage vs. which teams borrowed them.",
    )
    @app_commands.describe(item="Item name or Item ID (e.g. Arduino Uno, ESP32)")
    async def whereis(self, interaction: discord.Interaction, item: str):
        result = database.get_whereis_item(item)
        if not result:
            await interaction.response.send_message(
                f"❌ Item `{item}` was not found in inventory.", ephemeral=True
            )
            return

        inv_item = result["item"]
        active_loans = result["active_loans"]

        embed = discord.Embed(
            title=f"🔍 Location Tracker — {inv_item['name']}",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Lab Stock Location",
            value=f"• Physical Location: `{inv_item['location']}`\n• In Stock: **{inv_item['available_qty']} / {inv_item['total_qty']}** available",
            inline=False,
        )

        if active_loans:
            loan_lines = []
            for loan in active_loans:
                borrower = f"<@{loan['borrower_id']}>" if loan["borrower_id"] else "Unknown"
                loan_lines.append(
                    f"• **Team {loan['team_number']}** has **{loan['quantity']}x** "
                    f"(borrowed on `{loan['borrowed_at']}` by {borrower})"
                )
            embed.add_field(
                name=f"Currently Borrowed ({len(active_loans)} team(s))",
                value="\n".join(loan_lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="Currently Borrowed",
                value="✅ All units are currently in the IEEE lab storage.",
                inline=False,
            )

        embed.set_footer(text="IEEE Quarterly Projects • Inventory Location Tracking")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="borrowed",
        description="View items currently checked out by a specific team or across all teams.",
    )
    @app_commands.describe(
        team=f"Optional team number (1-{config.MAX_TEAMS}). Leave blank to see all teams.",
    )
    async def borrowed_list(
        self,
        interaction: discord.Interaction,
        team: Optional[int] = None,
    ):
        member = interaction.user
        is_staff = isinstance(member, discord.Member) and is_staff_or_admin(member)

        # If team not specified, check if member is in a team
        if team is None and isinstance(member, discord.Member):
            user_team_roles = [r for r in member.roles if (m := TEAM_ROLE_PATTERN.match(r.name))]
            if user_team_roles and not is_staff:
                match = TEAM_ROLE_PATTERN.match(user_team_roles[0].name)
                team = int(match.group(1))

        if team is None and not is_staff:
            await interaction.response.send_message(
                "❌ Please specify a team number (e.g. `/borrowed team:4`).",
                ephemeral=True,
            )
            return

        loans = database.get_borrowed_items(team_number=team)

        if not loans:
            msg = f"No items currently checked out for **Team {team}**." if team else "No items currently checked out across any team."
            await interaction.response.send_message(f"ℹ️ {msg}", ephemeral=True)
            return

        title = f"📋 Borrowed Items — Team {team}" if team else "📋 All Currently Borrowed Lab Items"
        embed = discord.Embed(
            title=title,
            color=discord.Color.orange(),
        )

        for loan in loans[:25]:
            borrower_mention = f"<@{loan['borrower_id']}>" if loan["borrower_id"] else "Unknown"
            field_name = f"Team {loan['team_number']} • {loan['quantity']}x {loan['item_name']}"
            field_val = (
                f"• Category: **{loan['category']}**\n"
                f"• Borrower: {borrower_mention}\n"
                f"• Checked Out: `{loan['borrowed_at']}`"
            )
            embed.add_field(name=field_name, value=field_val, inline=True)

        if len(loans) > 25:
            embed.set_footer(text=f"Showing 25 of {len(loans)} active loans.")
        else:
            embed.set_footer(text="IEEE Quarterly Projects • Equipment Tracking")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="loan-history",
        description="View chronological history of all checkouts and returns with timestamps.",
    )
    @app_commands.describe(
        team=f"Filter by team number (1-{config.MAX_TEAMS})",
        item="Filter by item name (e.g. Arduino)",
        limit="Number of log entries to retrieve (default: 15)",
    )
    async def loan_history(
        self,
        interaction: discord.Interaction,
        team: Optional[int] = None,
        item: Optional[str] = None,
        limit: int = 15,
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only Leadership ({', '.join(config.STAFF_ROLES)}) can view full loan audit history.",
                ephemeral=True,
            )
            return

        history = database.get_loan_history(team_number=team, item_query=item, limit=min(limit, 30))

        if not history:
            await interaction.response.send_message("ℹ️ No loan history entries found matching criteria.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📜 Lab Loan & Return History Log",
            description=f"Showing recent checkout and return activity with timestamps.",
            color=discord.Color.purple(),
        )

        lines = []
        for entry in history:
            borrower = f"<@{entry['borrower_id']}>" if entry["borrower_id"] else "Team"
            if entry["status"] == "returned":
                lines.append(
                    f"🟢 **RETURNED** | **Team {entry['team_number']}** returned **{entry['quantity']}x {entry['item_name']}**\n"
                    f"   ↳ *Out:* `{entry['borrowed_at']}` ➔ *Back:* `{entry['returned_at']}`"
                )
            else:
                lines.append(
                    f"🟡 **BORROWED** | **Team {entry['team_number']}** ({borrower}) checked out **{entry['quantity']}x {entry['item_name']}**\n"
                    f"   ↳ *Out:* `{entry['borrowed_at']}` *(Currently with team)*"
                )

        embed.description = "\n\n".join(lines)
        embed.set_footer(text="IEEE Quarterly Projects • Equipment Audit Log")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(InventoryCog(bot))
