import os
import glob
import asyncio
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
import discord
from discord import app_commands
from discord.ext import commands
from google import genai
from google.genai import types

import config
import database
from cogs.hardware_tickets import is_staff_or_admin


def get_gemini_client() -> Optional[genai.Client]:
    """Initialize and return a Gemini API client if API key is configured."""
    if not config.GEMINI_API_KEY:
        return None
    try:
        return genai.Client(api_key=config.GEMINI_API_KEY)
    except Exception as e:
        print(f"❌ Failed to initialize Gemini Client: {e}")
        return None


def load_all_knowledge() -> Tuple[str, Dict[str, Any]]:
    """
    Load static knowledge documents from knowledge/ and synced channel transcripts
    from the database cache.
    """
    knowledge_sections: List[str] = []
    doc_count = 0
    channel_count = 0

    # 1. Load static documents from knowledge directory
    knowledge_dir = config.KNOWLEDGE_DIR
    if os.path.exists(knowledge_dir):
        for ext in ("*.md", "*.txt"):
            for filepath in glob.glob(os.path.join(knowledge_dir, ext)):
                try:
                    filename = os.path.basename(filepath)
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().strip()
                    if content:
                        knowledge_sections.append(
                            f"=== DOCUMENT: {filename} ===\n{content}\n"
                        )
                        doc_count += 1
                except Exception as e:
                    print(f"⚠️ Error reading knowledge file {filepath}: {e}")

    # 2. Load cached channel transcripts from database
    cached_sources = database.get_all_knowledge_cache()
    for item in cached_sources:
        content = item.get("content", "").strip()
        source_name = item.get("source_name", "unknown")
        if content:
            knowledge_sections.append(
                f"=== SYNCED DISCORD CHANNEL: {source_name} (Updated {item.get('updated_at')}) ===\n{content}\n"
            )
            channel_count += 1

    combined_text = "\n\n".join(knowledge_sections)
    metadata = {
        "doc_count": doc_count,
        "channel_count": channel_count,
        "total_chars": len(combined_text),
    }
    return combined_text, metadata


def extract_grounding_sources(response) -> List[Tuple[str, str]]:
    """Extract web sources (title, uri) from Gemini grounding metadata if present."""
    sources: List[Tuple[str, str]] = []
    try:
        if response.candidates and response.candidates[0].grounding_metadata:
            meta = response.candidates[0].grounding_metadata
            chunks = getattr(meta, "grounding_chunks", None) or []
            seen_urls = set()
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if web and getattr(web, "uri", None):
                    uri = web.uri
                    title = getattr(web, "title", None) or uri
                    if uri not in seen_urls:
                        seen_urls.add(uri)
                        sources.append((title, uri))
    except Exception as e:
        print(f"Error parsing grounding metadata: {e}")
    return sources


def build_system_instruction(knowledge_base: str) -> str:
    """Construct the grounding system prompt for the Gemini model."""
    return (
        "You are the official IEEE Quarterly Projects (QP) AI Assistant for the UCSD IEEE Student Branch Discord server.\n"
        "Your purpose is to answer questions from students, teams, and mentors about the QP program, rules, hardware budgets, lab inventory, ticketing, timelines, and technical engineering advice.\n\n"
        "CRITICAL DISCORD FORMATTING & LENGTH RULES:\n"
        "- NO MARKDOWN TABLES: Discord does NOT render markdown tables (| col | col |). NEVER use tables under any circumstances. Present comparisons, pinouts, and tabular data using clean bulleted lists (e.g. '• **Pin A4:** SDA') or bold key-value pairs.\n"
        "- CONCISE LENGTH: Keep responses concise and focused (aim for under 1,500 characters). Avoid sprawling multi-page answers. The entire response should comfortably fit in a single clean Discord message without splitting.\n"
        "- BRIEF CODE SNIPPETS: When providing code, give only the essential 10-15 lines (e.g. pin definitions and setup calls). Never output huge 50+ line boilerplate sketches that get cut off.\n"
        "- DISCORD-COMPLIANT MARKDOWN: Use bold (**text**), italics (*text*), bullet points (- or •), sub-bullets (indented), headers (### Header), and inline code (`code`). Do NOT use HTML tags or LaTeX math ($).\n\n"
        "CRITICAL PROGRAM RULES & GUIDELINES:\n"
        "1. Competition Rules & Administration: Ground your answers in the provided QP Knowledge Base whenever possible for budgets, schedules, milestone deliverables, team sizes, and purchasing policies.\n"
        "2. Technical & Hardware Questions: For technical questions not explicitly in the QP Knowledge Base (microcontroller pinouts like ESP32/Arduino/RP2040, circuit schematics, sensors, I2C/SPI wiring, motor drivers, battery power, coding/debugging in C++/Python): Use your engineering knowledge to provide direct, practical, and accurate guidance.\n"
        "3. Hardware Budgets: Baseline is $50.00 per team, plus an additional +$11.00 for each verified IEEE student member on the team (e.g. $61 for 1 member, $72 for 2 members, etc.).\n"
        "4. Hardware Purchases: Handled via the '#hardware-requests' channel using the 'Request' button, which opens a private sequential ticket.\n"
        "5. Lab Equipment: Handled in the IEEE Student Lab using /checkout and /return.\n"
        "6. Mentorship / Help Queue: If a student needs in-person assistance with hardware debugging or design feedback, guide them to click 'Request Mentor Help / Feedback' in the #help-tickets channel.\n"
        "7. Administrative Exceptions: For decisions requiring human approval (like approving custom budget overages or granting exceptions), instruct the student to contact the QP Chair or open a help ticket.\n\n"
        f"=== OFFICIAL QP KNOWLEDGE BASE ===\n{knowledge_base}\n"
        "=== END OF KNOWLEDGE BASE ==="
    )


