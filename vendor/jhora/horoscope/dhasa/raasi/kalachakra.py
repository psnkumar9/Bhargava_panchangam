#!/usr/bin/env python
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
from jhora import const, utils
from jhora.panchanga import drik
from jhora.horoscope.chart import charts
""" TODO: Dhasa Progression does not seem to match with JHora """
# -*- coding: utf-8 -*-
"""
Kalachakra Daśā (L1..L6) with method switch:
  1 = PVR/book table logic (Moon-pāda KCD wheel) + proportional split at L2+
  2 = Sanjay Rath style cycle rotation (same as 1 here; hook for future gati nuances)
  3 = Rāghavācārya (JHora): L1 by navāṁśa progression; L2 by 9 pādas (via KCD tables)

Sources:
- P.V.R. Narasimha Rao (IndiaDivine): Rāghavācārya MD = navāṁśa progression; AD from Parāśara/KCD tables.  [1](https://www.youtube.com/@pvr108)
- PVR Kālacakra Daśā tutorial (1998): parent-first L2 order & sign-year weights.  
- PVR textbook (Ch.24): KCD wheel, savya/apasavya triads, pāda paramāyuṣ, sign-year durations.  [2](https://www.youtube.com/watch?v=BLnDJ3gKq3o)
"""

# -----------------------------
# Small internal helpers only
# -----------------------------
def _cycle_for(kc_index, paadham):
    """Return the 9-sign cycle (list of sign indices) for a given (group, pāda)."""
    return list(const.kalachakra_rasis[kc_index][paadham])  # shape: 4×4×9

def _rotate(lst, k):
    n = len(lst)
    if n == 0: return lst
    k %= n
    return lst[k:] + lst[:k]

def _rotate_cycle_from_sign(cycle, start_sign):
    return _rotate(cycle, cycle.index(start_sign)) if start_sign in cycle else cycle[:]

def _sign_year_weights(signs):
    return [float(const.kalachakra_dhasa_duration[s]) for s in signs]  # len=12

def _scaled_child_years_proportional(parent_years, weights):
    total = sum(weights) or 1.0
    return [parent_years * (w / total) for w in weights]

# ---------- method-specific L2 (re-used for deeper levels) ----------
def _antardhasa_pvr(parent_sign, kc_index, paadham, parent_years):
    """
    Method=1 (PVR/book table logic):
      - Order: 9-sign cycle for (kc_index, pāda), rotated to start at parent_sign.
      - Durations: proportional split of parent_years by KCD sign-year weights.
    """
    cyc = _rotate_cycle_from_sign(_cycle_for(kc_index, paadham), parent_sign)
    yrs = _scaled_child_years_proportional(parent_years, _sign_year_weights(cyc))
    return cyc, yrs

def _antardhasa_rath(parent_sign, kc_index, paadham, parent_years):
    """
    Method=2 (Sanjay Rath):
      - Same rotation + proportional split now; plug gati nuances later if desired.
    """
    cyc = _rotate_cycle_from_sign(_cycle_for(kc_index, paadham), parent_sign)
    yrs = _scaled_child_years_proportional(parent_years, _sign_year_weights(cyc))
    return cyc, yrs

# --- NAVĀṂŚA helpers for method=3 (Rāghavācārya) ---
_NAVAMSA_SPAN = 360.0 / 108.0  # 3°20' per navāṁśa (also pāda span)

