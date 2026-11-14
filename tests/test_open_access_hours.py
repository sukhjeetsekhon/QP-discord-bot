"""Unit and mock tests for Open Access Hours (OAH) cog, schedule engine, and /oah command."""

import datetime
import unittest
from unittest import mock
import discord
from discord.ext import commands

from cogs.open_access_hours import (
    OpenAccessHoursCog,
    get_oah_status,
    build_oah_embed,
    format_oah_embed,
    get_pacific_tz,
    get_current_pacific_time,
    _WindowsPacificTz,
    SCHEDULE,
    OAH_SCHEDULE,
    OAHShift,
    OAHStatusResult,
    CALENDAR_URL,
    LOCATION_TEXT,
)

# Deterministic Pacific Timezones for testing
PST = datetime.timezone(datetime.timedelta(hours=-8), name="PST")
PDT = datetime.timezone(datetime.timedelta(hours=-7), name="PDT")


class TestOAHScheduleDataAndConstants(unittest.TestCase):
    """Validates schedule definitions against knowledge/open_access_hours.md."""

    def test_total_shift_count(self):
        """Verifies exactly 12 shifts are defined across the week."""
        self.assertEqual(len(SCHEDULE), 12)

    def test_shifts_per_day(self):
        """Verifies shift distribution: Mon: 3, Tue: 4, Wed: 1, Thu: 4, Fri-Sun: 0."""
        day_counts = {i: 0 for i in range(7)}
        for shift in SCHEDULE:
            day_counts[shift.day] += 1

        self.assertEqual(day_counts[0], 3, "Monday must have 3 shifts")
        self.assertEqual(day_counts[1], 4, "Tuesday must have 4 shifts")
        self.assertEqual(day_counts[2], 1, "Wednesday must have 1 shift")
        self.assertEqual(day_counts[3], 4, "Thursday must have 4 shifts")
        self.assertEqual(day_counts[4], 0, "Friday must have 0 shifts")
        self.assertEqual(day_counts[5], 0, "Saturday must have 0 shifts")
        self.assertEqual(day_counts[6], 0, "Sunday must have 0 shifts")

    def test_shift_interval_validity(self):
        """Verifies start_time < end_time for all shifts."""
        for shift in SCHEDULE:
            start_min = shift.start_time.hour * 60 + shift.start_time.minute
            end_min = shift.end_time.hour * 60 + shift.end_time.minute
            self.assertLess(start_min, end_min, f"Shift {shift} has invalid interval")

    def test_officer_names_and_roles(self):
        """Verifies that expected officers and roles are represented in schedule."""
        officers = {s.name: s.role for s in SCHEDULE}
        self.assertEqual(officers.get("Ridhi"), "VC Events")
        self.assertEqual(officers.get("Sukhjeet"), "QP Chair")
        self.assertEqual(officers.get("Nishant"), "Social Chair")
        self.assertEqual(officers.get("Aiden"), "President")
        self.assertEqual(officers.get("Anthony"), "Design Chair")
        self.assertEqual(officers.get("Daniel H"), "Marketing Chair")
        self.assertEqual(officers.get("Ki"), "Webmaster")
        self.assertEqual(officers.get("Hannah"), "VC Operations")
        self.assertEqual(officers.get("Paul"), "Social Chair")
        self.assertEqual(officers.get("Cameryn"), "VP Internal")
        self.assertEqual(officers.get("Daniel Xu"), "VC Operations")


