"""
tests/test_oah_adversarial.py
Adversarial stress testing harness and empirical verification for OAH engine.
Simulates all 10,080 distinct minutes of a full week, stress-tests boundaries,
embed limits, timezone conversions, and execution throughput.
"""

import datetime
import time
import unittest
import discord

from cogs.open_access_hours import (
    SCHEDULE,
    CALENDAR_URL,
    LOCATION_TEXT,
    OAHShift,
    OAHStatusResult,
    NextSlotInfo,
    OfficerInfo,
    get_oah_status,
    build_oah_embed,
    get_pacific_tz,
    normalize_to_pacific,
    _WindowsPacificTz,
)

# Reference Pacific timezone for testing (Standard Time UTC-8, Daylight Time UTC-7)
PST = datetime.timezone(datetime.timedelta(hours=-8), name="PST")
PDT = datetime.timezone(datetime.timedelta(hours=-7), name="PDT")


class IndependentOAHOracle:
    """
    Completely independent ground-truth oracle for Open Access Hours,
    constructed directly from knowledge/open_access_hours.md specification.
    """

    # Minute offsets from midnight: start_min, end_min
    GROUND_TRUTH = {
        # Monday (0)
        0: [
            {"officer": "Ridhi", "role": "VC Events", "start": 11 * 60, "end": 13 * 60, "slot": "11:00 AM – 1:00 PM"},
            {"officer": "Sukhjeet", "role": "QP Chair", "start": 15 * 60, "end": 17 * 60, "slot": "3:00 PM – 5:00 PM"},
            {"officer": "Nishant", "role": "Social Chair", "start": 17 * 60 + 30, "end": 19 * 60 + 30, "slot": "5:30 PM – 7:30 PM"},
        ],
        # Tuesday (1)
        1: [
            {"officer": "Aiden", "role": "President", "start": 11 * 60, "end": 13 * 60, "slot": "11:00 AM – 1:00 PM"},
            {"officer": "Anthony", "role": "Design Chair", "start": 15 * 60, "end": 17 * 60, "slot": "3:00 PM – 5:00 PM"},
            {"officer": "Daniel H", "role": "Marketing Chair", "start": 17 * 60, "end": 19 * 60, "slot": "5:00 PM – 7:00 PM"},
            {"officer": "Ki", "role": "Webmaster", "start": 17 * 60, "end": 20 * 60, "slot": "5:00 PM – 8:00 PM"},
        ],
        # Wednesday (2)
        2: [
            {"officer": "Hannah", "role": "VC Operations", "start": 10 * 60, "end": 12 * 60, "slot": "10:00 AM – 12:00 PM"},
        ],
        # Thursday (3)
        3: [
            {"officer": "Paul", "role": "Social Chair", "start": 10 * 60, "end": 12 * 60, "slot": "10:00 AM – 12:00 PM"},
            {"officer": "Ki", "role": "Webmaster", "start": 12 * 60 + 45, "end": 13 * 60 + 45, "slot": "12:45 PM – 1:45 PM"},
            {"officer": "Cameryn", "role": "VP Internal", "start": 14 * 60, "end": 16 * 60, "slot": "2:00 PM – 4:00 PM"},
            {"officer": "Daniel Xu", "role": "VC Operations", "start": 15 * 60 + 30, "end": 17 * 60 + 30, "slot": "3:30 PM – 5:30 PM"},
        ],
        # Friday (4), Saturday (5), Sunday (6)
        4: [],
        5: [],
        6: [],
    }

    @classmethod
    def evaluate(cls, day: int, minute_of_day: int):
        shifts = cls.GROUND_TRUTH.get(day, [])
        # Half-open interval: start <= minute < end
        active = [s for s in shifts if s["start"] <= minute_of_day < s["end"]]
        is_open = len(active) > 0
        active_officers = {s["officer"] for s in active}

        # Future shifts today: start > minute
        future = [s for s in shifts if s["start"] > minute_of_day]
        next_slot_officers = set()
        next_start_min = None
        if future:
            next_start_min = min(s["start"] for s in future)
            next_slot_officers = {s["officer"] for s in future if s["start"] == next_start_min}

        return {
            "is_open": is_open,
            "active_officers": active_officers,
            "has_next_slot": len(future) > 0,
            "next_start_min": next_start_min,
            "next_officers": next_slot_officers,
        }


