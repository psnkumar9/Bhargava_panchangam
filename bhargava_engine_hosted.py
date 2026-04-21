from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "pydeps"))
sys.path.insert(0, str(ROOT / "drik-panchanga"))

import swisseph as swe  # type: ignore
import panchanga  # type: ignore


TITHI_NAMES = [
    None,
    "Shukla Pratipada",
    "Shukla Dwitiya",
    "Shukla Tritiya",
    "Shukla Chaturthi",
    "Shukla Panchami",
    "Shukla Shashthi",
    "Shukla Saptami",
    "Shukla Ashtami",
    "Shukla Navami",
    "Shukla Dasami",
    "Shukla Ekadashi",
    "Shukla Dwadasi",
    "Shukla Trayodashi",
    "Shukla Chaturdashi",
    "Pournami",
    "Krishna Pratipada",
    "Krishna Dwitiya",
    "Krishna Tritiya",
    "Krishna Chaturthi",
    "Krishna Panchami",
    "Krishna Shashthi",
    "Krishna Saptami",
    "Krishna Ashtami",
    "Krishna Navami",
    "Krishna Dasami",
    "Krishna Ekadashi",
    "Krishna Dwadasi",
    "Krishna Trayodashi",
    "Krishna Chaturdashi",
    "Amavasya",
]

NAKSHATRA_NAMES = [
    None,
    "Ashwini",
    "Bharani",
    "Krittika",
    "Rohini",
    "Mrigashira",
    "Ardra",
    "Punarvasu",
    "Pushya",
    "Ashlesha",
    "Magha",
    "Purva Phalguni",
    "Uttara Phalguni",
    "Hasta",
    "Chitta",
    "Swati",
    "Vishakha",
    "Anuradha",
    "Jyeshta",
    "Moola",
    "Purva Ashadha",
    "Uttara Ashadha",
    "Shravana",
    "Dhanishta",
    "Shatabhisha",
    "Purva Bhadrapada",
    "Uttara Bhadrapada",
    "Revati",
]

YOGA_NAMES = [
    None,
    "Vishkambha",
    "Priti",
    "Ayushman",
    "Saubhagya",
    "Shobhana",
    "Atiganda",
    "Sukarma",
    "Dhriti",
    "Shoola",
    "Ganda",
    "Vriddhi",
    "Dhruva",
    "Vyaghata",
    "Harshana",
    "Vajra",
    "Siddhi",
    "Vyatipata",
    "Variyana",
    "Parigha",
    "Shiva",
    "Siddha",
    "Sadhya",
    "Shubha",
    "Shukla",
    "Brahma",
    "Indra",
    "Vaidhriti",
]

KARANA_NAMES = [
    None,
    "Kimstughna",
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Garija",
    "Vanija",
    "Vishti",
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Garija",
    "Vanija",
    "Vishti",
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Garija",
    "Vanija",
    "Vishti",
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Garija",
    "Vanija",
    "Vishti",
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Garija",
    "Vanija",
    "Vishti",
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Garija",
    "Vanija",
    "Vishti",
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Garija",
    "Vanija",
    "Vishti",
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Garija",
    "Vanija",
    "Vishti",
    "Shakuni",
    "Chatushpada",
    "Naga",
]

VARA_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
MASA_NAMES = [
    None,
    "Chaitra",
    "Vaishakha",
    "Jyeshta",
    "Ashadha",
    "Shravana",
    "Bhadrapada",
    "Ashwayuja",
    "Kartika",
    "Margashira",
    "Pushya",
    "Magha",
    "Phalguna",
]
RASI_NAMES = [
    None,
    "Mesha",
    "Vrishabha",
    "Mithuna",
    "Karkataka",
    "Simha",
    "Kanya",
    "Tula",
    "Vrischika",
    "Dhanus",
    "Makara",
    "Kumbha",
    "Meena",
]

RAHU_SEGMENT = [8, 2, 7, 5, 6, 4, 3]
YAMAGANDA_SEGMENT = [5, 4, 3, 2, 1, 7, 6]
DAY_LORDS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
HORA_SEQUENCE = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

