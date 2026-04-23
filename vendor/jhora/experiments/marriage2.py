
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
import math  # <-- needed by month-level DT scorer
import swisseph as swe  # used to build JD for mid-month, etc.

# Expected available modules in your environment:
from jhora import const, utils
from jhora.panchanga import drik
from jhora.horoscope.chart import charts, house, arudhas
from jhora.horoscope.dhasa.graha import vimsottari
from jhora.horoscope.dhasa.raasi import kalachakra
from jhora.horoscope.dhasa.annual import patyayini
from jhora.horoscope.transit.tajaka import annual_chart, both_planets_within_their_deeptamsa
from jhora.horoscope.transit.saham import vivaha_saham

# ---------- Public wrapper (jd/place) ----------
_marriage_age_year_range = (20, 32)

# ======= DT TUNABLES =======
DT_PERFECT_ENABLED          = False  # strict degree-landing (rare) OFF by default
DT_PERFECT_ORB              = 2.0
DT_PERFECT_PAIR_WINDOW_DAYS = 15     # if strict booster enabled

# Fallback DT (recommended primary): JUP degree-tight to 7L/7H; SAT sign-aspects same target
DT_STRONG_ORB        = 2.0
DT_STRONG_JUP_TARGET = 'either'          # 'lord' | 'cusp' | 'either'
DT_STRONG_JUP_MODE   = 'landing_or_conj' # 'conj' | 'landing_or_conj'
DT_STRONG_AWARD      = 5                 # score awarded when fallback hits


def _score_dt_perfect_in_month(
    jd_birth,
    place,
    month_start,          # datetime OR drik.Date
    month_end,            # datetime OR drik.Date
    tol=2.0,
    sev_target=DT_STRONG_JUP_TARGET,  # 'lord' | 'cusp' | 'either'
    pair_window_days=15   # allow lead/lag; strict same-day would be 0
):
    """
    Strict 7th-centric DT booster inside one month window:
      - Jupiter conjunct natal 7L (|J-7L| <= tol), AND
      - Saturn exact 3/7/10 landing on (7L OR 7H) within ±pair_window_days
    Returns (score:int, detail:dict). Score defaults to +5 when found.
    """
    def circ(a, b):
        d = abs(((a - b) % 360.0))
        return d if d <= 180.0 else 360.0 - d

    def _to_local_jd(d, end_of_day=False):
        # Support drik.Date or datetime
        if hasattr(d, 'year') and hasattr(d, 'month') and hasattr(d, 'day') and not hasattr(d, 'hour'):
            jd_local = utils.gregorian_to_jd(d)
            if end_of_day:
                jd_local += (23.9999/24.0)
            return jd_local
        elif hasattr(d, 'year') and hasattr(d, 'hour'):
            return swe.julday(d.year, d.month, d.day,
                              (23.9999/24.0) if end_of_day else
                              (getattr(d, 'hour', 0) +
                               getattr(d, 'minute', 0)/60.0 +
                               getattr(d, 'second', 0)/3600.0))
        else:
            raise TypeError("month_start/month_end must be datetime or drik.Date")

    # --- Natal (fixed) ---
    natal_pp = charts.divisional_chart(jd_birth, place, divisional_chart_factor=1)
    natal_lagna_sign = None
    for pid, (zod, _deg) in natal_pp:
        if pid == const._ascendant_symbol:
            natal_lagna_sign = int(zod); break
    if natal_lagna_sign is None:
        return 0, {"why": "no_lagna"}

    sev_sign = (natal_lagna_sign + 6) % 12
    sev_lord_id = house.house_owner_from_planet_positions(natal_pp, sev_sign)
    sev_lord_abs = next((int(z)*30.0 + float(d)) % 360.0 for pid,(z,d) in natal_pp if pid == sev_lord_id)

    asc_nat = drik.ascendant(jd_birth, place)
    asc_abs_nat = (int(asc_nat[0]) * 30.0 + float(asc_nat[1])) % 360.0
    sev_cusp_abs = (asc_abs_nat + 180.0) % 360.0

    sv = (sev_target or 'either').lower()
    if sv not in ('lord', 'cusp', 'either'):
        sv = 'either'
    sat_targets = [('lord', sev_lord_abs)] if sv == 'lord' else \
                  [('cusp', sev_cusp_abs)] if sv == 'cusp' else \
                  [('lord', sev_lord_abs), ('cusp', sev_cusp_abs)]

    SAT_ASP = (60.0, 180.0, 300.0)

    # --- Month bounds (LOCAL JD) ---
    jd0 = _to_local_jd(month_start, end_of_day=False)
    jd1 = _to_local_jd(month_end,   end_of_day=True)

    # Extended window to accommodate Saturn lead/lag pairing
    ext0 = math.floor(jd0) - int(pair_window_days)
    ext1 = math.floor(jd1) + int(pair_window_days)
    if ext1 < ext0:
        return 0, {"why": "bad_bounds"}

    N = (ext1 - ext0) + 1  # number of integral days
    tz = float(place.timezone)

    # -- Precompute daily Saturn/Jupiter degrees (absolute, 0..360)
    sat_arr, jup_arr = [], []
    for d in range(N):
        day_jd_local = ext0 + d
        day_jd_utc   = day_jd_local - tz
        sat_arr.append(drik.sidereal_longitude(day_jd_utc, const._SATURN) % 360.0)
        jup_arr.append(drik.sidereal_longitude(day_jd_utc, const._JUPITER) % 360.0)

    base_start_idx = max(0, int(math.floor(jd0 - ext0)))
    base_end_idx   = min(N-1, int(math.floor(jd1 - ext0)))

    for i in range(base_start_idx, base_end_idx + 1):
        # Jupiter conj 7L on day i?
        if circ(jup_arr[i], sev_lord_abs) > tol:
            continue

        # Saturn hit within ±pair_window_days (indices clamped)
        k0 = max(0, i - int(pair_window_days))
        k1 = min(N-1, i + int(pair_window_days))

        sat_ok = False; hit_tag = None
        for tag, target_abs in sat_targets:
            for k in range(k0, k1 + 1):
                landings = [(sat_arr[k] + a) % 360.0 for a in SAT_ASP]
                if min(circ(L, target_abs) for L in landings) <= tol:
                    sat_ok = True; hit_tag = tag; break
            if sat_ok:
                hit_day = utils.jd_to_gregorian(ext0 + i)
                return 5, {
                    "hit_day": hit_day,
                    "saturn_target_used": hit_tag,
                    "sev_lord_abs": sev_lord_abs,
                    "sev_cusp_abs": sev_cusp_abs
                }

    return 0, {"why": "no_dt_perfect_day"}


