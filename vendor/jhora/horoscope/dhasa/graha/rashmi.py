#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# py -- routines for computing tithi, vara, etc.
#
# Copyright (C) 2013 Satish BD  <bdsatish@gmail.com>
# Downloaded from https://github.com/bdsatish/drik-panchanga
#
# This file is part of the "drik-panchanga" Python library
# for computing Hindu luni-solar calendar based on the Swiss ephemeris
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
# Copyright (C) Open Astro Technologies, USA.
# Modified by Sundar Sundaresan, USA. carnaticmusicguru2015@comcast.net
# Downloaded from https://github.com/naturalstupid/PyJHora
"""
    To calculate Rashmi Dhasa Bhukthu
"""
from jhora import const, utils
from jhora.horoscope.chart import charts
from jhora.panchanga import drik
MAX_RAYS = {0: 10, 1: 9, 2: 5, 3: 5, 4: 7, 5: 16, 6: 4}
one_year_duration = const.sidereal_year
vimsottari_adhipati = (
    lambda nak, seed_star=3: const.vimsottari_adhipati_list[
        (nak - seed_star + 3) % (len(const.vimsottari_adhipati_list))
    ]
)
def vimsottari_next_adhipati(lord, direction=1):
    """Returns next guy after `lord` in the adhipati_list"""
    current = const.vimsottari_adhipati_list.index(lord)
    next_index = (current + direction) % len(const.vimsottari_adhipati_list)
    return const.vimsottari_adhipati_list[next_index]