VARJYAM_START_HOURS = [
    [20.0], [9.6], [12.0], [16.0], [5.6], [8.4], [12.0], [8.0], [12.8],
    [12.0], [8.0], [7.2], [8.4], [8.0], [5.6], [5.6], [4.0], [5.6],
    [8.0, 22.4], [9.6], [8.0], [4.0], [4.0], [7.2], [6.4], [9.6], [12.0],
]
AMRITA_START_HOURS = [
    16.8, 19.2, 21.6, 20.8, 15.2, 14.0, 21.6, 17.6, 22.4,
    21.6, 17.6, 16.8, 18.0, 17.6, 15.2, 15.2, 13.6, 15.2,
    17.6, 19.2, 17.6, 13.6, 13.6, 16.8, 16.0, 19.2, 21.6,
]

SLOT_COUNT = 30


@dataclass
class Segment:
    label: str
    start_utc: float
    end_utc: float


def _tz_hours(date_str: str, timezone_name: str | None, timezone_offset_hours: float | None) -> float:
    if timezone_offset_hours is not None:
        return timezone_offset_hours
    if timezone_name == "Asia/Kolkata" or not timezone_name:
        return 5.5
    raise ValueError("A numeric timezone offset is required for non-Indian timezones in the local app.")


def _hms_to_hours(hms: list[int]) -> float:
    return hms[0] + hms[1] / 60.0 + hms[2] / 3600.0


def _format_hms(hours: float) -> str:
    total_seconds = int(round(hours * 3600))
    hh, rem = divmod(total_seconds, 3600)
    mm, _ = divmod(rem, 60)
    return f"{hh:02d}:{mm:02d}"


def _format_event_hms(hours: float) -> str:
    if hours < 0:
        return f"{_format_hms(hours + 24.0)} (-1)"
    return _format_hms(hours)


def _format_clock_with_offset(hours: float) -> str:
    day_offset = 0
    while hours < 0:
        hours += 24.0
        day_offset -= 1
    while hours >= 24.0:
        hours -= 24.0
        day_offset += 1
    text = _format_hms(hours)
    if day_offset > 0:
        return f"{text} (+{day_offset})"
    if day_offset < 0:
        return f"{text} ({day_offset})"
    return text


def _format_duration(hours: float) -> str:
    total_minutes = int(round(hours * 60))
    hh, mm = divmod(total_minutes, 60)
    return f"{hh}h {mm:02d}m"


def _format_degree_dms(degrees: float) -> str:
    total_seconds = int(round(degrees * 3600))
    dd, rem = divmod(total_seconds, 3600)
    mm, ss = divmod(rem, 60)
    if ss == 60:
        ss = 0
        mm += 1
    if mm == 60:
        mm = 0
        dd += 1
    return f"{dd:02d}\u00b0 {mm:02d}' {ss:02d}\""


def _local_hours_from_utc_jd(jd_utc: float, local_midnight_utc_jd: float) -> float:
    return (jd_utc - local_midnight_utc_jd) * 24.0


def _range_to_display(start_utc: float, end_utc: float, local_midnight_utc_jd: float) -> dict:
    start_h = _local_hours_from_utc_jd(start_utc, local_midnight_utc_jd)
    end_h = _local_hours_from_utc_jd(end_utc, local_midnight_utc_jd)
    return {
        "start_hours": start_h,
        "end_hours": end_h,
        "display": f"{_format_event_hms(start_h)} - {_format_event_hms(end_h)}",
    }


def _event_display_from_utc(jd_utc: float, local_midnight_utc_jd: float) -> str:
    return _format_hms(_local_hours_from_utc_jd(jd_utc, local_midnight_utc_jd))


