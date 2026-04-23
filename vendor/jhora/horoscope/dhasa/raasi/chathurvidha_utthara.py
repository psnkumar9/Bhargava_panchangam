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
""" 
    Chaturvidha Uttara Dasha 
        Lagna Uttara Dasha → Start from Lagna (Ascendant Rashi) - Dhasa Method = 1
        Kendra Uttara Dasha → Start from strongest Kendra (1st, 4th, 7th, 10th house Rashi) - Dhasa Method = 2
        Trikona Uttara Dasha → Start from strongest Trikona (1st, 5th, 9th house Rashi) - Dhasa Method = 3
        Dasha Uttara Dasha → Start from Rashi with the strongest planetary influence - Dhasa Method = 4
"""
from jhora import const, utils
from jhora.panchanga import drik
from jhora.horoscope.chart import charts, house
def valid_methods_available_for_planet_positions(planet_positions):
    """
        It is possible the seed may be same for some/all of these methods
        This function will return unique method numbers in such case
    """
    asc_house = planet_positions[0][1][0]
    _seeds = {}
    _seeds[1] = asc_house
    raasi_list = house.quadrants_of_the_raasi(asc_house)
    _seeds[2] = house.stronger_raasi_from_list_of_raasis(planet_positions, raasi_list)
    raasi_list = house.trines_of_the_raasi(asc_house)
    _seeds[3] = house.stronger_raasi_from_list_of_raasis(planet_positions, raasi_list)
    raasi_list = [(asc_house+h)%12 for h in range(12)]
    _seeds[4] = house.stronger_raasi_from_list_of_raasis(planet_positions, raasi_list)
    unique_methods = list(set({v: k for k, v in _seeds.items()}.values()))
    return unique_methods
def _dhasa_progression_and_duration(planet_positions, dhasa_method=1):

    """
    Returns a list of (raasi, duration) pairs for the chosen Uttara Dasha method.
    - dhasa_method = 1: Lagna Uttara Dasha (start from Lagna)
    - dhasa_method = 2: Kendra Uttara Dasha (start from strongest of 1/4/7/10 from Lagna)
    - dhasa_method = 3: Trikona Uttara Dasha (start from strongest of 1/5/9 from Lagna)
    - dhasa_method = 4: Dasha Uttara Dasha (start from globally strongest rāśi)
    Durations are 1..12 in progression from the seed.
    """
    asc_house = planet_positions[0][1][0]
    if dhasa_method==1:  # Lagna Uttara Dasha
        _seed = asc_house
    elif dhasa_method==2:
        raasi_list = house.quadrants_of_the_raasi(asc_house)
        _seed = house.stronger_raasi_from_list_of_raasis(planet_positions, raasi_list)
    elif dhasa_method==3:
        raasi_list = house.trines_of_the_raasi(asc_house)
        _seed = house.stronger_raasi_from_list_of_raasis(planet_positions, raasi_list)
    else:
        raasi_list = [(asc_house+h)%12 for h in range(12)]
        _seed = house.stronger_raasi_from_list_of_raasis(planet_positions, raasi_list)
    return {(_seed+h)%12:h+1 for h in range(12)}