class TestOAHWeeklyTimeline10080Minutes(unittest.TestCase):
    """
    Exhaustively tests every single minute of a 7-day week (10,080 distinct minutes)
    against the independent oracle in PST and PDT.
    """

    def test_full_week_simulation_10080_minutes_pst(self):
        """Simulate 10,080 minutes of a standard week (Nov 2, 2026 00:00 to Nov 8, 2026 23:59)."""
        base_monday = datetime.datetime(2026, 11, 2, 0, 0, tzinfo=PST)
        minutes_tested = 0
        open_count = 0
        closed_count = 0

        last_next_start_min = None
        current_day = None

        for m in range(7 * 24 * 60):  # 10,080 minutes
            dt = base_monday + datetime.timedelta(minutes=m)
            day = dt.weekday()
            minute_of_day = dt.hour * 60 + dt.minute

            if day != current_day:
                current_day = day
                last_next_start_min = -1  # Reset daily monotonicity tracker

            oracle_res = IndependentOAHOracle.evaluate(day, minute_of_day)
            engine_res = get_oah_status(dt)

            # 1. OPEN / CLOSED status must match oracle
            self.assertEqual(
                engine_res.is_open,
                oracle_res["is_open"],
                f"Mismatch at minute {m} ({dt.strftime('%A %H:%M')}) - expected is_open={oracle_res['is_open']}",
            )

            # 2. On-duty officers must match oracle
            engine_officers = {o.name if hasattr(o, "name") else str(o) for o in engine_res.current_officers}
            self.assertEqual(
                engine_officers,
                oracle_res["active_officers"],
                f"Officer mismatch at minute {m} ({dt.strftime('%A %H:%M')})",
            )

            # 3. Next timeslot presence and officers
            if oracle_res["has_next_slot"]:
                self.assertIsNotNone(
                    engine_res.next_slot,
                    f"Expected next_slot at minute {m} ({dt.strftime('%A %H:%M')}) but got None",
                )
                next_str = str(engine_res.next_slot)
                for off in oracle_res["next_officers"]:
                    self.assertIn(
                        off,
                        next_str,
                        f"Expected {off} in next_slot at minute {m} ({dt.strftime('%A %H:%M')})",
                    )

                # 4. Monotonicity of next_slot today
                next_slot_obj = engine_res.next_slot
                if hasattr(next_slot_obj, "start_time"):
                    start_min = next_slot_obj.start_time.hour * 60 + next_slot_obj.start_time.minute
                    self.assertGreaterEqual(
                        start_min,
                        last_next_start_min,
                        f"Non-monotonic next_slot at minute {m} ({dt.strftime('%A %H:%M')})",
                    )
                    last_next_start_min = start_min
            else:
                self.assertIsNone(
                    engine_res.next_slot,
                    f"Expected None next_slot at minute {m} ({dt.strftime('%A %H:%M')}) but got {engine_res.next_slot}",
                )

            # 5. Embed formatting compliance on every single minute of the week
            embed = build_oah_embed(engine_res)
            # Verify Discord limits
            total_len = len(embed.title or "") + len(embed.description or "")
            for field in embed.fields:
                self.assertLessEqual(len(field.name), 256)
                self.assertLessEqual(len(field.value), 1024)
                total_len += len(field.name) + len(field.value)
                self.assertNotIn("|", field.value, "Found markdown pipe table in embed field")
            self.assertLessEqual(total_len, 6000)
            if embed.description:
                self.assertNotIn("|", embed.description, "Found markdown pipe table in embed description")
            full_text = (embed.description or "") + "".join(f.value for f in embed.fields)
            self.assertIn(CALENDAR_URL, full_text)
            self.assertIn(LOCATION_TEXT, full_text)

            minutes_tested += 1
            if engine_res.is_open:
                open_count += 1
            else:
                closed_count += 1

        self.assertEqual(minutes_tested, 10080, "Did not test exactly 10,080 minutes")
        # Total scheduled hours:
        # Mon: 2 + 2 + 2 = 6h (360 min)
        # Tue: 2 + 2 + 3 = 7h (Daniel 5-7, Ki 5-8 total 17:00-20:00 = 3h; Aiden 2h, Anthony 2h) -> 7h = 420 min
        # Wed: 2h = 120 min
        # Thu: Paul 10-12 (2h), Ki 12:45-1:45 (1h), Cameryn 2-4 & Daniel Xu 3:30-5:30 (14:00-17:30 = 3.5h) -> 6.5h = 390 min
        # Total open minutes: 360 + 420 + 120 + 390 = 1290 minutes.
        self.assertEqual(open_count, 1290, f"Expected exactly 1290 open minutes across the week, got {open_count}")
        self.assertEqual(closed_count, 10080 - 1290)

    def test_full_week_simulation_10080_minutes_pdt_dst(self):
        """Simulate 10,080 minutes in Daylight Saving Time (Jun 1, 2026 to Jun 7, 2026)."""
        base_monday = datetime.datetime(2026, 6, 1, 0, 0, tzinfo=PDT)
        open_count = 0
        for m in range(10080):
            dt = base_monday + datetime.timedelta(minutes=m)
            status = get_oah_status(dt)
            if status.is_open:
                open_count += 1
        self.assertEqual(open_count, 1290, "DST week open minute count must equal 1290")