@lru_cache(maxsize=1)
def _load_pyjhora_modules():
    candidate_paths = [
        ROOT / "pydeps",
        ROOT.parent / "pydeps",
        Path(r"E:\AstroEngine\pydeps"),
    ]
    last_error = None
    for candidate in candidate_paths:
        if not candidate.exists():
            continue
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
        try:
            from jhora.panchanga import drik as jdrik  # type: ignore
            from jhora import const as jconst  # type: ignore
            from jhora import utils as jutils  # type: ignore
            return jdrik, jutils, jconst
        except ModuleNotFoundError as exc:
            last_error = exc
            continue
    raise RuntimeError(f"PyJHora could not be loaded from local engine paths: {last_error}")


def _local_datetime_from_date_hours(date_str: str, local_hours: float) -> datetime:
    base_dt = datetime.fromisoformat(f"{date_str}T00:00:00")
    return base_dt + timedelta(hours=local_hours)


def _pyjhora_context(date_str: str, local_hours: float, latitude: float, longitude: float, tz_hours: float):
    jdrik, jutils, jconst = _load_pyjhora_modules()
    local_dt = _local_datetime_from_date_hours(date_str, local_hours)
    seconds = local_dt.second + local_dt.microsecond / 1_000_000.0
    jd = jutils.julian_day_number(
        (local_dt.year, local_dt.month, local_dt.day),
        (local_dt.hour, local_dt.minute, seconds),
    )
    # Drik-side calculations also mutate Swiss Ephemeris global sidereal mode.
    # Reset PyJHora explicitly before every PyJHora-derived value so outputs stay
    # aligned with JHora settings regardless of earlier panchanga calls.
    jdrik.set_ayanamsa_mode("TRUE_LAHIRI", jd=jd)
    place = jdrik.Place("Selected Place", latitude, longitude, tz_hours)
    return jdrik, jconst, jd, place


def _lagna_context(date_str: str, local_hours: float, latitude: float, longitude: float, tz_hours: float) -> dict:
    jdrik, jconst, jd, place = _pyjhora_context(date_str, local_hours, latitude, longitude, tz_hours)
    sign_index, sign_degrees, nakshatra_no, pada_no = jdrik.ascendant(jd, place)
    sign_name = jconst.rasi_names_en[sign_index]
    return {
        "name": sign_name,
        "degrees": sign_degrees,
        "display": f"{sign_name} {_format_degree_dms(sign_degrees)}",
        "nakshatra_number": nakshatra_no,
        "nakshatra_name": NAKSHATRA_NAMES[nakshatra_no] if nakshatra_no < len(NAKSHATRA_NAMES) else str(nakshatra_no),
        "pada": pada_no,
    }


def _anandadi_context(date_str: str, local_hours: float, latitude: float, longitude: float, tz_hours: float) -> dict:
    jdrik, jconst, jd, place = _pyjhora_context(date_str, local_hours, latitude, longitude, tz_hours)
    yoga_index, reference = jdrik.anandhaadhi_yoga(jd, place)
    if 0 <= yoga_index < len(jconst.anandhaadhi_yoga_names):
        name = jconst.anandhaadhi_yoga_names[yoga_index].replace("_", " ").title()
    else:
        name = str(yoga_index)
    return {
        "index": yoga_index,
        "name": name,
        "reference": round(reference, 6) if isinstance(reference, (int, float)) else reference,
    }


def _collect_local_timeline(
    start_hours: float,
    end_hours: float,
    index_fn: Callable[[float], int],
    payload_fn: Callable[[float], dict],
    step_minutes: float = 10.0,
) -> list[dict]:
    results: list[dict] = []
    current_start = start_hours
    while current_start < end_hours - 1e-6:
        current_index = index_fn(current_start + 1e-6)
        cursor = current_start
        next_start = end_hours
        step_hours = step_minutes / 60.0
        while cursor < end_hours - 1e-6:
            probe = min(cursor + step_hours, end_hours)
            if index_fn(probe + (1e-6 if probe < end_hours else -1e-6)) != current_index:
                lo, hi = cursor, probe
                while hi - lo > (1.0 / 3600.0):
                    mid = (lo + hi) / 2.0
                    if index_fn(mid) == current_index:
                        lo = mid
                    else:
                        hi = mid
                next_start = hi
                break
            cursor = probe
        payload = payload_fn(current_start + 1e-6)
        payload["start_hours"] = current_start
        payload["end_hours"] = next_start
        payload["display"] = f"{_format_event_hms(current_start)} - {_format_event_hms(next_start)}"
        results.append(payload)
        current_start = next_start
    return results