def get_rashmi_dhasa_bhukthi(
    dob, tob, place,
    divisional_chart_factor=1,
    years=1, months=1, sixty_hours=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA, 
    dhasa_method=const.RASHMI_TYPE.BPHS_HIGHEST_RAY,      # 1=Highest Ray (BPHS), 2=Natural, 3=Vimshottari Order
    chart_method=1,
    navamsa_chart_method=1,
    vimsottari_method_seed_star=3,
    max_cycles=8,
    use_real_combusion_limits = True,
    round_duration=True,
):
    # --- 1. Constants & Tables (BPHS Canonical) ---
    MAX_RAYS = {0: 10, 1: 9, 2: 5, 3: 5, 4: 7, 5: 16, 6: 4}
    DEEP_EXALT = {0: 10, 1: 33, 2: 298, 3: 165, 4: 95, 5: 357, 6: 200}
    EXALT_SIGNS = {0: 0, 1: 1, 2: 9, 3: 5, 4: 3, 5: 11, 6: 6}
    OWNERS = {0: 2, 1: 5, 2: 3, 3: 1, 4: 0, 5: 3, 6: 5, 7: 2, 8: 4, 9: 6, 10: 6, 11: 4}
    VIM_LIST = const.vimsottari_adhipati_list
    ONE_YEAR_DAYS = 365.242199
    TARGET_SPAN = const.human_life_span_for_vimsottari_dhasa

    # --- 2. Initial Setup ---
    jd_birth = utils.julian_day_number(dob, tob)
    # Using your solar entry API
    jd_start = drik.next_solar_date(jd_birth, place, years, months, sixty_hours)
    
    d1_pos = charts.divisional_chart(jd_start, place, divisional_chart_factor,chart_method=chart_method)
    d9_pos = charts.divisional_chart(jd_start, place, 9,chart_method=navamsa_chart_method)
    
    sun_z, sun_l = next(pos for p_id, pos in d1_pos if p_id == 0)
    sun_abs_lon = (sun_z * 30) + sun_l
    retro_planets = drik.planets_in_retrograde(jd_start, place)
    # --- 3. Shuddha Rashmi Calculation ---
    planet_rays = {}
    for p_id, (zod, lon) in d1_pos[const.SUN_ID+1:const._pp_count_upto_saturn]: # Sun to Saturn
        idx = p_id -1
        if use_real_combusion_limits:
            combusion_limit = const.combustion_range_of_planets_from_sun_while_in_retrogade[idx] if p_id in retro_planets else const.combustion_range_of_planets_from_sun[idx]
        else:
            combusion_limit = 8.0
        abs_lon = (zod * 30) + lon
        deb_lon = (DEEP_EXALT[p_id] + 180) % 360
        dist = abs(abs_lon - deb_lon)
        if dist > 180: dist = 360 - dist
        # Base Rays
        rays = (dist / 180.0) * MAX_RAYS[p_id]
        # MULTIPLIERS (As required by BPHS for "Real" Rashmi Dasa)
        d9_zod = next(z for pid, (z, l) in d9_pos if pid == p_id)
        if zod == EXALT_SIGNS[p_id]: 
            rays *= 2.0  # Exaltation Sign multiplier
        if zod == d9_zod: 
            rays *= 2.0  # Vargottama multiplier (can stack with Exaltation)
        elif zod == OWNERS.get(zod): 
            rays *= (4.0/3.0) # Own Sign multiplier (4/3)
        # REDUCTIONS
        if p_id != 0 and abs(abs_lon - sun_abs_lon) < combusion_limit:
            rays *= 0.5 # Combustion reduction
        planet_rays[p_id] = round(rays, 8)
    total_rays = sum(planet_rays.values())
    # --- 4. Determine Sequence Order & Balance ---
    balance_factor = 1.0
    if dhasa_method == const.RASHMI_TYPE.BPHS_HIGHEST_RAY:
        # BPHS: Highest Strength/Rays Starts
        order = sorted(planet_rays.keys(), key=lambda x: planet_rays[x], reverse=True)
    elif dhasa_method == const.RASHMI_TYPE.NATURAL_ORDER:
        # Natural Naisargika Order (Sun to Saturn)
        order = const.SUN_TO_SATURN
    elif dhasa_method == const.RASHMI_TYPE.VIMSOTTARI_ORDER:
        # Vimshottari Hybrid
        moon_z, moon_l = next(pos for p_id, pos in d1_pos if p_id == 1)
        moon_abs_lon = (moon_z * 30) + moon_l
        nak_val = moon_abs_lon / (360/27)
        # Determining start lord using your seed_star argument
        start_lord = VIM_LIST[(int(nak_val) - vimsottari_method_seed_star + 3) % len(VIM_LIST)]
        # Build order using your next_adhipati API
        order = [start_lord]
        for _ in range(len(VIM_LIST) - 1):
            order.append(vimsottari_next_adhipati(order[-1]))
        # Filter Rahu/Ketu as they have 0 rays
        order = [p for p in order if p in planet_rays and planet_rays[p] > 0]
        # Calculate Balance from Nakshatra percentage
        balance_factor = 1.0 - (nak_val - int(nak_val))
    # --- 5. Recursive Engine ---
    results = []
    total_duration_years = 0.0
    jd_tracker = jd_start

    def recurse_dasa(current_depth, parent_duration, lords_list, is_first_maha):
        nonlocal jd_tracker, total_duration_years
        
        for i, p_id in enumerate(order):
            if total_duration_years >= TARGET_SPAN: return 
            if current_depth == 1:
                duration = planet_rays.get(p_id, 0)
                # Apply balance factor only to the first lord in the first cycle
                if is_first_maha and i == 0:
                    duration *= balance_factor
            else:
                duration = parent_duration * (planet_rays.get(p_id, 0) / total_rays)
            if duration <= 0: continue
            new_lords = lords_list + [p_id]
            if current_depth == dhasa_level_index:
                y, m, d, fh = utils.jd_to_gregorian(jd_tracker)
                durn= round(duration,dhasa_level_index+1) if round_duration else duration
                results.append([new_lords, (y, m, d, fh), durn])
                jd_tracker += (duration * ONE_YEAR_DAYS)
                total_duration_years += duration
            else:
                recurse_dasa(current_depth + 1, duration, new_lords, False)
    # --- 6. Cycle Execution ---
    cycles = 0
    while total_duration_years < TARGET_SPAN and cycles < max_cycles:
        recurse_dasa(1, None, [], (cycles == 0))
        cycles += 1
        if total_rays <= 0: break 
    return results
