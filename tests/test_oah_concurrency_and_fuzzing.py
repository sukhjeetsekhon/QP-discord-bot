"""
tests/test_oah_concurrency_and_fuzzing.py
Adversarial Stress, Boundary Fuzzing, and Concurrency Test Suite for /oah.
Authored by Challenger 2 for Milestone 1.

Verifies:
1. High-precision microsecond boundaries for all 12 rostered shifts (-1us, exact, +1us).
2. Overlap start/end transitions (Tuesday 5:00 PM, 7:00 PM, 8:00 PM; Thursday 3:30 PM, 4:00 PM).
3. Timezone edge cases: UTC day crossing rollback, DST transitions, fractional timezones, naive vs aware datetimes.
4. Slash command execution simulation under concurrent asynchronous mock interactions.
5. Invariant fuzzing across 2,500 random timestamps spanning 2024 to 2028.
"""

import asyncio
import datetime
import random
import unittest
from unittest import mock

import discord
from cogs.open_access_hours import (
    CALENDAR_URL,
    LOCATION_TEXT,
    OAH_SCHEDULE,
    SCHEDULE,
    OpenAccessHoursCog,
    _WindowsPacificTz,
    build_oah_embed,
    get_oah_status,
    get_pacific_tz,
    normalize_to_pacific,
)


