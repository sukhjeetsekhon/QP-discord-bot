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
DB_PATH = os.getenv("DB_PATH", "data/qp_bot.db")

# Optional: Server/Guild ID for fast slash command sync
_guild_id_env = os.getenv("GUILD_ID")
GUILD_ID = int(_guild_id_env) if _guild_id_env and _guild_id_env.isdigit() else None