def rashmi_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float years (optional)
    parent_end=None,             # (Y, M, D, fractional_hour) (optional)
    *,
    jd_at_dob,
    place,
    # REQUIRED knobs (explicit, matching base defaults):
    dhasa_method: int = const.RASHMI_TYPE.BPHS_HIGHEST_RAY,                    # 1=Highest Rays (BPHS), 2=Natural, 3=Vimshottari Hybrid
    chart_method: int = 1,
    navamsa_chart_method: int = 1,
    vimsottari_method_seed_star: int = 3,
    use_real_combusion_limits: bool = True,
    divisional_chart_factor: int = 1,
    years: int = 1, months: int = 1, sixty_hours: int = 1,
    **kwargs
):
    """
    Rāśmi Daśā — return ONLY the immediate (p -> p+1) children for the given parent span.

    Uses the same 'order' and 'planet_rays' as your base:
      • Anchor time = drik.next_solar_date(jd_at_dob, place, years, months, sixty_hours)
      • d1 and d9 computed there; rays built with exaltation/vargottama/own-sign multipliers
        and combustion reduction; order depends on dhasa_method.
      • Deeper levels use proportional rule: child_years = parent_years * (rays_i / total_rays)
      • NOTE: The 'balance_factor' is applied by your base ONLY to the first Mahā; it is NOT
        used inside immediate children.
    Returns:
      [ (lords_tuple_with_child), child_start_tuple, child_end_tuple ]
    """
    # ---- normalize lords path
    if isinstance(parent_lords, int):
        path = (parent_lords,)
    elif isinstance(parent_lords, (list, tuple)) and parent_lords:
        path = tuple(parent_lords)
    else:
        raise ValueError("parent_lords must be int or non-empty tuple/list of ints")

    # ---- canonical tuple <-> JD
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    # ---- resolve parent span
    start_jd = _tuple_to_jd(parent_start)
    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration (years) or parent_end (tuple).")

    ONE_YEAR_DAYS = 365.242199  # match your base
    if parent_end is None:
        parent_years = float(parent_duration)
        end_jd = start_jd + parent_years * ONE_YEAR_DAYS
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_years = (end_jd - start_jd) / ONE_YEAR_DAYS

    if end_jd <= start_jd:
        return []

    # ---- compute rays & order at the *anchor* (same as base)
    jd_start = drik.next_solar_date(jd_at_dob, place, years, months, sixty_hours)

    d1_pos = charts.divisional_chart(jd_start, place, divisional_chart_factor, chart_method=chart_method)
    d9_pos = charts.divisional_chart(jd_start, place, 9, chart_method=navamsa_chart_method)

    # Extract Sun abs lon and retro list (for combustion)
    sun_z, sun_l = next(pos for pid, pos in d1_pos if pid == 0)
    sun_abs_lon = (sun_z * 30) + sun_l
    retro_planets = drik.planets_in_retrograde(jd_start, place)

    # Canonical tables (copy of your base for consistency)
    MAX_RAYS = {0: 10, 1: 9, 2: 5, 3: 5, 4: 7, 5: 16, 6: 4}
    DEEP_EXALT = {0: 10, 1: 33, 2: 298, 3: 165, 4: 95, 5: 357, 6: 200}
    EXALT_SIGNS = {0: 0, 1: 1, 2: 9, 3: 5, 4: 3, 5: 11, 6: 6}
    OWNERS = {0: 2, 1: 5, 2: 3, 3: 1, 4: 0, 5: 3, 6: 5, 7: 2, 8: 4, 9: 6, 10: 6, 11: 4}
    VIM_LIST = const.vimsottari_adhipati_list

    planet_rays = {}
    for p_id, (zod, lon) in d1_pos[const.SUN_ID + 1:const._pp_count_upto_saturn]:  # Sun..Saturn only
        idx = p_id - 1
        if use_real_combusion_limits:
            comb_limit = (const.combustion_range_of_planets_from_sun_while_in_retrogade[idx]
                          if p_id in retro_planets else const.combustion_range_of_planets_from_sun[idx])
        else:
            comb_limit = 8.0
        abs_lon = (zod * 30) + lon
        deb_lon = (DEEP_EXALT[p_id] + 180) % 360
        dist = abs(abs_lon - deb_lon)
        if dist > 180: dist = 360 - dist

        # Base rays
        rays = (dist / 180.0) * MAX_RAYS[p_id]

        # Multipliers: Exaltation, Vargottama, Own sign (as in your base)
        d9_zod = next(z for pid, (z, l) in d9_pos if pid == p_id)
        if zod == EXALT_SIGNS[p_id]:
            rays *= 2.0
        if zod == d9_zod:
            rays *= 2.0
        elif zod == OWNERS.get(zod):
            rays *= (4.0 / 3.0)

        # Combustion reduction
        if p_id != 0 and abs(abs_lon - sun_abs_lon) < comb_limit:
            rays *= 0.5

        planet_rays[p_id] = max(0.0, float(round(rays, 8)))

    total_rays = sum(planet_rays.values())

    # Order per method
    if dhasa_method == 1:
        order = sorted(planet_rays.keys(), key=lambda x: planet_rays[x], reverse=True)
    elif dhasa_method == 2:
        order = list(const.SUN_TO_SATURN)
    else:
        # Vimśottari hybrid
        moon_z, moon_l = next(pos for pid, pos in d1_pos if pid == 1)
        moon_abs_lon = (moon_z * 30) + moon_l
        nak_val = moon_abs_lon / (360.0 / 27.0)
        start_lord = VIM_LIST[(int(nak_val) - vimsottari_method_seed_star + 3) % len(VIM_LIST)]
        seq = [start_lord]
        for _ in range(len(VIM_LIST) - 1):
            seq.append(vimsottari_next_adhipati(seq[-1]))
        # filter to 0..6 with positive rays
        order = [p for p in seq if p in planet_rays and planet_rays[p] > 0.0]

    if not order or total_rays <= 0.0:
        return []

    # ---- proportional tiling inside the parent (deeper-level rule)
    children = []
    jd_cursor = start_jd
    for i, p_id in enumerate(order):
        share = planet_rays[p_id] / total_rays
        child_years = parent_years * share
        if i == len(order) - 1:
            child_end = end_jd
        else:
            child_end = jd_cursor + child_years * ONE_YEAR_DAYS
        children.append([
            path + (p_id,),
            _jd_to_tuple(jd_cursor),
            _jd_to_tuple(child_end),
        ])
        jd_cursor = child_end
        if jd_cursor >= end_jd:
            break

    if children:
        children[-1][2] = _jd_to_tuple(end_jd)

    return children