class TestOAHMicrosecondBoundariesAllShifts(unittest.TestCase):
    """Stress-tests microsecond boundaries across every shift in SCHEDULE."""

    def setUp(self):
        self.tz = get_pacific_tz()
        # Representative test dates for Monday through Thursday
        self.mon = datetime.date(2026, 11, 2)
        self.tue = datetime.date(2026, 11, 3)
        self.wed = datetime.date(2026, 11, 4)
        self.thu = datetime.date(2026, 11, 5)

    def test_all_12_shifts_microsecond_delta_precision(self):
        """
        Tests every shift at -1us, exact start, +1us, -1us from end, exact end, and +1us.
        Enforces strict half-open interval [start, end) semantics.
        """
        day_dates = {0: self.mon, 1: self.tue, 2: self.wed, 3: self.thu}

        for shift in SCHEDULE:
            d = day_dates[shift.day]
            st = shift.start_time
            et = shift.end_time

            # 1. 1 microsecond before start_time: target shift MUST NOT be active
            dt_before_start = datetime.datetime.combine(
                d, st, tzinfo=self.tz
            ) - datetime.timedelta(microseconds=1)
            res_before = get_oah_status(dt_before_start)
            active_before = [o["name"] for o in res_before.current_officers]
            self.assertNotIn(
                shift.name,
                active_before,
                f"Shift {shift.name} ({shift.timeslot}) erroneously active at {dt_before_start} (T_start - 1us)",
            )

            # 2. Exactly at start_time: target shift MUST be active
            dt_exact_start = datetime.datetime.combine(d, st, tzinfo=self.tz)
            res_exact = get_oah_status(dt_exact_start)
            self.assertTrue(
                res_exact.is_open,
                f"Lab must be OPEN at exact start {dt_exact_start} for {shift.name}",
            )
            active_exact = [o["name"] for o in res_exact.current_officers]
            self.assertIn(
                shift.name,
                active_exact,
                f"Shift {shift.name} not in active officers at exact start {dt_exact_start}",
            )

            # 3. 1 microsecond after start_time: target shift MUST be active
            dt_after_start = dt_exact_start + datetime.timedelta(microseconds=1)
            res_after = get_oah_status(dt_after_start)
            active_after = [o["name"] for o in res_after.current_officers]
            self.assertIn(
                shift.name,
                active_after,
                f"Shift {shift.name} not active at {dt_after_start} (T_start + 1us)",
            )

            # 4. 1 microsecond before end_time: target shift MUST still be active
            dt_before_end = datetime.datetime.combine(
                d, et, tzinfo=self.tz
            ) - datetime.timedelta(microseconds=1)
            res_before_end = get_oah_status(dt_before_end)
            active_before_end = [o["name"] for o in res_before_end.current_officers]
            self.assertIn(
                shift.name,
                active_before_end,
                f"Shift {shift.name} must still be active at {dt_before_end} (T_end - 1us)",
            )

            # 5. Exactly at end_time: target shift MUST NOT be active
            dt_exact_end = datetime.datetime.combine(d, et, tzinfo=self.tz)
            res_exact_end = get_oah_status(dt_exact_end)
            active_exact_end = [o["name"] for o in res_exact_end.current_officers]
            self.assertNotIn(
                shift.name,
                active_exact_end,
                f"Shift {shift.name} must NOT be active at exact end {dt_exact_end}",
            )

            # 6. 1 microsecond after end_time: target shift MUST NOT be active
            dt_after_end = dt_exact_end + datetime.timedelta(microseconds=1)
            res_after_end = get_oah_status(dt_after_end)
            active_after_end = [o["name"] for o in res_after_end.current_officers]
            self.assertNotIn(
                shift.name,
                active_after_end,
                f"Shift {shift.name} must NOT be active at {dt_after_end} (T_end + 1us)",
            )

    def test_non_round_minute_microsecond_transitions(self):
        """Validates microsecond precision on shifts starting or ending at non-zero minutes."""
        # Thursday Ki: 12:45 PM – 1:45 PM
        t_pre = datetime.datetime(2026, 11, 5, 12, 44, 59, 999999, tzinfo=self.tz)
        res_pre = get_oah_status(t_pre)
        self.assertFalse(res_pre.is_open)
        self.assertIsNotNone(res_pre.next_slot)
        self.assertEqual(res_pre.next_slot.start_time, datetime.time(12, 45))

        t_start = datetime.datetime(2026, 11, 5, 12, 45, 0, 0, tzinfo=self.tz)
        res_start = get_oah_status(t_start)
        self.assertTrue(res_start.is_open)
        self.assertEqual(res_start.current_officers[0]["name"], "Ki")
        self.assertEqual(res_start.next_slot.start_time, datetime.time(14, 0))

        t_pre_end = datetime.datetime(2026, 11, 5, 13, 44, 59, 999999, tzinfo=self.tz)
        res_pre_end = get_oah_status(t_pre_end)
        self.assertTrue(res_pre_end.is_open)
        self.assertEqual(res_pre_end.current_officers[0]["name"], "Ki")

        t_end = datetime.datetime(2026, 11, 5, 13, 45, 0, 0, tzinfo=self.tz)
        res_end = get_oah_status(t_end)
        self.assertFalse(res_end.is_open)
        self.assertEqual(res_end.next_slot.start_time, datetime.time(14, 0))

        # Monday Nishant: 5:30 PM – 7:30 PM (17:30 - 19:30)
        t_nish_pre = datetime.datetime(2026, 11, 2, 17, 29, 59, 999999, tzinfo=self.tz)
        r_nish_pre = get_oah_status(t_nish_pre)
        self.assertFalse(r_nish_pre.is_open)
        self.assertEqual(r_nish_pre.next_slot.start_time, datetime.time(17, 30))

        t_nish_start = datetime.datetime(2026, 11, 2, 17, 30, 0, 0, tzinfo=self.tz)
        r_nish_start = get_oah_status(t_nish_start)
        self.assertTrue(r_nish_start.is_open)
        self.assertEqual(r_nish_start.current_officers[0]["name"], "Nishant")
        self.assertIsNone(r_nish_start.next_slot)