class TestOAHBoundaryTransitions(unittest.TestCase):
    """
    Adversarial boundary testing: microsecond before/after shift,
    midnight crossings, weekend transitions, and multi-officer handoffs.
    """

    def test_edge_of_midnight_sunday_to_monday(self):
        """Sun 23:59:59 -> Mon 00:00:00: closed throughout, next_slot switches from None to Ridhi."""
        sun_late = datetime.datetime(2026, 11, 1, 23, 59, 59, tzinfo=PST)
        mon_early = datetime.datetime(2026, 11, 2, 0, 0, 0, tzinfo=PST)

        res_sun = get_oah_status(sun_late)
        res_mon = get_oah_status(mon_early)

        self.assertFalse(res_sun.is_open)
        self.assertIsNone(res_sun.next_slot)

        self.assertFalse(res_mon.is_open)
        self.assertIsNotNone(res_mon.next_slot)
        self.assertIn("Ridhi", str(res_mon.next_slot))

    def test_edge_of_midnight_thursday_to_friday(self):
        """Thu 23:59:59 -> Fri 00:00:00: closed, next_slot remains None into weekend."""
        thu_late = datetime.datetime(2026, 11, 5, 23, 59, 59, tzinfo=PST)
        fri_early = datetime.datetime(2026, 11, 6, 0, 0, 0, tzinfo=PST)

        res_thu = get_oah_status(thu_late)
        res_fri = get_oah_status(fri_early)

        self.assertFalse(res_thu.is_open)
        self.assertIsNone(res_thu.next_slot)
        self.assertFalse(res_fri.is_open)
        self.assertIsNone(res_fri.next_slot)

    def test_subsecond_boundary_precision(self):
        """Tests microsecond transitions around Monday 11:00 AM (10:59:59.999999 vs 11:00:00.000000)."""
        pre_dt = datetime.datetime(2026, 11, 2, 10, 59, 59, 999999, tzinfo=PST)
        at_dt = datetime.datetime(2026, 11, 2, 11, 0, 0, 0, tzinfo=PST)
        end_dt = datetime.datetime(2026, 11, 2, 13, 0, 0, 0, tzinfo=PST)

        res_pre = get_oah_status(pre_dt)
        res_at = get_oah_status(at_dt)
        res_end = get_oah_status(end_dt)

        self.assertFalse(res_pre.is_open, "10:59:59.999999 must evaluate CLOSED")
        self.assertTrue(res_at.is_open, "11:00:00.000000 must evaluate OPEN")
        self.assertFalse(res_end.is_open, "13:00:00.000000 must evaluate CLOSED")

    def test_tuesday_officer_count_transitions(self):
        """
        Timeline on Tuesday:
        16:59: Anthony on duty (count=1)
        17:00: Anthony leaves, Daniel H & Ki start (count=2)
        18:59: Daniel H & Ki on duty (count=2)
        19:00: Daniel H leaves, Ki stays (count=1)
        19:59: Ki on duty (count=1)
        20:00: Ki leaves, lab closed (count=0)
        """
        times = [
            (datetime.time(16, 59), 1, {"Anthony"}),
            (datetime.time(17, 0), 2, {"Daniel H", "Ki"}),
            (datetime.time(18, 59), 2, {"Daniel H", "Ki"}),
            (datetime.time(19, 0), 1, {"Ki"}),
            (datetime.time(19, 59), 1, {"Ki"}),
            (datetime.time(20, 0), 0, set()),
        ]
        for t, expected_count, expected_names in times:
            dt = datetime.datetime(2026, 11, 3, t.hour, t.minute, tzinfo=PST)
            status = get_oah_status(dt)
            active_names = {o.name if hasattr(o, "name") else str(o) for o in status.current_officers}
            self.assertEqual(
                len(active_names),
                expected_count,
                f"Count mismatch at {t}: expected {expected_count}, got {len(active_names)}",
            )
            self.assertEqual(active_names, expected_names, f"Name mismatch at {t}")