def _score_part3_in_month(jd_birth, place, month_start, month_end, tol=2.0):
    """
    Part-3 style monthly refinement:
      - Jupiter within ±tol of transit Asc degree at some time in the month
      - Saturn's 3/7/10 exact landing also on that same Asc degree (±tol)
    Returns (score:int, detail:dict). Score defaults to +2 when found.
    """
    def circ(a, b):
        d = abs(((a - b) % 360.0))
        return d if d <= 180.0 else 360.0 - d

    def _to_local_jd(d, end_of_day=False):
        if hasattr(d, 'year') and hasattr(d, 'month') and hasattr(d, 'day') and not hasattr(d, 'hour'):
            jd_local = utils.gregorian_to_jd(d)
            if end_of_day:
                jd_local += (23.99/24.0)
            return jd_local
        elif hasattr(d, 'year') and hasattr(d, 'hour'):
            return swe.julday(d.year, d.month, d.day,
                              (23.99/24.0) if end_of_day else
                              (getattr(d, 'hour', 0) +
                               getattr(d, 'minute', 0)/60.0 +
                               getattr(d, 'second', 0)/3600.0))
        else:
            raise TypeError("month_start/month_end must be datetime or drik.Date")

    SAT_ASP = (60.0, 180.0, 300.0)
    tz = float(place.timezone)

    # Sample every 3 hours over the month (LOCAL times)
    sstep = 1.0/8.0  # 3h
    jd0 = _to_local_jd(month_start, end_of_day=False)
    jd1 = _to_local_jd(month_end,   end_of_day=True)

    jd = jd0
    while jd <= jd1 + 1e-9:
        asc = drik.ascendant(jd, place)
        asc_abs = (int(asc[0]) * 30.0 + float(asc[1])) % 360.0
        jdu = jd - tz
        jup_abs = drik.sidereal_longitude(jdu, const._JUPITER) % 360.0
        sat_abs = drik.sidereal_longitude(jdu, const._SATURN) % 360.0

        if circ(jup_abs, asc_abs) <= tol:
            landings = [(sat_abs + a) % 360.0 for a in SAT_ASP]
            if min(circ(L, asc_abs) for L in landings) <= tol:
                return 2, {"hit_time": utils.jd_to_gregorian(jd)}
        jd += sstep

    return 0, {}