class TestOAHOverlapTransitionsMicrosecond(unittest.TestCase):
    """Stress-tests overlapping shifts and multi-officer handoffs at microsecond resolution."""

    def setUp(self):
        self.tz = get_pacific_tz()
        self.tue = datetime.date(2026, 11, 3)
        self.thu = datetime.date(2026, 11, 5)

    def test_tuesday_handoff_and_staggered_concurrent_shifts(self):
        """
        Tuesday:
        - Anthony: 3:00 PM – 5:00 PM (15:00 – 17:00)
        - Daniel H: 5:00 PM – 7:00 PM (17:00 – 19:00)
        - Ki: 5:00 PM – 8:00 PM (17:00 – 20:00)
        """
        # 1. 16:59:59.999999 -> Anthony active (1), next slot 5:00 PM (Daniel H & Ki)
        t1 = datetime.datetime(2026, 11, 3, 16, 59, 59, 999999, tzinfo=self.tz)
        r1 = get_oah_status(t1)
        self.assertTrue(r1.is_open)
        self.assertEqual(len(r1.current_officers), 1)
        self.assertEqual(r1.current_officers[0]["name"], "Anthony")
        self.assertIsNotNone(r1.next_slot)
        self.assertEqual(len(r1.next_slot.officers), 2)
        next_names = [o["name"] for o in r1.next_slot.officers]
        self.assertIn("Daniel H", next_names)
        self.assertIn("Ki", next_names)

        # 2. 17:00:00.000000 -> Anthony ends, Daniel H & Ki start simultaneously (2 active), next slot None
        t2 = datetime.datetime(2026, 11, 3, 17, 0, 0, 0, tzinfo=self.tz)
        r2 = get_oah_status(t2)
        self.assertTrue(r2.is_open)
        self.assertEqual(len(r2.current_officers), 2)
        active_names = [o["name"] for o in r2.current_officers]
        self.assertIn("Daniel H", active_names)
        self.assertIn("Ki", active_names)
        self.assertNotIn("Anthony", active_names)
        self.assertIsNone(r2.next_slot)

        # 3. 18:59:59.999999 -> Daniel H and Ki both active (2), next slot None
        t3 = datetime.datetime(2026, 11, 3, 18, 59, 59, 999999, tzinfo=self.tz)
        r3 = get_oah_status(t3)
        self.assertTrue(r3.is_open)
        self.assertEqual(len(r3.current_officers), 2)

        # 4. 19:00:00.000000 -> Daniel H ends, Ki remains active until 20:00 (1 active)
        t4 = datetime.datetime(2026, 11, 3, 19, 0, 0, 0, tzinfo=self.tz)
        r4 = get_oah_status(t4)
        self.assertTrue(r4.is_open)
        self.assertEqual(len(r4.current_officers), 1)
        self.assertEqual(r4.current_officers[0]["name"], "Ki")
        self.assertIsNone(r4.next_slot)

        # 5. 19:59:59.999999 -> Ki active (1)
        t5 = datetime.datetime(2026, 11, 3, 19, 59, 59, 999999, tzinfo=self.tz)
        r5 = get_oah_status(t5)
        self.assertTrue(r5.is_open)
        self.assertEqual(len(r5.current_officers), 1)

        # 6. 20:00:00.000000 -> Ki ends, lab CLOSED (0 active)
        t6 = datetime.datetime(2026, 11, 3, 20, 0, 0, 0, tzinfo=self.tz)
        r6 = get_oah_status(t6)
        self.assertFalse(r6.is_open)
        self.assertEqual(len(r6.current_officers), 0)
        self.assertIsNone(r6.next_slot)

    def test_thursday_staggered_overlap(self):
        """
        Thursday:
        - Cameryn: 2:00 PM – 4:00 PM (14:00 – 16:00)
        - Daniel Xu: 3:30 PM – 5:30 PM (15:30 – 17:30)
        Overlap window: 3:30 PM – 4:00 PM.
        """
        # 1. 15:29:59.999999 -> Cameryn active (1), next slot 3:30 PM (Daniel Xu)
        t1 = datetime.datetime(2026, 11, 5, 15, 29, 59, 999999, tzinfo=self.tz)
        r1 = get_oah_status(t1)
        self.assertTrue(r1.is_open)
        self.assertEqual(len(r1.current_officers), 1)
        self.assertEqual(r1.current_officers[0]["name"], "Cameryn")
        self.assertIsNotNone(r1.next_slot)
        self.assertEqual(r1.next_slot.start_time, datetime.time(15, 30))

        # 2. 15:30:00.000000 -> Both Cameryn and Daniel Xu active (2), next slot None
        t2 = datetime.datetime(2026, 11, 5, 15, 30, 0, 0, tzinfo=self.tz)
        r2 = get_oah_status(t2)
        self.assertTrue(r2.is_open)
        self.assertEqual(len(r2.current_officers), 2)
        names = [o["name"] for o in r2.current_officers]
        self.assertIn("Cameryn", names)
        self.assertIn("Daniel Xu", names)
        self.assertIsNone(r2.next_slot)

        # 3. 15:59:59.999999 -> Both Cameryn and Daniel Xu active (2)
        t3 = datetime.datetime(2026, 11, 5, 15, 59, 59, 999999, tzinfo=self.tz)
        r3 = get_oah_status(t3)
        self.assertTrue(r3.is_open)
        self.assertEqual(len(r3.current_officers), 2)

        # 4. 16:00:00.000000 -> Cameryn ends, Daniel Xu active (1)
        t4 = datetime.datetime(2026, 11, 5, 16, 0, 0, 0, tzinfo=self.tz)
        r4 = get_oah_status(t4)
        self.assertTrue(r4.is_open)
        self.assertEqual(len(r4.current_officers), 1)
        self.assertEqual(r4.current_officers[0]["name"], "Daniel Xu")
        self.assertIsNone(r4.next_slot)

        # 5. 17:29:59.999999 -> Daniel Xu active (1)
        t5 = datetime.datetime(2026, 11, 5, 17, 29, 59, 999999, tzinfo=self.tz)
        r5 = get_oah_status(t5)
        self.assertTrue(r5.is_open)
        self.assertEqual(len(r5.current_officers), 1)

        # 6. 17:30:00.000000 -> Daniel Xu ends, lab closed (0)
        t6 = datetime.datetime(2026, 11, 5, 17, 30, 0, 0, tzinfo=self.tz)
        r6 = get_oah_status(t6)
        self.assertFalse(r6.is_open)
        self.assertEqual(len(r6.current_officers), 0)
        self.assertIsNone(r6.next_slot)