def _merge_short_timeline_segments(items: list[dict], min_minutes: float = 1.0) -> list[dict]:
    if not items:
        return items
    merged = [dict(items[0])]
    min_hours = min_minutes / 60.0
    for item in items[1:]:
        current = dict(item)
        duration = current["end_hours"] - current["start_hours"]
        if duration < min_hours and merged:
            merged[-1]["end_hours"] = current["end_hours"]
            merged[-1]["display"] = f"{_format_event_hms(merged[-1]['start_hours'])} - {_format_event_hms(merged[-1]['end_hours'])}"
            continue
        if merged[-1]["name"] == current["name"]:
            merged[-1]["end_hours"] = current["end_hours"]
            merged[-1]["display"] = f"{_format_event_hms(merged[-1]['start_hours'])} - {_format_event_hms(merged[-1]['end_hours'])}"
        else:
            merged.append(current)
    return merged


def _hora_timeline(
    previous_sunset_hours: float,
    sunrise_hours: float,
    sunset_hours: float,
    next_sunrise_hours: float,
    weekday: int,
) -> list[dict]:
    day_lord = DAY_LORDS[weekday]
    base_index = HORA_SEQUENCE.index(day_lord)
    entries: list[dict] = []
    day_hora_length = (sunset_hours - sunrise_hours) / 12.0
    for hora_index in range(12):
        start = sunrise_hours + hora_index * day_hora_length
        end = start + day_hora_length
        entries.append({
            "name": HORA_SEQUENCE[(base_index + hora_index) % 7],
            "display": f"{_format_clock_with_offset(start)} - {_format_clock_with_offset(end)}",
            "start_hours": start,
            "end_hours": end,
            "period": "day",
        })
    night_hora_length = (next_sunrise_hours - sunset_hours) / 12.0
    for night_index in range(12):
        hora_index = 12 + night_index
        start = sunset_hours + night_index * night_hora_length
        end = start + night_hora_length
        entries.append({
            "name": HORA_SEQUENCE[(base_index + hora_index) % 7],
            "display": f"{_format_clock_with_offset(start)} - {_format_clock_with_offset(end)}",
            "start_hours": start,
            "end_hours": end,
            "period": "night",
        })
    return entries


def _moon_phase(jd_utc: float) -> float:
    return (panchanga.lunar_longitude(jd_utc) - panchanga.solar_longitude(jd_utc)) % 360.0


def _nirayana_moon_longitude(jd_utc: float) -> float:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    return (panchanga.lunar_longitude(jd_utc) - swe.get_ayanamsa_ut(jd_utc)) % 360.0


def _nirayana_solar_longitude(jd_utc: float) -> float:
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    return (panchanga.solar_longitude(jd_utc) - swe.get_ayanamsa_ut(jd_utc)) % 360.0


def _tithi_index(jd_utc: float) -> int:
    return max(1, int(math.ceil(_moon_phase(jd_utc) / 12.0)))


def _karana_index(jd_utc: float) -> int:
    value = int(math.ceil(_moon_phase(jd_utc) / 6.0))
    return 60 if value == 0 else value


def _nakshatra_index(jd_utc: float) -> int:
    return max(1, int(math.ceil(_nirayana_moon_longitude(jd_utc) * 27.0 / 360.0)))


def _yoga_index(jd_utc: float) -> int:
    total = (_nirayana_moon_longitude(jd_utc) + _nirayana_solar_longitude(jd_utc)) % 360.0
    return max(1, int(math.ceil(total * 27.0 / 360.0)))


