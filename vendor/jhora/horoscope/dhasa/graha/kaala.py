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
""" Kaala Dhasa """
from jhora.panchanga import drik
from jhora import utils, const
_kaala_dhasa_life_span = 120 # years
year_duration = const.sidereal_year

def _dhasa_progression_and_periods(jd,place):
    previous_day_sunset_time = drik.sunset(jd-1, place)[0]
    today_sunset_time = drik.sunset(jd, place)[0]
    today_sunrise_time = drik.sunrise(jd, place)[0]
    tomorrow_sunrise_time = 24.0+drik.sunrise(jd+1, place)[0]
    _,_,_,birth_time = utils.jd_to_gregorian(jd)
    df = abs(today_sunset_time - today_sunrise_time)/6.0
    nf1 = abs(today_sunrise_time-previous_day_sunset_time)/6.0
    nf2 = abs(tomorrow_sunrise_time-today_sunset_time)/6.0
    dawn_start = today_sunrise_time-nf1; dawn_end=today_sunrise_time+nf1
    day_start = dawn_end; day_end = today_sunset_time-nf1
    dusk_start = day_end ; dusk_end = today_sunset_time+nf2
    yday_night_start = -(previous_day_sunset_time+nf1); yday_night_end = today_sunrise_time-nf1
    tonight_start = today_sunset_time+nf2; tonight_end = tomorrow_sunrise_time-nf2
    # Night is before dawn_start and after dusk_end
    if birth_time > dawn_start and birth_time < dawn_end: # dawn
        kaala_type = const.KAALA_TYPE.DAWN # 'Dawn'
        kaala_frac = (birth_time-dawn_start)/(dawn_end-dawn_start)
    elif birth_time > dusk_start and birth_time < dusk_end: # dusk
        kaala_type = const.KAALA_TYPE.DUSK # 'Dusk'
        kaala_frac = (birth_time-dusk_start)/(dusk_end-dusk_start)
    elif birth_time > day_start and birth_time < day_end: # Day
        kaala_type = const.KAALA_TYPE.DAY # 'Day'
        kaala_frac = (birth_time-day_start)/(day_end-day_start)
    elif birth_time > yday_night_start and birth_time < yday_night_end: # yday-night
        kaala_type = const.KAALA_TYPE.NIGHT # 'YDay-Night'
        kaala_frac = (birth_time-yday_night_start)/(yday_night_end-yday_night_start)
    elif birth_time > tonight_start and birth_time < tonight_end: # yday-night
        kaala_type = const.KAALA_TYPE.NIGHT # 'ToNight'
        kaala_frac = (birth_time-tonight_start)/(tonight_end-tonight_start)
    _kaala_dhasa_life_span_first_cycle = _kaala_dhasa_life_span*kaala_frac
    _dhasas1 = [(p+1)*_kaala_dhasa_life_span_first_cycle/45.0 for p in range(9)]
    # Second Cycle
    _kaala_dhasa_life_span_second_cycle = _kaala_dhasa_life_span - _kaala_dhasa_life_span_first_cycle
    _dhasas2 = [(p+1)*_kaala_dhasa_life_span_second_cycle/45.0 for p in range(9)]
    return kaala_type, kaala_frac,_dhasas1,_dhasas2