def _score_dt_strong_sign_in_month(
    jd_birth,
    place,
    month_start,                # datetime or drik.Date
    month_end,                  # datetime or drik.Date
    jup_target='either',        # 'lord' | 'cusp' | 'either'
    jup_mode='conj',            # 'conj' | 'landing_or_conj'
    tol=2.0
):
    """
    'Strong' DT fallback for a given month:
      - Jupiter hits 7th target by conjunction (±tol); if jup_mode='landing_or_conj', allow JUP 5/7/9 landing (±tol).
      - Saturn sign-aspects the SAME target's sign (3/7/10 from Saturn's transit sign) on the same day.
    Returns (score:int, detail:dict). Score = +3 when a day in the month satisfies.
    """
    def circ(a, b):
        d = abs(((a - b) % 360.0))
        return d if d <= 180.0 else 360.0 - d

    def _to_local_jd(d, end_of_day=False):
        if hasattr(d, 'year') and hasattr(d, 'month') and hasattr(d, 'day') and not hasattr(d, 'hour'):
            jd_local = utils.gregorian_to_jd(d)
            if end_of_day: jd_local += (23.99/24.0)
            return jd_local
        elif hasattr(d, 'year') and hasattr(d, 'hour'):
            return swe.julday(d.year, d.month, d.day,
                              (23.99/24.0) if end_of_day else
                              (getattr(d, 'hour', 0) +
                               getattr(d, 'minute', 0)/60.0 +
                               getattr(d, 'second', 0)/3600.0))
        else:
            raise TypeError("month_start/month_end must be datetime or drik.Date")

    # natal 7L abs & 7H cusp abs + their signs
    natal_pp = charts.divisional_chart(jd_birth, place, divisional_chart_factor=1)
    natal_lagna_sign = next(int(z) for pid,(z,_d) in natal_pp if pid == const._ascendant_symbol)
    sev_sign = (natal_lagna_sign + 6) % 12
    sev_lord_id = house.house_owner_from_planet_positions(natal_pp, sev_sign)
    sev_lord_abs = next((int(z)*30.0 + float(d)) % 360.0 for pid,(z,d) in natal_pp if pid == sev_lord_id)
    sev_lord_sign = int(sev_lord_abs // 30)

    asc_nat = drik.ascendant(jd_birth, place)
    sev_cusp_abs = ((int(asc_nat[0]) * 30.0 + float(asc_nat[1])) + 180.0) % 360.0
    sev_cusp_sign = int(sev_cusp_abs // 30)

    targets = []
    jt = (jup_target or 'either').lower()
    if jt == 'lord':
        targets = [("lord", sev_lord_abs, sev_lord_sign)]
    elif jt == 'cusp':
        targets = [("cusp", sev_cusp_abs, sev_cusp_sign)]
    else:
        targets = [("lord", sev_lord_abs, sev_lord_sign), ("cusp", sev_cusp_abs, sev_cusp_sign)]

    # month bounds (LOCAL JD)
    jd0 = _to_local_jd(month_start, False)
    jd1 = _to_local_jd(month_end,   True)
    tz = float(place.timezone)

    JUP_ASP = (120.0, 180.0, 240.0)  # 5/7/9
    SAT_SIG_OFFSETS = (2, 6, 9)      # +3/+7/+10 houses => +2/+6/+9 signs modulo-12

    day = 0
    while True:
        jd_local = math.floor(jd0) + day
        if jd_local > jd1: break
        jd_utc = jd_local - tz

        jup_abs = drik.sidereal_longitude(jd_utc, const._JUPITER) % 360.0
        sat_abs = drik.sidereal_longitude(jd_utc, const._SATURN)  % 360.0
        sat_sign = int(sat_abs // 30)

        for tag, tgt_abs, tgt_sign in targets:
            # Jupiter criterion
            jup_ok = (circ(jup_abs, tgt_abs) <= tol)
            if not jup_ok and jup_mode == 'landing_or_conj':
                jup_ok = (min(circ((jup_abs + a) % 360.0, tgt_abs) for a in JUP_ASP) <= tol)
            if not jup_ok:
                continue

            # Saturn sign-aspect to target sign (3rd/7th/10th)
            sat_aspect_signs = { (sat_sign + off) % 12 for off in SAT_SIG_OFFSETS }
            if tgt_sign in sat_aspect_signs:
                return 3, {
                    "hit_day": utils.jd_to_gregorian(jd_local),
                    "jupiter_abs": jup_abs,
                    "saturn_abs": sat_abs,
                    "target_used": tag,
                    "target_abs": tgt_abs,
                    "target_sign": tgt_sign
                }

        day += 1

    return 0, {"why": "no_strong_sign_day"}


def predict_marriage_windows_from_jd_place(jd, place, start_year=None, end_year=None, divisional_chart_factor=1,
                                           marriage_age_range=None):
    """
    Orchestrates the full algorithm over a year range:
    - Builds D1, D9, derived points (UL, DK, 7L, Vivaha Saham)
    - Iterates Vimshottari MD/AD and monthly Jupiter windows
    - Applies SCD (year), Tajaka annual triggers (month/week)
    - (Optional) Kalachakra + compressed D9 Narayana confirmation
    Returns: list of dicts [{year, month, score, window, reasons}, ...] sorted by score
    """
    # ---- Inputs / defaults ----
    marriage_age_range = _marriage_age_year_range if marriage_age_range is None else marriage_age_range
    yb, _, _, _ = utils.jd_to_gregorian(jd)

    allowed_min_year = yb + marriage_age_range[0]
    allowed_max_year = yb + marriage_age_range[1]

    if start_year is None:
        start_year = allowed_min_year
    if end_year is None:
        end_year = allowed_max_year

    iter_start_year = max(start_year, allowed_min_year)
    iter_end_year   = min(end_year, allowed_max_year)

    if iter_start_year > iter_end_year:
        return []

    # ---- Base charts from PyJHora ----
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
        # ---- YEAR-LEVEL (compute once per year) ----
        scd_info = _sudarsana_chakra_year_info(jd, place, year, chart_1d_d9)
        scd_score_year = _score_scd_year_support(scd_info, derived)

        tajaka = _get_varshaphala_marriage_triggers(jd, place, year, derived)

        # (Optional) re-enable after validation
        # kcd_score_year = _score_kalachakra_support(jd, place, year, derived)
        kcd_score_year = 0

        for month in range(1, 13):
            month_start = datetime(year, month, 1)
            month_end = _end_of_month(year, month)

            # ---- Day-level boosters first (visible even if vmd==0) ----
            if DT_PERFECT_ENABLED:
                dtp_score, dtp_detail = _score_dt_perfect_in_month(
                    jd, place, month_start, month_end,
                    tol=DT_PERFECT_ORB, sev_target='either',
                    pair_window_days=DT_PERFECT_PAIR_WINDOW_DAYS
                )
            else:
                dtp_score, dtp_detail = 0, {"why": "disabled"}

            dt_strong_score, dt_strong_detail = _score_dt_strong_sign_in_month(
                jd, place, month_start, month_end,
                jup_target=DT_STRONG_JUP_TARGET,
                jup_mode=DT_STRONG_JUP_MODE,
                tol=DT_STRONG_ORB
            )
            dt_strong_award = DT_STRONG_AWARD if dt_strong_score > 0 else 0

            # (Optional) Part-3 timing refinement
            p3_score, p3_detail = _score_part3_in_month(jd, place, month_start, month_end, tol=2.0)

            # ---- Vimshottari gating per month ----
            md_ad_pd = _active_vimsottari_in_window(segments, month_start, month_end)
            vmd = _score_vimsottari_capability(md_ad_pd, derived)

            # Skip only if nothing meaningful fires at all
            if vmd == 0 and (dtp_score == 0 and p3_score == 0 and dt_strong_award == 0):
                continue

            # ---- MONTH-LEVEL supports ----
            jtransit = _get_monthly_jupiter_transit_support(jd, place, year, month, derived)
            tajaka_score, tajaka_detail = _score_tajaka_month(tajaka, month_start, month_end, derived)

            # Optional/experimental neutral for now
            kcd_score = 0  # or use kcd_score_year
            cnd9_score = 0
            cultural = 0

            # ---- Compose total ----
            total = (vmd + jtransit + scd_score_year + tajaka_score +
                     dtp_score + p3_score + dt_strong_award +
                     kcd_score + cnd9_score + cultural)

            if total > 0:
                # Enriched reasons
                reasons = _collect_reasons(
                    md_ad_pd, jtransit, scd_info, tajaka_detail, kcd_score, cnd9_score, cultural, derived
                )
                reasons['scd_score']         = scd_score_year
                reasons['jupiter_transit']   = jtransit

                reasons['dt_perfect_enabled'] = DT_PERFECT_ENABLED
                reasons['dt_perfect_score']   = dtp_score
                reasons['dt_perfect_detail']  = dtp_detail

                reasons['dt_strong_score']    = dt_strong_award
                reasons['dt_strong_detail']   = dt_strong_detail
                reasons['dt_strong_mode']     = {"jup_target": DT_STRONG_JUP_TARGET,
                                                 "jup_mode": DT_STRONG_JUP_MODE,
                                                 "orb": DT_STRONG_ORB}

                reasons['part3_score']        = p3_score
                reasons['part3_detail']       = p3_detail

                # Patyayini overlap
                paty = tajaka.get('patyayini_schedule')
                if paty:
                    try:
                        LL = tajaka['annual_ll']
                        L7 = tajaka['annual_7l']
                        annual_pp = tajaka['annual_planet_positions']

                        ul_sign = derived['ul_d1']
                        ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign)

                        vs_lord = house.house_owner_from_planet_positions(annual_pp, tajaka['vivaha_saham_sign'])
                        m_lord = tajaka['muntha_lord']

                        targets = {const.VENUS_ID, L7, ul_lord, vs_lord, m_lord}
                        hit = _patyayini_month_hit(paty, month_start, month_end, targets)
                        reasons['patyayini_hit'] = hit
                        if hit:
                            reasons['patyayini_lords_in_month'] = sorted(
                                {sl['lord'] for sl in paty if not (sl['end'] < month_start or sl['start'] > month_end)},
                                key=str
                            )
                    except Exception:
                        reasons['patyayini_hit'] = False

                candidates.append({
                    'year': year,
                    'month': month,
                    'window': (month_start, month_end),
                    'score': total,
                    'reasons': reasons
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

    # Aspects (optional)
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
    out['night_time_birth'] = _is_night_birth(jd, place)

    return out


def _get_vimsottari_md_ad_pd(jd, place, divisional_chart_factor=1):
    _, vdb_info = vimsottari.get_vimsottari_dhasa_bhukthi(jd, place, divisional_chart_factor=divisional_chart_factor)
    segments = _expand_to_md_ad_segments(vdb_info)
    return segments


def _expand_to_md_ad_segments(vdb_info):
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
    return {'md': best['md'], 'ad': best['ad'], 'pd': best.get('pd')}


# ---- Vimshottari scoring ----

def _score_vimsottari_capability(md_ad_pd, derived):
    if not md_ad_pd:
        return 0
    score = 0
    score += score_planet_marriage_capability(md_ad_pd['md'], derived, tier='md')
    score += score_planet_marriage_capability(md_ad_pd['ad'], derived, tier='ad')
    if md_ad_pd.get('pd') is not None:
        score += score_planet_marriage_capability(md_ad_pd['pd'], derived, tier='pd')
    return score


def score_planet_marriage_capability(planet, derived, tier='md'):
    if planet is None:
        return 0

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
    Score Jupiter’s monthly position:
      +1 if Jupiter is in Lagna/5/7/9 from D1 Lagna
      +1 if Jupiter aspects D1 7th house sign (Jupiter: 5th, 7th, 9th)
      +1 if Jupiter aspects 7th-lord sign or is in/aspects UL sign
    """
    start = datetime(year, month, 1, 12, 0, 0)
    end = _end_of_month(year, month)
    mid = start + (end - start) / 2

    jd_mid = swe.julday(mid.year, mid.month, mid.day, mid.hour + mid.minute/60.0 + mid.second/3600.0)
    jd_utc = jd_mid - (place.timezone / 24.0)

    jup_lon = drik.sidereal_longitude(jd_utc, const._JUPITER)
    jup_sign = int(jup_lon // 30)

    lagna = derived['lagna_sign_d1']
    h7    = derived['seventh_house_sign_d1']
    l7sg  = derived['seventh_lord_sign_d1']
    ulsg  = derived['ul_d1']

    score = 0
    good = {lagna, (lagna+4) % 12, (lagna+6) % 12, (lagna+8) % 12}
    if jup_sign in good:
        score += 1

    jup_aspects = { (jup_sign + 4) % 12, (jup_sign + 6) % 12, (jup_sign + 8) % 12 }
    if h7 in jup_aspects:
        score += 1
    if (l7sg in jup_aspects) or (ulsg in jup_aspects) or (jup_sign == ulsg):
        score += 1

    return score


# ---- Sudarsana Chakra Dasa (SCD) year filter ----

def _sudarsana_chakra_year_info(jd, place, year, chart_1d_d9):
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    running_year = (year - by) + 1
    house_offset = running_year % 12

    lagna_sign_d9 = 0
    for sgn, token in enumerate(chart_1d_d9):
        if token:
            parts = token.split('/')
            if 'L' in parts:
                lagna_sign_d9 = sgn
                break

    scd_rasi_d9 = (lagna_sign_d9 + house_offset) % 12

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
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    years_after_dob = (year - by)

    annual_pp, (vf_y_m_d, vf_hours_local) = annual_chart(
        jd_at_dob=jd, place=place, divisional_chart_factor=1, years=years_after_dob
    )
    vf_hours = _safe_extract_float_hours(vf_hours_local)
    H, M, S = _hours_to_hms(vf_hours)
    vf_start = datetime(vf_y_m_d[0], vf_y_m_d[1], vf_y_m_d[2], H, M, S)

    jup_sign = _get_planet_sign_from_annual(annual_pp, const.JUPITER_ID)
    ven_sign = _get_planet_sign_from_annual(annual_pp, const.VENUS_ID)

    annual_lagna_sign = _find_lagna_sign_from_positions(annual_pp)
    annual_h7_sign = (annual_lagna_sign + const.HOUSE_7) % 12
    annual_ll = house.house_owner_from_planet_positions(annual_pp, annual_lagna_sign)
    annual_7l = house.house_owner_from_planet_positions(annual_pp, annual_h7_sign)

    night_time_birth = derived.get('night_time_birth', False)

    vs_ret = vivaha_saham(annual_pp, night_time_birth=night_time_birth)
    vs_sign, vs_abs_long = _parse_vivaha_saham_return(vs_ret)
    ven_abs_long = _get_planet_abs_long_from_positions(annual_pp, const.VENUS_ID)

    natal_lagna_sign = derived['lagna_sign_d1']
    muntha_sign = (natal_lagna_sign + years_after_dob) % 12
    muntha_lord = house.house_owner_from_planet_positions(annual_pp, muntha_sign)

    jd_vf_local = _gregorian_to_jd(vf_y_m_d[0], vf_y_m_d[1], vf_y_m_d[2], vf_hours)
    patyayini_raw = patyayini.get_dhasa_bhukthi(jd_vf_local, place, divisional_chart_factor=1, chart_method=1)
    patyayini_schedule = _expand_patyayini_schedule(patyayini_raw)

    tajaka = {
        'vf_start': vf_start,
        'years_after_dob': years_after_dob,
        'annual_planet_positions': annual_pp,
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
        'retro_flags': None,
    }
    return tajaka


def _expand_patyayini_schedule(patyayini_raw):
    if not patyayini_raw:
        return None

    first = patyayini_raw[0]
    out = []

    def _parse_dt_str(s):
        try:
            return datetime.fromisoformat(s)
        except Exception:
            try:
                return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.strptime(s.strip().split()[0], "%Y-%m-%d")

    if (
        isinstance(first, (list, tuple))
        and len(first) == 3
        and isinstance(first[1], list)
        and first[1]
        and isinstance(first[1][0], (list, tuple))
        and len(first[1][0]) == 2
        and isinstance(first[1][0][1], str)
    ):
        flat = []
        total_days = 0.0
        for major_lord, bhukthi_list, major_days in patyayini_raw:
            total_days += float(major_days)
            for (sub_lord, start_str) in bhukthi_list:
                start_dt = _parse_dt_str(start_str)
                flat.append((sub_lord, start_dt))
        flat.sort(key=lambda t: t[1])
        if not flat:
            return None

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
        starts = []
        for row in patyayini_raw:
            try:
                planet, (y, m, d), days = row
                start_dt = datetime(int(y), int(m), int(d), 0, 0, 0)
                starts.append((planet, start_dt, float(days)))
            except Exception:
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
    if not tajaka:
        return 0, {'ithasala_orb': 999, 'venus_saham_delta': 999}

    annual_pp = tajaka['annual_planet_positions']
    score = 0
    ithasala_best = 999

    ven_abs = tajaka['venus_abs_long']
    vs_abs = tajaka['vivaha_saham_abs_long']
    venus_saham_delta = _angle_delta_deg(ven_abs, vs_abs)

    if venus_saham_delta <= 2.0:
        score += 3
    elif venus_saham_delta <= 5.0:
        score += 2

    LL = tajaka['annual_ll']
    L7 = tajaka['annual_7l']
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, LL, L7)
    if has_it:
        if it_type == 3:
            score += 3; ithasala_best = 0
        else:
            score += 1; ithasala_best = min(ithasala_best, 1)

    m_lord = tajaka['muntha_lord']
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, m_lord)
    if has_it:
        if it_type == 3:
            score += 2; ithasala_best = 0
        else:
            score += 1; ithasala_best = min(ithasala_best, 1)

    vs_sign = tajaka['vivaha_saham_sign']
    vs_lord = house.house_owner_from_planet_positions(annual_pp, vs_sign)
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, vs_lord)
    if has_it:
        if it_type == 3:
            score += 2; ithasala_best = 0
        else:
            score += 1; ithasala_best = min(ithasala_best, 1)

    ul_sign = derived['ul_d1']
    ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign)
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, ul_lord)
    if has_it:
        score += 1
        ithasala_best = min(ithasala_best, 0 if it_type == 3 else 1)

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
    return swe.julday(y, m, d, hours_float)

def _is_night_birth(jd, place):
    by, bm, bd, birth_hours = utils.jd_to_gregorian(jd)
    sunrise_hours = drik.sunrise(jd, place)[0]
    sunset_hours  = drik.sunset(jd, place)[0]
    return (birth_hours >= sunset_hours) or (birth_hours < sunrise_hours)


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

    if 'patyayini_hit' in tajaka_detail:
        out['patyayini_hit'] = tajaka_detail['patyayini_hit']
    if 'patyayini_lords_in_month' in tajaka_detail:
        out['patyayini_lords_in_month'] = tajaka_detail['patyayini_lords_in_month']

    planet_names = getattr(utils, 'PLANET_NAMES', None)
    def _pname(p):
        if p == 'L':
            return 'Lagna'
        if isinstance(p, int) and 0 <= p <= 8 and planet_names:
            return planet_names[p]
        return str(p)

    out['md_ad_pd_names'] = {
        'md': _pname(md_ad_pd.get('md')) if md_ad_pd else None,
        'ad': _pname(md_ad_pd.get('ad')) if md_ad_pd else None,
        'pd': _pname(md_ad_pd.get('pd')) if (md_ad_pd and md_ad_pd.get('pd') is not None) else None
    }
    if out.get('patyayini_lords_in_month'):
        out['patyayini_lords_in_month_names'] = [
            _pname(pid) for pid in out['patyayini_lords_in_month']
        ]

    return out


# ---------- Optional TODOs (return 0 for now) ----------

def _score_compressed_d9_narayana(jd, place, month_start, month_end, derived):
    return 0

def _score_cultural_month(month_start, month_end):
    return 0


# ---------- (Optional) Adaptors you may or may not need ----------

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
    by, bm, bd, birth_hours = utils.jd_to_gregorian(jd)
    H, M, S = _hours_to_hms(birth_hours)
    dob = (by, bm, bd)
    tob = (H, M, S)

    try:
        kcd_rows = kalachakra.get_dhasa_bhukthi(
            dob, tob, place,
            divisional_chart_factor=1,
            dhasa_starting_planet=1,
            include_antardhasa=True,
            star_position_from_moon=1
        )
    except Exception:
        return 0

    kcd_segments = _expand_kalachakra_segments(kcd_rows)

    win_start = datetime(year, 1, 1, 0, 0, 0)
    win_end = datetime(year, 12, 31, 23, 59, 59)

    best = 0
    venus_sign_d1 = derived['venus_sign_d1']
    seventh_house_sign_d1 = derived['seventh_house_sign_d1']
    seventh_lord_d1 = derived['seventh_lord_d1']

    for seg in kcd_segments:
        if (seg['end'] < win_start) or (seg['start'] > win_end):
            continue
        md = seg['md']; ad = seg['ad']
        treat_as_rasi = (md is not None and md > 8) or (ad is not None and ad > 8)
        score = 0
        if treat_as_rasi:
            md_rasi = md; ad_rasi = ad
            if md_rasi == venus_sign_d1:
                score += 1
            if ad_rasi is not None:
                if ad_rasi == ((venus_sign_d1 + 6) % 12):
                    score += 1
                elif ad_rasi == ((md_rasi + 6) % 12):
                    score += 1
                elif ad_rasi == seventh_house_sign_d1:
                    score += 1
        else:
            md_pl = md; ad_pl = ad
            if md_pl == const.VENUS_ID or ad_pl == const.VENUS_ID:
                score += 1
            if md_pl == seventh_lord_d1 or ad_pl == seventh_lord_d1:
                score += 1
        best = max(best, min(score, 2))
        if best >= 2:
            break
    return best


def _expand_kalachakra_segments(kcd_rows):
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

    starts.sort(key=lambda t: t[2])
    for i, (md, ad, start_dt) in enumerate(starts):
        if i < len(starts) - 1:
            end_dt = starts[i+1][2] - timedelta(seconds=1)
        else:
            end_dt = datetime(9999, 12, 31, 23, 59, 59)
        segs.append({'md': md, 'ad': ad, 'start': start_dt, 'end': end_dt})
    return segs


############### temporary Probe Functions ##################

def probe_jupiter_conj_7L_days(jd_birth, place, start_year, end_year, tol=2.0):
    """Daily count of Jupiter within ±tol of natal D1 7L absolute degree."""
    natal_pp = charts.divisional_chart(jd_birth, place, divisional_chart_factor=1)
    natal_lagna_sign = None
    for pid, (zod, _deg) in natal_pp:
        if pid == const._ascendant_symbol:
            natal_lagna_sign = int(zod); break
    if natal_lagna_sign is None:
        print("[PROBE] No natal Lagna found."); return

    sev_sign = (natal_lagna_sign + 6) % 12
    sev_lord_id = house.house_owner_from_planet_positions(natal_pp, sev_sign)

    sev_lord_abs = None
    for pid, (zod, deg) in natal_pp:
        if pid == sev_lord_id:
            sev_lord_abs = (int(zod) * 30.0 + float(deg)) % 360.0
            break
    if sev_lord_abs is None:
        print("[PROBE] Could not locate natal 7L abs degree."); return

    print(f"[PROBE] natal 7L id={sev_lord_id}, 7L_abs={sev_lord_abs:.2f}°")

    tz = float(place.timezone)
    hits = 0
    near_days = []
    for y in range(start_year, end_year + 1):
        d0 = utils.gregorian_to_jd(drik.Date(y, 1, 1))
        d1 = utils.gregorian_to_jd(drik.Date(y, 12, 31)) + (23.99/24.0)
        N = int((d1 - d0) + 1.00001)
        for di in range(N):
            jd_local = d0 + di
            jd_utc   = jd_local - tz
            j = drik.sidereal_longitude(jd_utc, const._JUPITER) % 360.0
            d = abs(((j - sev_lord_abs) % 360.0)); d = d if d <= 180.0 else 360.0 - d
            if d <= tol:
                hits += 1
                near_days.append(utils.jd_to_gregorian(jd_local))
    print(f"[PROBE] days with Jupiter within ±{tol}° of natal 7L: {hits}")
    if hits:
        print("  e.g.,", near_days[:5], "...")


def probe_saturn_landing_near_jup_7L(jd_birth, place, year, month, tol=2.0, pair_window_days=15):
    """For a given month, list JUP≈7L days and Saturn min landing deltas on 7L/7H in ±pair_window_days."""
    natal_pp = charts.divisional_chart(jd_birth, place, divisional_chart_factor=1)
    natal_lagna_sign = next(int(zod) for pid,(zod,_deg) in natal_pp if pid == const._ascendant_symbol)
    sev_sign = (natal_lagna_sign + 6) % 12
    sev_lord_id = house.house_owner_from_planet_positions(natal_pp, sev_sign)
    sev_lord_abs = next((int(z)*30.0 + float(d)) % 360.0 for pid,(z,d) in natal_pp if pid == sev_lord_id)

    asc_nat = drik.ascendant(jd_birth, place)
    sev_cusp_abs = ((int(asc_nat[0]) * 30.0 + float(asc_nat[1])) + 180.0) % 360.0

    def circ(a,b):
        d = abs(((a-b) % 360.0));  return d if d <= 180.0 else 360.0 - d

    tz = float(place.timezone)
    SAT_ASP = (60.0, 180.0, 300.0)

    try:
        ms = drik.Date(year, month, 1)
        for d in (31,30,29,28):
            try:
                me = drik.Date(year, month, d); break
            except Exception:
                continue
    except Exception as e:
        print("[PROBE2] bad month:", e); return

    jd0 = utils.gregorian_to_jd(ms)
    jd1 = utils.gregorian_to_jd(me) + (23.99/24.0)

    day = 0
    found_any = False
    while True:
        jd_local = math.floor(jd0) + day
        if jd_local > jd1: break
        jd_utc   = jd_local - tz

        j = drik.sidereal_longitude(jd_utc, const._JUPITER) % 360.0
        dJ = circ(j, sev_lord_abs)

        if dJ <= tol:
            best_7L = 999.0; best_7H = 999.0
            for k in range(-pair_window_days, pair_window_days+1):
                k_local = jd_local + k
                s = drik.sidereal_longitude(k_local - tz, const._SATURN) % 360.0
                land = [(s + a) % 360.0 for a in SAT_ASP]
                best_7L = min(best_7L, min(circ(L, sev_lord_abs) for L in land))
                best_7H = min(best_7H, min(circ(L, sev_cusp_abs) for L in land))
            print(f"[PROBE2] {utils.jd_to_gregorian(jd_local)}  JUP-7L={dJ:.2f}°  "
                  f"Sa→7L_min={best_7L:.2f}°  Sa→7H_min={best_7H:.2f}°")
            found_any = True

        day += 1

    if not found_any:
        print("[PROBE2] No JUP≈7L days in this month.")


if __name__ == "__main__":
    utils.set_language('en')
    # dob = (1996,12,7); tob = (10,34,0); place = drik.Place('Chennai',13.0878,80.2785,5.5)
    dob = (1964,11,16); tob = (4,30,0); place = drik.Place('Karamadai',11.18,76.57,5.5)
    dob = (1969,6,22); tob = (21,41,0); place = drik.Place('Trichy',10.49,78.41,5.5)
    #dob = (1973,7,26); tob = (21,41,0); place = drik.Place('UNK',16+13/60,80+28/60,5.5)
    jd = utils.julian_day_number(dob, tob)
    # Diagnostics (optional)
    # probe_saturn_landing_near_jup_7L(jd, place, 1991, 10)
    # probe_jupiter_conj_7L_days(jd, place, start_year=1990, end_year=1998)
    print(predict_marriage_windows_from_jd_place(jd, place))