def get_dhasa_antardhasa(
    dob, tob, place,
    divisional_chart_factor=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,  # 1..6 (1=Maha only, 2=Antara/Bhukti, ...)
    method=1,
    chart_method=1,                                   # passed through if your API supports it
    round_duration=True,                              # round lowest-level durations for display
    **kwargs
):
    """
    Returns a flat list of the lowest-level entries:
      [ [raasi_path], (y, m, d, fh), duration_lowest_level_days ], ...
    where raasi_path contains raasi indices (0..11) per level.

    Simple, minimal rules:
    - Seed selection (method):
        1: Lagna (ascendant)
        2: Strongest Kendra among [1,4,7,10] from Lagna
        3: Strongest Trikona among [1,5,9] from Lagna
        4: Strongest among all 12
    - Durations: weights 1..12; top-level total = 78 days; sub-levels subdivide proportionally.
    - Each sub-level progression re-seeds from the parent raasi (standard for rāśi daśā).
    """
    SUM_W = 78
    YEAR_TO_DAY = const.sidereal_year
    TOP_TOTAL_DAYS = 78.0 * YEAR_TO_DAY

    def _sanitize_depth(depth):
        try:
            d = int(depth)
        except Exception:
            d = 2
        return max(1, min(6, d))

    def _progression_from_seed(seed):
        return [(seed + h) % 12 for h in range(12)]

    def _weights_for_progression(prog):
        return {r: (i + 1) for i, r in enumerate(prog)}

    def _build_level(prog, weights, parent_days):
        return [(r, parent_days * weights[r] / SUM_W) for r in prog]

    def _seed_for_method(planet_positions, asc_house, method):
        if method == 1:
            return asc_house
        elif method == 2:
            return house.stronger_raasi_from_list_of_raasis(
                planet_positions, house.quadrants_of_the_raasi(asc_house)
            )
        elif method == 3:
            return house.stronger_raasi_from_list_of_raasis(
                planet_positions, house.trines_of_the_raasi(asc_house)
            )
        elif method == 4:
            return house.stronger_raasi_from_list_of_raasis(
                planet_positions, [(asc_house + h) % 12 for h in range(12)]
            )
        else:
            raise ValueError(f"Unknown method: {method}")

    jd_at_dob = utils.julian_day_number(dob, tob)
    planet_positions = charts.divisional_chart(
        jd_at_dob, place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,**kwargs
    )

    asc_house = planet_positions[0][1][0]
    seed = _seed_for_method(planet_positions, asc_house, method)

    depth = _sanitize_depth(dhasa_level_index)
    rows = []

    def _recurse(current_seed, start_jd, parent_days, level, path):
        prog = _progression_from_seed(current_seed)
        weights = _weights_for_progression(prog)
        items = _build_level(prog, weights, parent_days)

        rolling_jd = start_jd
        for r, d_days in items:
            seg_start_jd = rolling_jd
            rolling_jd += d_days
            if level == 1:
                rows.append((path + [r], seg_start_jd, d_days))
            else:
                _recurse(r, seg_start_jd, d_days, level - 1, path + [r])

    _recurse(seed, jd_at_dob, TOP_TOTAL_DAYS, depth, [])

    results = []
    for raasi_path, start_jd, d_days in rows:
        y, m, d, fh = utils.jd_to_gregorian(start_jd)
        dur_years = d_days / YEAR_TO_DAY
        rd = round(dur_years, dhasa_level_index+1) if round_duration else dur_years
        results.append([raasi_path, (y, m, d, fh), rd])

    return results