class TestOAHTimezoneDSTAndDayCrossings(unittest.TestCase):
    """Stress-tests timezone conversions, day rollback from UTC, international timezones, and DST."""

    def test_utc_crossing_day_boundary_backward(self):
        """
        UTC Tuesday 02:00:00 UTC (PDT is UTC-7) corresponds to Monday 19:00:00 PDT.
        Monday 19:00 PDT is within Nishant's shift (5:30 PM - 7:30 PM).
        """
        dt_utc = datetime.datetime(2026, 7, 7, 2, 0, 0, tzinfo=datetime.timezone.utc)
        res = get_oah_status(dt_utc)
        self.assertTrue(res.is_open)
        self.assertEqual(len(res.current_officers), 1)
        self.assertEqual(res.current_officers[0]["name"], "Nishant")
        self.assertEqual(res.evaluated_time.strftime("%A"), "Monday")

    def test_utc_crossing_day_boundary_thursday_to_friday(self):
        """
        UTC Friday 00:00:00 UTC (PDT is UTC-7) corresponds to Thursday 17:00:00 PDT.
        Thursday 17:00 PDT is within Daniel Xu's shift (3:30 PM - 5:30 PM).
        """
        dt_utc = datetime.datetime(2026, 7, 10, 0, 0, 0, tzinfo=datetime.timezone.utc)
        res = get_oah_status(dt_utc)
        self.assertTrue(res.is_open)
        self.assertEqual(len(res.current_officers), 1)
        self.assertEqual(res.current_officers[0]["name"], "Daniel Xu")
        self.assertEqual(res.evaluated_time.strftime("%A"), "Thursday")

    def test_utc_crossing_into_weekend_closed(self):
        """
        UTC Monday 05:00:00 UTC (PST is UTC-8) corresponds to Sunday 21:00:00 PST.
        Sunday is closed all day.
        """
        dt_utc = datetime.datetime(2026, 11, 2, 5, 0, 0, tzinfo=datetime.timezone.utc)
        res = get_oah_status(dt_utc)
        self.assertFalse(res.is_open)
        self.assertEqual(len(res.current_officers), 0)
        self.assertIsNone(res.next_slot)

    def test_international_timezones_fractional_offsets(self):
        """Tests conversions from arbitrary worldwide timezones, including half-hour and 45-minute offsets."""
        # 1. Tokyo (JST, UTC+9): Wednesday 2026-07-08 03:00 JST -> Tuesday 2026-07-07 11:00 PDT (Aiden)
        jst = datetime.timezone(datetime.timedelta(hours=9))
        dt_jst = datetime.datetime(2026, 7, 8, 3, 0, 0, tzinfo=jst)
        res_jst = get_oah_status(dt_jst)
        self.assertTrue(res_jst.is_open)
        self.assertEqual(res_jst.current_officers[0]["name"], "Aiden")

        # 2. Kolkata (IST, UTC+5:30): Tuesday 2026-07-07 23:30 IST -> Tuesday 2026-07-07 11:00 PDT (Aiden)
        ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        dt_ist = datetime.datetime(2026, 7, 7, 23, 30, 0, tzinfo=ist)
        res_ist = get_oah_status(dt_ist)
        self.assertTrue(res_ist.is_open)
        self.assertEqual(res_ist.current_officers[0]["name"], "Aiden")

        # 3. Kathmandu (NPT, UTC+5:45): Tuesday 2026-07-07 23:45 NPT -> Tuesday 2026-07-07 11:00 PDT (Aiden)
        npt = datetime.timezone(datetime.timedelta(hours=5, minutes=45))
        dt_npt = datetime.datetime(2026, 7, 7, 23, 45, 0, tzinfo=npt)
        res_npt = get_oah_status(dt_npt)
        self.assertTrue(res_npt.is_open)
        self.assertEqual(res_npt.current_officers[0]["name"], "Aiden")

        # 4. Chatham Islands (CHAST, UTC+12:45): Wednesday 2026-07-08 06:45 -> Tuesday 2026-07-07 11:00 PDT (Aiden)
        chast = datetime.timezone(datetime.timedelta(hours=12, minutes=45))
        dt_chast = datetime.datetime(2026, 7, 8, 6, 45, 0, tzinfo=chast)
        res_chast = get_oah_status(dt_chast)
        self.assertTrue(res_chast.is_open)
        self.assertEqual(res_chast.current_officers[0]["name"], "Aiden")

    def test_dst_transitions_spring_forward_and_fall_back(self):
        """
        Verifies DST transition boundaries:
        - 2026 Spring Forward: Sunday March 8, 2026 (lab closed all day)
        - Monday immediately following Spring Forward: March 9, 2026 at 11:00 AM PDT (UTC 18:00) -> Ridhi
        - 2026 Fall Back: Sunday November 1, 2026 (lab closed all day)
        - Monday immediately following Fall Back: November 2, 2026 at 11:00 AM PST (UTC 19:00) -> Ridhi
        """
        # Sunday March 8 2026
        dt_sun_spring = datetime.datetime(2026, 3, 8, 12, 0, tzinfo=get_pacific_tz())
        res_sun_spring = get_oah_status(dt_sun_spring)
        self.assertFalse(res_sun_spring.is_open)

        # Monday March 9 2026 11:00 AM PDT (UTC 18:00)
        dt_mon_spring_utc = datetime.datetime(2026, 3, 9, 18, 0, tzinfo=datetime.timezone.utc)
        res_mon_spring = get_oah_status(dt_mon_spring_utc)
        self.assertTrue(res_mon_spring.is_open)
        self.assertEqual(res_mon_spring.current_officers[0]["name"], "Ridhi")

        # Sunday November 1 2026
        dt_sun_fall = datetime.datetime(2026, 11, 1, 12, 0, tzinfo=get_pacific_tz())
        res_sun_fall = get_oah_status(dt_sun_fall)
        self.assertFalse(res_sun_fall.is_open)

        # Monday November 2 2026 11:00 AM PST (UTC 19:00)
        dt_mon_fall_utc = datetime.datetime(2026, 11, 2, 19, 0, tzinfo=datetime.timezone.utc)
        res_mon_fall = get_oah_status(dt_mon_fall_utc)
        self.assertTrue(res_mon_fall.is_open)
        self.assertEqual(res_mon_fall.current_officers[0]["name"], "Ridhi")

    def test_naive_datetime_handling(self):
        """Ensures naive datetime input is safely converted to Pacific Time without raising TypeError."""
        naive_dt = datetime.datetime(2026, 11, 4, 10, 30)  # Wednesday 10:30
        res = get_oah_status(naive_dt)
        self.assertTrue(res.is_open)
        self.assertEqual(res.current_officers[0]["name"], "Hannah")
        self.assertEqual(res.evaluated_time.tzinfo, get_pacific_tz())

    def test_windows_fallback_tz_on_monday_shifts(self):
        """Ensures _WindowsPacificTz behaves correctly for both PDT and PST shifts."""
        fallback_tz = _WindowsPacificTz()
        # PDT Monday 11:00 AM: July 6, 2026
        pdt_dt = datetime.datetime(2026, 7, 6, 11, 0, tzinfo=fallback_tz)
        res_pdt = get_oah_status(pdt_dt)
        self.assertTrue(res_pdt.is_open)
        self.assertEqual(res_pdt.current_officers[0]["name"], "Ridhi")

        # PST Monday 11:00 AM: December 7, 2026
        pst_dt = datetime.datetime(2026, 12, 7, 11, 0, tzinfo=fallback_tz)
        res_pst = get_oah_status(pst_dt)
        self.assertTrue(res_pst.is_open)
        self.assertEqual(res_pst.current_officers[0]["name"], "Ridhi")


