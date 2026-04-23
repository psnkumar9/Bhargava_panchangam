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
# === Marriage Timing Prediction: Orchestration ===
# Assumes PyJHora is installed and you import the needed namespaces in your environment.
# This file keeps your variable names & calling patterns. TODOs are clearly marked.

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# External modules from your stack (assumed already available in your environment)
# If your actual module paths differ, adjust imports accordingly.
import swisseph as swe  # used to build JD for mid-month, etc.

# Expected available modules in your environment:
from jhora import const, utils
from jhora.panchanga import drik
from jhora.horoscope.chart import charts, house, arudhas
from jhora.horoscope.dhasa.graha import vimsottari
from jhora.horoscope.dhasa.raasi import kalachakra
from jhora.horoscope.dhasa.annual import patyayini
from jhora.horoscope.transit.tajaka import annual_chart, both_planets_within_their_deeptamsa
from jhora.horoscope.transit.saham import vivaha_saham_from_jd_place

# ---------- Public wrapper (jd/place) ----------
_marriage_age_year_range = (20, 32)

def predict_marriage_windows_from_jd_place(jd, place, start_year=None, end_year=None, divisional_chart_factor=1, method=1):
    """
    Orchestrates the full algorithm over a year range:
    - Builds D1, D9, derived points (UL, DK, 7L, Vivaha Saham)
    - Iterates Vimshottari MD/AD and monthly Jupiter windows
    - Applies SCD (year), Tajaka annual triggers (month/week)
    - (Optional) Kalachakra + compressed D9 Narayana confirmation
    Returns: list of dicts [{year, month, score, window, reasons}, ...] sorted by score
    """
    # ---- Inputs / defaults ----
    # Determine birth year
    yb, _, _, _ = utils.jd_to_gregorian(jd)

    # Compute the **allowed** year window based on marriage-age
    allowed_min_year = yb + _marriage_age_year_range[0]
    allowed_max_year = yb + _marriage_age_year_range[1]

    # Default start/end if None
    if start_year is None:
        start_year = allowed_min_year
    if end_year is None:
        end_year = allowed_max_year

    # **Hard clamp** the iteration range to the allowed window,
    # regardless of what the caller passed.
    iter_start_year = max(start_year, allowed_min_year)
    iter_end_year   = min(end_year, allowed_max_year)

    # If nothing to evaluate, return empty
    if iter_start_year > iter_end_year:
        return []

    # ---- collect chart information  ----
    rasi_planet_positions = charts.divisional_chart(jd, place, divisional_chart_factor=1)
    chart_1d_rasi = utils.get_house_planet_list_from_planet_positions(rasi_planet_positions)
    p_to_h_rasi = utils.get_planet_house_dictionary_from_planet_positions(rasi_planet_positions)

    navamsa_planet_positions = charts.divisional_chart(jd, place, divisional_chart_factor=9)
    chart_1d_d9 = utils.get_house_planet_list_from_planet_positions(navamsa_planet_positions)
    p_to_h_d9 = utils.get_planet_house_dictionary_from_planet_positions(navamsa_planet_positions)

    derived = _collect_marriage_primitives(
        jd, place,
        rasi_planet_positions, chart_1d_rasi, p_to_h_rasi,
        navamsa_planet_positions, chart_1d_d9, p_to_h_d9
    )

    _, vdb_info = vimsottari.get_vimsottari_dhasa_bhukthi(jd, place, divisional_chart_factor=divisional_chart_factor)
    segments = _expand_to_md_ad_segments(vdb_info)

    candidates = []

    for year in range(iter_start_year, iter_end_year + 1):
        scd_info = _sudarsana_chakra_year_info(jd, place, year, chart_1d_d9)
        tajaka = _get_varshaphala_marriage_triggers(jd, place, year, derived)

        for month in range(1, 13):
            month_start = datetime(year, month, 1)
            month_end = _end_of_month(year, month)

            md_ad_pd = _active_vimsottari_in_window(segments, month_start, month_end)
            vmd = _score_vimsottari_capability(md_ad_pd, derived)
            if vmd == 0:
                continue

            jtransit = _get_monthly_jupiter_transit_support(jd, place, year, month, derived)
            scd_score = _score_scd_year_support(scd_info, derived)
            tajaka_score, tajaka_detail = _score_tajaka_month(tajaka, month_start, month_end, derived)
            kcd_score = _score_kalachakra_support(jd, place, year, derived)  # may be 0 if not wired
            cnd9_score = _score_compressed_d9_narayana(jd, place, month_start, month_end, derived)  # may be 0 if not wired
            cultural = _score_cultural_month(month_start, month_end)  # may be 0 if not wired

            total = vmd + jtransit + scd_score + tajaka_score + kcd_score + cnd9_score + cultural

            if total > 0:
                # ===== BEGIN PATCH: enrich `reasons` so you can see *why* the month scored =====
                reasons = _collect_reasons(
                    md_ad_pd, jtransit, scd_info, tajaka_detail, kcd_score, cnd9_score, cultural, derived
                )
                # Make transit and SCD contributions explicit:
                reasons['jupiter_transit'] = jtransit          # 0..3
                reasons['scd_score'] = scd_score               # 0..2
            
                # Patyayini overlap (Venus/7L/UL-lord/Vivaha-Saham-lord/Muntha-lord):
                paty = tajaka.get('patyayini_schedule')
                if paty:
                    try:
                        LL = tajaka['annual_ll']
                        L7 = tajaka['annual_7l']
                        annual_pp = tajaka['annual_planet_positions']
            
                        # UL lord is computed in the ANNUAL chart
                        ul_sign = derived['ul_d1']
                        ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign)
            
                        # Vivaha Saham lord in the ANNUAL chart
                        vs_lord = house.house_owner_from_planet_positions(annual_pp, tajaka['vivaha_saham_sign'])
            
                        # Muntha lord (already in the bundle)
                        m_lord = tajaka['muntha_lord']
            
                        targets = {const.VENUS_ID, L7, ul_lord, vs_lord, m_lord}
                        hit = _patyayini_month_hit(paty, month_start, month_end, targets)
                        reasons['patyayini_hit'] = hit
                        if hit:
                            # List the lords whose slices overlap this month (sorted for stability)
                            reasons['patyayini_lords_in_month'] = sorted(
                                {sl['lord'] for sl in paty if not (sl['end'] < month_start or sl['start'] > month_end)},
                                key=str
                            )
                    except Exception:
                        # Be defensive: never break the flow if any lord lookup fails
                        reasons['patyayini_hit'] = False
                # ===== END PATCH ===============================================================

                candidates.append({
                    'year': year,
                    'month': month,
                    'window': (month_start, month_end),
                    'score': total,
                    'reasons': reasons#_collect_reasons(md_ad_pd, jtransit, scd_info, tajaka_detail, kcd_score, cnd9_score, cultural, derived)
                })

    candidates.sort(key=lambda c: (-c['score'], c['reasons'].get('ithasala_orb', 999), c['reasons'].get('venus_saham_delta', 999)))
    return candidates

# ---------- Calculation primitives & adapters ----------

