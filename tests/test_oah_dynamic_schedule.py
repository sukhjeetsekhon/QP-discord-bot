"""
tests/test_oah_dynamic_schedule.py
Unit tests verifying dynamic schedule display:
- Today's schedule during daytime / open hours
- Midday gap reopening information
- Next active day schedule when today's shifts are finished (e.g. Mon night -> Tue)
- Next active day schedule on Thursday night / Friday / weekend -> Monday
- Interactive OAHView toggle behavior
"""

import datetime
import unittest
from unittest import mock
import discord

from cogs.open_access_hours import (
    get_oah_status,
    build_oah_embed,
    OAHView,
    OAHStatusResult,
    CALENDAR_URL,
    LOCATION_TEXT,
)

PST = datetime.timezone(datetime.timedelta(hours=-8), name="PST")


class TestOAHDynamicSchedule(unittest.TestCase):
    """Verifies dynamic schedule behavior and next active day calculations."""

    def test_monday_night_shows_tuesday_schedule(self):
        """Monday at 8:00 PM (after Nishant's shift ends at 7:30 PM) -> Should show Tuesday schedule."""
        dt = datetime.datetime(2026, 11, 2, 20, 0, tzinfo=PST)
        status = get_oah_status(dt)

        self.assertFalse(status.is_open)
        self.assertTrue(status.is_closed_for_day)
        self.assertEqual(status.next_active_day, "Tuesday")
        self.assertEqual(status.next_active_date, datetime.date(2026, 11, 3))
        self.assertEqual(len(status.next_active_shifts), 4)

        embed = build_oah_embed(status)
        embed_text = " ".join([embed.title or "", embed.description or ""] + [f.name + " " + f.value for f in embed.fields])
        self.assertIn("CLOSED FOR TODAY", embed_text)
        self.assertIn("Tuesday", embed_text)
        self.assertIn("Aiden", embed_text)
        self.assertIn("Anthony", embed_text)
        self.assertIn("Daniel H", embed_text)
        self.assertIn("Ki", embed_text)

    def test_thursday_night_shows_monday_schedule(self):
        """Thursday at 6:00 PM (after Daniel Xu's shift ends at 5:30 PM) -> Should show Monday schedule."""
        dt = datetime.datetime(2026, 11, 5, 18, 0, tzinfo=PST)
        status = get_oah_status(dt)

        self.assertFalse(status.is_open)
        self.assertTrue(status.is_closed_for_day)
        self.assertEqual(status.next_active_day, "Monday")
        self.assertEqual(status.next_active_date, datetime.date(2026, 11, 9))
        self.assertEqual(len(status.next_active_shifts), 3)

        embed = build_oah_embed(status)
        embed_text = " ".join([embed.title or "", embed.description or ""] + [f.name + " " + f.value for f in embed.fields])
        self.assertIn("CLOSED FOR TODAY", embed_text)
        self.assertIn("Next Schedule: Monday", embed_text)
        self.assertIn("Ridhi", embed_text)
        self.assertIn("Sukhjeet", embed_text)
        self.assertIn("Nishant", embed_text)

    def test_friday_shows_monday_schedule(self):
        """Friday at 2:00 PM (no shifts) -> Should show Monday schedule."""
        dt = datetime.datetime(2026, 11, 6, 14, 0, tzinfo=PST)
        status = get_oah_status(dt)

        self.assertFalse(status.is_open)
        self.assertTrue(status.is_weekend_or_friday)
        self.assertEqual(status.next_active_day, "Monday")
        self.assertEqual(status.next_active_date, datetime.date(2026, 11, 9))

        embed = build_oah_embed(status)
        embed_text = " ".join([embed.title or "", embed.description or ""] + [f.name + " " + f.value for f in embed.fields])
        self.assertIn("Next Schedule: Monday", embed_text)
        self.assertIn("Ridhi", embed_text)

    def test_saturday_shows_weekend_closed_and_monday_schedule(self):
        """Saturday at 1:00 PM -> CLOSED FOR THE WEEKEND and shows Monday schedule."""
        dt = datetime.datetime(2026, 11, 7, 13, 0, tzinfo=PST)
        status = get_oah_status(dt)

        self.assertFalse(status.is_open)
        self.assertTrue(status.is_weekend_or_friday)
        self.assertEqual(status.next_active_day, "Monday")

        embed = build_oah_embed(status)
        embed_text = " ".join([embed.title or "", embed.description or ""] + [f.name + " " + f.value for f in embed.fields])
        self.assertIn("CLOSED FOR THE WEEKEND", embed_text)
        self.assertIn("Next Schedule: Monday", embed_text)

    def test_midday_gap_shows_reopening_and_todays_schedule(self):
        """Monday at 2:00 PM (between Ridhi 11-1 and Sukhjeet 3-5) -> Shows Reopening Today and Monday's lineup."""
        dt = datetime.datetime(2026, 11, 2, 14, 0, tzinfo=PST)
        status = get_oah_status(dt)

        self.assertFalse(status.is_open)
        self.assertFalse(status.is_closed_for_day)
        self.assertIsNotNone(status.next_slot)
        self.assertIn("3:00 PM", status.reopening_info)
        self.assertIn("Sukhjeet", status.reopening_info)

        embed = build_oah_embed(status)
        embed_text = " ".join([embed.title or "", embed.description or ""] + [f.name + " " + f.value for f in embed.fields])
        self.assertIn("CURRENTLY CLOSED", embed_text)
        self.assertIn("Reopening Today", embed_text)
        self.assertIn("3:00 PM", embed_text)
        self.assertIn("Sukhjeet", embed_text)
        self.assertIn("Today's Schedule (Monday)", embed_text)

    def test_open_now_shows_active_officer_and_today_schedule(self):
        """Monday at 3:30 PM -> Open now with Sukhjeet on duty and Monday's lineup."""
        dt = datetime.datetime(2026, 11, 2, 15, 30, tzinfo=PST)
        status = get_oah_status(dt)

        self.assertTrue(status.is_open)
        self.assertEqual(len(status.current_officers), 1)
        self.assertEqual(status.current_officers[0]["name"], "Sukhjeet")

        embed = build_oah_embed(status)
        embed_text = " ".join([embed.title or "", embed.description or ""] + [f.name + " " + f.value for f in embed.fields])
        self.assertIn("OPEN NOW", embed_text)
        self.assertIn("Sukhjeet", embed_text)
        self.assertIn("QP Chair", embed_text)
        self.assertIn("Today's Schedule (Monday)", embed_text)

    def test_full_week_embed_flag(self):
        """When full_week=True is passed, embed contains the Full Weekly Schedule field."""
        dt = datetime.datetime(2026, 11, 2, 15, 30, tzinfo=PST)
        status = get_oah_status(dt)

        embed = build_oah_embed(status, full_week=True)
        field_names = [f.name for f in embed.fields]
        self.assertIn("📅 Full Weekly Schedule", field_names)

    def test_oah_view_button_toggle(self):
        """Verifies OAHView button initializes and toggles state."""
        dt = datetime.datetime(2026, 11, 2, 15, 30, tzinfo=PST)
        status = get_oah_status(dt)

        # Initial view with full_week=False
        view = OAHView(status=status, showing_full_week=False)
        self.assertEqual(len(view.children), 1)
        self.assertEqual(view.children[0].label, "View Full Week")

        # Initial view with full_week=True
        view_full = OAHView(status=status, showing_full_week=True)
        self.assertEqual(len(view_full.children), 1)
        self.assertEqual(view_full.children[0].label, "View Today / Next Day")


if __name__ == "__main__":
    unittest.main()