def get_dhasa_antardhasa(
    dob, tob, place,
    years=1, months=1, sixty_hours=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
    round_duration=True                  # Round only returned durations; internal calcs use full precision
):
    """
        provides kaala dhasa bhukthi for a given date in julian day (includes birth time)

        @param dob: Date Struct (year,month,day)
        @param tob: time tuple (h,m,s)
        @param place: Place as tuple (place name, latitude, longitude, timezone)
        @param years: Yearly chart. number of years from date of birth
        @param months: Monthly chart. number of months from date of birth
        @param sixty_hours: 60-hour chart. number of 60 hours from date of birth
        @param dhasa_level_index: Depth level (1..6)
            1 = Maha only (no Antara)
            2 = + Antara (Bhukthi)
            3 = + Pratyantara
            4 = + Sookshma
            5 = + Prana
            6 = + Deha-antara
        @param round_duration: If True, round returned durations to dhasa_level_index

        @return:
            kaala_type, dhasa_info

            if dhasa_level_index == 1:
                dhasa_info: [ (dhasa_lord, start_str, dur_yrs), ... ]
            else:
                dhasa_info: [ (dhasa_lord, bhukthi_lord, [sublords...], start_str, leaf_dur_yrs), ... ]
                (tuple grows by one lord label per requested level)
    """
    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha-antara).")

    jd_at_dob = utils.julian_day_number(dob, tob)
    jd_years = drik.next_solar_date(jd_at_dob, place, years=years, months=months, sixty_hours=sixty_hours)

    kaala_type, kaala_frac, dhasas_first, dhasas_second = _dhasa_progression_and_periods(jd_years, place)

    dhasa_info = []
    start_jd = jd_years

    # Kaala sub-division of a parent period (two-phase, weighted 1..9)
    def _children_two_phase(parent_start_jd, parent_duration_years):
        """
        Yields (bhukthi_lord, child_start_jd, child_duration_years) for two phases:
          phase A = kaala_frac * parent, subdivided into weights 1..9 (sum 45)
          phase B = (1 - kaala_frac) * parent, subdivided into weights 1..9 (sum 45)
        bhukthi_lord is 0..8 in sequence (as in original code).
        """
        weights = list(range(1, 10))  # 1..9
        W = 45.0

        # Phase A
        phaseA = kaala_frac * parent_duration_years
        jd_cursor = parent_start_jd
        for blord, w in enumerate(weights):
            dur = phaseA * (w / W)
            yield (blord, jd_cursor, dur)
            jd_cursor += dur * year_duration

        # Phase B
        phaseB = (1.0 - kaala_frac) * parent_duration_years
        for blord, w in enumerate(weights):
            dur = phaseB * (w / W)
            yield (blord, jd_cursor, dur)
            jd_cursor += dur * year_duration

    # Recursive expander: apply Kaala rule at every depth (sum(children)=parent)
    def _recurse(level, parent_start_jd, parent_duration_years, prefix):
        """
        level: the current level to build (>=2). 'prefix' already contains lords up to previous level.
        """
        children = list(_children_two_phase(parent_start_jd, parent_duration_years))
        if not children:
            return

        if level < dhasa_level_index:
            # Go deeper: each child becomes parent for next level
            for blord, child_start_jd, child_dur in children:
                _recurse(level + 1, child_start_jd, child_dur, prefix + (blord,))
        else:
            # Leaf rows: round only for return (if requested); keep full precision for time accumulation
            for blord, child_start_jd, child_dur in children:
                durn = round(child_dur, dhasa_level_index+1) if round_duration else child_dur
                dhasa_info.append((prefix + (blord,), utils.jd_to_gregorian(child_start_jd), durn))

    # First Cycle
    for dhasa_lord in range(9):
        maha_dur_unrounded = dhasas_first[dhasa_lord]  # full precision for calcs
        if dhasa_level_index == 1:
            durn = round(maha_dur_unrounded, dhasa_level_index+1) if round_duration else maha_dur_unrounded
            dhasa_info.append(((dhasa_lord,), utils.jd_to_gregorian(start_jd), durn))
            start_jd += maha_dur_unrounded * year_duration
        else:
            _recurse(level=2, parent_start_jd=start_jd, parent_duration_years=maha_dur_unrounded, prefix=(dhasa_lord,))
            start_jd += maha_dur_unrounded * year_duration

    # Second Cycle
    for dhasa_lord in range(9):
        maha_dur_unrounded = dhasas_second[dhasa_lord]
        if dhasa_level_index == 1:
            durn = round(maha_dur_unrounded, dhasa_level_index+1) if round_duration else maha_dur_unrounded
            dhasa_info.append(((dhasa_lord,), utils.jd_to_gregorian(start_jd), durn))
            start_jd += maha_dur_unrounded * year_duration
        else:
            _recurse(level=2, parent_start_jd=start_jd, parent_duration_years=maha_dur_unrounded, prefix=(dhasa_lord,))
            start_jd += maha_dur_unrounded * year_duration

    return kaala_type, dhasa_info
