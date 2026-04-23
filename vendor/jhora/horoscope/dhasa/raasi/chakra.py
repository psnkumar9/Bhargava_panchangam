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
""" Chakra Dhasa """
"""
    Antardasa/Bhukthi Lords do not match with JHora - as it is not clear how it is implemented there
    So we start with mahadasa lord as the bhukthi lord.
"""
from jhora.panchanga import drik
from jhora import utils, const
_dhasa_duration = 10.0; _bhukthi_duration = _dhasa_duration/12.0
year_duration = const.sidereal_year

def _dhasa_seed(jd,place,lagna_house,lagna_lord_house):
    previous_day_sunset_time = drik.sunset(jd-1, place)[0]
    today_sunset_time = drik.sunset(jd, place)[0]
    today_sunrise_time = drik.sunrise(jd, place)[0]
    tomorrow_sunrise_time = 24.0+drik.sunrise(jd+1, place)[0]
    _,_,_,birth_time = utils.jd_to_gregorian(jd)
    df = abs(today_sunset_time - today_sunrise_time)/6.0
    nf1 = abs(today_sunrise_time-previous_day_sunset_time)/6.0
    nf2 = abs(tomorrow_sunrise_time-today_sunset_time)/6.0
    #print('df',df,'nf1',nf1,'nf2',nf2)
    dawn_start = today_sunrise_time-nf1; dawn_end=today_sunrise_time+nf1
    #print('dawn',dawn_start,dawn_end)
    day_start = dawn_end; day_end = today_sunset_time-nf1
    #print('day',day_start,day_end)
    dusk_start = day_end ; dusk_end = today_sunset_time+nf2
    #print('dusk',dusk_start,dusk_end)
    yday_night_start = -(previous_day_sunset_time+nf1); yday_night_end = today_sunrise_time-nf1
    tonight_start = today_sunset_time+nf2; tonight_end = tomorrow_sunrise_time-nf2
    #print('Night-Yday',yday_night_start,yday_night_end,'Night-today',tonight_start,tonight_end)
    # Night is before dawn_start and after dusk_end
    if birth_time > dawn_start and birth_time < dawn_end: # dawn
        kaala_period = 'Dawn'
        _dhasa_seed = (lagna_house+1)%12
    elif birth_time > dusk_start and birth_time < dusk_end: # dusk
        kaala_period = 'Dusk'
        _dhasa_seed = (lagna_house+1)%12
    elif birth_time > day_start and birth_time < day_end: # Day
        kaala_period = 'Day'
        _dhasa_seed = lagna_lord_house
    elif birth_time > yday_night_start and birth_time < yday_night_end: # yday-night
        kaala_period = 'YDay-Night'
        _dhasa_seed = lagna_house
    elif birth_time > tonight_start and birth_time < tonight_end: # yday-night
        kaala_period = 'ToNight'
        _dhasa_seed = lagna_house    
    return _dhasa_seed

