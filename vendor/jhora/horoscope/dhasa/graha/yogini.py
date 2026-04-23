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
from jhora.horoscope.chart import charts,sphuta
year_duration = const.sidereal_year
""" dhasa_adhipathi_dict = {planet:[(star list), dhasa duration] } """
seed_lord = 0
_seed_star = 1
dhasa_adhipathi_list = {1:1,0:2,4:3,2:4,3:5,6:6,5:7,7:8} # Total 36 years
dhasa_adhipathi_dict = {1: [6,14,22,], 0: [7,15,23], 4: [8,16,24], 2: [1,9,17,25], 3: [2,10,18,26], 6: [3,11,19,27], 5: [4,12,20], 7: [5,13,21]}
count_direction = 1 # 1> base star to birth star zodiac -1> base star to birth star antizodiac
def _next_adhipati(lord,dir=1):
    """Returns next lord after `lord` in the adhipati_list"""
    current = list(dhasa_adhipathi_list.keys()).index(lord)
    next_lord = list(dhasa_adhipathi_list.keys())[((current + dir) % len(dhasa_adhipathi_list))]
    return next_lord
def _maha_dhasa(nak,seed_star=_seed_star):
    return [ (_dhasa_lord, dhasa_adhipathi_list[_dhasa_lord]) 
            for _dhasa_lord,_star_list in dhasa_adhipathi_dict.items() 
                if ((nak-seed_star))%27+1 in _star_list][0]
def _antardhasa(lord,antardhasa_option=1):
    if antardhasa_option in [3,4]:
        lord = _next_adhipati(lord, dir=1) 
    elif antardhasa_option in [5,6]:
        lord = _next_adhipati(lord, dir=-1) 
    dir = 1 if antardhasa_option in [1,3,5] else -1
    _bhukthis = []
    for _ in range(len(dhasa_adhipathi_list)):
        _bhukthis.append(lord)
        lord = _next_adhipati(lord,dir)
    return _bhukthis
def _dhasa_start(jd,place,divisional_chart_factor=1,chart_method=1,star_position_from_moon=1,seed_star=_seed_star,
                 dhasa_starting_planet=1):
    one_star = (360 / 27.)        # 27 nakshatras span 360°
    planet_long = charts.get_chart_element_longitude(jd, place, divisional_chart_factor, chart_method,
                                        star_position_from_moon, dhasa_starting_planet)
    nak = int(planet_long / one_star); rem = (planet_long - nak * one_star)
    lord,res = _maha_dhasa(nak+1,seed_star)          # ruler of current nakshatra
    period = res
    period_elapsed = rem / one_star * period # years
    period_elapsed *= year_duration        # days
    start_date = jd - period_elapsed      # so many days before current day
    #print(nak+1,lord,utils.jd_to_gregorian(start_date),rem/one_star,period_elapsed)
    return [lord, start_date,res]