def _find_next_transition(
    start_utc: float,
    index_fn: Callable[[float], int],
    max_days: float = 2.0,
    step_days: float = 1.0 / 24.0,
) -> float | None:
    current = index_fn(start_utc + 1e-8)
    cursor = start_utc
    end = start_utc + max_days
    while cursor < end:
      next_cursor = min(cursor + step_days, end)
      if index_fn(next_cursor) != current:
        lo, hi = cursor, next_cursor
        while hi - lo > (1.0 / 86400.0):
          mid = (lo + hi) / 2.0
          if index_fn(mid) == current:
            lo = mid
          else:
            hi = mid
        return hi
      cursor = next_cursor
    return None


def _find_previous_transition(
    start_utc: float,
    index_fn: Callable[[float], int],
    max_days: float = 2.0,
    step_days: float = 1.0 / 24.0,
) -> float | None:
    current = index_fn(start_utc - 1e-8)
    cursor = start_utc
    end = start_utc - max_days
    while cursor > end:
      next_cursor = max(cursor - step_days, end)
      if index_fn(next_cursor) != current:
        lo, hi = next_cursor, cursor
        while hi - lo > (1.0 / 86400.0):
          mid = (lo + hi) / 2.0
          if index_fn(mid) == current:
            hi = mid
          else:
            lo = mid
        return lo
      cursor = next_cursor
    return None


def _collect_same_day_entries(
    local_midnight_utc_jd: float,
    index_fn: Callable[[float], int],
    name_lookup: list[str | None],
    max_days_back: float = 2.0,
) -> list[dict]:
    day_end = local_midnight_utc_jd + 1.0
    start_utc = _find_previous_transition(local_midnight_utc_jd, index_fn, max_days=max_days_back) or local_midnight_utc_jd
    current_index = index_fn(start_utc + 1e-8)
    entries: list[dict] = []

    while start_utc < day_end:
        next_transition = _find_next_transition(start_utc, index_fn, max_days=2.0)
        if next_transition is None:
            next_transition = day_end
        if next_transition > local_midnight_utc_jd:
            entries.append({
                "number": current_index,
                "name": name_lookup[current_index] if current_index < len(name_lookup) else str(current_index),
                "end_display": _event_display_from_utc(next_transition, local_midnight_utc_jd),
            })
        if next_transition >= day_end:
            break
        start_utc = next_transition
        current_index = index_fn(start_utc + 1e-8)

    return entries


def _day_segment_range(sunrise_hours: float, sunset_hours: float, segment_no: int) -> tuple[float, float]:
    seg = (sunset_hours - sunrise_hours) / 8.0
    start = sunrise_hours + (segment_no - 1) * seg
    return start, start + seg


def _durmuhurta_ranges(sunrise_hours: float, sunset_hours: float, weekday: int) -> list[tuple[float, float]]:
    day_duration = sunset_hours - sunrise_hours
    night_duration = 24.0 - day_duration
    table = {
        0: [(sunrise_hours, day_duration, 10.4)],
        1: [(sunrise_hours, day_duration, 6.4), (sunrise_hours, day_duration, 8.8)],
        2: [(sunrise_hours, day_duration, 2.4), (sunset_hours, night_duration, 4.8)],
        3: [(sunrise_hours, day_duration, 5.6)],
        4: [(sunrise_hours, day_duration, 4.0), (sunrise_hours, day_duration, 8.8)],
        5: [(sunrise_hours, day_duration, 2.4), (sunrise_hours, day_duration, 6.4)],
        6: [(sunrise_hours, day_duration, 1.6)],
    }
    duration = day_duration * 0.8 / 12.0
    result = []
    for base, span, offset in table.get(weekday, []):
        start = base + span * offset / 12.0
        result.append((start, start + duration))
    return result