def chunk_message(text: str, max_length: int = 1850) -> List[str]:
    """
    Split response into chunks under Discord's 2000 character limit without breaking words,
    and automatically preserve code block formatting across message boundaries.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk = ""
    in_code_block = False
    current_lang = ""

    for line in lines:
        stripped_line = line.strip()
        is_code_toggle = stripped_line.startswith("```")

        # Reserve headroom for closing ```\n if currently in a code block
        overhead = 6 if in_code_block else 0
        if len(current_chunk) + len(line) + 1 + overhead <= max_length:
            current_chunk += (line + "\n")
            if is_code_toggle:
                in_code_block = not in_code_block
                if in_code_block:
                    current_lang = stripped_line[3:].strip()
                else:
                    current_lang = ""
        else:
            # Reached max length, need to split cleanly
            if in_code_block:
                # Close the code block in the current chunk
                current_chunk += "```\n"
                chunks.append(current_chunk.strip())
                # Reopen code block in the new chunk
                current_chunk = f"```{current_lang}\n{line}\n"
                if is_code_toggle:
                    in_code_block = False
                    current_lang = ""
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                # If a single line is excessively long, break by words
                if len(line) > max_length:
                    words = line.split(" ")
                    current_chunk = ""
                    for word in words:
                        if len(current_chunk) + len(word) + 1 <= max_length:
                            current_chunk += (word + " ")
                        else:
                            chunks.append(current_chunk.strip())
                            current_chunk = word + " "
                    current_chunk += "\n"
                else:
                    current_chunk = line + "\n"
                if is_code_toggle:
                    in_code_block = True
                    current_lang = stripped_line[3:].strip()

    if current_chunk.strip():
        if in_code_block:
            current_chunk += "```\n"
        chunks.append(current_chunk.strip())

    return chunks


class AIHelpCog(commands.Cog):
    """Cog for the QP AI Q&A Help Channel and knowledge base."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._cached_knowledge: str = ""
        self._cached_metadata: Dict[str, Any] = {}
        self.reload_knowledge()

    def reload_knowledge(self):
        """Reload documents and cached channel transcripts into memory."""
        self._cached_knowledge, self._cached_metadata = load_all_knowledge()

    async def generate_ai_response(self, user_prompt: str, conversation_context: Optional[List[str]] = None) -> str:
        """Call Google Gemini API using the grounding knowledge base."""
        client = get_gemini_client()
        if not client:
            return (
                "⚠️ **Gemini AI is not configured yet.**\n"
                "An administrator needs to add the `GEMINI_API_KEY` in the bot's `.env` or Azure Container App environment settings.\n"
                "Get a free API key at: https://aistudio.google.com/"
            )

        if not self._cached_knowledge:
            self.reload_knowledge()

        system_instruction = build_system_instruction(self._cached_knowledge)

        # Build prompt incorporating recent conversational turns if available
        contents: List[str] = []
        if conversation_context:
            context_str = "\n".join(conversation_context)
            contents.append(f"Recent conversation in #ask-ai:\n{context_str}\n\nLatest user question:\n{user_prompt}")
        else:
            contents.append(user_prompt)

        # Determine candidate models with automatic fallback
        candidate_models = [config.GEMINI_MODEL]
        for fallback_model in ("gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite"):
            if fallback_model not in candidate_models:
                candidate_models.append(fallback_model)

        use_search = config.ENABLE_WEB_SEARCH
        search_failed = False
        last_error = ""

        for model_name in candidate_models:
            tools = [types.Tool(google_search=types.GoogleSearch())] if (use_search and not search_failed) else None
            try:
                # Use non-blocking async Gemini client call
                response = await client.aio.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,
                        tools=tools,
                    ),
                )
                if response.text:
                    reply = response.text
                    # Append web sources if Google Search was performed
                    sources = extract_grounding_sources(response)
                    if sources:
                        sources_list = "\n".join(f"• [{title}]({uri})" for title, uri in sources[:3])
                        reply += f"\n\n🌐 **Web Sources:**\n{sources_list}"
                    return reply
                return "⚠️ I couldn't generate a response. Please try rephrasing your question!"
            except Exception as e:
                error_str = str(e)
                last_error = error_str
                print(f"⚠️ Gemini API Error with model '{model_name}' (tools={bool(tools)}): {error_str}")

                # If the call failed while tools were active (e.g. search quota limit on free tier),
                # disable search for the remaining session and immediately retry with pure model text generation
                if tools is not None:
                    print("ℹ️ Request with Google Search failed (unpaid tier has 0 search quota). Retrying with built-in engineering knowledge...")
                    search_failed = True
                    try:
                        fallback_resp = await client.aio.models.generate_content(
                            model=model_name,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                system_instruction=system_instruction,
                                temperature=0.7,
                            ),
                        )
                        if fallback_resp.text:
                            return fallback_resp.text
                    except Exception as retry_e:
                        error_str = str(retry_e)
                        last_error = error_str
                        print(f"⚠️ Gemini retry without tools also failed on '{model_name}': {error_str}")

                # Check if this error is permanently non-recoverable (e.g. invalid API key)
                is_non_recoverable = any(
                    kw in error_str.lower()
                    for kw in ("api_key_invalid", "unauthenticated", "invalid_argument", "401")
                )
                if not is_non_recoverable:
                    # Transient error: 503 (high demand), 429 (rate limit), 404 (unavailable), 500 (server)
                    continue
                break

        if any(kw in last_error.lower() for kw in ("503", "unavailable", "high demand", "overloaded")):
            return "⚠️ The AI service is currently experiencing high demand. Please try asking again in a moment!"
        if any(kw in last_error.lower() for kw in ("resourceexhausted", "quota", "429")):
            return "⚠️ The free Gemini API rate limit was momentarily reached. Please wait a minute and try again!"
        return f"⚠️ An error occurred while communicating with the AI service: `{last_error[:150]}`"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for questions in the dedicated #ask-ai channel or direct @mentions."""
        # 1. Ignore bot messages and webhooks
        if message.author.bot or message.webhook_id:
            return

        # 2. Check if this is the AI help channel or the bot was mentioned
        channel_name = message.channel.name.lower() if isinstance(message.channel, (discord.TextChannel, discord.Thread)) else ""
        is_ai_channel = (
            channel_name == config.AI_HELP_CHANNEL_NAME.lower()
            or (config.AI_HELP_CHANNEL_ID is not None and message.channel.id == config.AI_HELP_CHANNEL_ID)
        )
        is_bot_mentioned = bool(self.bot.user and self.bot.user in message.mentions)

        if not is_ai_channel and not is_bot_mentioned:
            return

        # 3. Clean content and handle mentions
        raw_text = message.clean_content or ""
        if self.bot.user:
            raw_text = raw_text.replace(f"@{self.bot.user.name}", "").replace(f"@{self.bot.user.display_name}", "")
        content = raw_text.strip()

        # Handle empty content (e.g. user typed in #ask-ai when Message Content intent is disabled in Developer Portal)
        if not content:
            if is_ai_channel and not self.bot.intents.message_content:
                await message.reply(
                    "💡 *To ask me a question, please use the `/ask-ai` slash command or @mention me (@QP Helper Bot) with your question!*\n"
                    "> *(Admins: To allow direct questions without @mentions, enable **Message Content Intent** in the [Discord Developer Portal](https://discord.com/developers/applications)).*",
                    mention_author=False,
                )
            return

        # Ignore command invocations
        if content.startswith(("/", "!")):
            return

        # 4. Trigger typing indicator and gather recent short-term context
        async with message.channel.typing():
            recent_context: List[str] = []
            try:
                async for prev_msg in message.channel.history(limit=5, before=message):
                    if prev_msg.author == self.bot.user:
                        recent_context.append(f"Assistant: {prev_msg.clean_content[:300]}")
                    elif not prev_msg.author.bot and prev_msg.clean_content.strip():
                        recent_context.append(f"{prev_msg.author.display_name}: {prev_msg.clean_content[:300]}")
                recent_context.reverse()
            except Exception as e:
                print(f"Error fetching channel history for context: {e}")

            # 5. Generate AI answer
            reply_text = await self.generate_ai_response(content, conversation_context=recent_context)

            # 6. Send reply (split across chunks if over 2000 characters)
            chunks = chunk_message(reply_text)
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await message.reply(chunk, mention_author=False)
                else:
                    await message.channel.send(chunk)

    @app_commands.command(
        name="ask-ai",
        description="Ask the QP AI Assistant a question about rules, budgets, hardware, or debugging.",
    )
    @app_commands.describe(
        question="What would you like to know about Quarterly Projects?",
        private="Whether the response should only be visible to you (default: False)",
    )
    async def ask_ai_command(
        self,
        interaction: discord.Interaction,
        question: str,
        private: bool = False,
    ):
        await interaction.response.defer(ephemeral=private)

        answer = await self.generate_ai_response(question.strip())
        chunks = chunk_message(answer)

        # Send first chunk via followup
        await interaction.followup.send(
            content=f"**Q:** {question}\n\n{chunks[0]}",
            ephemeral=private,
        )
        # Send any remaining chunks
        for chunk in chunks[1:]:
            await interaction.followup.send(content=chunk, ephemeral=private)

    @app_commands.command(
        name="sync-ai-knowledge",
        description="Index previous Discord channel messages into the AI knowledge base (Admin only).",
    )
    @app_commands.describe(
        channel="Specific channel to index (leave blank to index all public channels)",
        message_limit="Maximum messages to scan per channel (default: 150)",
    )
    @app_commands.default_permissions(administrator=True)
    async def sync_ai_knowledge(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        message_limit: int = 150,
    ):
        if not isinstance(interaction.user, discord.Member) or not is_staff_or_admin(interaction.user):
            await interaction.response.send_message(
                f"❌ Only Leadership ({', '.join(config.STAFF_ROLES)}) can run this command.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ This command must be run in a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        if not self.bot.intents.message_content:
            await interaction.followup.send(
                "⚠️ **Message Content Intent is required to index past messages!**\n\n"
                "Discord requires the privileged **Message Content Intent** to read historical messages in channels.\n"
                "Without it, Discord hides message content from the bot.\n\n"
                "**How to enable it:**\n"
                "1. Visit the [Discord Developer Portal](https://discord.com/developers/applications)\n"
                "2. Select your Application -> Click **Bot** on the left menu\n"
                "3. Under **Privileged Gateway Intents**, turn ON **Message Content Intent**\n"
                "4. Click **Save Changes**, then restart/redeploy the bot.\n\n"
                "*(Note: Static documents in the `knowledge/` directory and the `/ask-ai` slash command work right now without this intent!)*",
                ephemeral=True,
            )
            return

        target_channels: List[discord.TextChannel] = []
        if channel:
            target_channels.append(channel)
        else:
            # Common channels with useful knowledge
            candidate_keywords = ["announcement", "faq", "resource", "general", "guideline", "info", "hardware"]
            for ch in guild.text_channels:
                ch_name = ch.name.lower()
                # Skip team channels, bot logs, and private ticket channels
                if ch_name.startswith(("team-", "request-", "help-", "bot-", "admin")):
                    continue
                if any(kw in ch_name for kw in candidate_keywords):
                    target_channels.append(ch)

        if not target_channels:
            await interaction.followup.send(
                "⚠️ No suitable public channels found to index. Please specify a channel with `channel:#name`.",
                ephemeral=True,
            )
            return

        total_indexed_messages = 0
        synced_channel_names: List[str] = []

        for ch in target_channels:
            try:
                # Check bot permissions in channel
                perms = ch.permissions_for(guild.me)
                if not perms.read_messages or not perms.read_message_history:
                    continue

                msg_entries: List[str] = []
                async for msg in ch.history(limit=message_limit, oldest_first=True):
                    # Filter out bot messages, slash commands, or pure embeds
                    if msg.author.bot or msg.clean_content.startswith(("/", "!")):
                        continue
                    text = msg.clean_content.strip()
                    if text:
                        time_str = msg.created_at.strftime("%Y-%m-%d")
                        msg_entries.append(f"{msg.author.display_name} ({time_str}): {text}")

                if msg_entries:
                    channel_text = f"Channel: #{ch.name}\n" + "\n".join(msg_entries)
                    database.save_knowledge_cache(
                        source_type="channel",
                        source_name=f"#{ch.name}",
                        content=channel_text,
                        message_count=len(msg_entries),
                    )
                    total_indexed_messages += len(msg_entries)
                    synced_channel_names.append(f"#{ch.name} ({len(msg_entries)} msgs)")
            except Exception as e:
                print(f"Error scanning channel #{ch.name}: {e}")

        # Reload memory cache
        self.reload_knowledge()

        embed = discord.Embed(
            title="🧠 AI Knowledge Base Synced Successfully!",
            description=(
                f"Scanned and indexed **{total_indexed_messages}** messages into the QP AI knowledge cache.\n"
                f"The AI in **#{config.AI_HELP_CHANNEL_NAME}** can now reference these past discussions to answer student questions."
            ),
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )
        if synced_channel_names:
            embed.add_field(
                name="Synced Channels",
                value="\n".join(f"• {c}" for c in synced_channel_names),
                inline=False,
            )
        embed.add_field(
            name="Static Documents",
            value=f"{self._cached_metadata.get('doc_count', 0)} documents loaded from `knowledge/`",
            inline=True,
        )
        embed.add_field(
            name="Total Knowledge Size",
            value=f"{self._cached_metadata.get('total_chars', 0):,} characters",
            inline=True,
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="ai-status",
        description="View status of the QP AI Assistant, loaded documents, and synced channels.",
    )
    async def ai_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        has_api_key = bool(config.GEMINI_API_KEY)
        client_status = "🟢 Configured (Google Gemini)" if has_api_key else "🔴 Missing `GEMINI_API_KEY` in environment"

        embed = discord.Embed(
            title="🤖 QP AI Assistant Status",
            color=discord.Color.blue() if has_api_key else discord.Color.red(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="API Status", value=client_status, inline=False)
        embed.add_field(name="Gemini Model", value=f"`{config.GEMINI_MODEL}`", inline=True)
        embed.add_field(name="AI Channel Name", value=f"`#{config.AI_HELP_CHANNEL_NAME}`", inline=True)
        intent_status = "🟢 Active (Direct text reading enabled)" if self.bot.intents.message_content else "🟡 Disabled in Portal (Slash commands & @mentions only)"
        embed.add_field(name="Message Content Intent", value=intent_status, inline=False)
        web_search_status = "🟢 Enabled (Live Google Search Grounding)" if config.ENABLE_WEB_SEARCH else "⚪ Disabled"
        embed.add_field(name="Web Search", value=web_search_status, inline=True)

        # Knowledge sources
        cached_sources = database.get_all_knowledge_cache()
        doc_count = self._cached_metadata.get("doc_count", 0)
        total_chars = self._cached_metadata.get("total_chars", 0)

        embed.add_field(
            name="Static Documents",
            value=f"📄 **{doc_count}** files in `knowledge/` folder",
            inline=True,
        )
        embed.add_field(
            name="Synced Channels",
            value=f"💬 **{len(cached_sources)}** Discord channels cached in database",
            inline=True,
        )
        embed.add_field(
            name="Knowledge Base Size",
            value=f"📊 **{total_chars:,}** characters loaded into context",
            inline=True,
        )

        if cached_sources:
            summary = ", ".join(f"{s['source_name']} ({s.get('message_count', 0)} msgs)" for s in cached_sources[:5])
            if len(cached_sources) > 5:
                summary += f", and {len(cached_sources) - 5} more..."
            embed.add_field(name="Cached Channels", value=summary, inline=False)

        embed.set_footer(text="IEEE Quarterly Projects • AI Assistance")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AIHelpCog(bot))
