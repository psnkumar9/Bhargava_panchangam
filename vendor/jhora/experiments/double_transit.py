#!/usr/bin/env python
"""
        STILL  UNDER EXPERIMENTATION - DO NOT USE THIS YET
"""
# -*- coding: UTF-8 -*-
# Copyright (C) Open Astro Technologies, USA.
# Modified by Sundar Sundaresan, USA. carnaticmusicguru2015@comcast.net
# Downloaded from https://github.com/naturalstupid/PyJHora

# This file is part of the "PyJHora" Python library
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# -*- coding: utf-8 -*-
import math
from typing import List, Tuple, Dict, Any
from jhora import const, utils
from jhora.horoscope.chart import charts,house
from jhora.panchanga import drik

def _find_planet_sign(planet_positions: List[List[Any]], planet_id: int) -> int:
    """Return zodiac (0..11) where the given planet_id sits in planet_positions."""
    for pid, (zodiac, _deg) in planet_positions:
        if pid == planet_id:
            return zodiac
    raise ValueError(f"Planet id {planet_id} not found in planet_positions")


def _find_lagna_sign(planet_positions: List[List[Any]]) -> int:
    """Return zodiac (0..11) of Lagna using const._ascendant_symbol."""
    asc = const._ascendant_symbol  # usually 'L'
    for pid, (zodiac, _deg) in planet_positions:
        if pid == asc:
            return zodiac
    raise ValueError("Lagna not found in planet_positions")


def _house_sign_from(base_sign: int, house_num: int) -> int:
    """House num: 1..12 relative to base_sign (0..11 zodiac) -> sign (0..11)."""
    return (base_sign + (house_num - 1)) % 12


def _seventh_lord_id_old(planet_positions: List[List[Any]], seventh_sign: int) -> int:
    """Return planet id who owns the 7th sign (from given frame) using provided API."""
    return house.house_owner_from_planet_positions(planet_positions, seventh_sign)


def _graha_aspect_signs(planet_sign: int, planet_id: int) -> List[int]:
    """
    Sign-based graha dṛṣṭi (no orb):
    - Saturn: aspects signs at +3, +7, +10
    - Jupiter: aspects signs at +5, +7, +9
    Returns list of target signs (0..11).
    """
    planet_sign = planet_sign % 12
    if planet_id == const.SATURN_ID:
        offs = (3, 7, 10)
    elif planet_id == const.JUPITER_ID:
        offs = (5, 7, 9)
    else:
        return []
    return [ (planet_sign + d) % 12 for d in offs ]


def _influences_sign(planet_transit_sign: int, planet_id: int, target_sign: int) -> bool:
    """Transit planet influences a sign if it occupies OR graha-aspects that sign."""
    if planet_transit_sign % 12 == target_sign % 12:
        return True
    return (target_sign % 12) in _graha_aspect_signs(planet_transit_sign, planet_id)