def get_dhasa_antardhasa(
    dob, tob, place,
    divisional_chart_factor=1, years=1, months=1, sixty_hours=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,  # 1..6: 1=Maha only, 2=+Antara (default), 3..6 deeper
    round_duration=True,                               # round only returned durations; JD math stays full precision
    **kwargs
):
    """
    Chakra daśā with multi-level depth (Maha → Antara → Pratyantara → …)

    Depth control (replaces include_antardhasa):
      1 = MAHA_DHASA_ONLY      -> rows: (l1,               start_str, dur_years)
      2 = ANTARA               -> rows: (l1, l2,           start_str, dur_years)       [DEFAULT]
      3 = PRATYANTARA          -> rows: (l1, l2, l3,       start_str, dur_years)
      4 = SOOKSHMA             -> rows: (l1, l2, l3, l4,   start_str, dur_years)
      5 = PRANA                -> rows: (l1, l2, l3, l4, l5,   start_str, dur_years)
      6 = DEHA                 -> rows: (l1, l2, l3, l4, l5, l6, start_str, dur_years)

    Duration policy:
      - Maha duration (years) = _dhasa_duration(planet_positions, sign)  [your original helper].
      - At every deeper level, the IMMEDIATE parent is split into 12 equal parts (Σchildren = parent).
    Ordering:
      - Maha sequence: 12 signs starting from dhasa_seed (or your reversed cycle if seed is even).
      - At each node, children = 12 signs in cyclic order starting from the *parent* sign.
    """
    # ---- safety ----------------------------------------------------------------
    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha).")

    # ---- annual epoch (bugfix: pass the correct sixty_hours) -------------------
    jd_at_dob = utils.julian_day_number(dob, tob)
    jd_years  = drik.next_solar_date(jd_at_dob, place, years=years, months=months, sixty_hours=sixty_hours)

    # ---- base chart (unchanged seed machinery) --------------------------------
    from jhora.horoscope.chart import charts, house
    pp = charts.divisional_chart(jd_years, place, divisional_chart_factor=divisional_chart_factor)
    lagna_house      = pp[0][1][0]
    lagna_lord       = house.house_owner_from_planet_positions(pp, lagna_house)
    lagna_lord_house = pp[lagna_lord + 1][1][0]

    # seed is for MAHA only—do not recompute it at deeper levels
    dhasa_seed = _dhasa_seed(jd_years, place, lagna_house, lagna_lord_house)

    # maha sequence (12 signs) starting from seed
    maha_signs = [(dhasa_seed + h) % 12 for h in range(12)]

    # children at any node: 12 signs starting from parent sign
    def _children_from(parent_sign):
        return [(parent_sign + k) % 12 for k in range(12)]

    # choose rounding precision; default to 2 if constant absent
    _round_ndigits = getattr(const, 'DHASA_DURATION_ROUNDING_TO', 2)

    def _recurse(level, parent_sign, parent_start_jd, parent_years, prefix, out_rows):
        """
        Depth >= 3:
          - child order: cyclic from parent_sign
          - child duration: parent_years / 12
        """
        bhuktis = _children_from(parent_sign)
        child_unrounded = parent_years / 12.0
        jd_cursor = parent_start_jd

        if level < dhasa_level_index:
            for child_sign in bhuktis:
                _recurse(level + 1, child_sign, jd_cursor, child_unrounded, prefix + (child_sign,), out_rows)
                jd_cursor += child_unrounded * year_duration
        else:
            for child_sign in bhuktis:
                start_str = utils.jd_to_gregorian(jd_cursor)
                dur_ret   = round(child_unrounded, dhasa_level_index+1) if round_duration else child_unrounded
                out_rows.append((prefix + (child_sign,), start_str, dur_ret))
                jd_cursor += child_unrounded * year_duration

    # ---- build rows per requested depth ---------------------------------------
    rows   = []
    jd_cur = jd_years

    for maha_sign in maha_signs:
        maha_years = _dhasa_duration
        if dhasa_level_index == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
            # L1: Maha only
            start_str = utils.jd_to_gregorian(jd_cur)
            dur_ret   = round(maha_years, dhasa_level_index+1) if round_duration else maha_years
            rows.append(((maha_sign,), start_str, dur_ret))
            jd_cur += maha_years * year_duration
            continue

        if dhasa_level_index == const.MAHA_DHASA_DEPTH.ANTARA:
            # L2: Antara — equal split of Maha into 12, children ordered from maha_sign
            child_unrounded = maha_years / 12.0
            jd_b = jd_cur
            for antara_sign in _children_from(maha_sign):
                start_str = utils.jd_to_gregorian(jd_b)
                dur_ret   = round(child_unrounded, dhasa_level_index+1) if round_duration else child_unrounded
                rows.append(((maha_sign, antara_sign), start_str, dur_ret))
                jd_b += child_unrounded * year_duration
            jd_cur += maha_years * year_duration
            continue

        # L3..L6: recursive equal-split below immediate parent
        _recurse(
            level=const.MAHA_DHASA_DEPTH.ANTARA,   # = 2; build 3..N
            parent_sign=maha_sign,
            parent_start_jd=jd_cur,
            parent_years=maha_years,
            prefix=(maha_sign,),
            out_rows=rows
        )
        jd_cur += maha_years * year_duration

    return rows
