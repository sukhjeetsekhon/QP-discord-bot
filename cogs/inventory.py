import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List, Dict, Any
from datetime import datetime
import re
import config
import database
from cogs.hardware_tickets import is_staff_or_admin
from cogs.team_assignment import TEAM_ROLE_PATTERN


class PublicBorrowReturnView(discord.ui.View):
    """Persistent controls on public active cards in #borrowed-items."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Request Return",
        style=discord.ButtonStyle.secondary,
        custom_id="qp:public_photo_req_return",
        emoji="📦",
        row=0,
    )
    async def public_request_return_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.message:
            return

        loan = database.get_photo_loan_by_message(interaction.message.id)
        if not loan:
            await interaction.response.send_message(
                "❌ Could not find the database record for this loan.", ephemeral=True
            )
            return

        if loan["status"] == "returned":
            await interaction.response.send_message(
                "✅ This item has already been marked as returned.", ephemeral=True
            )
            return

        # Check permissions: borrower, teammate, or staff
        is_staff = isinstance(interaction.user, discord.Member) and is_staff_or_admin(interaction.user)
        is_borrower = interaction.user.id == loan["borrower_id"]
        is_teammate = False
        if isinstance(interaction.user, discord.Member) and loan["team_number"]:
            target_role = f"team {loan['team_number']}"
            if any(r.name.lower() == target_role for r in interaction.user.roles):
                is_teammate = True

        if not (is_staff or is_borrower or is_teammate):
            await interaction.response.send_message(
                "❌ Only the borrower, their teammates, or Leadership can request a return.",
                ephemeral=True,
            )
            return

        database.update_photo_loan_status(loan["id"], "return_pending")

        # 1. Update the public card in #borrowed-items
        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed(title="Active Loan")
        embed.color = discord.Color.orange()
        for i, field in enumerate(embed.fields):
            if field.name == "📊 Status":
                embed.set_field_at(
                    i,
                    name="📊 Status",
                    value=f"⏳ **Return Pending Review**\n*(Dropped off by {interaction.user.mention})*",
                    inline=True,
                )
                break
        embed.set_footer(text=f"Return requested by {interaction.user.display_name} • Awaiting Leadership confirmation")

        # Disable button on public card
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == "qp:public_photo_req_return":
                child.disabled = True

        await interaction.message.edit(embed=embed, view=self)

        # 2. Sync to private card in #inventory if present
        if loan.get("log_channel_id") and loan.get("log_message_id") and interaction.guild:
            try:
                priv_channel = interaction.guild.get_channel(loan["log_channel_id"])
                if isinstance(priv_channel, discord.TextChannel):
                    priv_msg = await priv_channel.fetch_message(loan["log_message_id"])
                    if priv_msg and priv_msg.embeds:
                        priv_embed = priv_msg.embeds[0]
                        priv_embed.color = discord.Color.orange()
                        for i, field in enumerate(priv_embed.fields):
                            if field.name == "📊 Status":
                                priv_embed.set_field_at(
                                    i,
                                    name="📊 Status",
                                    value=f"⏳ **Return Pending Review**\n*(Dropped off by {interaction.user.mention})*",
                                    inline=True,
                                )
                                break
                        priv_embed.set_footer(text=f"Return requested by {interaction.user.display_name} • Awaiting Leadership confirmation")
                        await priv_msg.edit(embed=priv_embed)
            except Exception as e:
                print(f"⚠️ Could not sync return_pending to #inventory: {e}")

        await interaction.response.send_message(
            "📦 Return requested! Please drop off the item in the IEEE Project Space for an officer to inspect and confirm.",
            ephemeral=True,
        )


class InventoryReturnControlView(discord.ui.View):
    """Persistent controls on the private #inventory embed for Leadership review."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Request Return",
        style=discord.ButtonStyle.secondary,
        custom_id="qp:photo_loan_req_return",
        emoji="📦",
        row=0,
    )
    async def request_return_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.message:
            return

        loan = database.get_photo_loan_by_message(interaction.message.id)
        if not loan:
            await interaction.response.send_message(
                "❌ Could not find the database record for this loan.", ephemeral=True
            )
            return

        if loan["status"] == "returned":
            await interaction.response.send_message(
                "✅ This item has already been marked as returned.", ephemeral=True
            )
            return

        # Check permissions: borrower, teammate, or staff
        is_staff = isinstance(interaction.user, discord.Member) and is_staff_or_admin(interaction.user)
        is_borrower = interaction.user.id == loan["borrower_id"]
        is_teammate = False
        if isinstance(interaction.user, discord.Member) and loan["team_number"]:
            target_role = f"team {loan['team_number']}"
            if any(r.name.lower() == target_role for r in interaction.user.roles):
                is_teammate = True

        if not (is_staff or is_borrower or is_teammate):
            await interaction.response.send_message(
                "❌ Only the borrower, their teammates, or Leadership can request a return.",
                ephemeral=True,
            )
            return

        database.update_photo_loan_status(loan["id"], "return_pending")

        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed(title="Borrowed Item")
        embed.color = discord.Color.orange()
        for i, field in enumerate(embed.fields):
            if field.name == "📊 Status":
                embed.set_field_at(
                    i,
                    name="📊 Status",
                    value=f"⏳ **Return Pending Review**\n*(Dropped off by {interaction.user.mention})*",
                    inline=True,
                )
                break
        embed.set_footer(text=f"Return requested by {interaction.user.display_name} • Awaiting Leadership confirmation")

        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == "qp:photo_loan_req_return":
                child.disabled = True

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message(
            "📦 Return marked as pending review.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Confirm Return",
        style=discord.ButtonStyle.success,
        custom_id="qp:photo_loan_confirm_return",
        emoji="✅",
        row=0,
    )
    async def confirm_return_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.message:
            return

        # Only Leadership can confirm returns
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only Leadership ({', '.join(config.STAFF_ROLES)}) can confirm returns.",
                ephemeral=True,
            )
            return

        loan = database.get_photo_loan_by_message(interaction.message.id)
        if not loan:
            await interaction.response.send_message(
                "❌ Could not find the database record for this loan.", ephemeral=True
            )
            return

        if loan["status"] == "returned":
            await interaction.response.send_message(
                "✅ This item is already marked as returned.", ephemeral=True
            )
            return

        database.update_photo_loan_status(loan["id"], "returned", confirmed_by_id=interaction.user.id)

        now_ts = int(datetime.now().timestamp())
        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed(title="Borrowed Item")
        embed.color = discord.Color.green()
        for i, field in enumerate(embed.fields):
            if field.name == "📊 Status":
                embed.set_field_at(
                    i,
                    name="📊 Status",
                    value=f"🟢 **Returned**\n*(Confirmed by {interaction.user.mention})*",
                    inline=True,
                )
                break

        embed.add_field(
            name="📥 Return Confirmed",
            value=f"<t:{now_ts}:F> by {interaction.user.mention}",
            inline=False,
        )
        embed.set_footer(text=f"Return verified by {interaction.user.display_name} • Item back in lab storage")

        # Disable all buttons on private card
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        await interaction.message.edit(embed=embed, view=self)

        # Automatically DELETE the public card from #borrowed-items (keeping public feed active-only!)
        if loan.get("public_channel_id") and loan.get("public_message_id") and interaction.guild:
            try:
                pub_channel = interaction.guild.get_channel(loan["public_channel_id"])
                if isinstance(pub_channel, discord.TextChannel):
                    pub_msg = await pub_channel.fetch_message(loan["public_message_id"])
                    if pub_msg:
                        await pub_msg.delete()
            except Exception as e:
                print(f"⚠️ Could not delete public message from #borrowed-items: {e}")

        await interaction.response.send_message(
            f"✅ Return confirmed for Team {loan['team_number']} - **{loan['item_description']}**! Public card removed from active board.",
            ephemeral=True,
        )