def _collect_marriage_primitives(jd, place, pp_rasi, chart_1d_rasi, p_to_h_rasi, pp_d9, chart_1d_d9, p_to_h_d9):
    """
    Collects: 7H index, 7L in D1 and its aspects, Venus info, DK, UL (D1 & D9),
    D9: Lagna, 7H, 7L, placements of MD/AD/PD candidates, etc.
    Returns a dict used by all scoring functions.
    """
    out = {}

    # Birth meta
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    out['birth_year'] = by

    # --- D1 core ---
    out['lagna_sign_d1'] = p_to_h_rasi[const._ascendant_symbol]
    out['seventh_house_sign_d1'] = (out['lagna_sign_d1'] + const.HOUSE_7) % 12
    out['seventh_lord_d1'] = house.house_owner_from_planet_positions(pp_rasi, out['seventh_house_sign_d1'])

    # Venus sign in D1 (planet → sign)
    out['venus_sign_d1'] = p_to_h_rasi[const.VENUS_ID]

    # DK (planet id): chara_karakas returns [AK,...,DK]
    ck_list = house.chara_karakas(pp_rasi)
    out['dk'] = ck_list[-1] if isinstance(ck_list, (list, tuple)) else ck_list

    # UL in D1 & D9 (take A12/UL, i.e., last item)
    al_ul_d1 = arudhas.bhava_arudhas_from_planet_positions(pp_rasi)
    out['ul_d1'] = al_ul_d1[-1]
    al_ul_d9 = arudhas.bhava_arudhas_from_planet_positions(pp_d9)
    out['ul_d9'] = al_ul_d9[-1]

    # Convenience: 7th lord sign in D1 (lets us check Jupiter aspect to 7L)
    out['seventh_lord_sign_d1'] = p_to_h_rasi[out['seventh_lord_d1']]

    # Aspects (optional): keep None for now unless you want to wire a PyJHora API (TODO)
    out['aspects_d1'] = None
    out['aspects_d9'] = None

    # --- D9 core ---
    out['lagna_sign_d9'] = p_to_h_d9[const._ascendant_symbol]
    out['seventh_house_sign_d9'] = (out['lagna_sign_d9'] + const.HOUSE_7) % 12
    out['seventh_lord_d9'] = house.house_owner_from_planet_positions(pp_d9, out['seventh_house_sign_d9'])

    # Store p_to_h for scoring helpers
    out['p_to_h_rasi'] = p_to_h_rasi
    out['p_to_h_d9'] = p_to_h_d9

    # Night/day flag (for Vivaha Saham logic)
    out['night_time_birth'] = drik.is_night_birth(jd, place)

    return out


def _get_vimsottari_md_ad_pd(jd, place, divisional_chart_factor=1):
    """
    Keep for parity — not used directly anymore. We prepare segments using _expand_to_md_ad_segments().
    """
    _, vdb_info = vimsottari.get_vimsottari_dhasa_bhukthi(jd, place, divisional_chart_factor=divisional_chart_factor)
    segments = _expand_to_md_ad_segments(vdb_info)
    return segments


def _expand_to_md_ad_segments(vdb_info):
    """
    vdb_info: [ [md:int, ad:int, 'YYYY-MM-DD'], ... ]  (chronological)
    Returns: [{'md':int,'ad':int,'start':datetime,'end':datetime}, ...]
    The last segment gets a far-future end to cover queries beyond last listed date.
    """
    segs = []
    if not vdb_info:
        return segs
    # Build start datetimes
    starts = []
    for row in vdb_info:
        #print('row from vdb_info',row)
        md, ad, s = row
        s = s.split()[0].strip()# remove time from vdb_info row 
        y, m, d = map(int, s.split('-'))
        starts.append((md, ad, datetime(y, m, d)))

    for i, (md, ad, start_dt) in enumerate(starts):
        if i < len(starts) - 1:
            end_dt = starts[i+1][2] - timedelta(seconds=1)
        else:
            # Far future end for the last slice
            end_dt = datetime(9999, 12, 31, 23, 59, 59)
        segs.append({'md': md, 'ad': ad, 'pd': None, 'start': start_dt, 'end': end_dt})
    return segs


def _active_vimsottari_in_window(segments, win_start, win_end):
    """Filter the vimsottari segments that intersect [win_start, win_end] and pick the dominant MD/AD/PD."""
    hits = [s for s in segments if not (s['end'] < win_start or s['start'] > win_end)]
    if not hits:
        return None
    best = max(hits, key=lambda s: (min(s['end'], win_end) - max(s['start'], win_start)).total_seconds())
    return {'md': best['md'], 'ad': best['ad'], 'pd': best.get('pd')}

# ---- Vimshottari scoring ----

def _score_vimsottari_capability(md_ad_pd, derived):
    """
    Implements the MD/AD/PD gating & scoring as per examples (weights adjustable).
    Current heuristics (no aspects used yet; TODO for aspects):
      - Strong if planet is 7L (D1)
      - +1 if planet is Venus
      - +1 if planet is DK
      - +1 if planet sits in D1 7H
      - +1 if planet is well-placed in D9 (lagna/7/trines)
    """
    if not md_ad_pd:
        return 0
    score = 0
    score += score_planet_marriage_capability(md_ad_pd['md'], derived, tier='md')  # +0..?
    score += score_planet_marriage_capability(md_ad_pd['ad'], derived, tier='ad')  # +0..?
    if md_ad_pd.get('pd') is not None:
        score += score_planet_marriage_capability(md_ad_pd['pd'], derived, tier='pd')  # +0..?
    return score


def score_planet_marriage_capability(planet, derived, tier='md'):
    """
    Minimal heuristic consistent with examples; feel free to tune weights.
    Returns an integer score; stronger for MD/AD than PD.
    TODO: add aspect-based boosts when you provide graha drishti API.
    """
    if planet is None:
        return 0

    # Weights by tier
    base_if_7L = {'md': 3, 'ad': 3, 'pd': 2}.get(tier, 2)
    bonus = {'md': 1, 'ad': 1, 'pd': 1}.get(tier, 1)

    p_to_h_rasi = derived['p_to_h_rasi']
    p_to_h_d9 = derived['p_to_h_d9']

    score = 0

    # 7th lord in D1
    if planet == derived['seventh_lord_d1']:
        score += base_if_7L

    # Venus / DK connections
    if planet == const.VENUS_ID:
        score += bonus
    if planet == derived['dk']:
        score += bonus

    # Occupying D1 7th house
    if p_to_h_rasi.get(planet, -99) == derived['seventh_house_sign_d1']:
        score += bonus

    # Good in D9: Lagna/5/9 and 7th house (kendra/trikona-like support)
    d9_lagna = derived['lagna_sign_d9']
    d9_good = {d9_lagna, (d9_lagna + 4) % 12, (d9_lagna + 8) % 12, derived['seventh_house_sign_d9']}
    if p_to_h_d9.get(planet, -99) in d9_good:
        score += bonus

    return score


# ---- Transits (monthly Jupiter) ----

