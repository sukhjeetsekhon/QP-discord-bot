"""
cogs/open_access_hours.py
Open Access Hours (OAH) Slash Command and Schedule Engine for IEEE QP Discord Bot.
"""

from dataclasses import dataclass, field
import datetime
import sys
from typing import Any, Dict, List, Optional
import discord
from discord import app_commands
from discord.ext import commands

CALENDAR_URL = "https://ieeeatucsd.org/join"
LOCATION_TEXT = "IEEE Project Space (Jacobs Hall 4710 / EBU1-4710, 4th Floor)"
LOCATION_STR = LOCATION_TEXT

WEEKLY_SCHEDULE_TEXT = (
    "**Monday**\n"
    "• 11:00 AM – 1:00 PM: Ridhi (VC Events)\n"
    "• 3:00 PM – 5:00 PM: Sukhjeet (QP Chair)\n"
    "• 5:30 PM – 7:30 PM: Nishant (Social Chair)\n\n"
    "**Tuesday**\n"
    "• 11:00 AM – 1:00 PM: Aiden (President)\n"
    "• 3:00 PM – 5:00 PM: Anthony (Design Chair)\n"
    "• 5:00 PM – 7:00 PM: Daniel H (Marketing Chair)\n"
    "• 5:00 PM – 8:00 PM: Ki (Webmaster)\n\n"
    "**Wednesday**\n"
    "• 10:00 AM – 12:00 PM: Hannah (VC Operations)\n\n"
    "**Thursday**\n"
    "• 10:00 AM – 12:00 PM: Paul (Social Chair)\n"
    "• 12:45 PM – 1:45 PM: Ki (Webmaster)\n"
    "• 2:00 PM – 4:00 PM: Cameryn (VP Internal)\n"
    "• 3:30 PM – 5:30 PM: Daniel Xu (VC Operations)\n\n"
    "**Friday – Sunday**\n"
    "• Closed *(No regular officer drop-in hours)*"
)


class _WindowsPacificTz(datetime.tzinfo):
    """Zero-dependency fallback for America/Los_Angeles with US Daylight Saving Time rules."""

    def utcoffset(self, dt: Optional[datetime.datetime]) -> datetime.timedelta:
        return datetime.timedelta(hours=-7) if self._is_dst(dt) else datetime.timedelta(hours=-8)

    def dst(self, dt: Optional[datetime.datetime]) -> datetime.timedelta:
        return datetime.timedelta(hours=1) if self._is_dst(dt) else datetime.timedelta(0)

    def tzname(self, dt: Optional[datetime.datetime]) -> str:
        return "PDT" if self._is_dst(dt) else "PST"

    def _is_dst(self, dt: Optional[datetime.datetime]) -> bool:
        if dt is None:
            return False
        year = dt.year
        # 2nd Sunday in March at 2:00 AM
        first_sun_mar = 1 + (6 - datetime.datetime(year, 3, 1).weekday()) % 7
        dst_start = datetime.datetime(year, 3, first_sun_mar + 7, 2, 0)
        # 1st Sunday in November at 2:00 AM
        first_sun_nov = 1 + (6 - datetime.datetime(year, 11, 1).weekday()) % 7
        dst_end = datetime.datetime(year, 11, first_sun_nov, 2, 0)
        naive = dt.replace(tzinfo=None)
        return dst_start <= naive < dst_end

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, _WindowsPacificTz)

    def __hash__(self) -> int:
        return hash("WindowsPacificTz")


_WINDOWS_PACIFIC_TZ_SINGLETON = _WindowsPacificTz()


def get_pacific_tz() -> datetime.tzinfo:
    """
    Returns the Pacific Timezone (America/Los_Angeles).
    Provides a Windows-safe zero-dependency fallback implementing US DST rules
    in case zoneinfo database or tzdata package is missing on Windows.
    """
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/Los_Angeles")
    except Exception:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo("US/Pacific")
        except Exception:
            pass

    return _WINDOWS_PACIFIC_TZ_SINGLETON


def get_current_pacific_time() -> datetime.datetime:
    """Returns current aware datetime in Pacific Time."""
    return datetime.datetime.now(get_pacific_tz())


def normalize_to_pacific(now: Optional[datetime.datetime] = None) -> datetime.datetime:
    """Normalize input datetime to Pacific Timezone."""
    tz = get_pacific_tz()
    if now is None:
        return datetime.datetime.now(tz)
    elif now.tzinfo is not None:
        return now.astimezone(tz)
    else:
        return now.replace(tzinfo=tz)