def chathurvidha_utthara_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float (years) — provide either duration OR end
    parent_end=None,             # (Y, M, D, fractional_hour)
    *,
    jd_at_dob,
    place,
    # For parity; not needed for children (seed only matters at L1 in base)
    dhasa_method: int = 1,
    divisional_chart_factor: int = 1,
    chart_method: int = 1,
    round_duration: bool = False,    # tiler uses exact spans; runner selects via start/end
    **kwargs
):
    """
    Chathurvidha Utthara — return ONLY the immediate (p -> p+1) children under the given parent span.

    Rules (exactly as your base):
      • At each level, RESEED from the parent sign: progression = [parent, parent+1, ..., wrap].
      • Weights 1..12 map to the progression order; split parent by weights ∝ (1..12)/78.
      • Exact tiling: first child starts at parent_start; last child ends at parent_end.

    Output rows:
      [ (lords_tuple_with_child), child_start_tuple, child_end_tuple ]
    """
    # ---- normalize lords path
    if isinstance(parent_lords, int):
        path = (parent_lords,)
    elif isinstance(parent_lords, (list, tuple)) and parent_lords:
        path = tuple(parent_lords)
    else:
        raise ValueError("parent_lords must be int or non-empty tuple/list of ints")

    parent_sign = path[-1]

    # ---- tuple <-> JD helpers
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    # ---- resolve parent span
    start_jd = _tuple_to_jd(parent_start)
    YEAR_DAYS = const.sidereal_year   # same basis your base uses to convert years <-> days

    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration (years) or parent_end (tuple).")

    if parent_end is None:
        parent_years = float(parent_duration)
        end_jd = start_jd + parent_years * YEAR_DAYS
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_years = (end_jd - start_jd) / YEAR_DAYS

    if end_jd <= start_jd:
        return []  # instantaneous parent → nothing to tile

    # ---- reseed from parent sign: progression 12 signs, weights 1..12
    SUM_W = 78.0
    progression = [(parent_sign + h) % 12 for h in range(12)]
    weights     = {r: (i + 1) for i, r in enumerate(progression)}

    # ---- proportional tiling inside parent
    children = []
    jd_cursor = start_jd
    for i, r in enumerate(progression):
        share_years = parent_years * (weights[r] / SUM_W)
        # last child clamps to parent_end for exact closure
        if i == len(progression) - 1:
            child_end = end_jd
        else:
            child_end = jd_cursor + share_years * YEAR_DAYS

        children.append([
            path + (r,),
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
    *,
    dhasa_method: int = 1,               # 1..4 (seed methods from your base)
    divisional_chart_factor: int = 1,
    chart_method: int = 1,
    round_duration: bool = False,        # runner works on exact start/end
    **kwargs
):
    """
    Chathurvidha Utthara — narrow Mahā -> … -> target depth and return the full running ladder:

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

    # ---- tuple -> JD & zero-length helpers for utils
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _is_zero_length(s, e, eps_seconds=1.0):
        return (_tuple_to_jd(e) - _tuple_to_jd(s)) * 86400.0 <= eps_seconds

    def _to_utils_periods(children_rows, parent_end_tuple, eps_seconds=1.0):
        """
        children_rows: [ [lords_tuple, start_tuple, end_tuple], ... ]
        Returns: list of (lords_tuple, start_tuple) + sentinel (… , parent_end_tuple),
        filtering zero-length rows and enforcing strictly increasing starts.
        """
        filtered = [r for r in children_rows if not _is_zero_length(r[1], r[2], eps_seconds)]
        if not filtered:
            return []
        filtered.sort(key=lambda r: _tuple_to_jd(r[1]))
        proj, prev = [], None
        for lords, st, _en in filtered:
            sjd = _tuple_to_jd(st)
            if prev is None or sjd > prev:
                proj.append((lords, st)); prev = sjd
        proj.append((proj[-1][0], parent_end_tuple))  # sentinel to bound last child
        return proj

    def _as_tuple_lords(x):
        return (x,) if isinstance(x, int) else tuple(x)

    running_all = []

    # ---- L1: Mahā via your base (depth=1)
    # Your base returns: [ [raasi_path], (y,m,d,fh), duration_years ]
    #   where raasi_path is a list of indices (length=1 for L1).
    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)

    maha_rows = get_dhasa_antardhasa(
        dob, tob, place,
        divisional_chart_factor=divisional_chart_factor,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        method=dhasa_method,
        chart_method=chart_method,
        round_duration=False,**kwargs
    )
    # Normalize to (lords_tuple, start_tuple) for utils
    maha_for_utils = []
    for raasi_path, start_t, _dur_years in maha_rows:
        lords_tuple = tuple(raasi_path) if isinstance(raasi_path, list) else _as_tuple_lords(raasi_path)
        maha_for_utils.append((lords_tuple, start_t))

    # Select running Mahā
    rd1 = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    running = [_as_tuple_lords(rd1[0]), rd1[1], rd1[2]]
    running_all.append(running)

    if target_depth == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return running_all

    # ---- Levels 2..target: expand only the running parent each time
    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        # (p -> p+1) children by proportional (weights 1..12) split, reseeded from parent
        children = chathurvidha_utthara_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            dhasa_method=dhasa_method,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
            **kwargs
        )

        if not children:
            # Represent as zero-length at parent_end (no children at this depth)
            running = [parent_lords + (parent_lords[-1],), parent_end, parent_end]
            running_all.append(running)
            break

        # utils selection with sentinel & strictly increasing starts
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
    _dhasa_method = 4
    import time
    start_time = time.time()
    print("Dehā        :", get_running_dhasa_for_given_date(current_jd, jd_at_dob, place,
                                                            dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
                                                            dhasa_method=_dhasa_method))
    print('new method elapsed time',time.time()-start_time)
    start_time = time.time()
    ad = get_dhasa_antardhasa(dob,tob, place,dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,method=_dhasa_method)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,const.MAHA_DHASA_DEPTH.DEHA,
                                                               extract_running_period_for_all_levels=True))
    print('old method elapsed time',time.time()-start_time)
    exit()
    utils.set_language('en')
    dob = drik.Date(1996, 12, 7); tob = (10, 34, 0); place = drik.Place('Chennai,India', 13.03862, 80.261818, 5.5)
    jd_at_dob = utils.julian_day_number(dob,tob)
    dcf = 1
    pp = charts.divisional_chart(jd_at_dob, place, divisional_chart_factor=dcf)
    print(valid_methods_available_for_planet_positions(pp))
    cd = get_dhasa_antardhasa(dob, tob, place, divisional_chart_factor=dcf,
                                                dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
                                                method=4,
                                                )
    for row in cd:
        print(row)