class TestOAHAsyncConcurrency(unittest.IsolatedAsyncioTestCase):
    """Stress-tests slash command execution under high-concurrency async invocations."""

    async def test_concurrent_slash_command_burst_100(self):
        """Simulates 100 concurrent users firing /oah simultaneously."""
        bot_mock = mock.MagicMock(spec=discord.Client)
        cog = OpenAccessHoursCog(bot_mock)

        interactions = []
        for i in range(100):
            inter = mock.AsyncMock(spec=discord.Interaction)
            inter.response = mock.AsyncMock()
            inter.followup = mock.AsyncMock()
            inter.user = mock.MagicMock()
            inter.user.id = 1000 + i
            interactions.append(inter)

        async def invoke_oah(inter):
            if hasattr(cog.oah, "callback"):
                await cog.oah.callback(cog, inter)
            else:
                await cog.oah(inter)

        async def run_cmd(inter):
            # Introduce small async jitter to simulate network interleaving
            await asyncio.sleep(random.uniform(0.001, 0.01))
            await invoke_oah(inter)

        tasks = [run_cmd(inter) for inter in interactions]
        await asyncio.gather(*tasks)

        # Verify all 100 interactions received an embed response cleanly
        for i, inter in enumerate(interactions):
            self.assertEqual(
                inter.response.send_message.call_count,
                1,
                f"Interaction {i} should have sent exactly 1 message",
            )
            kwargs = inter.response.send_message.call_args.kwargs
            self.assertIn("embed", kwargs)
            embed = kwargs["embed"]
            self.assertIsInstance(embed, discord.Embed)
            self.assertIn(CALENDAR_URL, embed.description)
            self.assertIn(LOCATION_TEXT, embed.description)
            # Ensure no pipe markdown tables in any field
            for f in embed.fields:
                self.assertNotIn("|", f.value)

    async def test_concurrent_mixed_failures_and_successes(self):
        """Simulates concurrent interactions where some fail internally and must fall back safely."""
        bot_mock = mock.MagicMock(spec=discord.Client)
        cog = OpenAccessHoursCog(bot_mock)

        interactions = []
        for i in range(50):
            inter = mock.AsyncMock(spec=discord.Interaction)
            inter.response = mock.AsyncMock()
            inter.followup = mock.AsyncMock()
            # Alternating responses: half already done, half not done
            inter.response.is_done = mock.MagicMock(return_value=(i % 2 == 1))
            interactions.append(inter)

        call_count = 0

        def flaky_get_oah():
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:
                raise RuntimeError("Simulated transient internal failure")
            return get_oah_status()

        with mock.patch("cogs.open_access_hours.get_oah_status", side_effect=flaky_get_oah):
            async def run_flaky(inter):
                await asyncio.sleep(0.001)
                if hasattr(cog.oah, "callback"):
                    await cog.oah.callback(cog, inter)
                else:
                    await cog.oah(inter)

            tasks = [run_flaky(inter) for inter in interactions]
            # Should complete without any unhandled exception propagating
            await asyncio.gather(*tasks)

        for inter in interactions:
            total_sends = (
                inter.response.send_message.call_count + inter.followup.send.call_count
            )
            self.assertEqual(total_sends, 1)