def _navamsa_rasi_from_longitude(lon_deg):
    """
    Parāśara navāṁśa mapping (D‑9):
      Movable (Ar,Cn,Li,Cp): first navāṁśa starts from same sign
      Fixed   (Ta,Le,Sc,Aq): first navāṁśa starts from 9th (sign+8)
      Dual    (Ge,Vi,Sg,Pi): first navāṁśa starts from 5th (sign+4)
    Returns navāṁśa (sign) index 0..11.
    """
    lon = float(lon_deg) % 360.0
    rasi = int(lon // 30.0)             # 0..11
    off  = lon - (rasi * 30.0)          # 0..30
    n    = int(off // (30.0/9.0))       # which navāṁśa within sign (0..8)

    if rasi in (0, 3, 6, 9):      # movable
        start = rasi
    elif rasi in (1, 4, 7, 10):   # fixed
        start = (rasi + 8) % 12
    else:                         # dual
        start = (rasi + 4) % 12

    return (start + n) % 12

def _fraction_left_in_current_navamsa(lon_deg):
    lon = float(lon_deg) % 360.0
    x   = lon % 30.0
    span = 30.0 / 9.0
    i    = int(x // span)
    end  = (i + 1) * span
    left = end - x
    return max(0.0, min(1.0, left / span))

# --- method=3 AD builder (corrected) ---
def _padas_in_sign_desc(sign_idx):
    """
    Return the nine (nakshatra_index, pada_index0..3) that occupy a given sign (0..11),
    in *descending zodiac* order (end of sign -> start of sign), matching examples like:
      Ar -> Krittika-1, Bharani-4..1, Aswini-4..1
      Pi -> Revati-4..1, Uttarabhadra-4..1, Poorvabhadra-4
    We derive them programmatically using midpoints of the 9 navāṁśas within the sign.
    """
    start = sign_idx * 30.0
    # descending midpoints: 8..0
    mids = [start + (8 - i + 0.5) * _NAVAMSA_SPAN for i in range(9)]
    out = []
    for L in mids:
        nak, paa, _ = drik.nakshatra_pada(L)  # paa = 1..4
        out.append((nak-1, paa-1))
    return out  # list of 9 tuples

# --- helper: find kc-group for a nakshatra index (0..26) ---
def _kc_group_for_nak(nak_index):
    if   nak_index in const.savya_stars_1:      return 0
    elif nak_index in const.savya_stars_2:      return 1
    elif nak_index in const.apasavya_stars_1:   return 2
    else:                                       return 3

# --- NEW: method=3 AD builder (correct JHora/Rāghavācārya logic) ---
def _antardhasa_raghavacharya_for_md_navamsa(md_nav_start_lon, md_years):
    """
    L2 for method=3:
      • Determine the nakshatra & pāda of the MD navāṁśa (at its start).
      • Find the KCD table row for that (kc-group, pāda).
      • The entire 9‑sign row is the AD order.
      • Split MD years proportionally by KCD sign‑year weights (ΣAD = MD).
    """
    # tiny epsilon to avoid boundary ambiguity
    nak, paa, _ = drik.nakshatra_pada(md_nav_start_lon + 1e-9)  # paa=1..4
    nak_i, paa_i = nak - 1, paa - 1
    kc = _kc_group_for_nak(nak_i)

    # AD signs = the 9‑sign dāśā cycle for THIS pāda (per KCD tables)
    ad_signs = list(const.kalachakra_rasis[kc][paa_i])  # 9 signs

    # Durations: proportional split by KCD sign‑year weights
    weights  = _sign_year_weights(ad_signs)
    ad_years = _scaled_child_years_proportional(md_years, weights)
    return ad_signs, ad_years

# --- ascending pādas inside a sign (0°→30°) ---
def _padas_in_sign_asc(sign_idx):
    """
    Return the nine (nak_index, pada_index0..3) occupying a given sign (0..11),
    in ascending zodiac order within the sign (start -> end).
    """
    start = sign_idx * 30.0
    mids = [start + (i + 0.5) * _NAVAMSA_SPAN for i in range(9)]  # i=0..8
    out = []
    for L in mids:
        nak, paa, _ = drik.nakshatra_pada(L)  # paa = 1..4
        out.append((nak-1, paa-1))
    return out

def _antardhasa_raghavacharya_by_padas(md_sign, md_years):
    """
    Rāghavācārya L2: walk the 9 pādas inside the MD sign in ASCENDING order.
    For each (nak,pāda), take the KCD table for that pāda and pick its FIRST sign.
    Split years proportionally by KCD sign-year weights.
    """
    ad_signs = []
    for nak_i, paa_i in _padas_in_sign_asc(md_sign):
        # which KCD group does this nak belong to?
        if   nak_i in const.savya_stars_1:      kc = 0
        elif nak_i in const.savya_stars_2:      kc = 1
        elif nak_i in const.apasavya_stars_1:   kc = 2
        else:                                   kc = 3
        cycle = const.kalachakra_rasis[kc][paa_i]  # 9‑sign KCD cycle for this pāda
        ad_signs.append(int(cycle[0]))             # AD sign = first in that cycle

    weights = _sign_year_weights(ad_signs)
    ad_years = _scaled_child_years_proportional(md_years, weights)
    return ad_signs, ad_years

# ---------------------------------------------------------------
# L1 progression builder with birth balance and method hooks
# ---------------------------------------------------------------
def _get_dhasa_progression(planet_longitude, dhasa_method=const.KALACHAKRA_TYPE.PVR_BOOK):
    """
    Build the Mahā sequence and, for each Mahā, attach L2 payload
    according to the selected method.

    Returns:
        dhasa_periods: list of [md_sign, (bhut_rasis, bhut_years, kc_i, pa_i), md_years]
                       (kc_i, pa_i) are carried for recursion shape; inert for method=3.
    """
    # --------------------
    # method=3 short-path
    # --------------------
    if dhasa_method == const.KALACHAKRA_TYPE.RAGHAVACHARYA:
        lon0 = float(planet_longitude) % 360.0
        frac_left = _fraction_left_in_current_navamsa(lon0)
    
        # align to the start of the current navāṁśa to build the 9 MDs
        rasi = int(lon0 // 30.0)
        off  = lon0 - (rasi * 30.0)
        span = 30.0 / 9.0
        i0   = int(off // span)
        start_of_nav = (rasi * 30.0) + i0 * span
    
        md_nav_starts = [start_of_nav + k * _NAVAMSA_SPAN for k in range(9)]
        md_signs  = [_navamsa_rasi_from_longitude(L + 1e-9) for L in md_nav_starts]
        md_durs   = [float(const.kalachakra_dhasa_duration[s]) for s in md_signs]
        if md_durs:
            md_durs[0] = md_durs[0] * frac_left  # first MD partial by fraction-left
    
        # carry birth (kc, pāda) only to keep payload shape consistent
        nak_b, paa_b, _ = drik.nakshatra_pada(planet_longitude)
        nak_b -= 1; paa_b -= 1
        if   nak_b in const.savya_stars_1: kc_birth = 0
        elif nak_b in const.savya_stars_2: kc_birth = 1
        elif nak_b in const.apasavya_stars_1: kc_birth = 2
        else: kc_birth = 3
    
        dhasa_periods = []
        for md_sign, md_start, md_years in zip(md_signs, md_nav_starts, md_durs):
            # ADs = the 9‑sign KCD row indexed by THIS MD navāṁśa's nakṣatra‑pāda
            ad_signs, ad_years = _antardhasa_raghavacharya_for_md_navamsa(md_start, md_years)
            dhasa_periods.append([md_sign, (ad_signs, ad_years, kc_birth, paa_b), md_years])
        return dhasa_periods

    # --------------------
    # methods 1 & 2 (book KCD)
    # --------------------
    nakshatra, paadham, _ = drik.nakshatra_pada(planet_longitude)
    nakshatra -= 1
    paadham   -= 1

    if   nakshatra in const.savya_stars_1:      kalachakra_index = 0
    elif nakshatra in const.savya_stars_2:      kalachakra_index = 1
    elif nakshatra in const.apasavya_stars_1:   kalachakra_index = 2
    else:                                       kalachakra_index = 3

    cycle0 = _cycle_for(kalachakra_index, paadham)                         # 9 signs
    param0 = float(const.kalachakra_paramayush[kalachakra_index][paadham]) # 100/85/83/86 etc.
    dur0   = _sign_year_weights(cycle0)                                    # 9-slot weights

    # Fraction traversed inside the birth pāda
    one_star   = 360.0 / 27.0
    one_paadha = 360.0 / 108.0
    nak_start_long = nakshatra * one_star + paadham * one_paadha
    nak_frac = (planet_longitude - nak_start_long) / one_paadha  # 0..1

    # cum-sum (no numpy side-effects)
    dur0_cum, acc = [], 0.0
    for v in dur0:
        acc += v
        dur0_cum.append(acc)

    completed   = nak_frac * param0
    idx_at_birth = next(i for i, s in enumerate(dur0_cum) if s > completed)
    md_remaining = float(dur0_cum[idx_at_birth] - completed)

    # Next (group,pāda) after boundary
    kc_next = kalachakra_index
    pa_next = (paadham + 1) % 4
    if paadham == 3:
        kc_next = {0:1, 1:0, 2:3, 3:2}[kalachakra_index]

    cycle1 = _cycle_for(kc_next, pa_next)

    md_progression = cycle0[idx_at_birth:] + cycle1[:idx_at_birth]
    md_durations   = _sign_year_weights(md_progression)
    md_durations[0] = md_remaining

    split_at = len(cycle0) - idx_at_birth

    if   dhasa_method == const.KALACHAKRA_TYPE.PVR_BOOK: _children = _antardhasa_pvr
    else:                   _children = _antardhasa_rath

    dhasa_periods = []
    for i, md_sign in enumerate(md_progression):
        md_years = md_durations[i]
        if i < split_at:
            kc_i, pa_i = kalachakra_index, paadham
        else:
            kc_i, pa_i = kc_next, pa_next

        bhut_rasis, bhut_years = _children(md_sign, kc_i, pa_i, md_years)
        dhasa_periods.append([md_sign, (bhut_rasis, bhut_years, kc_i, pa_i), md_years])

    return dhasa_periods


# ---------------------------------------------------------
# Public KCD function with depth (L1..L6) & method switch
# ---------------------------------------------------------
def kalachakra_dhasa(
    planet_longitude,
    jd,
    dhasa_level_index=2,    # 1..6  (1=Maha only, 2=+Antara [default])
    round_duration=True,
    dhasa_method=const.KALACHAKRA_TYPE.PVR_BOOK,
    **kwargs
):
    """
    Returns rows shaped as: [ ((lords...), start_str, dur_years), ... ]
    """
    depth = int(dhasa_level_index)
    if not (1 <= depth <= 6):
        raise ValueError("dhasa_level_index must be in 1..6")

    dhasa_periods = _get_dhasa_progression(planet_longitude, dhasa_method=dhasa_method)
    if not dhasa_periods:
        return []

    rows = []
    jd_ptr_md = float(jd)

    if   dhasa_method == const.KALACHAKRA_TYPE.PVR_BOOK: _children = _antardhasa_pvr
    elif dhasa_method == const.KALACHAKRA_TYPE.SANJAY_RATH: _children = _antardhasa_rath
    elif dhasa_method == const.KALACHAKRA_TYPE.RAGHAVACHARYA: _children = _antardhasa_pvr  # not used; L2 precomputed
    else:                   _children = _antardhasa_pvr

    for md_sign, l2_payload, md_years in dhasa_periods:
        bhut_rasis, bhut_years, kc_i, pa_i = l2_payload

        if depth == 1:
            start_str = utils.jd_to_gregorian(jd_ptr_md)
            dur_ret   = round(md_years, depth + 1) if round_duration else md_years
            rows.append(((md_sign,), start_str, float(dur_ret)))
            jd_ptr_md += md_years * const.sidereal_year
            continue

        jd_ptr_l2 = jd_ptr_md
        if depth == 2:
            for blord, byears in zip(bhut_rasis, bhut_years):
                start_str = utils.jd_to_gregorian(jd_ptr_l2)
                dur_ret   = round(byears, depth + 1) if round_duration else byears
                rows.append(((md_sign, blord), start_str, float(dur_ret)))
                jd_ptr_l2 += byears * const.sidereal_year
            jd_ptr_md = jd_ptr_l2
            continue

        # --------- L3..L6 recursion (patched) ----------
        # We measure depth by the current prefix length, not by an arbitrary counter,
        # so that the final tuple always has exactly `depth` lords.
        def _recurse(prefix_lords, start_jd, parent_years, kc_for_node, pa_for_node):
            """
            prefix_lords : list[int] -> current chain (e.g., [L1, L2, ..., Lk])
            start_jd     : float     -> JD at start of this node
            parent_years : float     -> duration (years) of this node
            kc_for_node, pa_for_node: KCD context for child order (in method=3 this is inert)
        
            Emits a leaf row when len(prefix_lords) == depth (1..6).
            Otherwise splits into 9 children and recurses.
            """
            current_level = len(prefix_lords)        # 1..depth
            if current_level == depth:
                start_str = utils.jd_to_gregorian(start_jd)
                dur_ret   = round(parent_years, depth + 1) if round_duration else parent_years
                rows.append((tuple(prefix_lords), start_str, float(dur_ret)))
                return start_jd + parent_years * const.sidereal_year
        
            # produce 9 children for next level
            # NOTE: in method=3, L2 was precomputed; for deeper levels we still use the same
            # KCD child-builder (_children) unless you want a custom Rāghavācārya recursion.
            child_signs, child_years = _children(prefix_lords[-1], kc_for_node, pa_for_node, parent_years)
        
            jd_ptr = start_jd
            for cs, cy in zip(child_signs, child_years):
                jd_ptr = _recurse(prefix_lords + [cs], jd_ptr, cy, kc_for_node, pa_for_node)
            return jd_ptr
        
        # start recursion *from the bhukti* chains (prefix has 2 lords at L2)
        jd_ptr_after_md = jd_ptr_l2
        for blord, byears in zip(bhut_rasis, bhut_years):
            jd_ptr_after_md = _recurse([md_sign, blord], jd_ptr_after_md, byears, kc_i, pa_i)
        
        jd_ptr_md = jd_ptr_after_md

    return rows


# ---------------------------------------------------------
# Public router (seed selection + dasha call)
# ---------------------------------------------------------
def get_dhasa_bhukthi(
    dob, tob, place,
    divisional_chart_factor=1,
    chart_method=1,
    dhasa_starting_planet=1,      # default Moon
    star_position_from_moon=1,    # default from Moon
    dhasa_level_index=2,          # 1..6
    round_duration=True,
    dhasa_method=const.KALACHAKRA_TYPE.RAGHAVACHARYA, # Rangacharya Methos
    **kwargs
):
    """
    Wrapper: computes JD & seed longitude and returns KCD rows.

    NOTE for method=3 (Rāghavācārya):
      Use the same ayanāṁśa as JHora (e.g., TRUE+PUSHYA) for date‑matching.  [3](https://saptamatrika.ru/en/bphs)
    """
    jd = utils.julian_day_number(dob, tob)
    planet_long = charts.get_chart_element_longitude(
        jd, place, divisional_chart_factor, chart_method,
        star_position_from_moon, dhasa_starting_planet
    )
    return kalachakra_dhasa(
        planet_longitude=planet_long,
        jd=jd,
        dhasa_level_index=dhasa_level_index,
        round_duration=round_duration,
        dhasa_method=dhasa_method,
        **kwargs
    )
def nakshathra_dhasa_progression(
    jd_at_dob, place, jd_current,
    star_position_from_moon=1,
    divisional_chart_factor=1,
    chart_method=1,
    dhasa_starting_planet=1,
):
    y,m,d,fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y,m,d); tob = (fh,0,0)
    vd = get_dhasa_bhukthi(dob, tob, place, divisional_chart_factor, chart_method,dhasa_starting_planet,
                           star_position_from_moon, dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY)
    jds = [utils.julian_day_number(drik.Date(y,m,d),(fh,0,0)) for _,(y,m,d,fh),_ in vd]
    mpl = utils.degrees_between_jds(jds, jd_at_dob, jd_current)
    ppl = charts.get_nakshathra_dhasa_progression_longitudes(jd_at_dob, place, planet_progression_correction=mpl,
                                                             divisional_chart_factor=divisional_chart_factor,
                                                             chart_method=chart_method)
    return ppl
def kalachakra_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float years (one of: duration or end)
    parent_end=None,             # (Y, M, D, fractional_hour)
    *,
    jd_at_dob,
    place,
    dhasa_method: int = const.KALACHAKRA_TYPE.PVR_BOOK,       # 1=PVR, 2=Rath, 3=Rāghavācārya
    # Forward knobs used by your wrapper:
    divisional_chart_factor: int = 1,
    chart_method: int = 1,
    dhasa_starting_planet: int = 1,
    star_position_from_moon: int = 1,
    round_duration: bool = False,   # tiler returns exact spans; no rounding needed
    **kwargs
):
    """
    Kalachakra — return ONLY the immediate (p -> p+1) children inside the given parent span.

    Method semantics:
      • method==1 (PVR/book):  L2..L6 = 9-sign KCD cycle rotated to parent, proportional split by KCD sign-year weights.
      • method==2 (Rath):      same as 1 for now (hook for gati nuances later).
      • method==3 (Rāghavācārya):
            - L2 is precomputed from the MD navāṁśa’s nakṣatra‑pāda (payload).
            - L3+ reuse PVR child builder (as in your base).

    Child order/durations are derived exactly as your base does; KCD context (kc, pāda) is taken
    from the MD payload and is propagated to all deeper levels.
    """
    # ---- normalize lords path
    if isinstance(parent_lords, int):
        path = (parent_lords,)
    elif isinstance(parent_lords, (tuple, list)) and parent_lords:
        path = tuple(parent_lords)
    else:
        raise ValueError("parent_lords must be int or a non-empty tuple/list")
    parent_sign = path[-1]
    k = len(path)  # 1 = Mahā parent, 2 = Antara parent, etc.

    # ---- tuple <-> JD
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))
    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    # ---- parent span (years)
    YEAR_DAYS = const.sidereal_year
    start_jd = _tuple_to_jd(parent_start)
    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration (years) or parent_end (tuple).")
    if parent_end is None:
        parent_years = float(parent_duration)
        end_jd = start_jd + parent_years * YEAR_DAYS
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_years = (end_jd - start_jd) / YEAR_DAYS
    if end_jd <= start_jd:
        return []

    # ---- birth-epoch seed longitude (same as your wrapper) & KCD context per MD
    planet_long = charts.get_chart_element_longitude(
        jd_at_dob, place,
        divisional_chart_factor, chart_method,
        star_position_from_moon, dhasa_starting_planet
    )
    # Get full MD progression with L2 payloads (bhut_rasis, bhut_years, kc_i, pa_i)
    dhasa_periods = _get_dhasa_progression(planet_longitude=planet_long, dhasa_method=dhasa_method)
    if not dhasa_periods:
        return []

    # Find kc/pāda for THIS MD (the first lord in the path)
    md_sign = path[0]
    md_entry = next((e for e in dhasa_periods if int(e[0]) == int(md_sign)), None)
    if md_entry is None:
        return []  # parent cannot be expanded with this method/context
    bhut_rasis, bhut_years, kc_i, pa_i = md_entry[1]
    md_years = float(md_entry[2])

    # Decide how to build children under this parent
    def _children_method1(parent_sign_local, parent_years_local):
        # 9-cycle rotated to parent + proportional split by KCD weights
        cyc = _rotate_cycle_from_sign(_cycle_for(kc_i, pa_i), parent_sign_local)
        yrs = _scaled_child_years_proportional(parent_years_local, _sign_year_weights(cyc))
        return cyc, yrs

    def _children_method2(parent_sign_local, parent_years_local):
        # Same as method 1 (hook for gati in future)
        cyc = _rotate_cycle_from_sign(_cycle_for(kc_i, pa_i), parent_sign_local)
        yrs = _scaled_child_years_proportional(parent_years_local, _sign_year_weights(cyc))
        return cyc, yrs

    def _children_method3(parent_sign_local, parent_years_local):
        # For L2 (k==1): use precomputed payload order, scaled to this parent's years.
        # For deeper: reuse PVR child builder (same as your base’s recursion).
        if k == 1:
            # Scale payload L2 durations to match the actual parent_years
            total = float(sum(bhut_years)) or 1.0
            scale = parent_years_local / total
            cyc = list(bhut_rasis)
            yrs = [float(by) * scale for by in bhut_years]
            return cyc, yrs
        # L3+: PVR child builder with MD’s kc/pāda context
        return _children_method1(parent_sign_local, parent_years_local)

    if   dhasa_method == const.KALACHAKRA_TYPE.PVR_BOOK: child_builder = _children_method1
    elif dhasa_method == const.KALACHAKRA_TYPE.SANJAY_RATH: child_builder = _children_method2
    else:                   child_builder = _children_method3

    # ---- build & tile children for this parent
    child_signs, child_years = child_builder(parent_sign, parent_years)
    # Defensive: keep lengths consistent
    n = min(len(child_signs), len(child_years))
    child_signs, child_years = child_signs[:n], child_years[:n]
    if n == 0:
        return []

    out = []
    cursor = start_jd
    for i, (cs, cy) in enumerate(zip(child_signs, child_years)):
        child_end = end_jd if i == n - 1 else cursor + cy * YEAR_DAYS
        out.append([path + (int(cs),), _jd_to_tuple(cursor), _jd_to_tuple(child_end)])
        cursor = child_end
        if cursor >= end_jd:
            break

    # exact closure
    out[-1][2] = _jd_to_tuple(end_jd)
    return out
def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
    *,
    dhasa_method: int = const.KALACHAKRA_TYPE.PVR_BOOK,             # 1, 2, or 3
    # Forward knobs used by your wrapper:
    divisional_chart_factor: int = 1,
    chart_method: int = 1,
    dhasa_starting_planet: int = 1,
    star_position_from_moon: int = 1,
    round_duration: bool = False,      # runner uses exact (start,end)
    **kwargs
):
    """
    Kalachakra — narrow Mahā -> … -> target depth; return full running ladder:

      [
        [(l1,),              start1, end1],
        [(l1,l2),            start2, end2],
        [(l1,l2,l3),         start3, end3],
        [(l1,l2,l3,l4),      start4, end4],
        [(l1,l2,l3,l4,l5),   start5, end5],
        [(l1,l2,l3,l4,l5,l6),start6, end6],
      ]
    """

    # ---- depth normalization (Enum-friendly)
    def _normalize_depth(depth_val):
        try:
            depth = int(depth_val)
        except Exception:
            depth = int(const.MAHA_DHASA_DEPTH.DEHA)
        lo, hi = int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY), int(const.MAHA_DHASA_DEPTH.DEHA)
        return min(hi, max(lo, depth))
    target_depth = _normalize_depth(dhasa_level_index)

    # ---- helpers
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _is_zero_length(s, e, eps_seconds=1.0):
        # s,e are (y,m,d,fh)
        return (_tuple_to_jd(e) - _tuple_to_jd(s)) * 86400.0 <= eps_seconds

    def _to_utils_periods(children_rows, parent_end_tuple, eps_seconds=1.0):
        """
        children_rows: [ [lords_tuple, start_tuple, end_tuple], ... ]
        Returns: list of (lords_tuple, start_tuple) + sentinel(parent_end_tuple),
        filtering zero-length rows and enforcing strictly increasing starts.
        """
        flt = [r for r in children_rows if not _is_zero_length(r[1], r[2], eps_seconds)]
        if not flt:
            return []
        flt.sort(key=lambda r: _tuple_to_jd(r[1]))
        proj, prev = [], None
        for lords, st, _ in flt:
            sjd = _tuple_to_jd(st)
            if prev is None or sjd > prev:
                proj.append((lords, st)); prev = sjd
        proj.append((proj[-1][0], parent_end_tuple))  # sentinel
        return proj

    def _lords(x):
        return (x,) if isinstance(x, int) else tuple(x)

    running_all = []

    # ---- L1: Mahā via your base wrapper (anchored at birth JD)
    # base returns rows like: ((l1,), start_tuple, dur_years)
    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d); tob = (fh, 0, 0)

    maha_rows = get_dhasa_bhukthi(
        dob, tob, place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        dhasa_starting_planet=dhasa_starting_planet,
        star_position_from_moon=star_position_from_moon,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        round_duration=False,
        dhasa_method=dhasa_method,**kwargs
    )
    maha_for_utils = [(_lords(row[0]), row[1]) for row in maha_rows]

    # Select running Mahā
    rd1 = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    running = [_lords(rd1[0]), rd1[1], rd1[2]]
    running_all.append(running)

    if target_depth == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return running_all

    # ---- Levels 2..target: expand only the running parent each step (method-aware)
    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        children = kalachakra_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            dhasa_method=dhasa_method,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
            dhasa_starting_planet=dhasa_starting_planet,
            star_position_from_moon=star_position_from_moon,
            round_duration=False,
            **kwargs
        )

        if not children:
            # represent “no deeper split” as a zero-length at boundary
            running = [parent_lords + (parent_lords[-1],), parent_end, parent_end]
            running_all.append(running)
            break

        periods = _to_utils_periods(children, parent_end_tuple=parent_end)
        if not periods:
            last = children[-1]
            running = [last[0], last[1], last[1]]
        else:
            rdk = utils.get_running_dhasa_for_given_date(current_jd, periods)
            running = [_lords(rdk[0]), rdk[1], rdk[2]]

        running_all.append(running)

    return running_all