def _get_monthly_jupiter_transit_support(jd, place, year, month, derived):
    """
    Score Jupiter’s monthly position using drik.sidereal_longitude:
      +1 if Jupiter is in Lagna/5/7/9 from D1 Lagna
      +1 if Jupiter aspects D1 7th house sign (Jupiter graha drishti: 5th, 7th, 9th)
      +1 if Jupiter aspects 7th-lord's sign or is in/aspects UL sign
    Returns int 0..3.

    NOTE: Assumes 'place' has attribute '.timezone' as float hours. If yours is a tuple,
    replace 'place.timezone' with the correct index (TODO if needed).
    """
    # Midpoint of the month (safer for long months)
    start = datetime(year, month, 1, 12, 0, 0)
    end = _end_of_month(year, month)
    mid = start + (end - start) / 2

    # Build JD for mid (local) then adjust to UTC for transit API
    jd_mid = swe.julday(mid.year, mid.month, mid.day, mid.hour + mid.minute/60.0 + mid.second/3600.0)
    jd_utc = jd_mid - (place.timezone / 24.0)

    # Jupiter longitude/sign at mid-month
    jup_lon = drik.sidereal_longitude(jd_utc, const._JUPITER)  # degrees 0..360
    jup_sign = int(jup_lon // 30)

    lagna = derived['lagna_sign_d1']
    h7    = derived['seventh_house_sign_d1']
    l7sg  = derived['seventh_lord_sign_d1']
    ulsg  = derived['ul_d1']

    score = 0

    # 1) Jupiter in Lagna/5/7/9 from Lagna (rāśi)
    good = {lagna, (lagna+4) % 12, (lagna+6) % 12, (lagna+8) % 12}
    if jup_sign in good:
        score += 1

    # Helper: Jupiter's graha drishti signs (5th, 7th, 9th from Jupiter)
    jup_aspects = { (jup_sign + 4) % 12, (jup_sign + 6) % 12, (jup_sign + 8) % 12 }

    # 2) Aspect to 7th house sign
    if h7 in jup_aspects:
        score += 1

    # 3) Aspect to 7th-lord sign OR UL sign (or same sign)
    if (l7sg in jup_aspects) or (ulsg in jup_aspects) or (jup_sign == ulsg):
        score += 1

    return score

# ---- Sudarsana Chakra Dasa (SCD) year filter ----

def _sudarsana_chakra_year_info(jd, place, year, chart_1d_d9):
    """
    Compute SCD active house for the running year starting on birthday, map to D9 rasi,
    and collect Jupiter/Venus signs at Varshaphala start for scoring.

    Logic mirrors the examples:
      - Running year = (target_year - birth_year) + 1
      - House offset = running_year % 12  (0 ~ 1st, 1 ~ 2nd, ... 11 ~ 12th)
      - Map from D9 Lagna → scd_rasi_d9
      - Read Jup/Ven signs at Varshaphala start to score year (+2 max)
    """
    # Birth date from JD (year, month, day, float_hours)
    by, bm, bd, bh = utils.jd_to_gregorian(jd)

    # Running year per example
    running_year = (year - by)
    house_offset = running_year % 12

    # D9 Lagna sign from chart_1d_d9 (find 'L')
    lagna_sign_d9 = 0
    for sgn, token in enumerate(chart_1d_d9):
        if token:
            parts = token.split('/')
            if 'L' in parts:
                lagna_sign_d9 = sgn
                break

    scd_rasi_d9 = (lagna_sign_d9 + house_offset) % 12

    # Varshaphala annual chart for this year to extract Jup/Ven (D1)
    years_after_dob = (year - by)
    annual_pp, (vf_y_m_d, vf_hours_local) = annual_chart(jd_at_dob=jd, place=place, divisional_chart_factor=1, years=years_after_dob)
    vf_hours = _safe_extract_float_hours(vf_hours_local)
    H, M, S = _hours_to_hms(vf_hours)
    vf_start = datetime(vf_y_m_d[0], vf_y_m_d[1], vf_y_m_d[2], H, M, S)

    vf_jupiter_sign = _get_planet_sign_from_annual(annual_pp, const.JUPITER_ID)
    vf_venus_sign = _get_planet_sign_from_annual(annual_pp, const.VENUS_ID)

    return {
        'running_year': running_year,
        'house_offset': house_offset,
        'scd_rasi_d9': scd_rasi_d9,
        'vf_start': vf_start,
        'vf_jupiter_sign': vf_jupiter_sign,
        'vf_venus_sign': vf_venus_sign
    }


def _score_scd_year_support(scd_info, derived):
    """
    +1 if Jupiter == scd_rasi_d9 at Varshaphala start
    +1 if Venus  == scd_rasi_d9 at Varshaphala start
    Max +2, used to confirm the YEAR (like in Example 1).
    """
    if not scd_info:
        return 0
    scd_rasi = scd_info.get('scd_rasi_d9')
    if scd_rasi is None:
        return 0

    score = 0
    jup = scd_info.get('vf_jupiter_sign')
    ven = scd_info.get('vf_venus_sign')
    if jup is not None and jup == scd_rasi:
        score += 1
    if ven is not None and ven == scd_rasi:
        score += 1
    return score


# ---------- Tajaka (Varshaphala) bundle ----------

def _get_varshaphala_marriage_triggers(jd, place, year, derived):
    """
    Build annual Tajaka bundle for the Varshaphala year:
    - Varshaphala start (datetime), annual planet positions
    - Jupiter/Venus signs at Varshaphala start
    - Vivaha Saham (sign, abs_long)
    - Annual Lagna sign, LL, 7L
    - Muntha sign & Muntha lord
    - Patyayini schedule (computed from Varshaphala JD)
    """
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    years_after_dob = (year - by)

    # Annual (Varshaphala) chart in D1
    annual_pp, (vf_y_m_d, vf_hours_local) = annual_chart(
        jd_at_dob=jd, place=place, divisional_chart_factor=1, years=years_after_dob
    )
    vf_hours = _safe_extract_float_hours(vf_hours_local)
    H, M, S = _hours_to_hms(vf_hours)
    vf_start = datetime(vf_y_m_d[0], vf_y_m_d[1], vf_y_m_d[2], H, M, S)

    # Annual Jupiter/Venus
    jup_sign = _get_planet_sign_from_annual(annual_pp, const.JUPITER_ID)
    ven_sign = _get_planet_sign_from_annual(annual_pp, const.VENUS_ID)

    # Annual Lagna sign (from 'L')
    annual_lagna_sign = _find_lagna_sign_from_positions(annual_pp)

    # Annual LL / 7L planet ids
    annual_h7_sign = (annual_lagna_sign + const.HOUSE_7) % 12
    annual_ll = house.house_owner_from_planet_positions(annual_pp, annual_lagna_sign)
    annual_7l = house.house_owner_from_planet_positions(annual_pp, annual_h7_sign)

    # Night/day flag for Vivaha Saham
    night_time_birth = derived.get('night_time_birth', False)

    # Vivaha Saham (in ANNUAL chart)
    vs_ret = vivaha_saham(annual_pp, night_time_birth=night_time_birth)
    vs_sign, vs_abs_long = _parse_vivaha_saham_return(vs_ret)
    # Venus absolute longitude in annual chart
    ven_abs_long = _get_planet_abs_long_from_positions(annual_pp, const.VENUS_ID)

    # Muntha (from natal lagna + years), lord in annual chart
    natal_lagna_sign = derived['lagna_sign_d1']
    muntha_sign = (natal_lagna_sign + years_after_dob) % 12
    muntha_lord = house.house_owner_from_planet_positions(annual_pp, muntha_sign)

    # --- Patyayini from Varshaphala LOCAL JD ---
    jd_vf_local = _gregorian_to_jd(vf_y_m_d[0], vf_y_m_d[1], vf_y_m_d[2], vf_hours)
    patyayini_raw = patyayini.get_dhasa_bhukthi(jd_vf_local, place, divisional_chart_factor=1, chart_method=1)
    patyayini_schedule = _expand_patyayini_schedule(patyayini_raw)

    tajaka = {
        'vf_start': vf_start,
        'years_after_dob': years_after_dob,
        'annual_planet_positions': annual_pp,   # [[planet,(sign,lon)], ...]
        'jupiter_sign': jup_sign,
        'venus_sign': ven_sign,

        'annual_lagna_sign': annual_lagna_sign,
        'annual_ll': annual_ll,
        'annual_7l': annual_7l,

        'vivaha_saham_sign': vs_sign,
        'vivaha_saham_abs_long': vs_abs_long,
        'venus_abs_long': ven_abs_long,

        'muntha_sign': muntha_sign,
        'muntha_lord': muntha_lord,

        'patyayini_schedule': patyayini_schedule,
        'retro_flags': None,   # TODO: if you want aspect/applying logic in Tajaka
    }
    return tajaka



def _expand_patyayini_schedule(patyayini_raw):
    """
    Normalizes Patyayini output into:
      [{'lord': <planet_id or 'L'>, 'start': datetime, 'end': datetime, 'days': float}, ...]

    Supports TWO input formats:

    (A) Your implemented format (as per your function & printout):
        [
          [major_lord, [[sub_lord, 'YYYY-MM-DD HH:MM:SS'], ...], major_duration_days],
          [major_lord2, [[sub_lord, 'YYYY-MM-DD HH:MM:SS'], ...], major_duration_days2],
          ...
        ]
        - We flatten all [sub_lord, start_string] across all majors,
          sort by start, set end = next start (last ends at first_start + sum(major_duration_days)).

    (B) Older docstring format (if any code still returns it somewhere):
        [[planet_id, (Y,M,D), duration_days], ...]
        - We set end = next start, last ends at last_start + duration_days.
    """
    if not patyayini_raw:
        return None

    # Detect format by inspecting the first row
    first = patyayini_raw[0]
    out = []

    def _parse_dt_str(s):
        # 'YYYY-MM-DD HH:MM:SS' -> datetime
        try:
            return datetime.fromisoformat(s)
        except Exception:
            # Last resort: strip and try common patterns
            try:
                return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
            except Exception:
                # If only date present
                return datetime.strptime(s.strip().split()[0], "%Y-%m-%d")

    if (
        isinstance(first, (list, tuple))
        and len(first) == 3
        and isinstance(first[1], list)
        and first[1]  # not empty
        and isinstance(first[1][0], (list, tuple))
        and len(first[1][0]) == 2
        and isinstance(first[1][0][1], str)
    ):
        # ---- FORMAT (A): [major_lord, [[sub_lord, 'YYYY-MM-DD HH:MM:SS'], ...], major_duration_days] ----
        # 1) Flatten all (lord,start) pairs
        flat = []
        total_days = 0.0
        for major_lord, bhukthi_list, major_days in patyayini_raw:
            total_days += float(major_days)
            for (sub_lord, start_str) in bhukthi_list:
                start_dt = _parse_dt_str(start_str)
                flat.append((sub_lord, start_dt))
        # 2) Sort by start time
        flat.sort(key=lambda t: t[1])
        if not flat:
            return None

        # 3) Build slices with next-start end times; last ends at first_start + total_days
        first_start = flat[0][1]
        for i, (lord, start_dt) in enumerate(flat):
            if i < len(flat) - 1:
                end_dt = flat[i+1][1] - timedelta(seconds=1)
            else:
                end_dt = first_start + timedelta(days=total_days)
            days = (end_dt - start_dt).total_seconds() / 86400.0
            out.append({'lord': lord, 'start': start_dt, 'end': end_dt, 'days': days})

        return out

    else:
        # ---- FORMAT (B): [[planet_id, (Y,M,D), duration_days], ...] ----
        starts = []
        for row in patyayini_raw:
            try:
                planet, (y, m, d), days = row
                start_dt = datetime(int(y), int(m), int(d), 0, 0, 0)
                starts.append((planet, start_dt, float(days)))
            except Exception:
                # Skip malformed
                continue

        starts.sort(key=lambda t: t[1])
        for i, (planet, start_dt, days) in enumerate(starts):
            if i < len(starts) - 1:
                end_dt = starts[i+1][1] - timedelta(seconds=1)
            else:
                end_dt = start_dt + timedelta(days=days)
            out.append({'lord': planet, 'start': start_dt, 'end': end_dt, 'days': (end_dt - start_dt).total_seconds() / 86400.0})

        return out


# ---------- Tajaka month scoring ----------
def _score_tajaka_month(tajaka, month_start, month_end, derived):
    """
    Score for this month (Varshaphala triggers):
      +3 if |Venus - Vivaha Saham| <= 2°
      +2 if <= 5°
      +3 if Poorna Ithasala LL↔7L in annual chart; else +1 for other Ithasala
      +2 if Poorna Ithasala Venus↔Muntha lord; else +1 if any Ithasala
      +2 if Poorna Ithasala Venus↔Vivaha Saham lord; else +1 if any Ithasala
      +1 if Venus↔UL lord has Ithasala (optional, natal UL picked, checked in annual chart)
      +2 if month overlaps Patyayini of Venus/7L/UL/Saham lord/Muntha lord
    Returns (score:int, detail:dict)
    """
    if not tajaka:
        return 0, {'ithasala_orb': 999, 'venus_saham_delta': 999}

    annual_pp = tajaka['annual_planet_positions']
    score = 0
    ithasala_best = 999  # 0 for poorna, 1 for weaker, 999 if none

    # 1) Venus proximity to Vivaha Saham (annual instant proxy)
    ven_abs = tajaka['venus_abs_long']
    vs_abs = tajaka['vivaha_saham_abs_long']
    venus_saham_delta = _angle_delta_deg(ven_abs, vs_abs)

    if venus_saham_delta <= 2.0:
        score += 3
    elif venus_saham_delta <= 5.0:
        score += 2

    # 2) LL ↔ 7L Ithasala (annual)
    LL = tajaka['annual_ll']
    L7 = tajaka['annual_7l']
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, LL, L7)
    if has_it:
        if it_type == 3:
            score += 3
            ithasala_best = 0
        else:
            score += 1
            ithasala_best = min(ithasala_best, 1)

    # 3) Venus ↔ Muntha lord
    m_lord = tajaka['muntha_lord']
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, m_lord)
    if has_it:
        if it_type == 3:
            score += 2
            ithasala_best = 0
        else:
            score += 1
            ithasala_best = min(ithasala_best, 1)

    # 4) Venus ↔ Vivaha Saham lord
    vs_sign = tajaka['vivaha_saham_sign']
    vs_lord = house.house_owner_from_planet_positions(annual_pp, vs_sign)
    #print(annual_pp,const.VENUS_ID,vs_lord)
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, vs_lord)
    if has_it:
        if it_type == 3:
            score += 2
            ithasala_best = 0
        else:
            score += 1
            ithasala_best = min(ithasala_best, 1)

    # 5) Optional: Venus ↔ UL lord (UL from natal; lord checked in annual chart)
    ul_sign = derived['ul_d1']
    ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign)
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, ul_lord)
    if has_it:
        score += 1
        ithasala_best = min(ithasala_best, 0 if it_type == 3 else 1)


    # ... keep all current scoring above ...
    
    # 6) Patyayini schedule overlap (+2 if any target lord runs this month)
    paty = tajaka.get('patyayini_schedule')
    paty_hit = False
    paty_lords = []
    
    if paty:
        vs_sign = tajaka['vivaha_saham_sign']
        annual_pp = tajaka['annual_planet_positions']
        vs_lord = house.house_owner_from_planet_positions(annual_pp, vs_sign)
        m_lord = tajaka['muntha_lord']
        L7 = tajaka['annual_7l']
    
        ul_sign = derived['ul_d1']
        ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign)
    
        targets = {const.VENUS_ID, L7, ul_lord, vs_lord, m_lord}
        if _patyayini_month_hit(paty, month_start, month_end, targets):
            score += 2
            paty_hit = True
            paty_lords = sorted({
                sl['lord'] for sl in paty
                if not (sl['end'] < month_start or sl['start'] > month_end)
            }, key=str)
    
    detail = {
        'ithasala_orb': ithasala_best,
        'venus_saham_delta': round(venus_saham_delta, 2),
        'patyayini_hit': paty_hit,
        'patyayini_lords_in_month': paty_lords
    }
    return score, detail