class TestOAHTimezoneEngine(unittest.TestCase):
    """Validates Pacific Time conversion and fallback resilience."""

    def test_get_pacific_tz_returns_tzinfo(self):
        tz = get_pacific_tz()
        self.assertIsInstance(tz, datetime.tzinfo)

    def test_timezone_fallback_when_zoneinfo_missing(self):
        """Simulates ZoneInfoNotFoundError on Windows and asserts graceful fallback."""
        import zoneinfo
        with mock.patch("zoneinfo.ZoneInfo", side_effect=zoneinfo.ZoneInfoNotFoundError("Missing")):
            tz = get_pacific_tz()
            self.assertIsNotNone(tz)
            self.assertIsInstance(tz, datetime.tzinfo)

    def test_utc_to_pacific_conversion(self):
        """Verifies UTC 19:00 on Nov 2 (PST) converts to 11:00 AM Pacific."""
        utc_dt = datetime.datetime(2026, 11, 2, 19, 0, tzinfo=datetime.timezone.utc)
        status = get_oah_status(utc_dt)
        self.assertTrue(status.is_open)
        self.assertTrue(any("Ridhi" in o for o in status.current_officers))

    def test_windows_fallback_tz_dst_and_standard(self):
        """Directly tests _WindowsPacificTz DST calculation."""
        tz = _WindowsPacificTz()
        # Summer (July 1, 2026) -> PDT (UTC-7)
        summer_dt = datetime.datetime(2026, 7, 1, 12, 0, tzinfo=tz)
        self.assertEqual(summer_dt.utcoffset(), datetime.timedelta(hours=-7))
        self.assertEqual(summer_dt.tzname(), "PDT")

        # Winter (December 1, 2026) -> PST (UTC-8)
        winter_dt = datetime.datetime(2026, 12, 1, 12, 0, tzinfo=tz)
        self.assertEqual(winter_dt.utcoffset(), datetime.timedelta(hours=-8))
        self.assertEqual(winter_dt.tzname(), "PST")