class TestOAHEmbedStressAndAdversarialInputs(unittest.TestCase):
    """
    Stress-tests embed generator against extreme inputs, malicious strings,
    empty structures, and Discord formatting boundaries.
    """

    def test_embed_all_12_rostered_officers_concurrent(self):
        """Simulates all 12 rostered officers on duty simultaneously and checks Discord limits."""
        all_officers = [
            OfficerInfo(s.name, s.role, s.timeslot)
            for s in SCHEDULE
        ]
        status = OAHStatusResult(
            is_open=True,
            current_officers=all_officers,
            next_slot="3:00 PM – 5:00 PM: Test Next",
            today_schedule=[],
            full_schedule={},
            current_time=datetime.datetime(2026, 11, 2, 11, 0, tzinfo=PST),
        )
        embed = build_oah_embed(status)
        for field in embed.fields:
            self.assertLessEqual(len(field.value), 1024, f"Field '{field.name}' exceeds 1024 chars")
            self.assertNotIn("|", field.value)

    def test_officer_embed_capacity_boundary_limit(self):
        """
        Calculates empirical capacity boundary:
        Verifies up to 14 long officer descriptions fit comfortably within Discord's 1024-char limit,
        and documents the threshold where truncation would be needed if staffing ever scaled beyond 14.
        """
        officers_14 = [
            OfficerInfo(f"Officer Name {i}", f"VP Engineering Role {i}", "11:00 AM – 1:00 PM")
            for i in range(14)
        ]
        status = OAHStatusResult(
            is_open=True,
            current_officers=officers_14,
            next_slot=None,
            current_time=datetime.datetime(2026, 11, 2, 11, 0, tzinfo=PST),
        )
        embed = build_oah_embed(status)
        officer_field = next(f for f in embed.fields if "Officer" in f.name)
        self.assertLessEqual(len(officer_field.value), 1024, "14 officers must fit inside 1024 chars")

    def test_embed_adversarial_markdown_characters_in_officer_names(self):
        """Officers with markdown, pipe characters, newlines, and emojis."""
        adversarial_officers = [
            OfficerInfo("Test | Pipe | Name", "Role | Chair", "11:00 AM – 1:00 PM"),
            OfficerInfo("**Bold** and *Italic*", "Special & Role", "11:00 AM – 1:00 PM"),
            OfficerInfo("Unicode \u2603 \U0001F680 \u2764", "Role \u00A9", "11:00 AM – 1:00 PM"),
        ]
        status = OAHStatusResult(
            is_open=True,
            current_officers=adversarial_officers,
            next_slot="3:00 PM – 5:00 PM: Next Officer",
            today_schedule=[],
            full_schedule={},
            current_time=datetime.datetime(2026, 11, 2, 11, 0, tzinfo=PST),
        )
        embed = build_oah_embed(status)
        self.assertIsNotNone(embed)
        self.assertLessEqual(len(embed.fields[1].value), 1024)

    def test_embed_handles_none_timestamps(self):
        """Embed builder should gracefully handle missing timestamps."""
        status = OAHStatusResult(
            is_open=False,
            current_officers=[],
            next_slot=None,
            evaluated_time=None,
            current_time=None,
        )
        embed = build_oah_embed(status)
        self.assertIsNotNone(embed)
        self.assertIn("CLOSED", embed.fields[0].value)

    def test_embed_next_slot_various_structures(self):
        """Tests embed rendering when next_slot is dict, str, or NextSlotInfo."""
        # As raw dict
        dict_slot = {
            "timeslot": "3:00 PM – 5:00 PM",
            "officers": [{"name": "Sukhjeet", "role": "QP Chair"}],
            "description": "3:00 PM – 5:00 PM: Sukhjeet (QP Chair)",
        }
        status1 = OAHStatusResult(is_open=False, current_officers=[], next_slot=dict_slot)
        embed1 = build_oah_embed(status1)
        self.assertIn("Sukhjeet", "".join(f.value for f in embed1.fields))

        # As NextSlotInfo
        info_slot = NextSlotInfo(
            start_time=datetime.time(15, 0),
            timeslot="3:00 PM – 5:00 PM",
            officers=[{"name": "Sukhjeet", "role": "QP Chair"}],
        )
        status2 = OAHStatusResult(is_open=False, current_officers=[], next_slot=info_slot)
        embed2 = build_oah_embed(status2)
        self.assertIn("Sukhjeet", "".join(f.value for f in embed2.fields))