def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
    # Required Rashmi knobs (explicit):
    dhasa_method: int = 1,                  # 1=Highest Rays, 2=Natural, 3=Vimśottarī Hybrid
    chart_method: int = 1,
    navamsa_chart_method: int = 1,
    vimsottari_method_seed_star: int = 3,
    use_real_combusion_limits: bool = True,
    divisional_chart_factor: int = 1,
    years: int = 1, months: int = 1, sixty_hours: int = 1,
    max_cycles: int = 8,
    round_duration: bool = False,           # runner uses exact start/end
    **kwargs
):
    """
    Rāśmi Daśā — narrow Mahā -> … -> target depth and return the full running ladder:

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
        lo = int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY)
        hi = int(const.MAHA_DHASA_DEPTH.DEHA)
        return min(hi, max(lo, depth))

    target_depth = _normalize_depth(dhasa_level_index)

    # ---- tuple -> JD & zero-length helpers
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _is_zero_length(s, e, eps_seconds=1.0):
        return (_tuple_to_jd(e) - _tuple_to_jd(s)) * 86400.0 <= eps_seconds

    def _to_utils_periods(children_rows, parent_end_tuple, eps_seconds=1.0):
        """
        children_rows: [ [lords_tuple, start_tuple, end_tuple], ... ]
        Returns: list of (lords_tuple, start_tuple) + sentinel(parent_end_tuple),
        filtering zero-length rows and enforcing strictly increasing starts.
        """
        filtered = [r for r in children_rows if not _is_zero_length(r[1], r[2], eps_seconds=eps_seconds)]
        if not filtered:
            return []
        filtered.sort(key=lambda r: _tuple_to_jd(r[1]))
        proj, prev = [], None
        for lords, st, _en in filtered:
            sjd = _tuple_to_jd(st)
            if prev is None or sjd > prev:
                proj.append((lords, st)); prev = sjd
        proj.append((proj[-1][0], parent_end_tuple))  # sentinel
        return proj

    def _as_tuple_lords(x):
        return (x,) if isinstance(x, int) else tuple(x)

    running_all = []

    # ---- derive dob/tob for the base L1 generator
    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)

    # ---- Level 1: Mahā via your base function
    maha_rows = get_rashmi_dhasa_bhukthi(
        dob, tob, place,
        divisional_chart_factor=divisional_chart_factor,
        years=years, months=months, sixty_hours=sixty_hours,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        dhasa_method=dhasa_method,
        chart_method=chart_method,
        navamsa_chart_method=navamsa_chart_method,
        vimsottari_method_seed_star=vimsottari_method_seed_star,
        max_cycles=max_cycles,
        use_real_combusion_limits=use_real_combusion_limits,
        round_duration=False,
    )
    # normalize for utils: (lords_tuple, start_tuple)
    maha_for_utils = []
    for row in maha_rows:
        # base returns: [lords_list, (y,m,d,fh), duration]
        lords_any, start_t = row[0], row[1]
        lords_tuple = tuple(lords_any) if isinstance(lords_any, list) else _as_tuple_lords(lords_any)
        maha_for_utils.append((lords_tuple, start_t))

    # Running Mahā
    rd1 = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    lords1 = _as_tuple_lords(rd1[0])
    running = [lords1, rd1[1], rd1[2]]
    running_all.append(running)

    if target_depth == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return running_all

    # ---- Levels 2..target (expand only the running parent each step)
    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        children = rashmi_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            dhasa_method=dhasa_method,
            chart_method=chart_method,
            navamsa_chart_method=navamsa_chart_method,
            vimsottari_method_seed_star=vimsottari_method_seed_star,
            use_real_combusion_limits=use_real_combusion_limits,
            divisional_chart_factor=divisional_chart_factor,
            years=years, months=months, sixty_hours=sixty_hours,
            **kwargs
        )

        if not children:
            # If no children can be produced (all rays zero), freeze at this depth.
            running_all.append([parent_lords + (parent_lords[-1],), parent_end, parent_end])
            break

        periods_for_utils = _to_utils_periods(children, parent_end_tuple=parent_end)
        if not periods_for_utils:
            # all zero-length → boundary selection
            last = children[-1]
            running = [last[0], last[1], last[1]]
        else:
            rdk = utils.get_running_dhasa_for_given_date(current_jd, periods_for_utils)
            running = [_as_tuple_lords(rdk[0]), rdk[1], rdk[2]]

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
    import time
    start_time = time.time()
    print("Dehā        :", get_running_dhasa_for_given_date(current_jd, jd_at_dob, place, dhasa_level_index=6))
    print('new method elapsed time',time.time()-start_time)
    start_time = time.time()
    ad = get_rashmi_dhasa_bhukthi(dob,tob, place,dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,const.MAHA_DHASA_DEPTH.DEHA,
                                                               extract_running_period_for_all_levels=True,
                                                               dhasa_cycle_count=8))
    print('old method elapsed time',time.time()-start_time)
    exit()
    utils.set_language('en')
    dob = drik.Date(1996,12,7); tob = (10,34,0); place = drik.Place('Chennai,India',13.03862,80.261818,5.5)
    rd = get_rashmi_dhasa_bhukthi(dob, tob, place,dhasa_level_index=2,dhasa_method=1,use_real_combusion_limits=True)
    for row in rd:
        print(row)
    