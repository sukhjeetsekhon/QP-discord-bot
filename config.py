import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
MAX_TEAMS = int(os.getenv("MAX_TEAMS", "28"))
DEFAULT_TEAM_BUDGET = float(os.getenv("DEFAULT_TEAM_BUDGET", "50.0"))
IEEE_MEMBER_BONUS = float(os.getenv("IEEE_MEMBER_BONUS", "11.0"))

STAFF_ROLE_NAME = os.getenv("STAFF_ROLE_NAME", "QP Chair")

# List of staff/leadership roles that have access to review tickets, mentor queues, and workspaces
STAFF_ROLES = ["QP Chair", "Mentor", "Officer"]

TICKETS_CATEGORY_NAME = os.getenv("TICKETS_CATEGORY_NAME", "Hardware Requests")
MENTOR_CATEGORY_NAME = os.getenv("MENTOR_CATEGORY_NAME", "Help Requests")
AI_HELP_CHANNEL_NAME = os.getenv("AI_HELP_CHANNEL_NAME", "ask-ai")

# Optional: Specific Channel ID for the AI help channel
_ai_channel_id_env = os.getenv("AI_HELP_CHANNEL_ID")
AI_HELP_CHANNEL_ID = int(_ai_channel_id_env) if _ai_channel_id_env and _ai_channel_id_env.isdigit() else None

# Google Gemini API Settings (Free tier from Google AI Studio)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", "knowledge")

DB_PATH = os.getenv("DB_PATH", "data/qp_bot.db")

# Optional: Server/Guild ID for fast slash command sync
_guild_id_env = os.getenv("GUILD_ID")
GUILD_ID = int(_guild_id_env) if _guild_id_env and _guild_id_env.isdigit() else None
