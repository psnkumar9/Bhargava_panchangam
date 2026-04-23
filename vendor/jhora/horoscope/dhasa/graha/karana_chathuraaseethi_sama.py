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
year_duration = const.sidereal_year
""" Karana Based Chathuraaseethi Sama Dasa """

seed_lord = 0
dhasa_adhipathi_dict = {key: const.karana_lords[key] for key in list(const.karana_lords.keys())[:-2]} # Exclude Rahu and Ketu V4.2.7
dhasa_adhipathi_list = {k:12 for k in range(len(dhasa_adhipathi_dict))} # duration 12 years Total 84 years
count_direction = 1 # 1> base star to birth star zodiac -1> base star to birth star antizodiac
def _dhasa_adhipathi(karana_index):
    for key,(karana_list,durn) in dhasa_adhipathi_dict.items():
        if karana_index in karana_list:
            return key,durn 
def _next_adhipati(lord,dirn=1):
    """Returns next lord after `lord` in the adhipati_list"""
    current = list(dhasa_adhipathi_list.keys()).index(lord)
    next_lord = list(dhasa_adhipathi_list.keys())[((current + dirn) % len(dhasa_adhipathi_list))]
    return next_lord
def _maha_dhasa(nak):
    return [(_dhasa_lord, dhasa_adhipathi_list[_dhasa_lord]) for _dhasa_lord,_star_list in dhasa_adhipathi_dict.items() if nak in _star_list][0]
def _antardhasa(dhasa_lord,antardhasa_option=1):
    lord = dhasa_lord
    if antardhasa_option in [3,4]:
        lord = _next_adhipati(dhasa_lord, dirn=1) 
    elif antardhasa_option in [5,6]:
        lord = _next_adhipati(dhasa_lord, dirn=-1) 
    dirn = 1 if antardhasa_option in [1,3,5] else -1
    _bhukthis = []
    for _ in range(len(dhasa_adhipathi_list)):
        _bhukthis.append(lord)
        lord = _next_adhipati(lord,dirn)
    return _bhukthis
def _dhasa_start(jd,place):
    _,_,_,birth_time_hrs = utils.jd_to_gregorian(jd)
    _kar = drik.karana(jd, place)
    k_frac = utils.get_fraction(_kar[1], _kar[2], birth_time_hrs)
    lord,res = _dhasa_adhipathi(_kar[0])# V4.2.6
    period_elapsed = (1-k_frac)*res*year_duration
    start_date = jd - period_elapsed      # so many days before current day
    return [lord, start_date,res]

def get_dhasa_bhukthi(
    dob, tob, place,
    use_tribhagi_variation=False,
    divisional_chart_factor=1,
    chart_method=1,
    antardhasa_option=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
    round_duration=True      # NEW: round only returned durations; internal calcs use full precision
):
    """
        provides karana chathuraaseethi sama dhasa bhukthi for a given date in julian day (includes birth time)

        @param dob: Date Struct (year,month,day)
        @param tob: time tuple (h,m,s)
        @param place: Place as tuple (place name, latitude, longitude, timezone)
        @param use_tribhagi_variation: False (default), True means dhasa bhukthi duration in three phases 
        @param divisional_chart_factor: Default=1
        @param chart_method: Default=1
        @param antardhasa_option:
            1 => dhasa lord - forward (Default)
            2 => dhasa lord - backward
            3 => next dhasa lord - forward
            4 => next dhasa lord - backward
            5 => prev dhasa lord - forward
            6 => prev dhasa lord - backward
        @param dhasa_level_index: Depth (1..6)
            1 = Maha only (no Antara)
            2 = + Antara (Bhukthi)
            3 = + Pratyantara
            4 = + Sookshma
            5 = + Prana
            6 = + Deha-antara
        @param round_duration: If True, round only the returned duration values to dhasa_level_index

        @return:
            if dhasa_level_index == 1:
                [ (l1, start_str, dur_years), ... ]
            else:
                [ (l1, l2, ..., start_str, leaf_dur_years), ... ]
            (the tuple grows by one lord per requested level)
    """
    # --- original setup preserved ---
    _tribhagi_factor = 1.
    _dhasa_cycles = 1
    if use_tribhagi_variation:
        _tribhagi_factor = 1./3.
        _dhasa_cycles = int(_dhasa_cycles/_tribhagi_factor)

    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha).")

    jd = utils.julian_day_number(dob, tob)
    dhasa_lord, start_jd, _ = _dhasa_start(jd, place)

    retval = []

    # Use your existing antara ordering at every level
    def _children_of(parent_lord):
        return list(_antardhasa(parent_lord, antardhasa_option))

    # Nested partition of the immediate parent; internal calcs use full precision
    def _recurse(level, parent_lord, parent_start_jd, parent_duration_years, prefix):
        bhukthis = _children_of(parent_lord)
        if not bhukthis:
            return

        child_dur_unrounded = parent_duration_years / len(bhukthis)  # equal split (your antara logic)
        jd_cursor = parent_start_jd

        if level < dhasa_level_index:
            # go deeper: each child becomes the parent for next level
            for blord in bhukthis:
                _recurse(level + 1, blord, jd_cursor, child_dur_unrounded, prefix + (blord,))
                jd_cursor += child_dur_unrounded * year_duration
        else:
            # leaf rows: round only the returned duration if requested
            for blord in bhukthis:
                start_str = utils.jd_to_gregorian(jd_cursor)
                durn = round(child_dur_unrounded, dhasa_level_index+1) if round_duration else child_dur_unrounded
                retval.append((prefix + (blord,), start_str, durn))
                jd_cursor += child_dur_unrounded * year_duration

    for _ in range(_dhasa_cycles):
        for _ in range(len(dhasa_adhipathi_list)):
            # Maha duration — full precision internally; round only when returning
            maha_dur_unrounded = dhasa_adhipathi_list[dhasa_lord] * _tribhagi_factor

            if dhasa_level_index == 1:
                start_str = utils.jd_to_gregorian(start_jd)
                durn = round(maha_dur_unrounded, dhasa_level_index+1) if round_duration else maha_dur_unrounded
                retval.append(((dhasa_lord,), start_str, durn))
                start_jd += maha_dur_unrounded * year_duration
            else:
                _recurse(
                    level=2,
                    parent_lord=dhasa_lord,
                    parent_start_jd=start_jd,
                    parent_duration_years=maha_dur_unrounded,
                    prefix=(dhasa_lord,)
                )
                start_jd += maha_dur_unrounded * year_duration

            dhasa_lord = _next_adhipati(dhasa_lord)  # dirn=1 for dhasa sequence

    return retval
