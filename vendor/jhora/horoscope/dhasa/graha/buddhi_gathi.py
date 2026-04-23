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
from jhora import utils, const
from jhora.horoscope.chart import charts
from jhora.panchanga import drik

def get_dhasa_bhukthi(
    dob,
    tob,
    place,
    divisional_chart_factor=1,
    chart_method=1,
    years=1,
    months=1,
    sixty_hours=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,   # 1..6 (default=2 to include Antara like before)
    max_cycles=2,
    round_duration=True
):
    """
    Buddhi Gathi dasha expansions to the requested depth, controlled solely by `dhasa_level_index`.

    Parameters
    ----------
    dob : (year, month, day)
    tob : (hour, minute, second)
    place : Place
    divisional_chart_factor : int, default=1
        1=Rasi, 9=Navamsa, ...
    chart_method : int, default=1
    years, months, sixty_hours : int
        Passed to charts.divisional_chart().
    dhasa_level_index : int, default=2
        Tree depth (L1..L6):
          1 = Maha only (no Antara)
          2 = + Antara (Bhukthi)
          3 = + Pratyantara
          4 = + Sookshma
          5 = + Prana
          6 = + Deha-antara
        NOTE: Caller must pass a valid value in 1..6.
    max_cycles : int, default=2
        Iterate base progression cycles.

    Returns
    -------
    list of tuples
        Tuple shape depends on depth:
          L1: (l1, start, duration_years)
          L2: (l1, l2, start, duration_years)
          L3: (l1, l2, l3, start, duration_years)
          L4: (l1, l2, l3, l4, start, duration_years)
          L5: (l1, l2, l3, l4, l5, start, duration_years)
          L6: (l1, l2, l3, l4, l5, l6, start, duration_years)

    Notes
    -----
    * Equal subdivision at each depth: sub_duration = parent_duration / d_len
    * Rotation at every depth from the current lord’s index in the base sequence
    * Life-span guard using const.human_life_span_for_narayana_dhasa
    """

    # --- Validate depth (no normalization/clamping) -------------------------------
    if not (const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY <= dhasa_level_index <= const.MAHA_DHASA_DEPTH.DEHA):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha-antara).")

    max_level = dhasa_level_index  # L1=Maha ... L6=Deha-antara

    jd_at_dob = utils.julian_day_number(dob, tob)
    planet_positions = charts.divisional_chart(
        jd_at_dob,
        place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        years=years,
        months=months,
        sixty_hours=sixty_hours,
    )[:const._pp_count_upto_ketu]
    h_to_p = utils.get_house_planet_list_from_planet_positions(planet_positions[1:const._pp_count_upto_ketu])
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    planet_dict = {int(p): p_long for p, (_, p_long) in planet_positions[1:const._pp_count_upto_ketu]}
    asc_house = p_to_h[const._ascendant_symbol]

    dhasa_progression = []
    h1 = 0
    for h in range(12):
        hs = (asc_house + const.HOUSE_4 + h) % 12
        if h_to_p[hs] == '':
            continue
        planets = list(map(int, h_to_p[hs].split('/')))
        # Sort planets in this house by descending longitude
        d1 = {p: l for p, l in planet_dict.items() if p in planets}
        pl_new = [p for (p, _) in sorted(d1.items(), key=lambda item: item[1], reverse=True)]
        for pl in pl_new:
            durn = ((asc_house + h1 + 12) - p_to_h[pl]) % 12
            # If planet is exalted add +1  V4.6.3
            if const.house_strengths_of_planets[pl][p_to_h[pl]]==const._EXALTED_UCCHAM: durn += 1 
            # If planet is denilitated minus -1  V4.6.3
            if const.house_strengths_of_planets[pl][p_to_h[pl]]==const._DEBILITATED_NEECHAM: durn -= 1 
            dhasa_progression.append((pl, durn))
            h1 += 1

    d_len = len(dhasa_progression)
    if d_len == 0:
        return []

    base_order = [pl for (pl, _) in dhasa_progression]
    index_of = {pl: i for i, pl in enumerate(base_order)}
    lifespan_years = const.human_life_span_for_narayana_dhasa

    # --- Recursive subdivision engine --------------------------------------------
    def _recurse(level, start_index, start_jd_local, duration_years, prefix, rows_out):
        """
        level: current tree level (2..max_level). prefix holds L1..(level-1) lords.
        start_index: rotation start index in base_order for this node
        """
        sub_len = d_len
        if sub_len == 0:
            return

        sub_duration = duration_years / sub_len
        durn = round(sub_duration,dhasa_level_index+1) if round_duration else sub_duration
        if level < max_level:
            jd_cursor = start_jd_local
            for k in range(sub_len):
                lord = base_order[(start_index + k) % sub_len]
                next_start_index = index_of[lord]
                _recurse(level + 1, next_start_index, jd_cursor, sub_duration, prefix + (lord,), rows_out)
                jd_cursor += sub_duration * const.sidereal_year
        else:
            # Leaf: emit rows at the deepest requested level
            jd_cursor = start_jd_local
            for k in range(sub_len):
                lord = base_order[(start_index + k) % sub_len]
                row_start = utils.jd_to_gregorian(jd_cursor)
                row = (prefix + (lord,), row_start, durn)
                rows_out.append(row)
                jd_cursor += sub_duration * const.sidereal_year

    # --- Iterate Maha-dashas & expand to requested depth --------------------------
    dhasa_bhukthi_info = []
    start_jd = jd_at_dob
    total_dhasa_duration = 0

    cycles_done = 0
    outer_break = False
    while cycles_done < max_cycles and not outer_break:
        for dhasa_idx in range(d_len):
            dhasa_lord, dhasa_duration = dhasa_progression[dhasa_idx]
            durn = round(dhasa_duration, dhasa_level_index+1) if round_duration else dhasa_duration
            if dhasa_duration <= 0:
                continue

            if max_level == 1:
                # Maha only (keep original tuple & duration type)
                dhasa_start = utils.jd_to_gregorian(start_jd)
                row = ((dhasa_lord,), dhasa_start, durn)
                dhasa_bhukthi_info.append(row)
            else:
                rows_out = []
                start_index = index_of[dhasa_lord]
                _recurse(
                    level=2,
                    start_index=start_index,
                    start_jd_local=start_jd,
                    duration_years=dhasa_duration,
                    prefix=(dhasa_lord,),
                    rows_out=rows_out
                )
                dhasa_bhukthi_info.extend(rows_out)

            # advance to next maha
            start_jd += dhasa_duration * const.sidereal_year
            total_dhasa_duration += dhasa_duration

            if total_dhasa_duration >= lifespan_years:
                outer_break = True
                break
        cycles_done += 1

    return dhasa_bhukthi_info