def _patyayini_month_hit(paty_schedule, month_start, month_end, targets):
    """
    Returns True if any Patyayini slice whose 'lord' ∈ targets overlaps the [month_start, month_end] window.
    """
    for sl in paty_schedule:
        lord = sl['lord']
        s = sl['start']
        e = sl['end']
        if lord in targets:
            if not (e < month_start or s > month_end):
                return True
    return False


# ---------- Helpers (small, local, no renames elsewhere) ----------

def _get_planet_sign_from_annual(annual_planet_positions_list, planet_id):
    for pl, (sg, lon) in annual_planet_positions_list:
        if pl == planet_id:
            return sg
    return None

def _get_planet_abs_long_from_positions(planet_positions, planet_id):
    """
    Returns absolute longitude (0..360) of planet_id from [[planet,(sign,lon)],...]
    """
    for pl, (sg, lon) in planet_positions:
        if pl == planet_id:
            return (sg * 30.0) + float(lon)
    return None

def _find_lagna_sign_from_positions(planet_positions):
    for pl, (sg, lon) in planet_positions:
        if pl == 'L':
            return sg
    return 0

def _parse_vivaha_saham_return(vs_ret):
    """
    Accepts either:
      - (sign, lon_in_sign)  OR
      - abs_longitude_degrees (0..360)
    Returns (sign, abs_longitude)
    """
    if isinstance(vs_ret, (tuple, list)) and len(vs_ret) >= 2:
        sg = int(vs_ret[0])
        lon_in_sign = float(vs_ret[1])
        return sg, (sg * 30.0) + lon_in_sign
    else:
        abs_lon = float(vs_ret)
        sg = int(abs_lon // 30)
        return sg, abs_lon

def _angle_delta_deg(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)

def _end_of_month(y, m):
    if m == 12:
        return datetime(y, 12, 31, 23, 59, 59)
    return datetime(y, m+1, 1) - timedelta(seconds=1)

def _hours_to_hms(hours_float):
    """Convert float hours -> (H, M, S) integers."""
    h = int(hours_float)
    m = int((hours_float - h) * 60.0)
    s = int(round((((hours_float - h) * 60.0) - m) * 60.0))
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        h += 1
    return h, m, s

def _safe_extract_float_hours(vf_time):
    """
    Accepts either float hours (preferred new API) or an old 'HH:MM:SS'/'HH MM SS' string.
    Returns float hours.
    """
    if isinstance(vf_time, (int, float)):
        return float(vf_time)
    t = str(vf_time).strip().replace('°', ':').replace(' ', ':')
    parts = [p for p in t.split(':') if p != '']
    try:
        h = float(parts[0]) if len(parts) > 0 else 0.0
        m = float(parts[1]) if len(parts) > 1 else 0.0
        s = float(parts[2]) if len(parts) > 2 else 0.0
    except Exception:
        return 0.0
    return h + (m / 60.0) + (s / 3600.0)

def _gregorian_to_jd(y, m, d, hours_float):
    """
    Build Julian Day using Swiss Ephemeris convention for hours.
    This is LOCAL JD if you pass local hours (which is fine for Tajaka & Patyayini).
    """
    return swe.julday(y, m, d, hours_float)


def _collect_reasons(md_ad_pd, jtransit, scd_info, tajaka_detail, kcd_score, cnd9_score, cultural, derived):
    out = {
        'md_ad_pd': md_ad_pd,
        'ithasala_orb': tajaka_detail.get('ithasala_orb', 999),
        'venus_saham_delta': tajaka_detail.get('venus_saham_delta', 999),
        'kcd': kcd_score,
        'cnd9': cnd9_score,
        'cultural': cultural
    }
    out['jupiter_transit'] = jtransit
    out['scd_score'] = _score_scd_year_support(scd_info, derived)

    # Pull Patyayini flags (if _score_tajaka_month set them)
    if 'patyayini_hit' in tajaka_detail:
        out['patyayini_hit'] = tajaka_detail['patyayini_hit']
    if 'patyayini_lords_in_month' in tajaka_detail:
        out['patyayini_lords_in_month'] = tajaka_detail['patyayini_lords_in_month']

    # Names:
    planet_names = getattr(utils, 'PLANET_NAMES', None)
    def _pname(p):
        if p == 'L':
            return 'Lagna'
        if isinstance(p, int) and 0 <= p <= 8 and planet_names:
            return planet_names[p]
        return str(p)

    out['md_ad_pd_names'] = {
        'md': _pname(md_ad_pd.get('md')),
        'ad': _pname(md_ad_pd.get('ad')),
        'pd': _pname(md_ad_pd.get('pd'))
    }
    if out.get('patyayini_lords_in_month'):
        out['patyayini_lords_in_month_names'] = [
            _pname(pid) for pid in out['patyayini_lords_in_month']
        ]

    return out


# ---------- Optional TODOs (return 0 for now) ----------

def _score_compressed_d9_narayana(jd, place, month_start, month_end, derived):
    """Optional +0..2 if compressed D9 Narayana dasa rasi contains UL within this window. TODO: wire your ND9 API."""
    return 0

def _score_cultural_month(month_start, month_end):
    """+1 if the month overlaps auspicious marriage month (e.g., Maagha). TODO: map lunar months via your API."""
    return 0


# ---------- (Optional) Adaptors you may or may not need ----------
# Kept for parity; not used in current flow.

def to_chart_1d_from_positions(planet_positions):
    slots = [""] * 12
    for pl, (sg, lon) in planet_positions:
        if pl == 'L':
            slots[sg] = ("L" if slots[sg] == "" else slots[sg] + "/L")
        else:
            token = str(pl)
            slots[sg] = token if slots[sg] == "" else (slots[sg] + "/" + token)
    return slots

def to_p_to_h_from_positions(planet_positions):
    out = {}
    for pl, (sg, lon) in planet_positions:
        if pl == 'L':
            out['L'] = sg
        else:
            out[pl] = sg
    return out


# ---- Kalachakra Dasha (year-level cross-check) ----

def _score_kalachakra_support(jd, place, year, derived):
    """
    Year-level +0..2 score from Kalachakra Dasha, consistent with Example 5.

    Heuristic (rāśi-based, auto-detected):
      +1 if running KCD daśā rāśi equals Venus's sign in D1 (Venus-in-dasa-rasi)
      +1 if any KCD antar running in the year equals:
            - 7th from Venus's sign in D1, OR
            - 7th from the KCD daśā rāśi, OR
            - the D1 7th-house sign
    (max +2 per year)

    If KCD API returns planets (not rāśis), we fallback to a graha-based heuristic:
      +1 if MD or AD planet is Venus
      +1 if MD or AD planet is D1 7L
    (max +2 per year)
    """
    # Build dob/tob from JD (local)
    by, bm, bd, birth_hours = utils.jd_to_gregorian(jd)
    H, M, S = _hours_to_hms(birth_hours)
    dob = (by, bm, bd)
    tob = (H, M, S)

    try:
        # include_antardhasa=True to get MD/AD rows with start dates (string)
        kcd_rows = kalachakra.get_dhasa_bhukthi(
            dob, tob, place,
            divisional_chart_factor=1,
            dhasa_starting_planet=1,          # default from your doc (Moon)
            include_antardhasa=True,
            star_position_from_moon=1
        )
    except Exception:
        return 0  # if KCD not available, neutral

    kcd_segments = _expand_kalachakra_segments(kcd_rows)  # [{'md':x,'ad':y,'start':dt,'end':dt},...]

    # Year window
    win_start = datetime(year, 1, 1, 0, 0, 0)
    win_end = datetime(year, 12, 31, 23, 59, 59)

    # Collect segments overlapping this year; score the best
    best = 0

    # D1 primitives
    venus_sign_d1 = derived['venus_sign_d1']
    seventh_house_sign_d1 = derived['seventh_house_sign_d1']
    seventh_lord_d1 = derived['seventh_lord_d1']

    for seg in kcd_segments:
        if (seg['end'] < win_start) or (seg['start'] > win_end):
            continue

        md = seg['md']
        ad = seg['ad']

        # --- Auto-detect rāśi vs graha return ---
        #   If any lord value > 8, we treat as rāśi (0..11).
        treat_as_rasi = (md is not None and md > 8) or (ad is not None and ad > 8)

        score = 0
        if treat_as_rasi:
            # Rāśi-based scoring (preferred; matches the example narrative)
            md_rasi = md
            ad_rasi = ad

            # +1 if Venus in the MD rāśi (in D1)
            if md_rasi == venus_sign_d1:
                score += 1

            # +1 if AD rāśi equals (7th from Venus) OR (7th from MD-rāśi) OR (7H sign)
            if ad_rasi is not None:
                if ad_rasi == ((venus_sign_d1 + 6) % 12):
                    score += 1
                elif ad_rasi == ((md_rasi + 6) % 12):
                    score += 1
                elif ad_rasi == seventh_house_sign_d1:
                    score += 1

        else:
            # Graha-based fallback (if your KCD returns planets)
            md_pl = md
            ad_pl = ad

            # +1 if MD or AD is Venus
            if md_pl == const.VENUS_ID or ad_pl == const.VENUS_ID:
                score += 1

            # +1 if MD or AD is the D1 7th lord
            if md_pl == seventh_lord_d1 or ad_pl == seventh_lord_d1:
                score += 1

        best = max(best, min(score, 2))

        # Short-circuit if already maxed
        if best >= 2:
            break

    return best


def _expand_kalachakra_segments(kcd_rows):
    """
    Convert Kalachakra entries [[md, ad, 'YYYY-MM-DD'], ...] to
    [{'md':int,'ad':int,'start':datetime,'end':datetime}, ...] similar to Vimshottari expansion.
    """
    segs = []
    if not kcd_rows:
        return segs

    starts = []
    for row in kcd_rows:
        if len(row) < 3:
            continue
        md, ad, date_str = row[0], row[1], row[2]
        try:
            y, m, d = map(int, date_str.split('-'))
            starts.append((md, ad, datetime(y, m, d)))
        except Exception:
            continue

    starts.sort(key=lambda t: t[2])  # ensure chronological
    for i, (md, ad, start_dt) in enumerate(starts):
        if i < len(starts) - 1:
            end_dt = starts[i+1][2] - timedelta(seconds=1)
        else:
            end_dt = datetime(9999, 12, 31, 23, 59, 59)
        segs.append({'md': md, 'ad': ad, 'start': start_dt, 'end': end_dt})

    return segs
def _astrological_event_checker(jd, place, gender=0):
    EVENT_NAME = "Marraige Timing"
    EVENT_HOUSE_ID = const.HOUSE_7; event_karaka = const.JUPITER_ID if gender==0 else const.VENUS_ID
    EVENT_DCF = 9
    EVENT_AGE_RANGE = (20,40)
    event_age_range = EVENT_AGE_RANGE
    inputs = {}
    def _collect_basic_chart_info():
        pp_d1 = charts.divisional_chart(jd, place, divisional_chart_factor=1)
        inputs['pp_d1'] = pp_d1
        chart_d1 = utils.get_house_planet_list_from_planet_positions(pp_d1)
        inputs['chart_d1'] = chart_d1
        print('chart_d1',chart_d1)
        p_to_h_d1 = utils.get_planet_to_house_dict_from_chart(chart_d1)
        inputs['p_to_h_d1'] = p_to_h_d1
        pp_dcf = charts.divisional_chart(jd, place, divisional_chart_factor=EVENT_DCF)
        inputs['pp_dcf'] = pp_dcf
        chart_dcf = utils.get_house_planet_list_from_planet_positions(pp_dcf)
        inputs['chart_dcf'] = chart_dcf
        print('chart_dcf',chart_dcf)
        p_to_h_dcf = utils.get_planet_to_house_dict_from_chart(chart_dcf)
        inputs['p_to_h_dcf'] = p_to_h_dcf
        return
    def _get_all_chart_info():
        return [inputs[c] for c in ['pp_d1','chart_d1','p_to_h_d1','pp_dcf','chart_dcf','p_to_h_dcf']]
    def _get_aspecting_planets():
        pp_d1,chart_d1,p_to_h_d1,pp_dcf,chart_dcf,p_to_h_dcf = _get_all_chart_info()
        # aspecting asc and asc lord of D1
        
    def _evalulate_lords_and_houses():
        pp_d1 = inputs['pp_d1']
        chart_d1 = inputs['chart_d1']
        p_to_h_d1 = inputs['p_to_h_d1']
        pp_dcf = inputs['pp_dcf']
        chart_dcf = inputs['chart_dcf']
        lagna_house_d1 = p_to_h_d1['L']; event_house_d1 = (lagna_house_d1+EVENT_HOUSE_ID)%12
        inputs['lagna_house_d1'] = lagna_house_d1; inputs['event_house_d1'] = event_house_d1
        lagna_lord_d1 = house.house_owner_from_planet_positions(pp_d1, lagna_house_d1)
        inputs['lagna_lord_d1'] = lagna_lord_d1
        print("Lagna House D1",utils.RAASI_LIST[lagna_house_d1],'Lagna Lord D1',utils.PLANET_NAMES[lagna_lord_d1])
        planets_in_lagna_house_d1 = [utils.PLANET_NAMES[p] for p,h in p_to_h_d1.items() if h==lagna_house_d1 and p!='L']
        inputs['planets_in_lagna_house_d1'] = planets_in_lagna_house_d1
        print('planets_in_lagna_house_d1',utils.RAASI_LIST[lagna_house_d1],'are',planets_in_lagna_house_d1)
        p_to_h_dcf = inputs['p_to_h_dcf']
        lagna_house_dcf = p_to_h_dcf['L']; event_house_dcf = (lagna_house_dcf+EVENT_HOUSE_ID)%12
        inputs['lagna_house_dcf'] = lagna_house_dcf; inputs['event_house_dcf'] = event_house_dcf
        lagna_lord_dcf = house.house_owner_from_planet_positions(pp_dcf, lagna_house_dcf)
        inputs['lagna_lord_dcf'] = lagna_lord_dcf
        print("Lagna House DCF",utils.RAASI_LIST[lagna_house_dcf],'Lagna Lord DCF',utils.PLANET_NAMES[lagna_lord_dcf])
        planets_in_lagna_house_dcf = [utils.PLANET_NAMES[p] for p,h in p_to_h_d1.items() if h==lagna_house_dcf and p!='L']
        inputs['planets_in_lagna_house_dcf'] = planets_in_lagna_house_dcf
        print('planets_in_lagna_house_dcf',utils.RAASI_LIST[lagna_house_dcf],'are',planets_in_lagna_house_dcf)
        ## even lords and house lords
        planets_in_event_house_d1 = [utils.PLANET_NAMES[p] for p,h in p_to_h_d1.items() if h==event_house_d1 and p!='L']
        inputs['planets_in_event_house_d1'] = planets_in_event_house_d1
        print('planets_in_event_house_d1',utils.RAASI_LIST[event_house_d1],'are',planets_in_event_house_d1)
        lord_of_event_house_d1 = house.house_owner_from_planet_positions(pp_d1, event_house_d1)
        inputs['lord_of_event_house_d1'] = lord_of_event_house_d1
        print('lord_of_event_house_d1',utils.RAASI_LIST[event_house_d1],'is',utils.PLANET_NAMES[lord_of_event_house_d1])
        planets_in_event_house_dcf = [utils.PLANET_NAMES[p] for p,h in p_to_h_dcf.items() if h==event_house_dcf and p!='L']
        print('planets_in_event_house_dcf',utils.RAASI_LIST[event_house_dcf],'are',planets_in_event_house_dcf)
        inputs['planets_in_event_house_dcf'] = planets_in_event_house_dcf
        lord_of_event_house_dcf = house.house_owner_from_planet_positions(pp_dcf, event_house_dcf)
        print('lord_of_event_house_dcf',utils.RAASI_LIST[event_house_dcf],'is',utils.PLANET_NAMES[lord_of_event_house_dcf])
        inputs['lord_of_event_house_dcf'] = lord_of_event_house_dcf
        planets_aspecting_lagna_d1 = house.planets_aspecting_the_raasi(chart_d1, lagna_house_d1)
        print('planets_aspecting_lagna_d1',planets_aspecting_lagna_d1)
        planets_aspecting_lagna_lord_d1 = house.planets_aspecting_the_planet(chart_d1, lagna_lord_d1)
        print('planets_aspecting_lagna_lord_d1',planets_aspecting_lagna_lord_d1)
        planets_aspecting_event_house_d1 = house.planets_aspecting_the_raasi(chart_d1, event_house_d1)
        print('planets_aspecting_event_house_d1',planets_aspecting_event_house_d1)
        planets_aspecting_event_lord_d1 = house.planets_aspecting_the_planet(chart_d1, lord_of_event_house_d1)
        print('planets_aspecting_event_lord_d1',planets_aspecting_event_lord_d1)
        planets_aspecting_lagna_dcf = house.planets_aspecting_the_raasi(chart_dcf, lagna_house_dcf)
        print('planets_aspecting_lagna_dcf',planets_aspecting_lagna_dcf)
        planets_aspecting_lagna_lord_dcf = house.planets_aspecting_the_planet(chart_dcf, lagna_lord_dcf)
        print('planets_aspecting_lagna_lord_dcf',planets_aspecting_lagna_lord_dcf)
        planets_aspecting_event_house_dcf = house.planets_aspecting_the_raasi(chart_dcf, event_house_dcf)
        print('planets_aspecting_event_house_dcf',planets_aspecting_event_house_dcf)
        planets_aspecting_event_lord_dcf = house.planets_aspecting_the_planet(chart_dcf, lord_of_event_house_dcf)
        print('planets_aspecting_event_lord_dcf',planets_aspecting_event_lord_dcf)
    def _get_possible_dhasa_bhukthi_candidates():
        pp_d1,chart_d1,p_to_h_d1,pp_dcf,chart_dcf,p_to_h_dcf = _get_all_chart_info()
        db_candidates = []; _db_candidates_d1 =[]; _db_candidates_dcf = []
        possible_planets_dcf = ['lagna_lord_dcf','lord_of_event_house_dcf']
        # Asc Lord D1, Event House D1, Asc Lord DCF, Event House DCF 
        [_db_candidates_dcf.append(inputs[s]) for s in possible_planets_dcf]
        _db_candidates_dcf = list(set(_db_candidates_dcf))
        _stronger_planet_dcf = charts._stronger_planet_from_the_planet_positions(pp_dcf, _db_candidates_dcf)
        print('DCF candidates',[utils.PLANET_NAMES[p] for p in _db_candidates_dcf],"Stronger",utils.PLANET_NAMES[_stronger_planet_dcf])
        possible_planets_d1 = ['lagna_lord_d1','lord_of_event_house_d1']
        # Asc Lord D1, Event House D1, Asc Lord DCF, Event House DCF 
        [_db_candidates_d1.append(inputs[s]) for s in possible_planets_d1]
        _db_candidates_d1 = list(set(_db_candidates_d1))
        _stronger_planet_d1 = charts._stronger_planet_from_the_planet_positions(pp_d1, _db_candidates_d1)
        print('D1 candidates',[utils.PLANET_NAMES[p] for p in _db_candidates_d1],"Stronger",utils.PLANET_NAMES[_stronger_planet_d1])
        _stronger_candidate_per_dcf = charts._stronger_planet_from_the_planet_positions(pp_dcf, [_stronger_planet_dcf,_stronger_planet_d1])
        print("Strong candidate per DCF",utils.PLANET_NAMES[_stronger_candidate_per_dcf])
        _stronger_candidate_per_d1 = charts._stronger_planet_from_the_planet_positions(pp_d1, [_stronger_planet_dcf,_stronger_planet_d1])
        print("Strong candidate per D1",utils.PLANET_NAMES[_stronger_candidate_per_d1])
        db_candidates.append(_stronger_candidate_per_dcf); db_candidates.append(_stronger_candidate_per_d1)
        inputs['dhasa_candidates'] = db_candidates
        return db_candidates
    def _expand_vimsottari_db_to_md_ad_segments(vdb_info):
        segs = []
        if not vdb_info:
            return segs
        starts = []
        for row in vdb_info:
            md, ad, s = row
            s = s.split()[0].strip()
            y, m, d = map(int, s.split('-'))
            starts.append((md, ad, datetime(y, m, d)))
    
        for i, (md, ad, start_dt) in enumerate(starts):
            if i < len(starts) - 1:
                end_dt = starts[i+1][2] - timedelta(seconds=1)
            else:
                end_dt = datetime(9999, 12, 31, 23, 59, 59)
            segs.append({'md': md, 'ad': ad, 'pd': None, 'start': start_dt, 'end': end_dt})
        return segs
    def _active_vimsottari_in_window(segments, win_start, win_end):
        hits = [s for s in segments if not (s['end'] < win_start or s['start'] > win_end)]
        if not hits:
            return None
        best = max(hits, key=lambda s: (min(s['end'], win_end) - max(s['start'], win_start)).total_seconds())
        return {'md': best['md'], 'ad': best['ad'], 'pd': best.get('pd'), 'start':best.get('start')}
    def _planet_dhasa_range(segments, planet):
        cmp = lambda s: (s['md']==planet)
        start_found = False; end_found = False
        for s in segments:
            if cmp(s):
                if not start_found:
                    start_date = s['start']; start_found = True
            elif start_found:
                if not end_found:
                    end_date = s['start']; end_found = True
                else: break
        return {'md':planet,'start':start_date, 'end':end_date}
    def _dhasa_lord_at_the_given_date(segments,date_to_look_for: datetime,):
        """
        get dhasa segment matching the given date
        """
        cmp = lambda s: (s['start'] <= date_to_look_for <= s['end'])
        for s in segments:
            if 'start' not in s or 'end' not in s or 'md' not in s:
                continue  # or raise ValueError(...)
            if cmp(s):
                return (s['md'],s['ad'],s['start'],s['end'])
        return None
    def _tajaka_annual_chart(years,divisional_chart_factor=1):
        pp_annual,_ = annual_chart(jd, place, divisional_chart_factor=divisional_chart_factor, years=years)
        chart_annual = utils.get_house_planet_list_from_planet_positions(pp_annual)
        return chart_annual, pp_annual
    def _vivaha_saham(jd,place,divisional_chart_factor=1,years=1, months=1, sixty_hours=1):
        jd_years = drik.next_solar_date(jd, place, years=years, months=months, sixty_hours=sixty_hours)
        vs = vivaha_saham_from_jd_place(jd_years, place, divisional_chart_factor)
        vs_sign, vs_long = drik.dasavarga_from_long(vs, divisional_chart_factor)
        return vs_sign, vs_long
    def _planets_close_to_vivaha_saham(jd,place,divisional_chart_factor=1,years=1,
                                       vivaha_saham_tolerance=30):
        pp_annual,_ = annual_chart(jd, place, divisional_chart_factor, years=years)
        jd_years = drik.next_solar_date(jd, place, years=years)
        vs_abs_long = vivaha_saham_from_jd_place(jd_years, place, divisional_chart_factor)
        vs_sign,vs_long = drik.dasavarga_from_long(vs_abs_long, divisional_chart_factor)
        #return [(p,long) for p,(h,long) in pp_annual if abs(((h*30+long)%360)-vs_long) <= vivaha_saham_tolerance]
        return [(p,vs_sign) for p,(h,_) in pp_annual if h==vs_sign]

    _collect_basic_chart_info()
    _evalulate_lords_and_houses()
    _db_candidates = _get_possible_dhasa_bhukthi_candidates()
    _, vdb_info = vimsottari.get_vimsottari_dhasa_bhukthi(jd, place)
    
    inputs['vimsottari_info'] = vdb_info
    vdb_segs = _expand_vimsottari_db_to_md_ad_segments(vdb_info)
    #print('vimsottari',vdb_info)
    yb, _, _, _ = utils.jd_to_gregorian(jd)
    start_year = yb + event_age_range[0]
    end_year = yb + event_age_range[1]
    year_start = datetime(start_year, 1, 1, 0, 0, 0)
    year_end   = datetime(end_year, 12, 31, 23, 59, 59)
    md_ad_pd_year = _active_vimsottari_in_window(vdb_segs, year_start, year_end)
    print(md_ad_pd_year)
    if (md_ad_pd_year['md'] in _db_candidates):
        print(year_start,year_end,md_ad_pd_year)
    d_seg = _dhasa_lord_at_the_given_date(vdb_segs, wedding_date)
    print('wedding date',wedding_date,'dhasa lord',utils.PLANET_NAMES[d_seg[0]],
          'bhukthi lord',utils.PLANET_NAMES[d_seg[1]],"Starts:",d_seg[2],'Ends:',d_seg[3])
    for dbc in inputs['dhasa_candidates']:
        print(utils.PLANET_NAMES[dbc], _planet_dhasa_range(vdb_segs, dbc))
    years_from_dob = d_seg[2].year - yb + 1
    ta_cht,ta_pp = _tajaka_annual_chart(years=years_from_dob, divisional_chart_factor=1)
    print('Annual Chart for years from dob',years_from_dob,ta_cht)
    print([(utils.PLANET_NAMES[p],utils.RAASI_LIST[vs]) for p,vs in _planets_close_to_vivaha_saham(jd, place, divisional_chart_factor=1, years=years_from_dob)])
    start_jd = utils.julian_day_number(drik.Date(1998,12,15),(10,0,0))
    print(vimsottari._vimsottari_antara(const.JUPITER_ID,const.SATURN_ID, start_jd))
if __name__ == "__main__":
    utils.set_language('en')
    #dob = (1996,12,7); tob = (10,34,0); place = drik.Place('Chennai',13.0878,80.2785,5.5)
    #dob = (1964,11,16); tob = (4,30,0); place = drik.Place('Karamadai',11.18,76.57,5.5)
    #wedding_date = datetime(1995,6,5)
    #dob = drik.Date(1969,6,22); tob = (21,41,0); place = drik.Place('Trichy',10.49,78.41,5.5)
    #dob = (1973,7,26); tob = (21,41,0); place = drik.Place('UNK',16+13/60,80+28/60,5.5); wedding_date = datetime(1999,1,15)
    dob = (1968,5,21); tob = (23,5,0); place = drik.Place('UNK',18+40/60, 78+10/60,5.5); wedding_date = datetime(1992,2,15)
    jd = utils.julian_day_number(dob, tob)
    _astrological_event_checker(jd, place, gender=0)
    exit()
    print(predict_marriage_windows_from_jd_place(jd, place))