def kaala_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float years (optional)
    parent_end=None,             # (Y, M, D, fractional_hour) (optional)
    *,
    jd_at_dob,
    place,
    years: int = 1,
    months: int = 1,
    sixty_hours: int = 1,
    **kwargs
):
    """
    Kāla Daśā — return ONLY the immediate (p -> p+1) children under the given parent span.

    Rules (matches get_dhasa_antardhasa):
      • Children are formed by a TWO-PHASE split using kaala_frac:
            Phase A  = kaala_frac * parent
            Phase B  = (1 - kaala_frac) * parent
        Each phase is subdivided by weights 1..9 (sum=45), producing 9 children per phase,
        i.e., 18 immediate children total at each level.
      • Child labels (bhukthi_lord) are 0..8 in order for phase A, then again 0..8 for phase B
        (exactly like your _children_two_phase).

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

    # ---- compute the yearly anchor and Kaala parameters
    # Same as in your base: anchor on "yearly" chart from DOB, then get kaala params
    jd_years = drik.next_solar_date(jd_at_dob, place, years=years, months=months, sixty_hours=sixty_hours)
    kaala_type, kaala_frac, _dhasas_first, _dhasas_second = _dhasa_progression_and_periods(jd_years, place)
    # (We only need kaala_frac to subdivide the immediate parent.)

    # ---- two-phase subdivision at this immediate level
    weights = list(range(1, 10))  # 1..9
    W = 45.0

    phaseA_years = kaala_frac * parent_years
    phaseB_years = (1.0 - kaala_frac) * parent_years

    # Build (label, duration_years) pairs in sequence: phase A then phase B
    segments = []
    for blord, w in enumerate(weights):   # Phase A
        segments.append((blord, phaseA_years * (w / W)))
    for blord, w in enumerate(weights):   # Phase B
        segments.append((blord, phaseB_years * (w / W)))

    # ---- tile children within parent [start, end)
    children = []
    cursor = start_jd
    for idx, (blord, dur_y) in enumerate(segments):
        if idx == len(segments) - 1:
            child_end = end_jd
        else:
            child_end = cursor + dur_y * const.sidereal_year
        children.append([
            path + (blord,),
            _jd_to_tuple(cursor),
            _jd_to_tuple(child_end),
        ])
        cursor = child_end
        if cursor >= end_jd:
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
    years: int = 1,
    months: int = 1,
    sixty_hours: int = 1,
    round_duration: bool = False,     # runner uses exact start/end; leave unrounded
    **kwargs
):
    """
    Kāla Daśā — narrow Mahā -> … -> target level and return the full running ladder:

      [
        [(l1,),              start1, end1],            # Mahā
        [(l1,l2),            start2, end2],            # Antara
        [(l1,l2,l3),         start3, end3],            # Pratyantara
        [(l1,l2,l3,l4),      start4, end4],            # Sūkṣma
        [(l1,l2,l3,l4,l5),   start5, end5],            # Prāṇa
        [(l1,l2,l3,l4,l5,l6),start6, end6],            # Dehā
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

    # ---- tuple <-> JD helpers
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _is_zero_length(s, e, eps_seconds=1.0):
        return (_tuple_to_jd(e) - _tuple_to_jd(s)) * 86400.0 <= eps_seconds

    def _to_utils_periods(children_rows, parent_end_tuple, eps_seconds=1.0):
        """
        children_rows: [ [lords_tuple, start_tuple, end_tuple], ... ]
        Returns: list of (lords_tuple, start_tuple) + sentinel (any_lords, parent_end_tuple),
        filtering zero-length rows and enforcing strictly increasing starts for utils.
        """
        # filter zero-length
        filtered = [r for r in children_rows if not _is_zero_length(r[1], r[2], eps_seconds=eps_seconds)]
        if not filtered:
            return []
        filtered.sort(key=lambda r: _tuple_to_jd(r[1]))
        proj, prev = [], None
        for lords, st, _en in filtered:
            sjd = _tuple_to_jd(st)
            if prev is None or sjd > prev:
                proj.append((lords, st)); prev = sjd
        # sentinel
        proj.append((proj[-1][0], parent_end_tuple))
        return proj

    def _as_tuple_lords(x):
        return (x,) if isinstance(x, int) else tuple(x)

    # ---- derive dob/tob (base function needs them)
    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)

    running_all = []

    # ---- Level 1: Mahā via your base function
    kaala_type, maha_rows = get_dhasa_antardhasa(
        dob, tob, place,
        years=years,
        months=months,
        sixty_hours=sixty_hours,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        round_duration=False,
    )
    # normalize for utils: (lords_tuple, start_tuple)
    maha_for_utils = []
    for row in maha_rows:
        # row: ((lord,), start_tuple, duration_years)
        lords_any, start_t = row[0], row[1]
        maha_for_utils.append((_as_tuple_lords(lords_any), start_t))

    # select running Mahā
    rd1 = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    lords1 = _as_tuple_lords(rd1[0])
    running = [lords1, rd1[1], rd1[2]]
    running_all.append(running)

    if target_depth == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return running_all

    # ---- Levels 2..target
    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        # Expand only this parent via the 2-phase (weights 1..9 each) rule
        children = kaala_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            years=years,
            months=months,
            sixty_hours=sixty_hours,
        )

        if not children:
            # represent as zero-length at parent_end
            running = [parent_lords + (parent_lords[-1],), parent_end, parent_end]
            running_all.append(running)
            continue

        # utils selection with sentinel & strictly increasing starts
        periods_for_utils = _to_utils_periods(children, parent_end_tuple=parent_end)
        if not periods_for_utils:
            # all zero-length → boundary selection
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
    _,ad = get_dhasa_antardhasa(dob,tob, place,dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,const.MAHA_DHASA_DEPTH.DEHA,
                                                               extract_running_period_for_all_levels=True))
    print('old method elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.kaala_test()