class BorrowItemPanelButtonView(discord.ui.View):
    """Persistent button panel in #borrow-items for starting an item borrowing thread."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Borrow Lab Item",
        style=discord.ButtonStyle.primary,
        custom_id="qp:borrow_item_btn",
        emoji="📸",
        row=0,
    )
    async def borrow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if not guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Guild context required.", ephemeral=True)
            return

        # Auto-detect team from roles
        team_num = None
        for role in interaction.user.roles:
            m = TEAM_ROLE_PATTERN.match(role.name)
            if m:
                team_num = int(m.group(1))
                break

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("❌ This panel must be in a text channel.", ephemeral=True)
            return

        team_label = f"Team {team_num}" if team_num else "Unassigned Team"
        thread_name = f"borrow-{interaction.user.display_name[:15]}-t{team_num if team_num else 'x'}"

        try:
            thread = await channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                auto_archive_duration=1440,
                reason=f"Borrow log thread for {interaction.user.display_name}",
            )
        except (discord.Forbidden, discord.HTTPException):
            try:
                thread = await channel.create_thread(
                    name=thread_name,
                    type=discord.ChannelType.public_thread,
                    auto_archive_duration=1440,
                    reason=f"Borrow log thread for {interaction.user.display_name}",
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"❌ Could not create a borrowing thread: {e}", ephemeral=True
                )
                return

        try:
            await thread.add_user(interaction.user)
        except Exception:
            pass

        instructions = (
            f"👋 Welcome {interaction.user.mention}!\n\n"
            f"**Team Detected:** `{team_label}`\n\n"
            "**To log your borrowed item, reply to this thread with:**\n"
            "1. 📷 An attached **photo** of the item(s) you are borrowing.\n"
            "2. 📝 The **Item Name / Description & Quantity** in your message text (e.g. `2x Arduino Uno, 1x Breadboard`).\n"
        )
        if not team_num:
            instructions += "\n*(If you are in a team, please mention 'Team X' in your message).* \n"
        instructions += (
            "\nOnce you post your photo and description, your checkout will be automatically logged to `#borrowed-items` for all teams to see, "
            "and an internal audit copy will be filed with Leadership in `#inventory`!\n\n"
            "⏳ *This thread will remain open for 24 hours so you can review your receipt.*"
        )

        embed = discord.Embed(
            title="📸 Borrow Lab Item Checkout",
            description=instructions,
            color=discord.Color.blue(),
        )
        embed.set_footer(text="IEEE Quarterly Projects • Lab Inventory Tracker")

        await thread.send(content=interaction.user.mention, embed=embed)
        await interaction.response.send_message(
            f"✅ Created your private checkout thread: {thread.mention}. Please upload your photo there!",
            ephemeral=True,
        )


class InventoryCog(commands.Cog):
    """Commands for managing IEEE QP lab inventory, photo-based borrowing, and checkouts/returns."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ==========================================
    # PHOTO-BASED BORROWING THREAD LISTENER
    # ==========================================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for photo uploads in borrowing threads."""
        if message.author.bot:
            return

        if not isinstance(message.channel, discord.Thread):
            return

        if not message.channel.name.startswith("borrow-"):
            return

        # Check if this thread already has an active or completed loan logged
        existing_loans = database.get_all_photo_loans()
        if any(l.get("thread_id") == message.channel.id for l in existing_loans):
            return

        # Check for image attachments
        image_attachments = [
            a for a in message.attachments
            if (a.content_type and a.content_type.startswith("image/"))
            or a.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
        ]

        if not image_attachments:
            await message.reply(
                "⚠️ **Please attach a photo** of the item you borrowed along with your message!",
                mention_author=True,
            )
            return

        item_desc = message.content.strip()
        if not item_desc:
            await message.reply(
                "⚠️ **Please include the item name/description and quantity** in your message text (e.g. `2x SG90 Servo Motors`) along with your photo!",
                mention_author=True,
            )
            return

        # Detect team number: first check message text, then check member roles
        team_num = None
        match_text = re.search(r"team\s*(\d+)", item_desc, re.IGNORECASE)
        if match_text:
            team_num = int(match_text.group(1))
        elif isinstance(message.author, discord.Member):
            for role in message.author.roles:
                m = TEAM_ROLE_PATTERN.match(role.name)
                if m:
                    team_num = int(m.group(1))
                    break

        guild = message.guild
        if not guild:
            return

        # Locate or create the private #inventory channel (Leadership only)
        inv_channel_name = config.INVENTORY_CHANNEL_NAME.lower()
        inv_channel = discord.utils.get(guild.text_channels, name=inv_channel_name)
        if not inv_channel:
            try:
                inv_channel = await guild.create_text_channel(
                    name=inv_channel_name,
                    topic="Internal audit log of borrowed lab components and equipment (Leadership only).",
                )
            except Exception as e:
                await message.reply(f"❌ Could not find or create `#{inv_channel_name}`: {e}")
                return

        # Locate or create the public #borrowed-items channel (Active items board)
        pub_channel_name = config.BORROWED_ITEMS_CHANNEL_NAME.lower()
        pub_channel = discord.utils.get(guild.text_channels, name=pub_channel_name)
        if not pub_channel:
            try:
                pub_channel = await guild.create_text_channel(
                    name=pub_channel_name,
                    topic="Active equipment and components currently borrowed by QP teams.",
                )
            except Exception as e:
                await message.reply(f"❌ Could not find or create `#{pub_channel_name}`: {e}")
                return

        now_ts = int(datetime.now().timestamp())

        # 1. Build private #inventory embed (Audit card)
        priv_embed = discord.Embed(
            title=f"📦 Borrowed Item: {item_desc}",
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        priv_embed.add_field(name="🏷️ Team", value=f"Team {team_num}" if team_num else "Unassigned", inline=True)
        priv_embed.add_field(name="👤 Borrower", value=message.author.mention, inline=True)
        priv_embed.add_field(name="📊 Status", value="🟡 **Borrowed (In Use)**", inline=True)
        priv_embed.add_field(name="📝 Item Description", value=item_desc, inline=False)
        priv_embed.add_field(name="⏰ Borrowed Time", value=f"<t:{now_ts}:F> (<t:{now_ts}:R>)", inline=False)
        priv_embed.set_image(url=image_attachments[0].url)
        priv_embed.set_footer(text=f"Logged by {message.author.display_name} • Internal Leadership Record")

        # 2. Build public #borrowed-items embed (Active board card)
        pub_embed = discord.Embed(
            title=f"📦 Active Checkout: {item_desc}",
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        pub_embed.add_field(name="🏷️ Team", value=f"Team {team_num}" if team_num else "Unassigned", inline=True)
        pub_embed.add_field(name="👤 Borrower", value=message.author.mention, inline=True)
        pub_embed.add_field(name="📊 Status", value="🟡 **Borrowed (In Use)**", inline=True)
        pub_embed.add_field(name="📝 Item Details", value=item_desc, inline=False)
        pub_embed.add_field(name="⏰ Borrowed Time", value=f"<t:{now_ts}:F> (<t:{now_ts}:R>)", inline=False)
        pub_embed.set_image(url=image_attachments[0].url)
        pub_embed.set_footer(text="Borrowed from IEEE Project Space • Click 'Request Return' when returning to lab")

        # Save to database
        loan_id = database.create_photo_loan(
            team_number=team_num or 0,
            borrower_id=message.author.id,
            item_description=item_desc,
            image_url=image_attachments[0].url,
            log_channel_id=inv_channel.id,
            public_channel_id=pub_channel.id,
            thread_id=message.channel.id,
        )

        # Post private card to #inventory
        priv_view = InventoryReturnControlView()
        priv_msg = await inv_channel.send(embed=priv_embed, view=priv_view)

        # Post active card to #borrowed-items
        pub_view = PublicBorrowReturnView()
        pub_msg = await pub_channel.send(embed=pub_embed, view=pub_view)

        database.update_photo_loan_messages(
            loan_id,
            log_channel_id=inv_channel.id,
            log_message_id=priv_msg.id,
            public_channel_id=pub_channel.id,
            public_message_id=pub_msg.id,
        )

        # 3. Send self-contained Receipt to the participant in the thread (linking to #borrowed-items!)
        confirm_embed = discord.Embed(
            title="✅ Item Checkout Confirmed!",
            description=(
                f"Your borrowed item has been officially logged and is now visible on the active board in {pub_channel.mention}!\n\n"
                f"[**View Active Card in #{pub_channel.name}**]({pub_msg.jump_url})\n\n"
                "**Return Instructions:**\n"
                "When your team finishes with the equipment or at the end of the quarter, return it to the IEEE Project Space (Jacobs Hall 4309) during Open Access Hours. "
                f"You can click **Request Return 📦** on your card in {pub_channel.mention} when dropping off items."
            ),
            color=discord.Color.green(),
        )
        confirm_embed.add_field(name="🏷️ Team", value=f"Team {team_num}" if team_num else "Unassigned", inline=True)
        confirm_embed.add_field(name="📝 Item", value=item_desc, inline=True)
        confirm_embed.add_field(name="⏰ Time", value=f"<t:{now_ts}:t>", inline=True)
        confirm_embed.set_thumbnail(url=image_attachments[0].url)
        confirm_embed.set_footer(text="Receipt saved • This thread will remain open for 24 hours.")
        await message.reply(embed=confirm_embed)

    # ==========================================
    # PHOTO BORROWING COMMANDS
    # ==========================================

    @app_commands.command(
        name="setup-borrow-panel",
        description="Post the persistent 'Borrow Lab Item' button panel in #borrow-items (Leadership only).",
    )
    @app_commands.describe(
        channel="Optional channel to post the panel in (defaults to #borrow-items)"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_borrow_panel(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only Leadership ({', '.join(config.STAFF_ROLES)}) can setup the borrowing panel.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ Guild context required.", ephemeral=True)
            return

        target_channel = channel
        if not target_channel:
            channel_name = config.BORROW_ITEMS_CHANNEL_NAME.lower()
            target_channel = discord.utils.get(guild.text_channels, name=channel_name)
            if not target_channel:
                try:
                    target_channel = await guild.create_text_channel(
                        name=channel_name,
                        topic="Log equipment and parts borrowed from the IEEE Project Space.",
                    )
                except Exception as e:
                    await interaction.response.send_message(
                        f"❌ Failed to find or create `#{channel_name}`: {e}", ephemeral=True
                    )
                    return

        embed = discord.Embed(
            title="📸 IEEE Lab Item Borrowing & Inventory Log",
            description=(
                "Borrowing components or tools from the **IEEE Project Space (Jacobs Hall 4309)**?\n\n"
                "**How to Log Borrowed Items:**\n"
                "1. Click the **'📸 Borrow Lab Item'** button below.\n"
                "2. The bot creates a private checkout thread for your team.\n"
                "3. In the thread, upload a **photo** of the item along with the **item name & quantity**.\n"
                "4. Your checkout is automatically logged to `#borrowed-items` for all teams to see, and archived in `#inventory` for Leadership!\n\n"
                "**Returning Items:**\n"
                "Return all items to the Project Space when your team finishes or by the end of the quarter. "
                "Click **Request Return 📦** on your `#borrowed-items` post when dropping off items."
            ),
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="📍 Project Space Location",
            value="Jacobs Hall 4309 (4th Floor) • During Open Access Hours",
            inline=False,
        )
        embed.set_footer(text="IEEE Quarterly Projects • Equipment Tracking")

        view = BorrowItemPanelButtonView()
        msg = await target_channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Borrowing panel posted in {target_channel.mention}!\n[Jump to Panel]({msg.jump_url})",
            ephemeral=True,
        )

    @app_commands.command(
        name="borrow-photo",
        description="Directly log a borrowed lab item with a photo attachment.",
    )
    @app_commands.describe(
        image="Photo of the item(s) being borrowed",
        item="Item name / description and quantity (e.g. '2x Arduino Uno, 1x breadboard')",
        team=f"Optional team number (1-{config.MAX_TEAMS}). Auto-detected from role if omitted.",
    )
    async def borrow_photo_cmd(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        item: str,
        team: Optional[int] = None,
    ):
        if not (image.content_type and image.content_type.startswith("image/")) and not image.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            await interaction.response.send_message("❌ The uploaded attachment must be an image file.", ephemeral=True)
            return

        member = interaction.user
        if team is None and isinstance(member, discord.Member):
            for role in member.roles:
                m = TEAM_ROLE_PATTERN.match(role.name)
                if m:
                    team = int(m.group(1))
                    break

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ Guild context required.", ephemeral=True)
            return

        inv_channel_name = config.INVENTORY_CHANNEL_NAME.lower()
        inv_channel = discord.utils.get(guild.text_channels, name=inv_channel_name)
        if not inv_channel:
            try:
                inv_channel = await guild.create_text_channel(
                    name=inv_channel_name,
                    topic="Internal audit log of borrowed lab components and equipment (Leadership only).",
                )
            except Exception as e:
                await interaction.response.send_message(f"❌ Could not find or create `#{inv_channel_name}`: {e}", ephemeral=True)
                return

        pub_channel_name = config.BORROWED_ITEMS_CHANNEL_NAME.lower()
        pub_channel = discord.utils.get(guild.text_channels, name=pub_channel_name)
        if not pub_channel:
            try:
                pub_channel = await guild.create_text_channel(
                    name=pub_channel_name,
                    topic="Active equipment and components currently borrowed by QP teams.",
                )
            except Exception as e:
                await interaction.response.send_message(f"❌ Could not find or create `#{pub_channel_name}`: {e}", ephemeral=True)
                return

        now_ts = int(datetime.now().timestamp())

        # Private audit card
        priv_embed = discord.Embed(
            title=f"📦 Borrowed Item: {item.strip()}",
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        priv_embed.add_field(name="🏷️ Team", value=f"Team {team}" if team else "Unassigned", inline=True)
        priv_embed.add_field(name="👤 Borrower", value=interaction.user.mention, inline=True)
        priv_embed.add_field(name="📊 Status", value="🟡 **Borrowed (In Use)**", inline=True)
        priv_embed.add_field(name="📝 Item Description", value=item.strip(), inline=False)
        priv_embed.add_field(name="⏰ Borrowed Time", value=f"<t:{now_ts}:F> (<t:{now_ts}:R>)", inline=False)
        priv_embed.set_image(url=image.url)
        priv_embed.set_footer(text=f"Logged by {interaction.user.display_name} • Internal Leadership Record")

        # Public active card
        pub_embed = discord.Embed(
            title=f"📦 Active Checkout: {item.strip()}",
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        pub_embed.add_field(name="🏷️ Team", value=f"Team {team}" if team else "Unassigned", inline=True)
        pub_embed.add_field(name="👤 Borrower", value=interaction.user.mention, inline=True)
        pub_embed.add_field(name="📊 Status", value="🟡 **Borrowed (In Use)**", inline=True)
        pub_embed.add_field(name="📝 Item Details", value=item.strip(), inline=False)
        pub_embed.add_field(name="⏰ Borrowed Time", value=f"<t:{now_ts}:F> (<t:{now_ts}:R>)", inline=False)
        pub_embed.set_image(url=image.url)
        pub_embed.set_footer(text="Borrowed from IEEE Project Space • Click 'Request Return' when returning to lab")

        loan_id = database.create_photo_loan(
            team_number=team or 0,
            borrower_id=interaction.user.id,
            item_description=item.strip(),
            image_url=image.url,
            log_channel_id=inv_channel.id,
            public_channel_id=pub_channel.id,
        )

        priv_view = InventoryReturnControlView()
        priv_msg = await inv_channel.send(embed=priv_embed, view=priv_view)

        pub_view = PublicBorrowReturnView()
        pub_msg = await pub_channel.send(embed=pub_embed, view=pub_view)

        database.update_photo_loan_messages(
            loan_id,
            log_channel_id=inv_channel.id,
            log_message_id=priv_msg.id,
            public_channel_id=pub_channel.id,
            public_message_id=pub_msg.id,
        )

        await interaction.response.send_message(
            f"✅ **Item successfully logged to {pub_channel.mention}!**\n[Jump to Active Card]({pub_msg.jump_url})",
            ephemeral=True,
        )

    @app_commands.command(
        name="borrowed-items",
        description="View photo-logged items borrowed by a team or across all teams.",
    )
    @app_commands.describe(
        team=f"Optional team number (1-{config.MAX_TEAMS}). Leave blank to see all teams.",
        status="Filter by status (borrowed, return_pending, returned, or all)",
    )
    @app_commands.choices(
        status=[
            app_commands.Choice(name="Currently Borrowed (In Use)", value="borrowed"),
            app_commands.Choice(name="Return Pending Review", value="return_pending"),
            app_commands.Choice(name="Returned", value="returned"),
            app_commands.Choice(name="All Records", value="all"),
        ]
    )
    async def borrowed_items_cmd(
        self,
        interaction: discord.Interaction,
        team: Optional[int] = None,
        status: Optional[str] = "borrowed",
    ):
        member = interaction.user
        is_staff = isinstance(member, discord.Member) and is_staff_or_admin(member)

        if team is None and isinstance(member, discord.Member):
            for role in member.roles:
                m = TEAM_ROLE_PATTERN.match(role.name)
                if m and not is_staff:
                    team = int(m.group(1))
                    break

        filter_status = None if status == "all" else status

        if team:
            loans = database.get_photo_loans_by_team(team, status=filter_status)
        else:
            loans = database.get_all_photo_loans(status=filter_status)

        if not loans:
            status_text = f" with status `{status}`" if status != "all" else ""
            msg = f"No photo-logged items found for **Team {team}**{status_text}." if team else f"No photo-logged items found{status_text}."
            await interaction.response.send_message(f"ℹ️ {msg}", ephemeral=True)
            return

        title = f"📸 Borrowed Items — Team {team}" if team else "📸 All Photo-Logged Lab Items"
        embed = discord.Embed(
            title=title,
            description=f"Showing **{min(len(loans), 15)}** of **{len(loans)}** recorded photo loan(s).",
            color=discord.Color.blue(),
        )

        status_emojis = {
            "borrowed": "🟡 Borrowed",
            "return_pending": "⏳ Return Pending",
            "returned": "🟢 Returned",
        }

        for loan in loans[:15]:
            borrower_mention = f"<@{loan['borrower_id']}>" if loan.get("borrower_id") else "Unknown"
            status_str = status_emojis.get(loan.get("status"), "Unknown")
            jump_link = ""
            if loan.get("status") != "returned" and loan.get("public_channel_id") and loan.get("public_message_id"):
                jump_link = f"\n• [View Active Card](https://discord.com/channels/{interaction.guild_id}/{loan['public_channel_id']}/{loan['public_message_id']})"

            field_name = f"Team {loan['team_number']} • {loan['item_description'][:35]}"
            field_val = (
                f"• Status: **{status_str}**\n"
                f"• Borrower: {borrower_mention}\n"
                f"• Logged: `{loan.get('borrowed_at', 'N/A')}`"
                f"{jump_link}"
            )
            embed.add_field(name=field_name, value=field_val, inline=False)

        if loans[0].get("image_url"):
            embed.set_thumbnail(url=loans[0]["image_url"])

        embed.set_footer(text="IEEE Quarterly Projects • Lab Inventory Tracker")
        await interaction.response.send_message(embed=embed)

    # ==========================================
    # EXISTING CATALOG COMMANDS
    # ==========================================

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

        for item in items[:25]:
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