def _saturn_jupiter_transit_signs(jd_transit: float, place) -> Tuple[int, int]:
    """
    Compute sidereal transit signs for Saturn & Jupiter at given jd_transit
    using jd_utc = jd - place.timezone.
    """
    jd_utc = jd_transit - float(place.timezone)
    sat_long = drik.sidereal_longitude(jd_utc, const._SATURN)
    jup_long = drik.sidereal_longitude(jd_utc, const._JUPITER)
    sat_sign = int(sat_long // 30) % 12
    jup_sign = int(jup_long // 30) % 12
    return sat_sign, jup_sign


def _frame_targets(planet_positions: List[List[Any]], base_sign: int) -> Dict[str, Any]:
    """
    Compute target signs & 7L for a frame:
      - primary candidates: 7H sign, 7L natal sign
      - supporting: 2H sign, 11H sign
    """
    seventh_sign = _house_sign_from(base_sign, 7)
    second_sign = _house_sign_from(base_sign, 2)
    eleventh_sign = _house_sign_from(base_sign, 11)

    seventh_lord_id = _seventh_lord_id_old(planet_positions, seventh_sign)
    seventh_lord_sign = _find_planet_sign(planet_positions, seventh_lord_id)

    return {
        "primary_signs": {seventh_sign, seventh_lord_sign},
        "support_signs": {second_sign, eleventh_sign},
        "seventh_sign": seventh_sign,
        "seventh_lord_id": seventh_lord_id,
        "seventh_lord_sign": seventh_lord_sign,
        "second_sign": second_sign,
        "eleventh_sign": eleventh_sign,
    }


def _double_transit_hits_for_frame(
    sat_sign: int,
    jup_sign: int,
    frame_targets: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Check strict double transit per frame:
      - There exists a PRIMARY target in {7H, 7L_sign} influenced by BOTH S & J
      - There exists a SUPPORT target in {2H, 11H} influenced by BOTH S & J
    Returns details with booleans and which targets hit.
    """
    prim_hits = []
    for ps in frame_targets["primary_signs"]:
        s_hit = _influences_sign(sat_sign, const.SATURN_ID, ps)
        j_hit = _influences_sign(jup_sign, const.JUPITER_ID, ps)
        if s_hit and j_hit:
            prim_hits.append(ps)

    supp_hits = []
    for ss in frame_targets["support_signs"]:
        s_hit = _influences_sign(sat_sign, const.SATURN_ID, ss)
        j_hit = _influences_sign(jup_sign, const.JUPITER_ID, ss)
        if s_hit and j_hit:
            supp_hits.append(ss)

    return {
        "primary_ok": len(prim_hits) > 0,
        "support_ok": len(supp_hits) > 0,
        "primary_targets": prim_hits,   # signs where both S&J hit
        "support_targets": supp_hits,   # signs where both S&J hit
    }


def _double_transit_condition_on_date(
    jd_birth: float,
    place,
    jd_transit: float,
    require_both_frames: bool = False,
) -> Dict[str, Any]:
    """
    Evaluate pure Double Transit on a single date.
    Returns a dict with booleans and diagnostics.
    """
    # Natal rāśi
    natal_pp = charts.divisional_chart(jd_birth, place, divisional_chart_factor=1)
    lagna_sign = _find_lagna_sign(natal_pp)
    moon_sign = _find_planet_sign(natal_pp, const.MOON_ID)

    # Targets per frame
    lagna_targets = _frame_targets(natal_pp, lagna_sign)
    chandra_targets = _frame_targets(natal_pp, moon_sign)

    # Transit signs (sidereal)
    sat_sign, jup_sign = _saturn_jupiter_transit_signs(jd_transit, place)

    # Check per frame
    lagna_res = _double_transit_hits_for_frame(sat_sign, jup_sign, lagna_targets)
    chandra_res = _double_transit_hits_for_frame(sat_sign, jup_sign, chandra_targets)

    lagna_ok = lagna_res["primary_ok"] and lagna_res["support_ok"]
    chandra_ok = chandra_res["primary_ok"] and chandra_res["support_ok"]

    if require_both_frames:
        overall_ok = lagna_ok and chandra_ok
    else:
        overall_ok = lagna_ok or chandra_ok

    return {
        "ok": overall_ok,
        "lagna_ok": lagna_ok,
        "chandra_ok": chandra_ok,
        "lagna_res": lagna_res,
        "chandra_res": chandra_res,
        "sat_sign": sat_sign,
        "jup_sign": jup_sign,
    }


def _years_to_days(years: float) -> float:
    """Mean tropical year; good enough for monthly scanning of slow-movers."""
    return years * 365.2425


def double_transit_marriage_windows(
    jd_birth: float,
    place,
    marriage_age_range: Tuple[int, int] = (20, 35),
    step_days: float = 30.0,
    require_both_frames: bool = False,
) -> List[Dict[str, Any]]:
    """
    Scan the given age window from birth and return dates (JDs) where
    STRICT Double Transit (Saturn+Jupiter) marriage condition is met.

    STRICT rule per frame:
      - BOTH Saturn & Jupiter influence (occupy OR graha-aspect) the PRIMARY target:
          { 7th house sign, 7th lord's natal sign }
      - BOTH Saturn & Jupiter influence the SUPPORT target:
          { 2nd house sign, 11th house sign }
    Frame logic:
      - If require_both_frames=True => both Lagna and Moon frames must satisfy
      - Else (default) => either frame suffices

    Returns a list of dicts:
      {
        "jd": <transit_jd>,
        "ok": True,
        "lagna_ok": bool,
        "chandra_ok": bool,
        "sat_sign": int,
        "jup_sign": int,
        "lagna_primary_targets": [signs],
        "lagna_support_targets": [signs],
        "chandra_primary_targets": [signs],
        "chandra_support_targets": [signs],
      }
    """
    start_year, end_year = marriage_age_range
    if end_year <= start_year:
        raise ValueError("marriage_age_range must be (start_year, end_year) with end > start")

    start_jd = jd_birth + _years_to_days(start_year)
    end_jd = jd_birth + _years_to_days(end_year)

    out = []
    jd = start_jd
    while jd <= end_jd:
        res = _double_transit_condition_on_date(
            jd_birth=jd_birth,
            place=place,
            jd_transit=jd,
            require_both_frames=require_both_frames,
        )
        if res["ok"]:
            out.append({
                "date": utils.jd_to_gregorian(jd),
                "ok": True,
                "lagna_ok": res["lagna_ok"],
                "chandra_ok": res["chandra_ok"],
                "sat_sign": res["sat_sign"],
                "jup_sign": res["jup_sign"],
                "lagna_primary_targets": res["lagna_res"]["primary_targets"],
                "lagna_support_targets": res["lagna_res"]["support_targets"],
                "chandra_primary_targets": res["chandra_res"]["primary_targets"],
                "chandra_support_targets": res["chandra_res"]["support_targets"],
            })
        jd += step_days

    return out

# === helpers ================================================================

def _abs_degree(zodiac: int, deg_in_sign: float) -> float:
    return (zodiac % 12) * 30.0 + float(deg_in_sign)

def _find_body(planet_positions: List[List[Any]], body_id) -> Tuple[int, float]:
    """Return (sign, deg_in_sign) for given body_id (e.g., const._ascendant_symbol, const.MOON_ID, etc.)."""
    for pid, (zod, deg) in planet_positions:
        if pid == body_id:
            return (int(zod), float(deg))
    raise ValueError(f"Body {body_id} not found")

def _lagna_abs_deg(natal_pp: List[List[Any]]) -> float:
    s, d = _find_body(natal_pp, const._ascendant_symbol)
    return _abs_degree(s, d)

def _planet_abs_deg(natal_pp: List[List[Any]], pid: int) -> float:
    s, d = _find_body(natal_pp, pid)
    return _abs_degree(s, d)

def _house_cusp_equal(anchor_abs_deg: float, house_num: int) -> float:
    """Equal houses anchored at anchor_abs_deg (house_num: 1..12)."""
    return (anchor_abs_deg + 30.0 * (house_num - 1)) % 360.0

def _mod360(x: float) -> float:
    y = x % 360.0
    return y if y >= 0 else y + 360.0

def _circ_abs_diff(a: float, b: float) -> float:
    """Smallest absolute angular difference (deg) on the circle."""
    d = abs(_mod360(a) - _mod360(b))
    return d if d <= 180.0 else 360.0 - d

def _within_orb(angle: float, targets: List[float], orb: float) -> bool:
    return any(_circ_abs_diff(angle, t) <= orb for t in targets)

def _planet_hits_target_degree(transit_deg: float, pid: int, target_deg: float, orb: float) -> bool:
    """
    Degree-locked hit:
      (a) planet within orb of target degree, OR
      (b) target degree is within orb of planet's graha-drishti lines (exact aspect angles)
    """
    # (a) near cusp/planet degree itself
    if _circ_abs_diff(transit_deg, target_deg) <= orb:
        return True

    # (b) exact graha-drishti angles to the target
    if pid == const.SATURN_ID:
        aspect_angles = (60.0, 180.0, 300.0)  # 3, 7, 10 houses
    elif pid == const.JUPITER_ID:
        aspect_angles = (120.0, 180.0, 240.0) # 5, 7, 9 houses
    else:
        return False

    # Compute the angular separation from planet to target
    delta = _mod360(target_deg - transit_deg)
    return _within_orb(delta, list(aspect_angles), orb)

def _seventh_lord_id_new(natal_pp: List[List[Any]], base_sign: int) -> int:
    seventh_sign = (base_sign + 6) % 12
    return house.house_owner_from_planet_positions(natal_pp, seventh_sign)

def _saturn_jupiter_transit_degrees(jd_transit: float, place) -> Tuple[float, float]:
    jd_utc = jd_transit - float(place.timezone)
    sat_deg = float(drik.sidereal_longitude(jd_utc, const._SATURN)) % 360.0
    jup_deg = float(drik.sidereal_longitude(jd_utc, const._JUPITER)) % 360.0
    return sat_deg, jup_deg

def _frame_targets_abs_degrees(natal_pp: List[List[Any]], anchor_abs_deg: float, base_sign: int) -> Dict[str, float]:
    """Return absolute degrees for {2H cusp, 7H cusp, 11H cusp, 7L degree} for this frame."""
    twoH = _house_cusp_equal(anchor_abs_deg, 2)
    sevH = _house_cusp_equal(anchor_abs_deg, 7)
    elevH = _house_cusp_equal(anchor_abs_deg, 11)
    sev_lord_id = _seventh_lord_id_new(natal_pp, base_sign)
    sev_lord_abs = _planet_abs_deg(natal_pp, sev_lord_id)
    return {"twoH": twoH, "sevH": sevH, "elevH": elevH, "sevL_deg": sev_lord_abs}

def _check_frame_degree_locked(sat_deg: float, jup_deg: float, targets: Dict[str, float], orb: float) -> Dict[str, Any]:
    """
    For this frame:
      PRIMARY must be satisfied by both S & J on the SAME one among {sevH, sevL_deg}
      SUPPORT must be satisfied by both S & J on the SAME one among {twoH, elevH}
    """
    prim_candidates = [("7H", targets["sevH"]), ("7L", targets["sevL_deg"])]
    supp_candidates = [("2H", targets["twoH"]), ("11H", targets["elevH"])]

    prim_hit_name = None
    for name, deg in prim_candidates:
        if (_planet_hits_target_degree(sat_deg, const.SATURN_ID, deg, orb) and
            _planet_hits_target_degree(jup_deg, const.JUPITER_ID, deg, orb)):
            prim_hit_name = name
            break

    supp_hit_name = None
    for name, deg in supp_candidates:
        if (_planet_hits_target_degree(sat_deg, const.SATURN_ID, deg, orb) and
            _planet_hits_target_degree(jup_deg, const.JUPITER_ID, deg, orb)):
            supp_hit_name = name
            break

    return {
        "primary_ok": prim_hit_name is not None,
        "support_ok": supp_hit_name is not None,
        "primary_target": prim_hit_name,
        "support_target": supp_hit_name,
    }

def _planet_hits_target_in_window(jd_center: float, place, pid: int, target_deg: float,
                                  orb: float, half_window_days: int) -> bool:
    """
    Returns True if planet pid hits target_deg within ±half_window_days of jd_center
    (planet near target degree OR exact graha-drishti lines within orb).
    """
    d = -int(half_window_days)
    while d <= int(half_window_days):
        jd = jd_center + float(d)
        jd_utc = jd - float(place.timezone)
        p_deg = float(drik.sidereal_longitude(jd_utc, pid)) % 360.0
        if _planet_hits_target_degree(p_deg, pid, target_deg, orb):
            return True
        d += 1
    return False


def _check_frame_degree_locked_pairing(jd_center: float, place,
                                       frame_targets: Dict[str, float],
                                       orb: float, pair_window_days: int) -> Dict[str, Any]:
    """
    Degree-locked pairing check for one frame:
      PRIMARY: both S & J hit SAME target in {7H cusp, 7L degree} within ±pair_window_days of jd_center.
      SUPPORT: both S & J hit SAME target in {2H cusp, 11H cusp} within ±pair_window_days of jd_center.
    """
    prim_candidates = [("7H", frame_targets["sevH"]), ("7L", frame_targets["sevL_deg"])]
    supp_candidates = [("2H", frame_targets["twoH"]), ("11H", frame_targets["elevH"])]

    prim_hit = None
    for name, deg in prim_candidates:
        s_ok = _planet_hits_target_in_window(jd_center, place, const.SATURN_ID, deg, orb, pair_window_days)
        j_ok = _planet_hits_target_in_window(jd_center, place, const.JUPITER_ID, deg, orb, pair_window_days)
        if s_ok and j_ok:
            prim_hit = name
            break

    supp_hit = None
    for name, deg in supp_candidates:
        s_ok = _planet_hits_target_in_window(jd_center, place, const.SATURN_ID, deg, orb, pair_window_days)
        j_ok = _planet_hits_target_in_window(jd_center, place, const.JUPITER_ID, deg, orb, pair_window_days)
        if s_ok and j_ok:
            supp_hit = name
            break

    return {
        "primary_ok": prim_hit is not None,
        "support_ok": supp_hit is not None,
        "primary_target": prim_hit,
        "support_target": supp_hit,
    }

def _merge_contiguous_days(jds: List[float]) -> List[Tuple[float, float]]:
    """Compress consecutive-day hits into windows."""
    if not jds:
        return []
    jds_sorted = sorted(jds)
    windows = []
    start = prev = jds_sorted[0]
    for x in jds_sorted[1:]:
        if x - prev <= 1.01:  # ~1 day
            prev = x
            continue
        windows.append((start, prev))
        start = prev = x
    windows.append((start, prev))
    return windows

#def _years_to_days(years: float) -> float:
#    return years * 365.2425

# === main ===================================================================


def _precompute_transit_degrees(jd_start: float, jd_end: float, place) -> Tuple[List[float], List[float], float, int]:
    """
    Precompute daily sidereal longitudes for Saturn & Jupiter from jd_start..jd_end (inclusive).
    Returns (sat_arr, jup_arr, jd0, n_days) where index i maps to jd = jd0 + i.
    """
    n_days = int(math.floor(jd_end - jd_start)) + 1
    if n_days <= 0:
        return [], [], jd_start, 0
    sat_arr = [0.0] * n_days
    jup_arr = [0.0] * n_days
    jd0 = jd_start
    tz = float(place.timezone)
    for i in range(n_days):
        jd = jd0 + i
        jd_utc = jd - tz
        sat_arr[i] = float(drik.sidereal_longitude(jd_utc, const._SATURN)) % 360.0
        jup_arr[i] = float(drik.sidereal_longitude(jd_utc, const._JUPITER)) % 360.0
    return sat_arr, jup_arr, jd0, n_days


def _planet_hits_target_in_window_precomp(center_idx: int, deg_arr: List[float], pid: int,
                                          target_deg: float, orb: float, half_window: int) -> bool:
    """
    Fast version: check hits using precomputed degrees.
    (a) planet near target degree OR
    (b) target within orb of planet's exact graha-drishti lines.
    """
    i0 = max(0, center_idx - half_window)
    i1 = min(len(deg_arr) - 1, center_idx + half_window)

    # choose aspect angles based on planet id
    if pid == const.SATURN_ID:
        aspect_angles = (60.0, 180.0, 300.0)
    elif pid == const.JUPITER_ID:
        aspect_angles = (120.0, 180.0, 240.0)
    else:
        return False

    for i in range(i0, i1 + 1):
        pdeg = deg_arr[i]
        # near target itself
        if _circ_abs_diff(pdeg, target_deg) <= orb:
            return True
        # near exact graha-drishti lines
        delta = _mod360(target_deg - pdeg)
        if _within_orb(delta, aspect_angles, orb):
            return True
    return False


def _check_frame_degree_locked_pairing_precomp(center_idx: int,
                                               sat_arr: List[float], jup_arr: List[float],
                                               frame_targets: Dict[str, float],
                                               orb: float, pair_window_days: int) -> Dict[str, Any]:
    """
    Pairing check, but uses precomputed sat_arr/jup_arr instead of ephemeris calls.
    """
    prim_candidates = [("7H", frame_targets["sevH"]), ("7L", frame_targets["sevL_deg"])]
    supp_candidates = [("2H", frame_targets["twoH"]), ("11H", frame_targets["elevH"])]
    halfw = int(pair_window_days)

    prim_hit = None
    for name, deg in prim_candidates:
        s_ok = _planet_hits_target_in_window_precomp(center_idx, sat_arr, const.SATURN_ID, deg, orb, halfw)
        j_ok = _planet_hits_target_in_window_precomp(center_idx, jup_arr, const.JUPITER_ID, deg, orb, halfw)
        if s_ok and j_ok:
            prim_hit = name
            break

    supp_hit = None
    for name, deg in supp_candidates:
        s_ok = _planet_hits_target_in_window_precomp(center_idx, sat_arr, const.SATURN_ID, deg, orb, halfw)
        j_ok = _planet_hits_target_in_window_precomp(center_idx, jup_arr, const.JUPITER_ID, deg, orb, halfw)
        if s_ok and j_ok:
            supp_hit = name
            break

    return {
        "primary_ok": prim_hit is not None,
        "support_ok": supp_hit is not None,
        "primary_target": prim_hit,
        "support_target": supp_hit,
    }




def double_transit_marriage_windows_degree_locked(
    jd_birth: float,
    place,
    marriage_age_range: Tuple[int, int] = (20, 35),
    orb_degrees: float = 3.0,           # realistic cusp orb
    pair_window_days: int = 60,         # ±days for S/J pairing (same target)
    require_both_frames: bool = True,   # keep True for strong DT
    frame_pair_window_days: int = 30,   # ±days tolerance between Lagna & Moon frames
) -> List[Dict[str, Any]]:
    """
    DTM-Degree v1 (paired, precomputed, frame-tolerant):
      - PRIMARY: both S & J hit SAME one in {7H cusp, 7L natal degree} within ±pair_window_days of a center day.
      - SUPPORT: both S & J hit SAME one in {2H cusp, 11H cusp} within ±pair_window_days of a center day.
      - Frames: require Lagna and Moon frames to satisfy, but allow a ±frame_pair_window_days lead/lag
                between their satisfied center days (instead of exact same date).
      - Daily scan across age window; merged contiguous days returned as windows.
    """
    try:
        if marriage_age_range[1] <= marriage_age_range[0]:
            raise ValueError("marriage_age_range must be (start_year, end_year) with end > start")

        print(f"[DTM] ENTER degree_locked_precomp: range={marriage_age_range}, "
              f"orb={orb_degrees}, pair=±{pair_window_days}d, both_frames={require_both_frames}, "
              f"frame_pair=±{frame_pair_window_days}d")

        # Natal rāśi positions
        natal_pp = charts.divisional_chart(jd_birth, place, divisional_chart_factor=1)

        # Frame anchors (absolute degrees)
        lagna_sign, lagna_deg_in_sign = _find_body(natal_pp, const._ascendant_symbol)
        lagna_abs = _abs_degree(lagna_sign, lagna_deg_in_sign)
        moon_sign, moon_deg_in_sign = _find_body(natal_pp, const.MOON_ID)
        moon_abs = _abs_degree(moon_sign, moon_deg_in_sign)

        # Targets
        lagna_targets   = _frame_targets_abs_degrees(natal_pp, lagna_abs, lagna_sign)
        chandra_targets = _frame_targets_abs_degrees(natal_pp, moon_abs, moon_sign)

        # Base scan window
        start_jd = jd_birth + _years_to_days(marriage_age_range[0])
        end_jd   = jd_birth + _years_to_days(marriage_age_range[1])

        # Precompute degrees for an extended window to accommodate S/J pairing ±days
        ext_start = start_jd - pair_window_days
        ext_end   = end_jd   + pair_window_days

        sat_arr, jup_arr, jd0, n_days = _precompute_transit_degrees(ext_start, ext_end, place)
        if n_days <= 0:
            print("[DTM] No days to scan (n_days<=0).")
            return []

        print(f"[DTM] Precomputed S/J degrees for {n_days} days: "
              f"{utils.jd_to_gregorian(jd0)} .. {utils.jd_to_gregorian(jd0 + n_days - 1)}")

        # Index range for the *base* window
        i_start = int(round(start_jd - jd0))
        i_end   = int(round(end_jd   - jd0))
        base_len = i_end - i_start + 1
        if base_len <= 0:
            print("[DTM] base window length <=0.")
            return []

        # Per-day per-frame results over the base window
        lagna_ok_arr   = [False] * base_len
        chandra_ok_arr = [False] * base_len

        # Diagnostics: how often each frame (alone) passes strict (prim+supp) on its own center day
        any_prim_lagna = any_supp_lagna = both_prim_supp_lagna = 0
        any_prim_chandra = any_supp_chandra = both_prim_supp_chandra = 0

        # Compute frame-specific strict hits for each center day in base window
        for idx in range(i_start, i_end + 1):
            base_i = idx - i_start  # 0-based within base window

            lagna_res = _check_frame_degree_locked_pairing_precomp(
                idx, sat_arr, jup_arr, lagna_targets, orb_degrees, pair_window_days
            )
            chandra_res = _check_frame_degree_locked_pairing_precomp(
                idx, sat_arr, jup_arr, chandra_targets, orb_degrees, pair_window_days
            )

            if lagna_res["primary_ok"]:  any_prim_lagna += 1
            if lagna_res["support_ok"]:  any_supp_lagna += 1
            if lagna_res["primary_ok"] and lagna_res["support_ok"]:
                both_prim_supp_lagna += 1
                lagna_ok_arr[base_i] = True

            if chandra_res["primary_ok"]:  any_prim_chandra += 1
            if chandra_res["support_ok"]:  any_supp_chandra += 1
            if chandra_res["primary_ok"] and chandra_res["support_ok"]:
                both_prim_supp_chandra += 1
                chandra_ok_arr[base_i] = True

        print("[DTM] lagna: any_prim:", any_prim_lagna, " any_supp:", any_supp_lagna,
              " both_prim+supp:", both_prim_supp_lagna)
        print("[DTM] chandra: any_prim:", any_prim_chandra, " any_supp:", any_supp_chandra,
              " both_prim+supp:", both_prim_supp_chandra)

        # If we do NOT require both frames, just OR them
        if not require_both_frames:
            combined = [lagna_ok_arr[i] or chandra_ok_arr[i] for i in range(base_len)]
        else:
            # Frame-pairing tolerance: allow frames to satisfy within ±F days
            F = max(0, int(frame_pair_window_days))
            lagna_near   = [False] * base_len
            chandra_near = [False] * base_len

            for i, ok in enumerate(lagna_ok_arr):
                if not ok: continue
                a = max(0, i - F)
                b = min(base_len - 1, i + F)
                for k in range(a, b + 1):
                    lagna_near[k] = True

            for i, ok in enumerate(chandra_ok_arr):
                if not ok: continue
                a = max(0, i - F)
                b = min(base_len - 1, i + F)
                for k in range(a, b + 1):
                    chandra_near[k] = True

            combined = [lagna_near[i] and chandra_near[i] for i in range(base_len)]

        # Convert combined booleans to JD days and merge to windows
        hit_days = []
        for i, is_hit in enumerate(combined):
            if is_hit:
                jd = jd0 + (i_start + i)
                hit_days.append(jd)

        windows = _merge_contiguous_days(hit_days)
        print("[DTM] windows idx:", [(int(round(s - jd0)), int(round(e - jd0))) for (s, e) in windows])

        # Build output with a sample center day from each window
        out = []
        for (w_start, w_end) in windows:
            sample_jd = w_start
            sample = {
                "date": utils.jd_to_gregorian(sample_jd),
                "note": f"Both frames satisfied within ±{frame_pair_window_days}d; S/J paired within ±{pair_window_days}d; orb={orb_degrees}°",
            }
            out.append({
                "start_jd": utils.jd_to_gregorian(w_start),
                "end_jd": utils.jd_to_gregorian(w_end),
                "sample": sample,
            })
        return out

    except Exception as e:
        import traceback
        print("[DTM][ERROR]", str(e))
        traceback.print_exc()
        return []


if __name__ == "__main__":
    utils.set_language('en')
    #dob = (1996,12,7); tob = (10,34,0); place = drik.Place('Chennai',13.0878,80.2785,5.5)
    #dob = (1964,11,16); tob = (4,30,0); place = drik.Place('Karamadai',11.18,76.57,5.5)
    dob = (1969,6,22); tob = (21,41,0); place = drik.Place('Trichy',10.49,78.41,5.5)
    #dob = (1973,7,26); tob = (21,41,0); place = drik.Place('UNK',16+13/60,80+28/60,5.5)
    jd  = utils.julian_day_number(dob, tob)

    # sign-based method (monthly)
    ret1 = double_transit_marriage_windows(jd, place, marriage_age_range=(20,35), step_days=30.0)#, require_both_frames=True)
    print("[SIGN-BASED] hits:", len(ret1))
    print(ret1)
    # Degree-locked DT: both frames, ±60d S/J pairing, ±30d frame tolerance
    ret_deg = double_transit_marriage_windows_degree_locked(
        jd, place,
        marriage_age_range=(20,35),
        orb_degrees=3.0,
        pair_window_days=60,
        require_both_frames=True,
        frame_pair_window_days=30,
    )
    print("[DEGREE-LOCKED] windows:", ret_deg)