def chakra_immediate_children(
    parent_lords,
    parent_start,
    parent_duration=None,
    parent_end=None,
    *,
    jd_at_dob,
    place,
    **kwargs
):
    """
    Chakra — ONLY the immediate (p -> p+1) children within the given parent span.
      • Children = 12 signs cyclic from parent sign (inclusive)
      • Sama split: parent_years / 12
      • Exact tiling [start, end)
    """
    if isinstance(parent_lords, int):
        path = (parent_lords,)
    elif isinstance(parent_lords, (list, tuple)) and parent_lords:
        path = tuple(parent_lords)
    else:
        raise ValueError("parent_lords must be int or non-empty tuple/list")

    parent_sign = path[-1]

    def _jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))
    def _to_tuple(jd):
        return utils.jd_to_gregorian(jd)

    start_jd = _jd(parent_start)
    YEAR_DAYS = const.sidereal_year

    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration (years) or parent_end (tuple).")
    if parent_end is None:
        parent_years = float(parent_duration)
        end_jd = start_jd + parent_years * YEAR_DAYS
    else:
        end_jd = _jd(parent_end)
        parent_years = (end_jd - start_jd) / YEAR_DAYS

    if end_jd <= start_jd:
        return []

    # 12 signs cyclic from parent
    children_signs = [(parent_sign + k) % 12 for k in range(12)]
    child_years = parent_years / 12.0

    out = []
    cursor = start_jd
    for i, sgn in enumerate(children_signs):
        if i == 11:
            end = end_jd
        else:
            end = cursor + child_years * YEAR_DAYS
        out.append([path + (sgn,), _to_tuple(cursor), _to_tuple(end)])
        cursor = end
        if cursor >= end_jd:
            break

    if out:
        out[-1][2] = _to_tuple(end_jd)
    return out
def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
    *,
    divisional_chart_factor=1, years=1, months=1, sixty_hours=1,
    **kwargs
):
    """
    Chakra — narrow Mahā -> … -> target, returning full running ladder.
    """
    def _normalize_depth(x):
        try: d = int(x)
        except: d = int(const.MAHA_DHASA_DEPTH.DEHA)
        lo, hi = int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY), int(const.MAHA_DHASA_DEPTH.DEHA)
        return min(hi, max(lo, d))
    target_depth = _normalize_depth(dhasa_level_index)

    def _jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))
    def _is_zero(s, e, eps=1.0):
        return (_jd(e) - _jd(s)) * 86400.0 <= eps
    def _to_utils(children, parent_end):
        flt = [r for r in children if not _is_zero(r[1], r[2])]
        if not flt: return []
        flt.sort(key=lambda r: _jd(r[1]))
        proj, prev = [], None
        for lords, st, _ in flt:
            sj = _jd(st)
            if prev is None or sj > prev:
                proj.append((lords, st)); prev = sj
        proj.append((proj[-1][0], parent_end))  # sentinel
        return proj
    def _as_tuple_lords(x): return (x,) if isinstance(x, int) else tuple(x)

    # L1 via base
    # Derive dob,tob from jd_at_dob for your base
    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d); tob = (fh, 0, 0)

    maha_rows = get_dhasa_antardhasa(
        dob, tob, place,
        divisional_chart_factor=divisional_chart_factor,
        years=years, months=months, sixty_hours=sixty_hours,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        round_duration=False,**kwargs
    )
    maha_for_utils = [(_as_tuple_lords(row[0]), row[1]) for row in maha_rows]

    running_all = []
    rd1 = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    running = [_as_tuple_lords(rd1[0]), rd1[1], rd1[2]]
    running_all.append(running)

    if target_depth == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return running_all

    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        children = chakra_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,**kwargs
        )
        if not children:
            running = [parent_lords + (parent_lords[-1],), parent_end, parent_end]
            running_all.append(running)
            break

        periods = _to_utils(children, parent_end=parent_end)
        if not periods:
            last = children[-1]
            running = [last[0], last[1], last[1]]
        else:
            rdk = utils.get_running_dhasa_for_given_date(current_jd, periods)
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
    ad = get_dhasa_antardhasa(dob,tob, place,dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,const.MAHA_DHASA_DEPTH.DEHA,
                                                               extract_running_period_for_all_levels=True))
    print('old method elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.chakra_test()