def _current_hora(
    reference_hours: float,
    previous_sunset_hours: float,
    sunrise_hours: float,
    sunset_hours: float,
    next_sunrise_hours: float,
    weekday: int,
) -> dict:
    if reference_hours < sunrise_hours:
        active_weekday = (weekday - 1) % 7
        day_lord = DAY_LORDS[active_weekday]
        base_index = HORA_SEQUENCE.index(day_lord)
        hora_length = (sunrise_hours - previous_sunset_hours) / 12.0
        night_index = min(11, max(0, int((reference_hours - previous_sunset_hours) // hora_length)))
        hora_index = 12 + night_index
        start = previous_sunset_hours + night_index * hora_length
        end = start + hora_length
    elif reference_hours < sunset_hours:
        day_lord = DAY_LORDS[weekday]
        base_index = HORA_SEQUENCE.index(day_lord)
        hora_length = (sunset_hours - sunrise_hours) / 12.0
        hora_index = min(11, int((reference_hours - sunrise_hours) // hora_length))
        start = sunrise_hours + hora_index * hora_length
        end = start + hora_length
    else:
        day_lord = DAY_LORDS[weekday]
        base_index = HORA_SEQUENCE.index(day_lord)
        hora_length = (next_sunrise_hours - sunset_hours) / 12.0
        night_index = min(11, int((reference_hours - sunset_hours) // hora_length))
        hora_index = 12 + night_index
        start = sunset_hours + night_index * hora_length
        end = start + hora_length
    return {
        "ruler": HORA_SEQUENCE[(base_index + hora_index) % 7],
        "start_hours": start,
        "end_hours": end,
        "display": f"{_format_hms(start)} - {_format_hms(end)}",
    }


def _parse_reference_time(time_text: str | None) -> float | None:
    if not time_text:
        return None
    raw = time_text.strip()
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("Time must be in HH:MM or HH:MM:SS format.")
    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2]) if len(parts) == 3 else 0
    if hour < 0 or hour > 23 or minute < 0 or minute > 59 or second < 0 or second > 59:
        raise ValueError("Invalid time supplied.")
    return hour + minute / 60.0 + second / 3600.0


def _nakshatra_segments_for_day(local_midnight_utc_jd: float) -> list[Segment]:
    day_end = local_midnight_utc_jd + 1.0
    actual_start = _find_previous_transition(local_midnight_utc_jd, _nakshatra_index, max_days=2.0) or local_midnight_utc_jd
    current_idx = _nakshatra_index(actual_start + 1e-8)
    current_start = actual_start
    segments: list[Segment] = []
    while current_start < day_end:
        next_transition = _find_next_transition(current_start, _nakshatra_index, max_days=2.0)
        if next_transition is None:
            next_transition = current_start + 1.5
        segments.append(Segment(NAKSHATRA_NAMES[current_idx], current_start, next_transition))
        current_start = next_transition
        current_idx = _nakshatra_index(current_start + 1e-8)
    return segments


def _clip_events(
    segments: list[Segment],
    local_midnight_utc_jd: float,
    start_offsets: list[float],
    label: str,
) -> list[dict]:
    day_end = local_midnight_utc_jd + 1.0
    results = []
    for segment in segments:
        duration_hours = (segment.end_utc - segment.start_utc) * 24.0
        event_duration_hours = duration_hours * 1.6 / 24.0
        for offset in start_offsets:
            event_start = segment.start_utc + (offset * duration_hours / 24.0) / 24.0
            event_end = event_start + event_duration_hours / 24.0
            if event_start < local_midnight_utc_jd or event_start >= day_end:
                continue
            payload = _range_to_display(event_start, event_end, local_midnight_utc_jd)
            payload["nakshatra"] = segment.label
            payload["kind"] = label
            results.append(payload)
    return results


def calculate_panchanga(
    date_str: str,
    latitude: float,
    longitude: float,
    timezone_name: str = "Asia/Kolkata",
    timezone_offset_hours: float | None = None,
    time_text: str | None = None,
) -> dict:
    tz_hours = _tz_hours(date_str, timezone_name, timezone_offset_hours)
    year, month, day = map(int, date_str.split("-"))
    date = panchanga.Date(year, month, day)
    place = panchanga.Place(latitude, longitude, tz_hours)
    jd = panchanga.gregorian_to_jd(date)
    local_midnight_utc_jd = jd - tz_hours / 24.0

    sunrise_jd_local, sunrise_hms = panchanga.sunrise(jd, place)
    sunset_jd_local, sunset_hms = panchanga.sunset(jd, place)
    next_date_dt = datetime.fromisoformat(date_str).date() + timedelta(days=1)
    next_date = panchanga.Date(next_date_dt.year, next_date_dt.month, next_date_dt.day)
    next_sunrise_jd_local, next_sunrise_hms = panchanga.sunrise(panchanga.gregorian_to_jd(next_date), place)
    previous_date_dt = datetime.fromisoformat(date_str).date() - timedelta(days=1)
    previous_date = panchanga.Date(previous_date_dt.year, previous_date_dt.month, previous_date_dt.day)
    previous_sunset_jd_local, previous_sunset_hms = panchanga.sunset(panchanga.gregorian_to_jd(previous_date), place)

    sunrise_hours = _hms_to_hours(sunrise_hms)
    sunset_hours = _hms_to_hours(sunset_hms)
    next_sunrise_hours = _hms_to_hours(next_sunrise_hms) + 24.0
    previous_sunset_hours = _hms_to_hours(previous_sunset_hms) - 24.0
    day_length_hours = sunset_hours - sunrise_hours
    night_length_hours = next_sunrise_hours - sunset_hours

    tithi_data = panchanga.tithi(jd, place)
    nakshatra_data = panchanga.nakshatra(jd, place)
    yoga_data = panchanga.yoga(jd, place)
    sunrise_utc_jd = sunrise_jd_local - tz_hours / 24.0
    karana_number = _karana_index(sunrise_utc_jd + 1e-8)
    karana_end_utc = _find_next_transition(sunrise_utc_jd, _karana_index, max_days=1.0)

    weekday = panchanga.vaara(jd)
    masa_number, masa_is_adhika = panchanga.masa(jd, place)
    rasi_number = int(panchanga.raasi(jd))

    now_local = datetime.now()
    reference_hours = _parse_reference_time(time_text)
    if reference_hours is None:
        reference_hours = now_local.hour + now_local.minute / 60.0 if now_local.date().isoformat() == date_str else sunrise_hours
    hora = _current_hora(reference_hours, previous_sunset_hours, sunrise_hours, sunset_hours, next_sunrise_hours, weekday)

    rahu_start, rahu_end = _day_segment_range(sunrise_hours, sunset_hours, RAHU_SEGMENT[weekday])
    yama_start, yama_end = _day_segment_range(sunrise_hours, sunset_hours, YAMAGANDA_SEGMENT[weekday])

    nak_segments = _nakshatra_segments_for_day(local_midnight_utc_jd)
    amrita_events = []
    varjyam_events = []
    for segment in nak_segments:
        idx = NAKSHATRA_NAMES.index(segment.label)
        amrita_events.extend(_clip_events([segment], local_midnight_utc_jd, [AMRITA_START_HOURS[idx - 1]], "amrita"))
        varjyam_events.extend(_clip_events([segment], local_midnight_utc_jd, VARJYAM_START_HOURS[idx - 1], "varjyam"))

    tithi_entries = _collect_same_day_entries(local_midnight_utc_jd, _tithi_index, TITHI_NAMES)
    nakshatra_entries = _collect_same_day_entries(local_midnight_utc_jd, _nakshatra_index, NAKSHATRA_NAMES)
    yoga_entries = _collect_same_day_entries(local_midnight_utc_jd, _yoga_index, YOGA_NAMES)
    karana_entries = _collect_same_day_entries(local_midnight_utc_jd, _karana_index, KARANA_NAMES)

    tithi_end_display = _format_hms(_hms_to_hours(tithi_data[1]))
    nak_end_display = _format_hms(_hms_to_hours(nakshatra_data[1]))
    yoga_end_display = _format_hms(_hms_to_hours(yoga_data[1]))
    karana_end_display = _format_hms(_local_hours_from_utc_jd(karana_end_utc, local_midnight_utc_jd)) if karana_end_utc else "--"
    current_lagna = _lagna_context(date_str, reference_hours, latitude, longitude, tz_hours)
    current_anandadi = _anandadi_context(date_str, reference_hours, latitude, longitude, tz_hours)
    hora_timeline = _hora_timeline(previous_sunset_hours, sunrise_hours, sunset_hours, next_sunrise_hours, weekday)
    lagna_timeline = _merge_short_timeline_segments(_collect_local_timeline(
        0.0,
        24.0,
        lambda local_hours: _lagna_context(date_str, local_hours, latitude, longitude, tz_hours)["name"],
        lambda local_hours: {"name": _lagna_context(date_str, local_hours, latitude, longitude, tz_hours)["display"]},
        step_minutes=5.0,
    ), min_minutes=1.0)
    anandadi_timeline = _merge_short_timeline_segments(_collect_local_timeline(
        0.0,
        24.0,
        lambda local_hours: _anandadi_context(date_str, local_hours, latitude, longitude, tz_hours)["index"],
        lambda local_hours: {"name": _anandadi_context(date_str, local_hours, latitude, longitude, tz_hours)["name"]},
        step_minutes=10.0,
    ), min_minutes=1.0)

    return {
        "date": date_str,
        "timezone": timezone_name,
        "timezone_offset_hours": tz_hours,
        "reference_time": _format_hms(reference_hours),
        "weekday": {"number": weekday, "name": VARA_NAMES[weekday]},
        "sunrise": {"hours": sunrise_hours, "display": _format_hms(sunrise_hours)},
        "sunset": {"hours": sunset_hours, "display": _format_hms(sunset_hours)},
        "next_sunrise": {"hours": next_sunrise_hours, "display": _format_hms(next_sunrise_hours)},
        "day_length": {"hours": day_length_hours, "display": _format_duration(day_length_hours)},
        "night_length": {"hours": night_length_hours, "display": _format_duration(night_length_hours)},
        "masa": {"number": masa_number, "name": MASA_NAMES[masa_number], "adhika": masa_is_adhika},
        "rasi": {"number": rasi_number, "name": RASI_NAMES[rasi_number]},
        "tithi": {
            "number": tithi_data[0],
            "name": TITHI_NAMES[tithi_data[0]],
            "end_display": tithi_end_display,
            "paksha": "Shukla" if tithi_data[0] <= 15 else "Krishna",
            "entries": tithi_entries,
        },
        "nakshatra": {
            "number": nakshatra_data[0],
            "name": NAKSHATRA_NAMES[nakshatra_data[0]],
            "end_display": nak_end_display,
            "entries": nakshatra_entries,
        },
        "yoga": {
            "number": yoga_data[0],
            "name": YOGA_NAMES[yoga_data[0]],
            "end_display": yoga_end_display,
            "entries": yoga_entries,
        },
        "karana": {
            "number": karana_number,
            "name": KARANA_NAMES[karana_number],
            "end_display": karana_end_display,
            "entries": karana_entries,
        },
        "hora": hora,
        "lagna": current_lagna,
        "anandadi_yoga": current_anandadi,
        "rahu_kalam": {"display": f"{_format_hms(rahu_start)} - {_format_hms(rahu_end)}"},
        "yamagandam": {"display": f"{_format_hms(yama_start)} - {_format_hms(yama_end)}"},
        "durmuhurtam": [{"display": f"{_format_hms(start)} - {_format_hms(end)}"} for start, end in _durmuhurta_ranges(sunrise_hours, sunset_hours, weekday)],
        "amrita_gadiyalu": amrita_events,
        "varjyam": varjyam_events,
        "timelines": {
            "hora": hora_timeline,
            "lagna": lagna_timeline,
            "anandadi_yoga": anandadi_timeline,
        },
    }


if __name__ == "__main__":
    print(json.dumps(calculate_panchanga("2026-04-14", 17.385, 78.4867, timezone_offset_hours=5.5), indent=2))