def get_dhasa_bhukthi(
    dob, tob, place,
    use_tribhagi_variation=False,
    star_position_from_moon=1,
    divisional_chart_factor=1,
    chart_method=1,
    seed_star=_seed_star,
    dhasa_starting_planet=1,
    antardhasa_option=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,  # 1..6 (1=Maha only, 2=+Antara, 3..6 deeper)
    round_duration=True
):
    """
    Returns a list of rows, each row shaped as:
        [(lords_tuple), start_tuple, duration_years]

    Examples by depth:
      L1 -> [(l1,), start, dur]
      L2 -> [(l1, l2), start, dur]
      L3 -> [(l1, l2, l3), start, dur]
      L4 -> [(l1, l2, l3, l4), start, dur]
      L5 -> [(l1, l2, l3, l4, l5), start, dur]
      L6 -> [(l1, l2, l3, l4, l5, l6), start, dur]

    Notes
    -----
    - Durations at lower levels equal‑split the IMMEDIATE parent (your current logic).
    - Only the returned duration is rounded when round_duration=True; JD math uses full precision.
    - Tribhagi behavior: increases cycles (3 -> 9) but does not scale durations (kept as in your legacy).
    - Depends on: _dhasa_start, _antardhasa, _next_adhipati, dhasa_adhipathi_list, year_duration, utils.jd_to_gregorian
    """
    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha).")

    # ---- Tribhagi cycles (legacy behavior) -------------------------------------
    _dhasa_cycles = 3
    if use_tribhagi_variation:
        _dhasa_cycles = 9  # legacy: just increase cycles

    # ---- Birth JD and starting Maha --------------------------------------------
    jd = utils.julian_day_number(dob, tob)
    dhasa_lord, start_jd, _ = _dhasa_start(
        jd, place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        star_position_from_moon=star_position_from_moon,
        seed_star=seed_star,
        dhasa_starting_planet=dhasa_starting_planet
    )

    # ---- Helpers ----------------------------------------------------------------
    def _children_of(parent_lord):
        """Ordered sequence of immediate children under parent_lord."""
        return _antardhasa(parent_lord, antardhasa_option)

    def _emit_row(lords_tuple, start_jd_value, duration_years):
        start_tuple = utils.jd_to_gregorian(start_jd_value)
        dur_out = round(duration_years, dhasa_level_index) if round_duration else duration_years
        rows.append([lords_tuple, start_tuple, dur_out])

    def _recurse(level, parent_lord, parent_start_jd, parent_years, prefix_tuple):
        """
        Generic equal-split recursion for levels >= 3.

        Invariant:
          - prefix_tuple holds lords up to (level - 1).
          - If level < target: descend to build next level.
          - If level == target: emit children of parent (depth == target).

        This yields exactly `dhasa_level_index` lords per row.
        """
        bhukthis = _children_of(parent_lord)
        if not bhukthis:
            raise ValueError(f"No children returned by _antardhasa for lord={parent_lord} at level={level}")

        n = len(bhukthis)
        child_years_unrounded = parent_years / n
        jd_cursor = parent_start_jd

        if level < dhasa_level_index:
            # Build the next level for each child
            for child_lord in bhukthis:
                _recurse(level + 1, child_lord, jd_cursor, child_years_unrounded, prefix_tuple + (child_lord,))
                jd_cursor += child_years_unrounded * year_duration
        else:
            # Leaf: emit rows for children at the requested depth
            for child_lord in bhukthis:
                _emit_row(prefix_tuple + (child_lord,), jd_cursor, child_years_unrounded)
                jd_cursor += child_years_unrounded * year_duration

    rows = []

    # ---- Main expansion over cycles & Maha sequence -----------------------------
    for _ in range(_dhasa_cycles):
        for _ in range(len(dhasa_adhipathi_list)):
            maha_years_unrounded = float(dhasa_adhipathi_list[dhasa_lord])

            if dhasa_level_index == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
                # L1: single maha segment
                _emit_row((dhasa_lord,), start_jd, maha_years_unrounded)
                start_jd += maha_years_unrounded * year_duration

            elif dhasa_level_index == const.MAHA_DHASA_DEPTH.ANTARA:
                # L2: equal-split maha among antara children
                bhukthis = _children_of(dhasa_lord)
                if not bhukthis:
                    raise ValueError(f"No L2 children for maha lord={dhasa_lord}")
                n = len(bhukthis)
                child_years_unrounded = maha_years_unrounded / n
                jd_cursor = start_jd
                for blord in bhukthis:
                    _emit_row((dhasa_lord, blord), jd_cursor, child_years_unrounded)
                    jd_cursor += child_years_unrounded * year_duration
                start_jd += maha_years_unrounded * year_duration

            else:
                # L3..L6: recurse from level=2 with prefix=(maha,)
                _recurse(
                    level=const.MAHA_DHASA_DEPTH.ANTARA,  # 2
                    parent_lord=dhasa_lord,
                    parent_start_jd=start_jd,
                    parent_years=maha_years_unrounded,
                    prefix_tuple=(dhasa_lord,)
                )
                start_jd += maha_years_unrounded * year_duration

            # Next Maha lord
            dhasa_lord = _next_adhipati(dhasa_lord)

    return rows