def buddhigathi_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float years (optional)
    parent_end=None,             # (Y, M, D, fractional_hour) (optional)
    *,
    dob,
    tob,
    place,
    divisional_chart_factor=1,
    chart_method=1,
    years=1,
    months=1,
    sixty_hours=1,
):
    """
    Buddhi Gathi – return ONLY the immediate (p->p+1) children under a given parent span.

    Output rows:
        [ (lords_tuple_with_child), child_start_tuple, child_end_tuple ]

    Rules (matches your engine):
      • Equal subdivision at every sub-level: child_years = parent_years / d_len
      • Child order is base_order rotated so it starts at the parent_lord
      • base_order is built from birth varga chart exactly as in get_dhasa_bhukthi()
      • The last child end is forced to parent_end (tiling closure)
    """
    # ---- normalize lords path
    if isinstance(parent_lords, int):
        path = (parent_lords,)
    elif isinstance(parent_lords, (list, tuple)):
        if len(parent_lords) == 0:
            raise ValueError("parent_lords cannot be empty")
        path = tuple(parent_lords)
    else:
        raise TypeError("parent_lords must be int or tuple/list of ints")

    parent_lord = path[-1]

    # ---- tuple <-> JD helpers (canonical)
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    # ---- parent start/end in JD
    start_jd = _tuple_to_jd(parent_start)
    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration (years) or parent_end (tuple).")

    if parent_end is None:
        parent_years = float(parent_duration)
        end_jd = start_jd + parent_years * const.sidereal_year
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_years = (end_jd - start_jd) / const.sidereal_year

    if end_jd <= start_jd:
        # Parent is instantaneous; return empty list (caller may treat as zero-length)
        return []

    # ---- Build base_order exactly like get_dhasa_bhukthi -----------------
    jd_at_dob = utils.julian_day_number(dob, tob)
    planet_positions = charts.divisional_chart(
        jd_at_dob,
        place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        years=years,
        months=months,
        sixty_hours=sixty_hours,
    )[:const._pp_count_upto_ketu]

    h_to_p = utils.get_house_planet_list_from_planet_positions(
        planet_positions[1:const._pp_count_upto_ketu]
    )
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    planet_dict = {int(p): p_long for p, (_, p_long) in planet_positions[1:const._pp_count_upto_ketu]}
    asc_house = p_to_h[const._ascendant_symbol]

    dhasa_progression = []
    h1 = 0
    for h in range(12):
        hs = (asc_house + const.HOUSE_4 + h) % 12
        if h_to_p[hs] == '':
            continue
        planets = list(map(int, h_to_p[hs].split('/')))
        # Sort by descending longitude
        d1 = {p: l for p, l in planet_dict.items() if p in planets}
        pl_new = [p for (p, _) in sorted(d1.items(), key=lambda item: item[1], reverse=True)]
        for pl in pl_new:
            durn = ((asc_house + h1 + 12) - p_to_h[pl]) % 12
            # exalted +1
            if const.house_strengths_of_planets[pl][p_to_h[pl]] == const._EXALTED_UCCHAM:
                durn += 1
            # debilitated -1
            if const.house_strengths_of_planets[pl][p_to_h[pl]] == const._DEBILITATED_NEECHAM:
                durn -= 1
            dhasa_progression.append((pl, durn))
            h1 += 1

    d_len = len(dhasa_progression)
    if d_len == 0:
        return []

    base_order = [pl for (pl, _) in dhasa_progression]
    index_of = {pl: i for i, pl in enumerate(base_order)}

    # ---- Equal split & rotation by parent_lord ---------------------------
    sub_len = d_len
    sub_years = parent_years / sub_len  # equal split at this level

    start_index = index_of.get(parent_lord, 0)
    rotated = base_order[start_index:] + base_order[:start_index]

    # ---- Tile children inside the parent --------------------------------
    children = []
    cursor = start_jd
    for i, child_lord in enumerate(rotated):
        # Last child ends exactly at parent_end
        if i == sub_len - 1:
            child_end = end_jd
        else:
            child_end = cursor + sub_years * const.sidereal_year

        children.append([
            path + (child_lord,),
            _jd_to_tuple(cursor),
            _jd_to_tuple(child_end),
        ])
        cursor = child_end
        if cursor >= end_jd:
            break

    # Force numeric closure
    if children:
        children[-1][2] = _jd_to_tuple(end_jd)

    return children