class TestOAHScheduleEvaluatorBoundaries(unittest.TestCase):
    """Validates half-open intervals, gaps, concurrent shifts, and next slot logic."""

    # --- Monday Tests ---
    def test_monday_1059_am_closed_pre_shift(self):
        dt = datetime.datetime(2026, 11, 2, 10, 59, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertEqual(res.current_officers, [])
        self.assertIsNotNone(res.next_slot)
        self.assertIn("Ridhi", str(res.next_slot))
        self.assertIn("11:00 AM", str(res.next_slot))

    def test_monday_1100_am_open_exact_start(self):
        dt = datetime.datetime(2026, 11, 2, 11, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        self.assertTrue(any("Ridhi" in o for o in res.current_officers))
        self.assertIsNotNone(res.next_slot)
        self.assertIn("Sukhjeet", str(res.next_slot))
        self.assertIn("3:00 PM", str(res.next_slot))

    def test_monday_1200_pm_open_midpoint(self):
        dt = datetime.datetime(2026, 11, 2, 12, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        self.assertTrue(any("Ridhi" in o for o in res.current_officers))
        self.assertIn("Sukhjeet", str(res.next_slot))

    def test_monday_100_pm_closed_exact_end(self):
        dt = datetime.datetime(2026, 11, 2, 13, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertEqual(res.current_officers, [])
        self.assertIn("Sukhjeet", str(res.next_slot))

    def test_monday_200_pm_closed_gap(self):
        dt = datetime.datetime(2026, 11, 2, 14, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertIn("Sukhjeet", str(res.next_slot))

    def test_monday_300_pm_open(self):
        dt = datetime.datetime(2026, 11, 2, 15, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        self.assertTrue(any("Sukhjeet" in o for o in res.current_officers))
        self.assertIn("Nishant", str(res.next_slot))

    def test_monday_500_pm_closed_between_shifts(self):
        dt = datetime.datetime(2026, 11, 2, 17, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertIn("Nishant", str(res.next_slot))

    def test_monday_530_pm_open(self):
        dt = datetime.datetime(2026, 11, 2, 17, 30, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        self.assertTrue(any("Nishant" in o for o in res.current_officers))
        self.assertIsNone(res.next_slot)

    def test_monday_730_pm_closed_exact_end(self):
        dt = datetime.datetime(2026, 11, 2, 19, 30, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertIsNone(res.next_slot)

    def test_monday_1159_pm_closed_late_night(self):
        dt = datetime.datetime(2026, 11, 2, 23, 59, 59, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertIsNone(res.next_slot)

    # --- Tuesday Tests (Concurrent Shifts) ---
    def test_tuesday_1100_am_open(self):
        dt = datetime.datetime(2026, 11, 3, 11, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        self.assertTrue(any("Aiden" in o for o in res.current_officers))
        self.assertIn("Anthony", str(res.next_slot))

    def test_tuesday_400_pm_next_slot_concurrent(self):
        """Anthony is on duty at 4:00 PM; next slot at 5:00 PM has both Daniel H & Ki."""
        dt = datetime.datetime(2026, 11, 3, 16, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        self.assertTrue(any("Anthony" in o for o in res.current_officers))
        self.assertIsNotNone(res.next_slot)
        next_str = str(res.next_slot)
        self.assertIn("Daniel H", next_str)
        self.assertIn("Ki", next_str)
        self.assertIn("5:00 PM", next_str)

    def test_tuesday_500_pm_handoff_and_simultaneous_start(self):
        dt = datetime.datetime(2026, 11, 3, 17, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        officer_names = " ".join(res.current_officers)
        self.assertIn("Daniel H", officer_names)
        self.assertIn("Ki", officer_names)
        self.assertNotIn("Anthony", officer_names)
        self.assertIsNone(res.next_slot)

    def test_tuesday_530_pm_concurrent_shift(self):
        dt = datetime.datetime(2026, 11, 3, 17, 30, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        officer_names = " ".join(res.current_officers)
        self.assertIn("Daniel H", officer_names)
        self.assertIn("Ki", officer_names)
        self.assertIsNone(res.next_slot)

    def test_tuesday_700_pm_partial_transition_boundary(self):
        dt = datetime.datetime(2026, 11, 3, 19, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        officer_names = " ".join(res.current_officers)
        self.assertIn("Ki", officer_names)
        self.assertNotIn("Daniel H", officer_names)
        self.assertIsNone(res.next_slot)

    def test_tuesday_730_pm_partial_transition_midpoint(self):
        dt = datetime.datetime(2026, 11, 3, 19, 30, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        officer_names = " ".join(res.current_officers)
        self.assertIn("Ki", officer_names)
        self.assertNotIn("Daniel H", officer_names)
        self.assertIsNone(res.next_slot)

    def test_tuesday_800_pm_closed_exact_end(self):
        dt = datetime.datetime(2026, 11, 3, 20, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertEqual(res.current_officers, [])
        self.assertIsNone(res.next_slot)

    def test_tuesday_801_pm_closed_after_hours(self):
        dt = datetime.datetime(2026, 11, 3, 20, 1, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertIsNone(res.next_slot)

    # --- Wednesday Tests ---
    def test_wednesday_900_am_closed_pre_shift(self):
        dt = datetime.datetime(2026, 11, 4, 9, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertIsNotNone(res.next_slot)
        self.assertIn("Hannah", str(res.next_slot))

    def test_wednesday_1000_am_open(self):
        dt = datetime.datetime(2026, 11, 4, 10, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        self.assertTrue(any("Hannah" in o for o in res.current_officers))
        self.assertIsNone(res.next_slot)

    def test_wednesday_1200_pm_closed(self):
        dt = datetime.datetime(2026, 11, 4, 12, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertIsNone(res.next_slot)

    # --- Thursday Tests (Staggered Overlaps & Non-round times) ---
    def test_thursday_1000_am_open(self):
        dt = datetime.datetime(2026, 11, 5, 10, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        self.assertTrue(any("Paul" in o for o in res.current_officers))
        self.assertIn("Ki", str(res.next_slot))

    def test_thursday_1200_pm_closed(self):
        dt = datetime.datetime(2026, 11, 5, 12, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertIn("Ki", str(res.next_slot))
        self.assertIn("12:45 PM", str(res.next_slot))

    def test_thursday_1245_pm_open_non_round(self):
        dt = datetime.datetime(2026, 11, 5, 12, 45, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        self.assertTrue(any("Ki" in o for o in res.current_officers))
        self.assertIn("Cameryn", str(res.next_slot))

    def test_thursday_145_pm_closed_non_round(self):
        dt = datetime.datetime(2026, 11, 5, 13, 45, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertIn("Cameryn", str(res.next_slot))

    def test_thursday_200_pm_open(self):
        dt = datetime.datetime(2026, 11, 5, 14, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        self.assertTrue(any("Cameryn" in o for o in res.current_officers))
        self.assertIn("Daniel Xu", str(res.next_slot))

    def test_thursday_330_pm_overlap_start(self):
        dt = datetime.datetime(2026, 11, 5, 15, 30, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        officer_names = " ".join(res.current_officers)
        self.assertIn("Cameryn", officer_names)
        self.assertIn("Daniel Xu", officer_names)

    def test_thursday_345_pm_concurrent_shift(self):
        dt = datetime.datetime(2026, 11, 5, 15, 45, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        officer_names = " ".join(res.current_officers)
        self.assertIn("Cameryn", officer_names)
        self.assertIn("Daniel Xu", officer_names)

    def test_thursday_400_pm_transition(self):
        dt = datetime.datetime(2026, 11, 5, 16, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        officer_names = " ".join(res.current_officers)
        self.assertIn("Daniel Xu", officer_names)
        self.assertNotIn("Cameryn", officer_names)

    def test_thursday_530_pm_closed_exact_end(self):
        dt = datetime.datetime(2026, 11, 5, 17, 30, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertIsNone(res.next_slot)

    # --- Friday & Weekend Tests ---
    def test_friday_200_pm_closed_all_day(self):
        dt = datetime.datetime(2026, 11, 6, 14, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertEqual(res.current_officers, [])
        self.assertIsNone(res.next_slot)

    def test_saturday_closed(self):
        dt = datetime.datetime(2026, 11, 7, 12, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertEqual(res.current_officers, [])
        self.assertIsNone(res.next_slot)

    def test_sunday_1200_pm_closed_weekend(self):
        dt = datetime.datetime(2026, 11, 8, 12, 0, tzinfo=PST)
        res = get_oah_status(dt)
        self.assertFalse(res.is_open)
        self.assertEqual(res.current_officers, [])
        self.assertIsNone(res.next_slot)

    # --- DST (PDT) Test ---
    def test_daylight_saving_pdt_open(self):
        dt = datetime.datetime(2026, 10, 19, 11, 0, tzinfo=PDT)
        res = get_oah_status(dt)
        self.assertTrue(res.is_open)
        self.assertTrue(any("Ridhi" in o for o in res.current_officers))


class TestOAHEmbedFormatting(unittest.TestCase):
    """Validates embed fields, colors, links, and table prohibitions."""

    def test_embed_open_status_and_color(self):
        res = OAHStatusResult(
            is_open=True,
            current_officers=["Ridhi (VC Events)"],
            next_slot="3:00 PM – 5:00 PM: Sukhjeet (QP Chair)",
            today_schedule=[],
            full_schedule={},
            current_time=datetime.datetime(2026, 11, 2, 11, 0, tzinfo=PST),
        )
        embed = build_oah_embed(res)
        self.assertIn(embed.color.value, (0x2ECC71, 0x57F287))
        self.assertIn("OPEN", embed.title + " " + "".join(f.name + f.value for f in embed.fields))
        self.assertIn("Ridhi", "".join(f.value for f in embed.fields))

    def test_embed_closed_status_and_color(self):
        res = OAHStatusResult(
            is_open=False,
            current_officers=[],
            next_slot="11:00 AM – 1:00 PM: Ridhi (VC Events)",
            today_schedule=[],
            full_schedule={},
            current_time=datetime.datetime(2026, 11, 2, 10, 0, tzinfo=PST),
        )
        embed = build_oah_embed(res)
        self.assertIn(embed.color.value, (0xE74C3C, 0xED4245))
        self.assertIn("CLOSED", embed.title + " " + "".join(f.name + f.value for f in embed.fields))

    def test_embed_contains_location_and_calendar_link(self):
        res = get_oah_status(datetime.datetime(2026, 11, 2, 11, 0, tzinfo=PST))
        embed = build_oah_embed(res)
        full_text = (embed.description or "") + " " + " ".join(f.value for f in embed.fields)
        self.assertIn("https://ieeeatucsd.org/join", full_text)
        self.assertIn("Jacobs Hall 4710", full_text)
        self.assertIn("EBU1-4710", full_text)
        self.assertIn("4th Floor", full_text)

    def test_embed_strictly_forbids_markdown_tables(self):
        """Asserts NO pipe table characters (| or |---) appear in embed description or fields."""
        res = get_oah_status(datetime.datetime(2026, 11, 2, 11, 0, tzinfo=PST))
        embed = build_oah_embed(res)
        if embed.description:
            self.assertNotIn("|---", embed.description)
            self.assertNotIn("| Col |", embed.description)
            self.assertNotIn("|", embed.description)
        for field in embed.fields:
            self.assertNotIn("|---", field.value)
            self.assertNotIn("| Col |", field.value)
            self.assertNotIn("|", field.value)

    def test_embed_field_lengths_within_limits(self):
        """Asserts all embed fields comply with Discord length limits."""
        res = get_oah_status(datetime.datetime(2026, 11, 2, 11, 0, tzinfo=PST))
        embed = build_oah_embed(res)
        total_len = len(embed.title or "") + len(embed.description or "")
        for field in embed.fields:
            self.assertLessEqual(len(field.name), 256)
            self.assertLessEqual(len(field.value), 1024)
            total_len += len(field.name) + len(field.value)
        self.assertLessEqual(total_len, 6000)


class TestOAHSlashCommandInteraction(unittest.IsolatedAsyncioTestCase):
    """Validates /oah slash command callback execution via mock discord.Interaction."""

    async def asyncSetUp(self):
        self.bot = mock.MagicMock(spec=commands.Bot)
        self.cog = OpenAccessHoursCog(self.bot)

    async def test_oah_command_success_open(self):
        interaction = mock.AsyncMock(spec=discord.Interaction)
        interaction.response = mock.AsyncMock()
        interaction.response.is_done = mock.MagicMock(return_value=False)
        interaction.followup = mock.AsyncMock()

        fixed_now = datetime.datetime(2026, 11, 2, 11, 30, tzinfo=PST)
        with mock.patch("cogs.open_access_hours.get_current_pacific_time", return_value=fixed_now):
            if hasattr(self.cog.oah, "callback"):
                await self.cog.oah.callback(self.cog, interaction)
            else:
                await self.cog.oah(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)
        self.assertIn("OPEN", embed.title + " " + "".join(f.name + f.value for f in embed.fields))

    async def test_oah_command_success_closed(self):
        interaction = mock.AsyncMock(spec=discord.Interaction)
        interaction.response = mock.AsyncMock()
        interaction.response.is_done = mock.MagicMock(return_value=False)
        interaction.followup = mock.AsyncMock()

        fixed_now = datetime.datetime(2026, 11, 6, 14, 0, tzinfo=PST)
        with mock.patch("cogs.open_access_hours.get_current_pacific_time", return_value=fixed_now):
            if hasattr(self.cog.oah, "callback"):
                await self.cog.oah.callback(self.cog, interaction)
            else:
                await self.cog.oah(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        embed = kwargs.get("embed")
        self.assertIsNotNone(embed)
        self.assertIn("CLOSED", embed.title + " " + "".join(f.name + f.value for f in embed.fields))

    async def test_oah_command_error_handling(self):
        """Verifies unexpected errors produce a safe user response without raising unhandled exception."""
        interaction = mock.AsyncMock(spec=discord.Interaction)
        interaction.response = mock.AsyncMock()
        interaction.response.is_done = mock.MagicMock(return_value=False)
        interaction.followup = mock.AsyncMock()

        with mock.patch("cogs.open_access_hours.get_oah_status", side_effect=RuntimeError("Internal test failure")):
            if hasattr(self.cog.oah, "callback"):
                await self.cog.oah.callback(self.cog, interaction)
            else:
                await self.cog.oah(interaction)

        interaction.response.send_message.assert_awaited_once()
        _, kwargs = interaction.response.send_message.call_args
        sent_content = str(kwargs.get("content", "")) + str(kwargs.get("embed", ""))
        self.assertTrue(len(sent_content) > 0)


class TestOAHNegativeConstraints(unittest.TestCase):
    """Validates architectural boundaries: no background briefings, no role gates."""

    def setUp(self):
        self.bot = mock.MagicMock(spec=commands.Bot)
        self.cog = OpenAccessHoursCog(self.bot)

    def test_no_background_tasks(self):
        """Verifies cog has no discord.ext.tasks.loop instances."""
        from discord.ext import tasks
        for attr_name in dir(self.cog):
            attr = getattr(self.cog, attr_name)
            self.assertNotIsInstance(attr, tasks.Loop, f"Cog has background task loop: {attr_name}")

    def test_command_has_no_role_checks(self):
        """Verifies /oah is public and has no restrictive permissions checks."""
        cmd = getattr(self.cog, "oah")
        checks = getattr(cmd, "checks", [])
        self.assertEqual(len(checks), 0, "Slash command /oah should have no role permission checks")


if __name__ == "__main__":
    unittest.main()