def karana_chathuraaseethi_sama_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float years (optional)
    parent_end=None,             # (Y, M, D, fractional_hour) (optional)
    *,
    jd_at_dob,
    place,
    antardhasa_option: int = 1,
    **kwargs
):
    """
    Karana Chathurāśīti (Sama) — return ONLY the immediate (p -> p+1) children.

    Rules (matches your base get_dhasa_bhukthi()):
      • Child order at every level via your antara rule: _antardhasa(parent_lord, antardhasa_option)
      • Sama = equal split at this level: child_years = parent_years / len(children)
      • Last child end forced to parent_end (exact tiling)

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

    # ---- canonical tuple <-> JD
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    # ---- parent span
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
        return []  # instantaneous parent → nothing to tile

    # ---- child sequence via your antara rule (order/direction)
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
            child_end = cursor + child_years * const.sidereal_year

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
    antardhasa_option: int = 1,
    use_tribhagi_variation: bool = False,
    divisional_chart_factor: int = 1,
    chart_method: int = 1,
    round_duration: bool = False,      # runner uses exact start/end; rounding not needed here
    **kwargs
):
    """
    Karana Chathurāśīti (Sama) — narrow Mahā -> … -> target depth and return the full ladder:

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
        Returns: list of (lords_tuple, start_tuple) + sentinel (any_lords, parent_end_tuple),
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

    # ---- derive dob/tob for base
    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)

    running_all = []

    # ---- Level 1: Mahā via your base generator
    maha_rows = get_dhasa_bhukthi(
        dob, tob, place,
        use_tribhagi_variation=use_tribhagi_variation,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        antardhasa_option=antardhasa_option,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        round_duration=False,
    )
    # normalize for utils: (lords_tuple, start_tuple)
    maha_for_utils = []
    for row in maha_rows:
        # row: ((lord,), start_tuple, duration_years)
        lords_any, start_t = row[0], row[1]
        maha_for_utils.append((_as_tuple_lords(lords_any), start_t))

    # Running Mahā
    rd1 = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    lords1 = _as_tuple_lords(rd1[0])
    running = [lords1, rd1[1], rd1[2]]
    running_all.append(running)

    if target_depth == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return running_all

    # ---- Levels 2..target
    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        # Expand only this parent (Sama + antara order)
        children = karana_chathuraaseethi_sama_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            antardhasa_option=antardhasa_option,
            **kwargs
        )

        if not children:
            # represent as zero-length at parent_end
            running = [parent_lords + (parent_lords[-1],), parent_end, parent_end]
            running_all.append(running)
            continue

        # utils selection with sentinel & strictly increasing starts
        periods_for_utils = _to_utils_periods(children, parent_end_tuple=parent_end)
        if not periods_for_utils:
            last = children[-1]
            running = [last[0], last[1], last[1]]
        else:
            rdk = utils.get_running_dhasa_for_given_date(current_jd, periods_for_utils)
            lords_k = _as_tuple_lords(rdk[0])
            running = [lords_k, rdk[1], rdk[2]]

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
    ad = get_dhasa_bhukthi(dob,tob, place,dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,const.MAHA_DHASA_DEPTH.DEHA,
                                                               extract_running_period_for_all_levels=True))
    print('old method elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    const.use_24hour_format_in_to_dms = False
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.karana_chathuraseethi_sama_test()