def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
    *,
    divisional_chart_factor=1,
    chart_method=1,
    years=1,
    months=1,
    sixty_hours=1,
):
    """
    Buddhi Gathi – narrow Mahā → … → target depth and return the full ladder:

        [
          [(l1,),              start1, end1],
          [(l1,l2),            start2, end2],
          [(l1,l2,l3),         start3, end3],
          [(l1,l2,l3,l4),      start4, end4],
          [(l1,l2,l3,l4,l5),   start5, end5],
          [(l1,l2,l3,l4,l5,l6),start6, end6],
        ]
    """
    y,m,d,fh = utils.jd_to_gregorian(jd_at_dob); dob = drik.Date(y,m,d); tob=(fh,0,0)
    # ---- helpers
    def _as_tuple_lords(x):
        return (x,) if isinstance(x, int) else tuple(x)

    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _is_zero_length(s, e, eps_seconds=1.0):
        return (_tuple_to_jd(e) - _tuple_to_jd(s)) * 86400.0 <= eps_seconds

    def _to_utils_periods(children_rows, parent_end_tuple, eps_seconds=1.0):
        """
        children_rows: [ [lords_tuple, start_tuple, end_tuple], ... ]
        Returns: list of (lords_tuple, start_tuple) + sentinel (any_lords, parent_end_tuple),
        filtering zero-length rows and enforcing strictly increasing starts.
        """
        # filter zero-length
        filtered = [r for r in children_rows if not _is_zero_length(r[1], r[2], eps_seconds=eps_seconds)]
        if not filtered:
            return []

        filtered.sort(key=lambda r: _tuple_to_jd(r[1]))

        proj = []
        prev = None
        for lords, st, _en in filtered:
            sjd = _tuple_to_jd(st)
            if prev is None or sjd > prev:
                proj.append((lords, st))
                prev = sjd
            # else skip equal starts

        # sentinel
        proj.append((proj[-1][0], parent_end_tuple))
        return proj

    # ---- clamp depth
    try:
        target_depth = int(dhasa_level_index)
    except Exception:
        target_depth = const.MAHA_DHASA_DEPTH.DEHA
    target_depth = max(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY, min(const.MAHA_DHASA_DEPTH.DEHA, target_depth))

    # ---- Level 1: Mahā using your base generator
    maha_rows = get_dhasa_bhukthi(
        dob,
        tob,
        place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        years=years,
        months=months,
        sixty_hours=sixty_hours,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,        # Mahā only
        max_cycles=2,               # keep default; if you need 1, pass explicitly
        round_duration=False,       # runner uses start/end; round not required
    )

    # normalize for utils: (lords_tuple, start_tuple)
    maha_for_utils = []
    for row in maha_rows:
        # row: ((lord,), start, duration_years)
        lords_any, start_t = row[0], row[1]
        maha_for_utils.append((_as_tuple_lords(lords_any), start_t))

    running_all = []

    # Running Mahā
    rd = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    lords = _as_tuple_lords(rd[0])
    running = [lords, rd[1], rd[2]]
    running_all.append(running)

    if target_depth == 1:
        return running_all

    # ---- Levels 2..target
    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        # Expand only this parent (equal split + rotated base order)
        children = buddhigathi_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            dob=dob,
            tob=tob,
            place=place,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
            years=years,
            months=months,
            sixty_hours=sixty_hours,
        )
        if not children:
            # All zero at this level or parent instantaneous; return zero-length at parent_end
            running = [parent_lords + (parent_lords[-1],), parent_end, parent_end]
            running_all.append(running)
            continue

        # Prepare for utils: (lords, start) + sentinel(parent_end)
        periods_for_utils = _to_utils_periods(children, parent_end_tuple=parent_end)
        if not periods_for_utils:
            # nothing to select (e.g., all zero-duration)
            last = children[-1]
            running = [last[0], last[1], last[1]]
        else:
            rd_k = utils.get_running_dhasa_for_given_date(current_jd, periods_for_utils)
            lords_k = _as_tuple_lords(rd_k[0])
            running = [lords_k, rd_k[1], rd_k[2]]

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
    print("Dehā        :", get_running_dhasa_for_given_date(current_jd, jd_at_dob, place,
                                                            dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA))
    print('new method elapsed time',time.time()-start_time)
    start_time = time.time()
    ad = get_dhasa_bhukthi(dob,tob, place,dhasa_level_index=6)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad, const.MAHA_DHASA_DEPTH.DEHA,
                                                               extract_running_period_for_all_levels=True,
                                                               dhasa_cycle_count=2))
    print('old method elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = False
    pvr_tests.buddhi_gathi_test()