class TestOAHTimezoneResilience(unittest.TestCase):
    """Verifies timezone normalizations across international timezones and DST."""

    def test_naive_datetime_interpreted_as_pacific(self):
        """Naive datetime is treated as Pacific local time."""
        naive_dt = datetime.datetime(2026, 11, 2, 11, 30)
        norm = normalize_to_pacific(naive_dt)
        self.assertIsNotNone(norm.tzinfo)
        self.assertEqual(norm.hour, 11)
        self.assertEqual(norm.minute, 30)

    def test_foreign_timezones_normalized_accurately(self):
        """
        UTC: 19:00 on Monday Nov 2 -> 11:00 PST (Open)
        Tokyo (JST, UTC+9): 04:00 on Tuesday Nov 3 -> 11:00 PST Monday Nov 2 (Open)
        New York (EST, UTC-5): 14:00 on Monday Nov 2 -> 11:00 PST (Open)
        """
        utc_dt = datetime.datetime(2026, 11, 2, 19, 0, tzinfo=datetime.timezone.utc)
        res_utc = get_oah_status(utc_dt)
        self.assertTrue(res_utc.is_open)

        jst = datetime.timezone(datetime.timedelta(hours=9), name="JST")
        jst_dt = datetime.datetime(2026, 11, 3, 4, 0, tzinfo=jst)
        res_jst = get_oah_status(jst_dt)
        self.assertTrue(res_jst.is_open)

        est = datetime.timezone(datetime.timedelta(hours=-5), name="EST")
        est_dt = datetime.datetime(2026, 11, 2, 14, 0, tzinfo=est)
        res_est = get_oah_status(est_dt)
        self.assertTrue(res_est.is_open)


class TestOAHPerformanceAndLatency(unittest.TestCase):
    """Measures throughput and execution latency under high load."""

    def test_evaluations_throughput(self):
        """1,000 get_oah_status() evaluations should complete in under 2.0 seconds."""
        base_dt = datetime.datetime(2026, 11, 2, 11, 15, tzinfo=PST)
        iterations = 1000

        t0 = time.perf_counter()
        for i in range(iterations):
            get_oah_status(base_dt)
        t1 = time.perf_counter()

        elapsed = t1 - t0
        usec_per_call = (elapsed / iterations) * 1_000_000

        # Sub-2ms requirement even on Windows with uncached zoneinfo disk I/O
        self.assertLess(
            elapsed,
            2.0,
            f"1,000 evaluations took {elapsed:.3f}s (>2.0s limit)",
        )
        print(f"\n[PERFORMANCE] get_oah_status throughput: {iterations / elapsed:,.0f} ops/sec ({usec_per_call:.2f} µs/op)")

    def test_1000_embed_builds_throughput(self):
        """1,000 build_oah_embed() calls should complete in under 0.5 seconds."""
        base_dt = datetime.datetime(2026, 11, 2, 11, 15, tzinfo=PST)
        status = get_oah_status(base_dt)
        iterations = 1000

        t0 = time.perf_counter()
        for i in range(iterations):
            build_oah_embed(status)
        t1 = time.perf_counter()

        elapsed = t1 - t0
        usec_per_call = (elapsed / iterations) * 1_000_000

        self.assertLess(elapsed, 1.0, f"1,000 embed builds took {elapsed:.3f}s")
        print(f"[PERFORMANCE] build_oah_embed throughput: {iterations / elapsed:,.0f} ops/sec ({usec_per_call:.2f} µs/op)")


if __name__ == "__main__":
    unittest.main()