@dataclass(frozen=True)
class OAHShift:
    """Represents a scheduled Open Access Hours shift."""
    day: int  # 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday
    name: str
    role: str
    start_time: datetime.time
    end_time: datetime.time
    timeslot: str

    @property
    def officer(self) -> str:
        return self.name

    @property
    def start(self) -> datetime.time:
        return self.start_time

    @property
    def end(self) -> datetime.time:
        return self.end_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "officer": self.name,
            "role": self.role,
            "start": self.start_time,
            "end": self.end_time,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "timeslot": self.timeslot,
            "shift": self.timeslot,
        }


# Authoritative weekly schedule definition (knowledge/open_access_hours.md)
SCHEDULE: List[OAHShift] = [
    # Monday (0)
    OAHShift(0, "Ridhi", "VC Events", datetime.time(11, 0), datetime.time(13, 0), "11:00 AM – 1:00 PM"),
    OAHShift(0, "Sukhjeet", "QP Chair", datetime.time(15, 0), datetime.time(17, 0), "3:00 PM – 5:00 PM"),
    OAHShift(0, "Nishant", "Social Chair", datetime.time(17, 30), datetime.time(19, 30), "5:30 PM – 7:30 PM"),
    # Tuesday (1)
    OAHShift(1, "Aiden", "President", datetime.time(11, 0), datetime.time(13, 0), "11:00 AM – 1:00 PM"),
    OAHShift(1, "Anthony", "Design Chair", datetime.time(15, 0), datetime.time(17, 0), "3:00 PM – 5:00 PM"),
    OAHShift(1, "Daniel H", "Marketing Chair", datetime.time(17, 0), datetime.time(19, 0), "5:00 PM – 7:00 PM"),
    OAHShift(1, "Ki", "Webmaster", datetime.time(17, 0), datetime.time(20, 0), "5:00 PM – 8:00 PM"),
    # Wednesday (2)
    OAHShift(2, "Hannah", "VC Operations", datetime.time(10, 0), datetime.time(12, 0), "10:00 AM – 12:00 PM"),
    # Thursday (3)
    OAHShift(3, "Paul", "Social Chair", datetime.time(10, 0), datetime.time(12, 0), "10:00 AM – 12:00 PM"),
    OAHShift(3, "Ki", "Webmaster", datetime.time(12, 45), datetime.time(13, 45), "12:45 PM – 1:45 PM"),
    OAHShift(3, "Cameryn", "VP Internal", datetime.time(14, 0), datetime.time(16, 0), "2:00 PM – 4:00 PM"),
    OAHShift(3, "Daniel Xu", "VC Operations", datetime.time(15, 30), datetime.time(17, 30), "3:30 PM – 5:30 PM"),
]

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
OAH_SCHEDULE: Dict[str, List[Dict[str, Any]]] = {day: [] for day in DAY_NAMES}
for _shift in SCHEDULE:
    OAH_SCHEDULE[DAY_NAMES[_shift.day]].append(_shift.to_dict())