def nakshathra_dhasa_progression(
    jd_at_dob, place, jd_current,
    star_position_from_moon=1,
    use_tribhagi_variation=False,
    divisional_chart_factor=1,
    chart_method=1,
    seed_star=_seed_star,
    antardhasa_option=1,
    dhasa_starting_planet=1,
    dhasa_level_index = const.MAHA_DHASA_DEPTH.ANTARA,
    get_running_dhasa = True,
):
    y,m,d,fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y,m,d); tob = (fh,0,0)
    DLI = dhasa_level_index
    vd = get_dhasa_bhukthi(
        dob, tob, place,
        use_tribhagi_variation,
        star_position_from_moon,
        divisional_chart_factor,
        chart_method,
        seed_star,
        dhasa_starting_planet,
        antardhasa_option,
        dhasa_level_index=DLI)
    if get_running_dhasa: 
        vdc = utils.get_running_dhasa_for_given_date(jd_current, vd)
        print(vdc)
    jds = [utils.julian_day_number(drik.Date(y,m,d),(fh,0,0)) for _,(y,m,d,fh),_ in vd]
    mpl = utils.degrees_between_jds(jds, jd_at_dob, jd_current)
    planet_long = charts.get_chart_element_longitude(jd_at_dob, place, divisional_chart_factor, chart_method,
                                        star_position_from_moon, dhasa_starting_planet)

    birth_star_index = int((planet_long % 360.0) // utils.ONE_NAK)
    prog_long = utils.progressed_abs_long_general(jds, jd_current, birth_star_index,
                                                  dhasa_level_index=DLI,
                                                  total_lords_in_dhasa=len(dhasa_adhipathi_list))
    progression_correction = (prog_long - planet_long)%360
    if get_running_dhasa:
        return progression_correction, vdc
    else:
        return progression_correction
    #print(dhasa_starting_planet,'Progressed_longitude',prog_long,'correction',progression_correction)
    ppl = charts.get_nakshathra_dhasa_progression_longitudes(jd_at_dob, place, planet_progression_correction=progression_correction,
                                                             divisional_chart_factor=divisional_chart_factor,
                                                             chart_method=chart_method)
    return ppl
def yogini_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float years (one of duration or end must be provided)
    parent_end=None,             # (Y, M, D, fractional_hour)
    *,
    jd_at_dob,
    place,
    # REQUIRED knob (explicit, used by _antardhasa)
    antardhasa_option: int = 1,
    # Accepted for API parity (not needed by the tiler itself)
    star_position_from_moon=1,
    divisional_chart_factor=1,
    chart_method=1,
    seed_star=_seed_star,
    dhasa_starting_planet=1,
    use_tribhagi_variation=False,
    **kwargs
):
    """
    Yoginī — return ONLY the immediate (p -> p+1) children inside the given parent span.

    Matches your base get_dhasa_bhukthi():
      • Antara order at EVERY level via: _antardhasa(parent_lord, antardhasa_option)
      • Sama subdivision at this level: child_years = parent_years / n
      • Exact tiling within [parent_start, parent_end)

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
    parent_lord = path[-1]

    # ---- canonical tuple <-> JD helpers
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    # ---- resolve parent span
    start_jd = _tuple_to_jd(parent_start)
    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration (years) or parent_end (tuple).")

    YEAR_DAYS = const.sidereal_year  # same basis as your module's year_duration

    if parent_end is None:
        parent_years = float(parent_duration)
        end_jd = start_jd + parent_years * YEAR_DAYS
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_years = (end_jd - start_jd) / YEAR_DAYS

    if end_jd <= start_jd:
        return []  # instantaneous parent → nothing to tile

    # ---- child sequence via your antara rule
    def _children_of(pl):
        return list(_antardhasa(pl, antardhasa_option))

    child_lords = _children_of(parent_lord)
    if not child_lords:
        return []

    # ---- equal split at this level
    n = len(child_lords)
    child_years = parent_years / n

    # ---- tile children within parent [start, end)
    children = []
    cursor = start_jd
    for i, cl in enumerate(child_lords):
        if i == n - 1:
            child_end = end_jd
        else:
            child_end = cursor + child_years * YEAR_DAYS

        children.append([
            path + (cl,),
            _jd_to_tuple(cursor),
            _jd_to_tuple(child_end),
        ])
        cursor = child_end
        if cursor >= end_jd:
            break

    if children:
        children[-1][2] = _jd_to_tuple(end_jd)  # closure

    return children
def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
    *,
    # Forwarded to Yoginī base:
    use_tribhagi_variation: bool = False,
    star_position_from_moon: int = 1,
    divisional_chart_factor: int = 1,
    chart_method: int = 1,
    seed_star=_seed_star,
    dhasa_starting_planet: int = 1,
    antardhasa_option: int = 1,
    round_duration: bool = False,     # runner uses exact start/end
    **kwargs
):
    """
    Yoginī — narrow Mahā -> … -> target depth and return the full running ladder:

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
        for lords, st, _ in filtered:
            sjd = _tuple_to_jd(st)
            if prev is None or sjd > prev:
                proj.append((lords, st)); prev = sjd
        proj.append((proj[-1][0], parent_end_tuple))  # sentinel
        return proj

    def _as_tuple_lords(x):
        return (x,) if isinstance(x, int) else tuple(x)

    running_all = []

    # ---- derive dob,tob once for the base L1 generator
    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)

    # ---- Level 1: Mahā via your base Yoginī generator
    maha_rows = get_dhasa_bhukthi(
        dob, tob, place,
        use_tribhagi_variation=use_tribhagi_variation,
        star_position_from_moon=star_position_from_moon,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        seed_star=_seed_star,
        dhasa_starting_planet=dhasa_starting_planet,
        antardhasa_option=antardhasa_option,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        round_duration=False,
    )
    # normalize for utils: (lords_tuple, start_tuple)
    maha_for_utils = [(_as_tuple_lords(row[0]), row[1]) for row in maha_rows]

    # Running Mahā
    rd1 = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    running = [_as_tuple_lords(rd1[0]), rd1[1], rd1[2]]
    running_all.append(running)

    if target_depth == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return running_all

    # ---- Levels 2..target: expand only the running parent at each step
    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        children = yogini_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            antardhasa_option=antardhasa_option,
            star_position_from_moon=star_position_from_moon,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
            seed_star=seed_star,
            dhasa_starting_planet=dhasa_starting_planet,
            use_tribhagi_variation=use_tribhagi_variation,
            **kwargs
        )

        if not children:
            # represent as zero-length at parent_end
            running = [parent_lords + (parent_lords[-1],), parent_end, parent_end]
            running_all.append(running)
            break

        # utils selection with sentinel
        periods_for_utils = _to_utils_periods(children, parent_end_tuple=parent_end)
        if not periods_for_utils:
            # all zero-length → represent boundary
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
    print("Dehā        :", get_running_dhasa_for_given_date(current_jd, jd_at_dob, place,
                                                            dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA))
    print('new method elapsed time',time.time()-start_time)
    start_time = time.time()
    ad = get_dhasa_bhukthi(dob,tob, place,dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,const.MAHA_DHASA_DEPTH.DEHA,
                                                               extract_running_period_for_all_levels=True,
                                                               dhasa_cycle_count=3))
    print('old method elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.yogini_test()
    