class TestOAHFuzzingInvariants(unittest.TestCase):
    """Adversarial random fuzzing harness verifying invariants across 2,500 dates and times."""

    def test_2500_random_timestamps_fuzzing(self):
        """
        Generates 2,500 randomized datetimes spanning 2024 to 2028 (including leap years and DST boundaries).
        Validates core mathematical and domain invariants on each evaluation.
        """
        rng = random.Random(42)  # Deterministic seed for reproducibility
        tz = get_pacific_tz()

        start_ts = int(datetime.datetime(2024, 1, 1, 0, 0, tzinfo=tz).timestamp())
        end_ts = int(datetime.datetime(2028, 12, 31, 23, 59, tzinfo=tz).timestamp())

        for i in range(2500):
            random_ts = rng.randint(start_ts, end_ts)
            random_us = rng.randint(0, 999999)
            dt = datetime.datetime.fromtimestamp(random_ts, tz=tz).replace(microsecond=random_us)

            res = get_oah_status(dt)
            weekday = dt.weekday()
            cur_time = dt.time()

            # Invariant 1: Type safety
            self.assertIsInstance(res.is_open, bool)
            self.assertIsInstance(res.current_officers, list)
            self.assertIsInstance(res.today_schedule, list)

            # Invariant 2: Friday (4), Saturday (5), Sunday (6) MUST ALWAYS be CLOSED
            if weekday in (4, 5, 6):
                self.assertFalse(res.is_open)
                self.assertEqual(len(res.current_officers), 0)
                self.assertIsNone(res.next_slot)

            # Invariant 3: If OPEN, at least 1 officer on duty and all are within shift intervals
            if res.is_open:
                self.assertGreaterEqual(len(res.current_officers), 1)
                for off in res.current_officers:
                    name = off["name"]
                    # Find shift definition
                    matching_shifts = [
                        s for s in SCHEDULE if s.day == weekday and s.name == name
                    ]
                    self.assertTrue(len(matching_shifts) >= 1)
                    active_any = any(
                        s.start_time <= cur_time < s.end_time for s in matching_shifts
                    )
                    self.assertTrue(
                        active_any,
                        f"Officer {name} reported active at {dt} but not in shift window",
                    )
            else:
                self.assertEqual(len(res.current_officers), 0)

            # Invariant 4: If next_slot exists, it must be strictly after cur_time
            if res.next_slot is not None:
                self.assertGreater(res.next_slot.start_time, cur_time)
                # Ensure no earlier shift starts after cur_time today
                earlier_shifts = [
                    s for s in SCHEDULE
                    if s.day == weekday
                    and cur_time < s.start_time < res.next_slot.start_time
                ]
                self.assertEqual(
                    len(earlier_shifts),
                    0,
                    f"Found shift earlier than next_slot at {dt}: {earlier_shifts}",
                )

            # Invariant 5: Embed construction never fails and complies with Discord constraints
            embed = build_oah_embed(res)
            self.assertIsInstance(embed, discord.Embed)
            self.assertIn(CALENDAR_URL, embed.description)
            self.assertIn(LOCATION_TEXT, embed.description)
            self.assertLessEqual(len(embed.description or ""), 4096)
            for field in embed.fields:
                self.assertNotIn("|", field.value)
                self.assertLessEqual(len(field.name), 256)
                self.assertLessEqual(len(field.value), 1024)


if __name__ == "__main__":
    unittest.main()
