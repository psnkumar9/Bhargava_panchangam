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


#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Part-3 (degree-tight) range scanner:
  - Sensitive Point (SP) = transit Ascendant absolute degree at the given place/time.
  - Jupiter must be within ±tol degrees of SP (conjunction).
  - (Optional) Saturn's exact graha-drishti (3/7/10 ⇒ +60, +180, +300) must land within ±tol on the same SP.

7th target reinforcement (degree-tight Double Transit):
  - 7th target can be 'lord', 'cusp', or 'either' (default) from the NATAL chart.
  - Within ±pair_window_days around the center day, require:
      * (strict) BOTH Saturn & Jupiter hit the chosen 7th target degree (by conjunction or exact graha-drishti) within ±tol
      * (looser) either planet hits the target (configurable)

Intraday sampling:
  - Ascendant changes ~360°/sidereal-day; evaluate Asc multiple times/day (e.g., every 2-3 hours)
    so you don't miss Jupiter≈Asc moments.

Dependencies: jhora.const, jhora.utils, jhora.horoscope.chart.{charts,house}, jhora.panchanga.drik
"""

import math
from typing import List, Dict, Any, Tuple

from jhora import const, utils
from jhora.horoscope.chart import charts, house
from jhora.panchanga import drik


# ----------------- small helpers -----------------

def _wrap360(x: float) -> float:
    x %= 360.0
    return x + 360.0 if x < 0 else x


def _circ_abs_diff(a: float, b: float) -> float:
    d = abs((_wrap360(a) - _wrap360(b)) % 360.0)
    return d if d <= 180.0 else 360.0 - d


def _years_to_days(years: float) -> float:
    return years * 365.2425


def _merge_contiguous_days(jds: List[float]) -> List[Tuple[float, float]]:
    if not jds:
        return []
    jds_sorted = sorted(jds)
    out, start, prev = [], jds_sorted[0], jds_sorted[0]
    for x in jds_sorted[1:]:
        if x - prev <= 1.01:  # ~1 day tolerance
            prev = x
        else:
            out.append((start, prev))
            start = prev = x
    out.append((start, prev))
    return out


def _asc_abs_deg(jd: float, place) -> float:
    """
    Ascendant absolute degree:
      drik.ascendant may return (sign, deg_in_sign) or (sign, deg_in_sign, ..., ...)
      We accept 4-tuple as used in the user's code: asc_sign, asc_deg_in_sign, _, _
    """
    asc = drik.ascendant(jd, place)
    if isinstance(asc, (list, tuple)) and len(asc) >= 2:
        asc_sign, asc_deg_in_sign = asc[0], asc[1]
    else:
        raise ValueError("drik.ascendant(jd, place) must return at least (sign, deg_in_sign)")
    return _wrap360(int(asc_sign) * 30.0 + float(asc_deg_in_sign))


def _find_body_abs_deg(natal_pp, body_id) -> float:
    """ natal_pp: [[pid, (zod, deg)], ...] """
    for pid, (zod, deg) in natal_pp:
        if pid == body_id:
            return _wrap360(int(zod) * 30.0 + float(deg))
    raise ValueError(f"Body {body_id} not found in natal positions")


def _any_aspect_hits(planet_abs: float, aspects: Tuple[float, ...], target_abs: float, tol: float) -> bool:
    """Exact graha-drishti line (planet_abs + k) lands within ±tol of target_abs?"""
    for k in aspects:
        if _circ_abs_diff(_wrap360(planet_abs + k), target_abs) <= tol:
            return True
    return False


# ----------------- precompute Saturn/Jupiter array -----------------

def _precompute_sj_degrees(jd_start: float, jd_end: float, place) -> Tuple[List[float], List[float], float, int]:
    """
    Precompute daily sidereal longitudes (absolute degrees) for Saturn & Jupiter
    from jd_start..jd_end (inclusive). Returns (sat_arr, jup_arr, jd0, n_days).
    Index i corresponds to jd = jd0 + i.
    """
    n_days = int(math.floor(jd_end - jd_start)) + 1
    if n_days <= 0:
        return [], [], jd_start, 0

    sat_arr = [0.0] * n_days
    jup_arr = [0.0] * n_days
    tz = float(place.timezone)
    jd0 = jd_start
    for i in range(n_days):
        jd = jd0 + i
        jd_utc = jd - tz
        sat_arr[i] = _wrap360(drik.sidereal_longitude(jd_utc, const._SATURN))
        jup_arr[i] = _wrap360(drik.sidereal_longitude(jd_utc, const._JUPITER))
    return sat_arr, jup_arr, jd0, n_days


# ----------------- main range scanner -----------------

def scan_part3_with_7th_target_windows(
    jd_birth: float,
    place,
    marriage_age_range: Tuple[int, int] = (20, 35),
    tol: float = 2.0,
    require_saturn_hit_on_asc: bool = True,
    pair_window_days_on_7th: int = 180,         # lead/lag window for S & J to hit 7th target (lord/cusp)
    require_both_planets_on_7th: bool = True,   # both S & J must hit 7th target within the pairing window
    samples_per_day: int = 12,                  # intraday Asc sampling (e.g., 12 => every 2 hours)
    sev_target: str = "either",                 # 'lord' | 'cusp' | 'either'
    print_diagnostics: bool = True,
) -> List[Dict[str, Any]]:
    """
    Range-scan of Part-3 (degree-tight) + 7th target (Double Transit) across an age window.

    PRIMARY (Part-3):
      - Sensitive point (SP) = transit Asc absolute degree at the same place (intraday samples).
      - Jupiter must be within ±tol of SP (conjunction).
      - If require_saturn_hit_on_asc=True, Saturn's exact 3/7/10 drishti landing must also be within ±tol of SP.

    7th target reinforcement (degree-tight Double Transit):
      - 7th target(s) derived from the NATAL chart (fixed):
          * 7th lord's natal degree ('lord')
          * 7th-house cusp degree from natal equal houses ('cusp')
          * 'either' accepts either target
      - Within ±pair_window_days_on_7th around the center day, require:
          * (strict) BOTH Saturn & Jupiter hit the chosen 7th target degree (conjunction OR exact drishti within ±tol), OR
          * (looser) either planet hits (if require_both_planets_on_7th=False)

    Returns merged windows:
      [
        {
          "start_jd": (Y, M, D, fraction),
          "end_jd":   (Y, M, D, fraction),
          "sample": {
             "date": (Y, M, D, fraction),
             "note": "...",
             "asc_abs": <float>,
             "jupiter_abs": <float>,
             "saturn_abs": <float>,
             "sev_lord_id": <int>,
             "sev_lord_abs": <float>,
             "sev_cusp_abs": <float>,
             "sev_target_used": "lord" | "cusp"
          }
        },
        ...
      ]
    """
    start_age, end_age = marriage_age_range
    if end_age <= start_age:
        raise ValueError("marriage_age_range must be (start_age, end_age) with end_age > start_age")

    # --- Natal (fixed) ---
    natal_pp = charts.divisional_chart(jd_birth, place, divisional_chart_factor=1)

    # Natal Lagna sign (from natal_pp) -> 7th sign -> 7L id -> natal 7L absolute degree
    natal_lagna_sign = None
    for pid, (zod, _deg) in natal_pp:
        if pid == const._ascendant_symbol:
            natal_lagna_sign = int(zod)
            break
    if natal_lagna_sign is None:
        raise ValueError("Could not find natal Lagna in natal positions")

    sev_sign = (natal_lagna_sign + 6) % 12
    sev_lord_id = house.house_owner_from_planet_positions(natal_pp, sev_sign)
    sev_lord_abs = _find_body_abs_deg(natal_pp, sev_lord_id)  # natal 7L absolute degree

    # Natal Asc absolute degree (for natal 7H cusp)
    asc_nat = drik.ascendant(jd_birth, place)
    asc_sign_nat, asc_deg_nat = asc_nat[0], asc_nat[1]
    asc_abs_nat = _wrap360(int(asc_sign_nat) * 30.0 + float(asc_deg_nat))
    sev_cusp_abs = _wrap360(asc_abs_nat + 180.0)  # natal 7th-house cusp (equal houses)

    # Choose 7th target(s)
    sev_target = (sev_target or "either").lower()
    if sev_target not in ("lord", "cusp", "either"):
        raise ValueError("sev_target must be 'lord', 'cusp', or 'either'")

    if sev_target == "lord":
        sev_target_abs_list = [("lord", sev_lord_abs)]
    elif sev_target == "cusp":
        sev_target_abs_list = [("cusp", sev_cusp_abs)]
    else:  # 'either'
        sev_target_abs_list = [("lord", sev_lord_abs), ("cusp", sev_cusp_abs)]

    # --- Build scan window (daily) preserving the birth-time local clock ---
    frac_birth = jd_birth - math.floor(jd_birth)  # keep same time-of-day (local)
    start_jd = math.floor(jd_birth + _years_to_days(start_age)) + frac_birth
    end_jd   = math.floor(jd_birth + _years_to_days(end_age))   + frac_birth
    # --- Precompute Saturn/Jupiter for extended window (for 7th pairing) ---
    ext_start = start_jd - pair_window_days_on_7th
    ext_end   = end_jd   + pair_window_days_on_7th
    sat_arr, jup_arr, jd0, n_days = _precompute_sj_degrees(ext_start, ext_end, place)
    if n_days <= 0:
        return []

    # --- Scan base window ---
    i_start = int(round(start_jd - jd0))
    i_end   = int(round(end_jd   - jd0))
    base_len = i_end - i_start + 1
    if base_len <= 0:
        return []

    # Diagnostics
    dbg_jup_near_asc_days = 0
    dbg_primary_ok_days   = 0
    dbg_7th_pair_ok_days  = 0

    hit_days: List[float] = []
    details: List[Dict[str, Any]] = []

    SAT_ASP = (60.0, 180.0, 300.0)
    JUP_ASP = (120.0, 180.0, 240.0)

    s_per_day = max(1, int(samples_per_day))
    step_frac = 1.0 / float(s_per_day)

    for idx in range(i_start, i_end + 1):
        jd_center_day = jd0 + idx

        # Slow movers (reuse daily)
        sat_abs_day = sat_arr[idx]
        jup_abs_day = jup_arr[idx]

        # --- PRIMARY (Part-3) across intraday samples ---
        primary_ok = False
        jup_near_asc_any = False
        sat_line_hits_any = False
        asc_abs_sample = None  # keep last checked asc for diagnostics

        for s in range(s_per_day):
            jd_sample = jd_center_day + s * step_frac
            asc_abs = _asc_abs_deg(jd_sample, place)
            asc_abs_sample = asc_abs

            jup_near_asc = (_circ_abs_diff(jup_abs_day, asc_abs) <= tol)
            sat_line_hits_asc = _any_aspect_hits(sat_abs_day, SAT_ASP, asc_abs, tol)

            if jup_near_asc:
                jup_near_asc_any = True
            if sat_line_hits_asc:
                sat_line_hits_any = True

            if jup_near_asc and (sat_line_hits_asc if require_saturn_hit_on_asc else True):
                primary_ok = True
                break  # found a time that satisfies Part-3 on this date

        if jup_near_asc_any:
            dbg_jup_near_asc_days += 1
        if primary_ok:
            dbg_primary_ok_days += 1
        if not primary_ok:
            continue  # cannot satisfy 7th checks unless Part-3 holds

        # --- 7th target pairing within ±pair_window_days_on_7th ---
        halfw = int(pair_window_days_on_7th)
        sev_ok_any_target = False
        sev_hit_tag = None

        i0 = max(0, idx - halfw)
        i1 = min(len(sat_arr) - 1, idx + halfw)

        for tag, target_abs in sev_target_abs_list:
            jup_hits_target = False
            sat_hits_target = False

            for k in range(i0, i1 + 1):
                # Jupiter hits target? (conjunction OR exact 5/7/9 landing)
                if (not jup_hits_target) and (
                    _circ_abs_diff(jup_arr[k], target_abs) <= tol or
                    _any_aspect_hits(jup_arr[k], JUP_ASP, target_abs, tol)
                ):
                    jup_hits_target = True

                # Saturn hits target? (conjunction OR exact 3/7/10 landing)
                if (not sat_hits_target) and (
                    _circ_abs_diff(sat_arr[k], target_abs) <= tol or
                    _any_aspect_hits(sat_arr[k], SAT_ASP, target_abs, tol)
                ):
                    sat_hits_target = True

                if jup_hits_target and sat_hits_target:
                    break

            sev_ok = (jup_hits_target and sat_hits_target) if require_both_planets_on_7th else (jup_hits_target or sat_hits_target)
            if sev_ok:
                sev_ok_any_target = True
                sev_hit_tag = tag
                break  # accept this day if any 7th target worked

        if sev_ok_any_target:
            dbg_7th_pair_ok_days += 1
            hit_days.append(jd_center_day)
            details.append({
                "jd": jd_center_day,
                "date": utils.jd_to_gregorian(jd_center_day),
                "asc_abs": asc_abs_sample,
                "jupiter_abs": jup_abs_day,
                "saturn_abs": sat_abs_day,
                "sev_lord_id": sev_lord_id,
                "sev_lord_abs": sev_lord_abs,
                "sev_cusp_abs": sev_cusp_abs,
                "sev_target_used": sev_hit_tag,
                "jupiter_near_asc_any": jup_near_asc_any,
                "saturn_drishti_hits_asc_any": sat_line_hits_any,
                "samples_per_day": s_per_day,
                "pair_window_days_on_7th": pair_window_days_on_7th,
            })

    # Merge to windows (days where condition holds at least at one time)
    windows = _merge_contiguous_days(hit_days)

    if print_diagnostics:
        print("[PART-3 DIAG] days with (Jupiter near Asc) at some time:", dbg_jup_near_asc_days)
        print("[PART-3 DIAG] days with PRIMARY satisfied at some time:", dbg_primary_ok_days,
              f"(require_saturn_hit_on_asc={require_saturn_hit_on_asc})")
        print("[7th DIAG] days where 7th pairing is satisfied:", dbg_7th_pair_ok_days,
              f"(both={require_both_planets_on_7th}, pair±={pair_window_days_on_7th}d, target='{sev_target}')")

    out: List[Dict[str, Any]] = []
    for (w_start, w_end) in windows:
        sample = next((d for d in details if w_start <= d["jd"] <= w_end), None)
        out.append({
            "start_jd": utils.jd_to_gregorian(w_start),
            "end_jd":   utils.jd_to_gregorian(w_end),
            "sample": {
                "date": sample["date"] if sample else utils.jd_to_gregorian(w_start),
                "note": (f"Part-3 (Jup~Asc ±{tol}°, Sat 3/7/10 on Asc={require_saturn_hit_on_asc}) "
                         f"+ 7th target ({sev_target}; pair ±{pair_window_days_on_7th}d; "
                         f"both={require_both_planets_on_7th}); samples/day={s_per_day}"),
                "asc_abs": sample["asc_abs"] if sample else None,
                "jupiter_abs": sample["jupiter_abs"] if sample else None,
                "saturn_abs": sample["saturn_abs"] if sample else None,
                "sev_lord_id": sample["sev_lord_id"] if sample else None,
                "sev_lord_abs": sample["sev_lord_abs"] if sample else None,
                "sev_cusp_abs": sample["sev_cusp_abs"] if sample else None,
                "sev_target_used": sample["sev_target_used"] if sample else None,
            }
        })
    return out


def scan_dt_perfect_fit_windows(
    jd_birth: float,
    place,
    marriage_age_range: Tuple[int, int] = (20, 35),
    tol: float = 2.0,
    sev_target: str = "either",      # 'lord' | 'cusp' | 'either' (for Saturn's target)
    pair_window_days: int = 0,       # 0 => same-day; small values (e.g., 3) allow near-simultaneity
    print_diagnostics: bool = True,
) -> List[Dict[str, Any]]:
    """
    PERFECT-FIT DT (strict, 7th-centric; no Asc/Part-3 layer):

      Required:
        - Jupiter conjunct natal 7th-lord degree (|J - 7L| <= tol)

      AND (one of):
        - Saturn exact graha-drishti (3/7/10 => +60/180/300) landing on 7th-lord degree within tol
        - Saturn exact graha-drishti landing on 7th-house cusp degree within tol

      Same-day by default (pair_window_days=0). You may allow small ±N days if needed.

    Returns merged windows of days that satisfy the condition.
    """
    start_age, end_age = marriage_age_range
    if end_age <= start_age:
        raise ValueError("marriage_age_range must be (start_age, end_age) with end_age > start_age")

    # --- Natal (fixed) ---
    natal_pp = charts.divisional_chart(jd_birth, place, divisional_chart_factor=1)

    # Natal Lagna sign -> 7th sign -> 7L id -> natal 7L absolute degree
    natal_lagna_sign = None
    for pid, (zod, _deg) in natal_pp:
        if pid == const._ascendant_symbol:
            natal_lagna_sign = int(zod)
            break
    if natal_lagna_sign is None:
        raise ValueError("Could not find natal Lagna in natal positions")

    sev_sign = (natal_lagna_sign + 6) % 12
    sev_lord_id = house.house_owner_from_planet_positions(natal_pp, sev_sign)
    sev_lord_abs = _find_body_abs_deg(natal_pp, sev_lord_id)

    # Natal 7H cusp (equal houses) from natal Asc degree
    asc_nat = drik.ascendant(jd_birth, place)
    asc_sign_nat, asc_deg_nat = asc_nat[0], asc_nat[1]
    asc_abs_nat = _wrap360(int(asc_sign_nat) * 30.0 + float(asc_deg_nat))
    sev_cusp_abs = _wrap360(asc_abs_nat + 180.0)

    # Select Saturn's target(s)
    sev_target = (sev_target or "either").lower()
    if sev_target not in ("lord", "cusp", "either"):
        raise ValueError("sev_target must be 'lord', 'cusp', or 'either'")
    if sev_target == "lord":
        sat_targets = [("lord", sev_lord_abs)]
    elif sev_target == "cusp":
        sat_targets = [("cusp", sev_cusp_abs)]
    else:
        sat_targets = [("lord", sev_lord_abs), ("cusp", sev_cusp_abs)]

    # --- Build daily scan window at same local clock as birth ---
    frac_birth = jd_birth - math.floor(jd_birth)
    start_jd = math.floor(jd_birth + _years_to_days(start_age)) + frac_birth
    end_jd   = math.floor(jd_birth + _years_to_days(end_age))   + frac_birth

    # Precompute S/J for ±pair window coverage
    ext_start = start_jd - pair_window_days
    ext_end   = end_jd   + pair_window_days
    sat_arr, jup_arr, jd0, n_days = _precompute_sj_degrees(ext_start, ext_end, place)
    if n_days <= 0:
        return []

    # base window indexes
    i_start = int(round(start_jd - jd0))
    i_end   = int(round(end_jd   - jd0))
    base_len = i_end - i_start + 1
    if base_len <= 0:
        return []

    SAT_ASP = (60.0, 180.0, 300.0)

    hit_days: List[float] = []
    details: List[Dict[str, Any]] = []

    # Diagnostics counters
    dbg_jup_conj_7L = 0
    dbg_sat_hits_7th = 0

    for idx in range(i_start, i_end + 1):
        jd_center = jd0 + idx

        # Jupiter conjunct 7th-lord on center day?
        jup_abs = jup_arr[idx]
        jup_conj_7L = (_circ_abs_diff(jup_abs, sev_lord_abs) <= tol)
        if not jup_conj_7L:
            continue
        dbg_jup_conj_7L += 1

        # Saturn hits 7th target (lord or cusp) within ±pair_window_days
        halfw = int(pair_window_days)
        i0 = max(0, idx - halfw)
        i1 = min(len(sat_arr) - 1, idx + halfw)

        sat_ok_any = False
        sat_hit_tag = None

        for tag, target_abs in sat_targets:
            sat_ok = False
            for k in range(i0, i1 + 1):
                sat_abs = sat_arr[k]
                # Saturn exact graha-drishti landing on target (no conjunction in this strict profile)
                if _any_aspect_hits(sat_abs, SAT_ASP, target_abs, tol):
                    sat_ok = True
                    break
            if sat_ok:
                sat_ok_any = True
                sat_hit_tag = tag
                break

        if sat_ok_any:
            dbg_sat_hits_7th += 1
            hit_days.append(jd_center)
            details.append({
                "jd": jd_center,
                "date": utils.jd_to_gregorian(jd_center),
                "jupiter_abs": jup_abs,
                "sev_lord_id": sev_lord_id,
                "sev_lord_abs": sev_lord_abs,
                "sev_cusp_abs": sev_cusp_abs,
                "saturn_target_used": sat_hit_tag,
                "tol": tol,
                "pair_window_days": pair_window_days,
            })

    windows = _merge_contiguous_days(hit_days)
    if print_diagnostics:
        print("[PERFECT-DT DIAG] JUP conjunct 7L days:", dbg_jup_conj_7L)
        print("[PERFECT-DT DIAG] SAT hit (7L/7H) days:", dbg_sat_hits_7th,
              f"(pair±={pair_window_days}d, target='{sev_target}')")

    out: List[Dict[str, Any]] = []
    for (w_start, w_end) in windows:
        sample = next((d for d in details if w_start <= d["jd"] <= w_end), None)
        out.append({
            "start_jd": utils.jd_to_gregorian(w_start),
            "end_jd":   utils.jd_to_gregorian(w_end),
            "sample": sample
        })
    return out

# ----------------- usage example -----------------

if __name__ == "__main__":
    utils.set_language('en')

    # EXAMPLES (uncomment the one you want)
    # dob = (1996, 12, 7);  tob = (10, 34, 0); place = drik.Place('Chennai',   13.0878, 80.2785, 5.5)
    # dob = (1964, 11, 16); tob = ( 4, 30, 0); place = drik.Place('Karamadai', 11.1800, 76.5700, 5.5)
    dob = (1969, 6, 22);   tob = (21, 41, 0); place = drik.Place('Trichy',    10.4900, 78.4100, 5.5)

    jd = utils.julian_day_number(dob, tob)
    from jhora.horoscope.chart import charts
    pp = charts.rasi_chart(jd, place); chart_1d = utils.get_house_planet_list_from_planet_positions(pp)
    print(chart_1d)
    """
    # Strict Part-3; 7th target = 'either'; wider pairing; 12 samples/day (every 2 hours)
    ret = scan_part3_with_7th_target_windows(
        jd_birth=jd,
        place=place,
        marriage_age_range=(20, 40),
        tol=2.0,
        require_saturn_hit_on_asc=True,     # keep Part-3 strict (Jup~Asc & Sat line on Asc)
        pair_window_days_on_7th=1080,        # allow realistic lead/lag for S/J to both reach 7th target
        require_both_planets_on_7th=True,   # strict DT on the 7th target (set False to loosen)
        samples_per_day=12,                 # intraday Asc sampling
        sev_target='either',                # 'lord' | 'cusp' | 'either'
        print_diagnostics=True,
    )

    print("MEDIUM-PART-3 windows:", len(ret))
    for w in ret:
        print(w)
    """
    
    ret = scan_dt_perfect_fit_windows(
        jd_birth=jd,
        place=place,
        marriage_age_range=(20,35),
        tol=2.0,                 # 1.5–2.0° typical for degree-tight
        sev_target='either',     # Saturn may hit 7L OR 7H
        pair_window_days=0,      # same-day; try 3–7 if you need small leeway
        print_diagnostics=True
    )
    print("PERFECT-FIT DT windows:", len(ret))
    for w in ret:
        print(w)
