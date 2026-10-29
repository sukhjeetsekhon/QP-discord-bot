import asyncio
import sys
import discord
from discord.ext import commands
import config
import database
from cogs.team_assignment import TeamAssignmentView
from cogs.hardware_tickets import TicketRequestView, TicketControlView
from cogs.mentor_queue import MentorQueueSetupView, MentorTicketControlView

# Configure required Discord intents
def make_intents(enable_message_content: bool = True, enable_members: bool = True) -> discord.Intents:
    """Build discord Intents with optional privileged intents."""
    intents = discord.Intents.default()
    intents.members = enable_members  # Required for inspecting and managing member roles
    intents.guilds = True
    intents.message_content = enable_message_content  # For direct questions in #ask-ai
    return intents


class QPBot(commands.Bot):
    def __init__(self, intents: discord.Intents):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

    async def setup_hook(self):
        """Executed before the bot starts accepting events."""
        # 1. Initialize SQLite database
        try:
            database.init_db()
            print("📦 SQLite Database initialized successfully.")
        except Exception as e:
            print(f"❌ Failed to initialize database: {e}", file=sys.stderr)

        # 2. Register persistent UI views so buttons work across restarts
        self.add_view(TeamAssignmentView())
        self.add_view(TicketRequestView())
        self.add_view(TicketControlView())
        self.add_view(MentorQueueSetupView())
        self.add_view(MentorTicketControlView())

        # 3. Load extension cogs
        initial_extensions = [
            "cogs.team_assignment",
            "cogs.hardware_tickets",
            "cogs.team_workspaces",
            "cogs.mentor_queue",
            "cogs.inventory",
            "cogs.ai_help",
        ]
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                print(f" Loaded extension: {ext}")
            except Exception as e:
                print(f"❌ Failed to load extension {ext}: {e}", file=sys.stderr)

        # 4. Sync slash commands
        try:
            if config.GUILD_ID:
                guild_obj = discord.Object(id=config.GUILD_ID)
                self.tree.copy_global_to(guild=guild_obj)
                synced = await self.tree.sync(guild=guild_obj)
                print(f"⚡ Synced {len(synced)} slash commands instantly to test guild ({config.GUILD_ID}).")
            else:
                synced = await self.tree.sync()
                print(f"🌐 Synced {len(synced)} global slash commands.")
        except Exception as e:
            print(f"⚠️ Slash command sync error: {e}", file=sys.stderr)

    async def on_ready(self):
        print("=" * 55)
        print(f"🤖 QP Discord Bot logged in as: {self.user} (ID: {self.user.id})")
        print(f" Connected to {len(self.guilds)} server(s)")
        print(f" Max Teams: {config.MAX_TEAMS}")
        print(f" Team Budget Allocation: ${config.DEFAULT_TEAM_BUDGET:.2f}")
        print(f" Staff Role: {config.STAFF_ROLE_NAME}")
        print(f" Tickets Category: {config.TICKETS_CATEGORY_NAME}")
        print(f" AI Help Channel: #{config.AI_HELP_CHANNEL_NAME} ({'Gemini Active' if config.GEMINI_API_KEY else 'No GEMINI_API_KEY'})")
        print(f" Message Content Intent: {'Enabled' if self.intents.message_content else 'Disabled (Privileged intent fallback)'}")
        print(f" Database Path: {config.DB_PATH}")
        print("=" * 55)


async def main():
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "your_bot_token_here":
        print(
            "❌ ERROR: DISCORD_TOKEN is missing or not set in your .env file.\n"
            "Please copy .env.example to .env and add your Discord bot token.",
            file=sys.stderr,
        )
        sys.exit(1)

    token = config.DISCORD_TOKEN

    # Tier 1: Try starting with full intents (including Message Content)
    try:
        bot = QPBot(intents=make_intents(enable_message_content=True, enable_members=True))
        async with bot:
            await bot.start(token)
        return
    except discord.errors.PrivilegedIntentsRequired:
        print(
            "\n" + "=" * 65 + "\n"
            "⚠️ PRIVILEGED INTENT NOTICE:\n"
            "Discord rejected connection with 'Message Content Intent' enabled\n"
            "because it is not yet toggled ON in the Discord Developer Portal.\n\n"
            "👉 To enable direct question answering in #ask-ai:\n"
            "   1. Visit https://discord.com/developers/applications\n"
            "   2. Select your Application -> Click 'Bot' in the left menu\n"
            "   3. Under 'Privileged Gateway Intents', turn ON 'Message Content Intent'\n"
            "   4. Click 'Save Changes'\n\n"
            "🔄 Retrying startup with standard intents (Message Content disabled)...\n"
            "   Note: All slash commands (/ask-ai, /budget, etc.) work normally!\n"
            + "=" * 65 + "\n",
            file=sys.stderr,
        )

    # Tier 2: Fallback without Message Content intent (keeps Members intent)
    try:
        fallback_bot = QPBot(intents=make_intents(enable_message_content=False, enable_members=True))
        async with fallback_bot:
            await fallback_bot.start(token)
        return
    except discord.errors.PrivilegedIntentsRequired:
        print(
            "\n" + "=" * 65 + "\n"
            "⚠️ PRIVILEGED INTENT NOTICE:\n"
            "Discord also rejected 'Server Members Intent'.\n"
            "Retrying with basic intents (role synchronization may be limited)...\n"
            + "=" * 65 + "\n",
            file=sys.stderr,
        )

    # Tier 3: Safe minimal fallback
    minimal_bot = QPBot(intents=make_intents(enable_message_content=False, enable_members=False))
    async with minimal_bot:
        await minimal_bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot shut down cleanly.")