if __name__ == "__main__":
    utils.set_language('en')
    dob = drik.Date(1996,12,7); tob = (10,34,0)
    place = drik.Place('Chennai,IN', 13.0389, 80.2619, +5.5)    
    jd_at_dob  = utils.julian_day_number(dob, tob)
    from datetime import datetime
    current_date_str,current_time_str = datetime.now().strftime('%Y,%m,%d;%H:%M:%S').split(';')
    y,m,d = map(int,current_date_str.split(','))
    hh,mm,ss = map(int,current_time_str.split(':')); fh = hh+mm/60+ss/3600
    print(utils.date_time_tuple_to_date_time_string(y, m, d, fh))
    current_jd = utils.julian_day_number(drik.Date(y,m,d),(hh,mm,ss))
    _dhasa_method = 3
    import time
    start_time = time.time()
    print("Dehā        :", get_running_dhasa_for_given_date(current_jd, jd_at_dob, place,
                                                            dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
                                                            dhasa_method=_dhasa_method))
    print('new method elapsed time',time.time()-start_time)
    start_time = time.time()
    ad = get_dhasa_bhukthi(dob,tob, place,dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
                           dhasa_method=_dhasa_method)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,const.MAHA_DHASA_DEPTH.DEHA,
                                                               extract_running_period_for_all_levels=True))
    print('old method elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    utils.set_language('en')
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.kalachakra_dhasa_tests()