class OfficerInfo(str):
    """Represents an on-duty officer. Inherits from str for string operations and supports dict access."""
    name: str
    role: str
    timeslot: str
    shift: str

    def __new__(cls, name: str, role: str, timeslot: str):
        representation = f"{name} ({role})"
        instance = super().__new__(cls, representation)
        instance.name = name
        instance.role = role
        instance.timeslot = timeslot
        instance.shift = timeslot
        return instance

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            if item in ("name", "officer"):
                return self.name
            elif item == "role":
                return self.role
            elif item in ("timeslot", "shift"):
                return self.timeslot
            raise KeyError(item)
        return super().__getitem__(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default


class NextSlotInfo(str):
    """Represents the next upcoming timeslot today. Inherits from str and supports dict access."""
    start_time: datetime.time
    timeslot: str
    time_str: str
    officers: List[Dict[str, str]]
    description: str

    def __new__(
        cls,
        start_time: datetime.time,
        timeslot: str,
        officers: List[Dict[str, str]],
        description: str = "",
    ):
        if not description:
            names = ", ".join(f"{o['name']} ({o['role']})" for o in officers)
            description = f"{timeslot}: {names}"
        instance = super().__new__(cls, description)
        instance.start_time = start_time
        instance.timeslot = timeslot
        instance.time_str = timeslot
        instance.officers = officers
        instance.description = description
        return instance

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, str):
            if item in ("timeslot", "time_str"):
                return self.timeslot
            elif item == "start_time":
                return self.start_time
            elif item == "officers":
                return self.officers
            elif item == "description":
                return self.description
            raise KeyError(item)
        return super().__getitem__(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default


@dataclass
class OAHStatusResult:
    """Evaluation result for Open Access Hours."""
    is_open: bool
    current_officers: List[Any]
    next_slot: Optional[Any] = None
    today_schedule: List[Any] = field(default_factory=list)
    full_schedule: Dict[str, Any] = field(default_factory=lambda: OAH_SCHEDULE)
    evaluated_time: Optional[datetime.datetime] = None
    current_time: Optional[datetime.datetime] = None
    # Enhanced dynamic scheduling attributes
    next_active_day: str = ""
    next_active_date: Optional[datetime.date] = None
    next_active_shifts: List[Any] = field(default_factory=list)
    is_closed_for_day: bool = False
    is_weekend_or_friday: bool = False
    reopening_info: Optional[str] = None

    def __post_init__(self):
        if self.evaluated_time is None and self.current_time is not None:
            self.evaluated_time = self.current_time
        elif self.current_time is None and self.evaluated_time is not None:
            self.current_time = self.evaluated_time

    def __getitem__(self, item: str) -> Any:
        """Allow dict-like subscripting for backward compatibility."""
        return getattr(self, item)


def get_oah_status(now: Optional[datetime.datetime] = None) -> OAHStatusResult:
    """
    Evaluates whether the IEEE Project Space is currently OPEN or CLOSED.
    Uses half-open intervals [start, end) where exact start is open and exact end is closed.
    Supports concurrent shifts, calculates the next upcoming timeslot today,
    and identifies the next active day when all shifts for today have finished (or on Friday/weekends).
    """
    if now is None:
        dt_pac = get_current_pacific_time()
    else:
        dt_pac = normalize_to_pacific(now)

    day_idx = dt_pac.weekday()
    current_time = dt_pac.time()

    # Shifts for today
    today_shifts = [s for s in SCHEDULE if s.day == day_idx]

    # Half-open interval check: start_time <= current_time < end_time
    active_shifts = [
        s for s in today_shifts
        if s.start_time <= current_time < s.end_time
    ]
    is_open = len(active_shifts) > 0

    current_officers = [
        OfficerInfo(s.name, s.role, s.timeslot)
        for s in active_shifts
    ]

    # Next timeslot today: earliest shift start where start_time > current_time
    future_shifts = [s for s in today_shifts if s.start_time > current_time]
    next_slot: Optional[NextSlotInfo] = None
    reopening_info: Optional[str] = None

    if future_shifts:
        earliest_start = min(s.start_time for s in future_shifts)
        concurrent_next = [s for s in future_shifts if s.start_time == earliest_start]
        officers_list = [
            {"name": s.name, "role": s.role, "timeslot": s.timeslot, "shift": s.timeslot}
            for s in concurrent_next
        ]
        timeslot_str = concurrent_next[0].timeslot
        if len(officers_list) == 1:
            desc = f"{timeslot_str}: {officers_list[0]['name']} ({officers_list[0]['role']})"
            reopening_info = f"Reopens today at **{timeslot_str}** with **{officers_list[0]['name']}** ({officers_list[0]['role']})"
        else:
            names_roles = ", ".join(f"{o['name']} ({o['role']})" for o in officers_list)
            desc = f"{timeslot_str}: {names_roles}"
            reopening_info = f"Reopens today at **{timeslot_str}** with **{names_roles}**"

        next_slot = NextSlotInfo(
            start_time=earliest_start,
            timeslot=timeslot_str,
            officers=officers_list,
            description=desc,
        )

    # Calculate Next Active Day (if shifts are done today or today is Friday/weekend)
    is_weekend_or_friday = day_idx in (4, 5, 6)
    is_closed_for_day = (not is_open) and (len(future_shifts) == 0)

    next_active_day = ""
    next_active_date: Optional[datetime.date] = None
    next_active_shifts: List[Any] = []

    for i in range(1, 8):
        cand_date = dt_pac.date() + datetime.timedelta(days=i)
        cand_day_idx = cand_date.weekday()
        cand_shifts = [s for s in SCHEDULE if s.day == cand_day_idx]
        if cand_shifts:
            next_active_day = DAY_NAMES[cand_day_idx]
            next_active_date = cand_date
            next_active_shifts = [s.to_dict() for s in cand_shifts]
            break

    return OAHStatusResult(
        is_open=is_open,
        current_officers=current_officers,
        next_slot=next_slot,
        today_schedule=[s.to_dict() for s in today_shifts],
        full_schedule=OAH_SCHEDULE,
        evaluated_time=dt_pac,
        current_time=dt_pac,
        next_active_day=next_active_day,
        next_active_date=next_active_date,
        next_active_shifts=next_active_shifts,
        is_closed_for_day=is_closed_for_day,
        is_weekend_or_friday=is_weekend_or_friday,
        reopening_info=reopening_info,
    )


def format_shift_lines(shifts: List[Any]) -> str:
    """Format a list of shift dictionaries into clean bullet points."""
    if not shifts:
        return "• None scheduled"
    lines = []
    for s in shifts:
        name = s.get("name") or s.get("officer")
        role = s.get("role")
        slot = s.get("timeslot") or s.get("shift")
        lines.append(f"• **{slot}**: {name} ({role})")
    return "\n".join(lines)


def build_oah_embed(status: OAHStatusResult, full_week: bool = False) -> discord.Embed:
    """Build a rich Discord Embed representing the current OAH status, today/next day schedule, or full week."""
    eval_time = (
        status.evaluated_time
        or status.current_time
        or datetime.datetime.now(datetime.timezone.utc)
    )
    day_name = eval_time.strftime("%A") if eval_time else ""

    if status.is_open:
        color = discord.Color.green()
        status_text = "🟢 **OPEN NOW**"
    elif status.is_weekend_or_friday:
        color = discord.Color.red()
        status_text = "🔴 **CLOSED FOR THE WEEKEND**" if eval_time.weekday() in (5, 6) else "🔴 **CURRENTLY CLOSED**"
    elif status.is_closed_for_day:
        color = discord.Color.red()
        status_text = "🔴 **CLOSED FOR TODAY**"
    else:
        # Midday gap or pre-shift
        color = discord.Color.red()
        status_text = "🔴 **CURRENTLY CLOSED**"

    embed = discord.Embed(
        title="IEEE Project Space — Open Access Hours",
        description=(
            f"📍 **Location:** {LOCATION_TEXT}\n"
            f"🔗 **Live Calendar:** {CALENDAR_URL}\n\n"
            "Drop in to work on projects, solder under supervision, use lab equipment, "
            "or get project advice from IEEE officers!"
        ),
        color=color,
        timestamp=eval_time,
    )

    # 1. Status Indicator
    embed.add_field(name="Current Status", value=status_text, inline=True)

    # 2. Officers on Duty
    if status.is_open and status.current_officers:
        lines = []
        for off in status.current_officers:
            if isinstance(off, dict) or hasattr(off, "get"):
                name = off.get("name") or str(off)
                role = off.get("role")
                slot = off.get("timeslot") or off.get("shift")
                if role and slot:
                    lines.append(f"• **{name}** ({role}) — *{slot}*")
                elif role:
                    lines.append(f"• **{name}** ({role})")
                else:
                    lines.append(f"• **{name}**")
            else:
                lines.append(f"• **{off}**")
        officers_text = "\n".join(lines)
    else:
        officers_text = "None *(Lab is closed)*"
    embed.add_field(name="👤 Officer(s) on Duty", value=officers_text, inline=True)

    # 3. Next Timeslot / Reopening Field
    if status.is_open:
        if status.next_slot:
            next_text = f"• **{status.next_slot}**"
        else:
            next_text = "No further shifts scheduled for today."
        embed.add_field(name="⏰ Next Timeslot Today", value=next_text, inline=False)
    elif status.next_slot:
        # Reopening today
        reopen_text = status.reopening_info or f"Reopens at **{status.next_slot}**"
        embed.add_field(name="⏰ Reopening Today", value=reopen_text, inline=False)
    else:
        # No further shifts today or weekend
        if status.is_weekend_or_friday:
            next_text = f"The lab is closed today. Next Open Access Hours are on **{status.next_active_day}**."
        else:
            next_text = f"All shifts for today have finished. Next Open Access Hours are on **{status.next_active_day}**."
        embed.add_field(name="⏰ Next Timeslot Today", value=next_text, inline=False)

    # 4. Schedule Section (Today's / Next Active Day's OR Full Week)
    if full_week:
        embed.add_field(name="📅 Full Weekly Schedule", value=WEEKLY_SCHEDULE_TEXT, inline=False)
    else:
        if status.is_open or (status.next_slot and status.today_schedule):
            # Focus on today's schedule
            today_text = format_shift_lines(status.today_schedule)
            embed.add_field(
                name=f"📅 Today's Schedule ({day_name})",
                value=today_text,
                inline=False,
            )
        else:
            # Shifts for today are done, or it's Friday/weekend: Focus on Next Active Day!
            date_str = status.next_active_date.strftime("%b %d") if status.next_active_date else ""
            header = f"📅 Next Schedule: {status.next_active_day}" + (f" ({date_str})" if date_str else "")
            next_shifts_text = format_shift_lines(status.next_active_shifts)
            embed.add_field(
                name=header,
                value=next_shifts_text,
                inline=False,
            )

    embed.set_footer(text="IEEE Quarterly Projects • Open Access Hours • All times Pacific (PT)")
    return embed


format_oah_embed = build_oah_embed


class OAHView(discord.ui.View):
    """Interactive controls on /oah to toggle between Today/Next Day and Full Week schedules."""

    def __init__(self, status: OAHStatusResult, showing_full_week: bool = False):
        super().__init__(timeout=300)
        self.status = status
        self.showing_full_week = showing_full_week
        self._sync_buttons()

    def _sync_buttons(self):
        self.clear_items()
        if self.showing_full_week:
            btn = discord.ui.Button(
                label="View Today / Next Day",
                emoji="⏰",
                style=discord.ButtonStyle.primary,
                custom_id="qp:oah_toggle_today",
            )
            btn.callback = self.toggle_view
            self.add_item(btn)
        else:
            btn = discord.ui.Button(
                label="View Full Week",
                emoji="📅",
                style=discord.ButtonStyle.secondary,
                custom_id="qp:oah_toggle_full",
            )
            btn.callback = self.toggle_view
            self.add_item(btn)

    async def toggle_view(self, interaction: discord.Interaction):
        self.showing_full_week = not self.showing_full_week
        self._sync_buttons()
        new_embed = build_oah_embed(self.status, full_week=self.showing_full_week)
        await interaction.response.edit_message(embed=new_embed, view=self)


class OpenAccessHoursCog(commands.Cog):
    """Cog providing the on-demand /oah slash command for Open Access Hours."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="oah",
        description="Check Open Access Hours (OAH) status for the IEEE Project Space",
    )
    @app_commands.describe(
        full_week="Show the complete weekly schedule for Monday through Thursday (default: False)",
        private="Whether the response should only be visible to you (default: False)",
    )
    async def oah(
        self,
        interaction: discord.Interaction,
        full_week: bool = False,
        private: bool = False,
    ):
        """Slash command to display the current OAH status, on-duty officers, and schedule."""
        try:
            status = get_oah_status()
            embed = build_oah_embed(status, full_week=full_week)
            view = OAHView(status=status, showing_full_week=full_week)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=private)
        except Exception as e:
            print(f"❌ Error in /oah command: {e}", file=sys.stderr)
            msg = (
                "⚠️ An error occurred while retrieving the Open Access Hours schedule. "
                f"Please check the live calendar at {CALENDAR_URL}."
            )
            is_done = False
            if hasattr(interaction.response, "is_done"):
                try:
                    done_val = interaction.response.is_done()
                    if hasattr(done_val, "close") and callable(done_val.close):
                        done_val.close()
                    if isinstance(done_val, bool):
                        is_done = done_val
                    elif hasattr(done_val, "return_value") and isinstance(done_val.return_value, bool):
                        is_done = done_val.return_value
                except Exception:
                    is_done = False

            if not is_done:
                await interaction.response.send_message(content=msg, ephemeral=True)
            else:
                await interaction.followup.send(content=msg, ephemeral=True)


OpenAccessHours = OpenAccessHoursCog


async def setup(bot: commands.Bot):
    """Extension entry point for bot.py."""
    await bot.add_cog(OpenAccessHoursCog(bot))
