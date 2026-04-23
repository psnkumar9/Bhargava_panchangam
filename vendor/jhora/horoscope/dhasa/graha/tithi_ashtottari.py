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
        Calculates Tithi Ashtottari (=108) Dasha-bhukthi-antara-sukshma-prana
        Ref: https://www.indiadivine.org/content/topic/1488164-vedavyasa-tithi-ashtottari-dasa-tutorial/

"""

import swisseph as swe
from collections import OrderedDict as Dict
from jhora import const,utils
from jhora.panchanga import drik
from jhora.horoscope.chart import house
year_duration = const.sidereal_year  # some say 360 days, others 365.25 or 365.2563 etc
human_life_span_for_ashtottari_dhasa = 108
""" 
    {ashtottari adhipati:[(tithis),dasa_length]} 
"""
ashtottari_adhipathi_list = [0,1,2,3,6,4,7,5]
ashtottari_adhipathi_dict = {0:[(1,9,16,24),6],1:[(2,10,17,25),15],2:[(3,11,18,26),8],3:[(4,12,19,27),17],
                             6:[(7,15,22),10],4:[(5,13,20,28),19],7:[(8,23,30),12],5:[(6,14,21,29),21]}
def _ashtottari_adhipathi(tithi_index):
    for key,(tithi_list,durn) in ashtottari_adhipathi_dict.items():
        if tithi_index in tithi_list:
            return key,durn 
def _ashtottari_dasha_start_date(jd,place,tithi_index=1):
    _,_,_,birth_time_hrs = utils.jd_to_gregorian(jd)
    tit = drik.tithi(jd, place,tithi_index=tithi_index)
    t_frac = utils.get_fraction(tit[1], tit[2], birth_time_hrs)
    lord,res = _ashtottari_adhipathi(tit[0])          # ruler of current nakshatra
    period_elapsed = (1-t_frac)*res*year_duration
    start_jd = jd - period_elapsed      # so many days before current day
    return [lord, start_jd]
def _ashtottari_next_adhipati(lord,dirn=1):
    """Returns next lord after `lord` in the adhipati_list"""
    current = ashtottari_adhipathi_list.index(lord)
    next_index = (current + dirn) % len(ashtottari_adhipathi_list)
    return list(ashtottari_adhipathi_dict.keys())[next_index]
def ashtottari_mahadasa(jd,place,tithi_index):
    """
        returns a dictionary of all mahadashas and their start dates
        @return {mahadhasa_lord_index, (starting_year,starting_month,starting_day,starting_time_in_hours)}
    """
    lord, start_date = _ashtottari_dasha_start_date(jd,place,tithi_index)
    retval = Dict()
    for _ in range(len(ashtottari_adhipathi_list)):
        retval[lord] = start_date
        lord_duration = ashtottari_adhipathi_dict[lord][1]
        start_date += lord_duration * year_duration
        lord = _ashtottari_next_adhipati(lord)
    return retval
def ashtottari_bhukthi(dhasa_lord, start_date,antardhasa_option=3):
    """
        Compute all bhukthis of given nakshatra-lord of Mahadasa and its start date
    """
    lord = dhasa_lord
    if antardhasa_option in [3,4]:
        lord = _ashtottari_next_adhipati(lord, dirn=1) 
    elif antardhasa_option in [5,6]:
        lord = _ashtottari_next_adhipati(lord, dirn=-1) 
    dirn = 1 if antardhasa_option in [1,3,5] else -1
    dhasa_lord_duration = ashtottari_adhipathi_dict[dhasa_lord][1]
    retval = Dict()
    #lord = _ashtottari_next_adhipati(dhasa_lord,dirn) # For Ashtottari first bhukkti starts from dhasa's next lord
    for _ in range(len(ashtottari_adhipathi_list)):
        retval[lord] = start_date
        lord_duration = ashtottari_adhipathi_dict[lord][1]
        factor = lord_duration * dhasa_lord_duration / human_life_span_for_ashtottari_dhasa
        start_date += factor * year_duration
        lord = _ashtottari_next_adhipati(lord,dirn)
    return retval
def ashtottari_anthara(dhasa_lord, bhukthi_lord,bhukthi_lord_start_date):
    """
        Compute all bhukthis of given nakshatra-lord of Mahadasa, its bhukthi lord and bhukthi_lord's start date
    """
    dhasa_lord_duration = ashtottari_adhipathi_dict[dhasa_lord][1]
    retval = Dict()
    lord = _ashtottari_next_adhipati(bhukthi_lord) # For Ashtottari first bhukkti starts from dhasa's next lord
    for _ in range(len(ashtottari_adhipathi_list)):
        retval[lord] = bhukthi_lord_start_date
        lord_duration = ashtottari_adhipathi_dict[lord][1]
        factor = lord_duration * dhasa_lord_duration / human_life_span_for_ashtottari_dhasa
        bhukthi_lord_start_date += factor * year_duration
        lord = _ashtottari_next_adhipati(lord)
    return retval

def get_dhasa_bhukthi(
    jd, place,
    use_tribhagi_variation=False,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,  # 1..6 (1=Maha only, 2=+Antara, 3..6 deeper)
    tithi_index=1,
    antardhasa_option=3
):
    """
        provides Tithi Ashtottari dhasa bhukthi for a given date in julian day (includes birth time)
        This is Ashtottari Dhasa based on tithi instead of nakshathra

        @param jd: Julian day for birthdate and birth time
        @param place: Place as tuple (place name, latitude, longitude, timezone) 
        @param use_tribhagi_variation: False (default), True means dhasa bhukthi duration in three phases 
        @param dhasa_level_index: Depth level (1..6)
            1 = Maha only (no Antardasha)
            2 = + Antardasha (Bhukthi)    [Default]
            3 = + Pratyantara
            4 = + Sookshma
            5 = + Prana
            6 = + Deha-antara
        @param tithi_index: 1=>Janma, 2=>Dhana, 3=>Bhratri, 4=>Matri, 5=>Putra, 6=>Satru, 7=>Kalatra, 8=>Mrutyu,
                           9=>Bhagya, 10=>Karma, 11=>Laabha, 12=>Vyaya
        @param antardhasa_option:
            1 => dhasa lord - forward
            2 => dhasa lord - backward
            3 => next dhasa lord - forward (Default)
            4 => next dhasa lord - backward
            5 => prev dhasa lord - forward
            6 => prev dhasa lord - backward

        @return:
          If dhasa_level_index==1: [ [dhasa_lord, start_str], ... ]
          If dhasa_level_index==2: [ [dhasa_lord, bhukthi_lord, start_str], ... ]
          If dhasa_level_index>=3: [ [l1, l2, l3, ..., start_str], ... ]  (variable-length lists)
    """
    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha).")

    global human_life_span_for_ashtottari_dhasa
    _dhasa_cycles = 1
    _tribhagi_factor = 1
    if use_tribhagi_variation:
        _tribhagi_factor = 1./3.
        _dhasa_cycles = int(_dhasa_cycles/_tribhagi_factor)
        # Preserve your original behavior: mutate global H and scale each adhipati year
        human_life_span_for_ashtottari_dhasa *= _tribhagi_factor
        for k, (v1, v2) in ashtottari_adhipathi_dict.items():
            ashtottari_adhipathi_dict[k] = [v1, round(v2 * _tribhagi_factor, 2)]

    # Tithi-based maha start dates (unchanged helper)
    dashas = ashtottari_mahadasa(jd, place, tithi_index)

    dhasa_bhukthi = []
    H = human_life_span_for_ashtottari_dhasa  # 108 (or scaled by tribhāgī)
    # We will need the year length; this module defines `year_duration = const.sidereal_year`
    # and we retain it.

    # -- Child ordering: same antara start & direction as regular Ashtottari --
    def _child_start_and_dir(parent_lord):
        lord = parent_lord
        if antardhasa_option in [3, 4]:
            lord = _ashtottari_next_adhipati(parent_lord, dirn=1)
        elif antardhasa_option in [5, 6]:
            lord = _ashtottari_next_adhipati(parent_lord, dirn=-1)
        dirn = 1 if antardhasa_option in [1, 3, 5] else -1
        return lord, dirn

    def _children_of(parent_lord, parent_start_jd, parent_years):
        """
        One full child cycle under `parent_lord`, nested partition:
          child_years = parent_years * (Y(child)/H),
        marching from the start child and direction defined by antardhasa_option.
        Y(child) is taken from ashtottari_adhipathi_dict[child][1].
        """
        start_lord, dirn = _child_start_and_dir(parent_lord)
        jd_cursor = parent_start_jd
        lord = start_lord
        for _ in range(len(ashtottari_adhipathi_list)):
            Y = ashtottari_adhipathi_dict[lord][1]
            dur_yrs = parent_years * (Y / H)
            yield (lord, jd_cursor, dur_yrs)
            jd_cursor += dur_yrs * year_duration
            lord = _ashtottari_next_adhipati(lord, dirn)

    # -- Depth handling --
    for _ in range(_dhasa_cycles):
        # L1 (Maha only)
        if dhasa_level_index == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
            for lord in dashas:
                jd1 = dashas[lord]
                dhasa_bhukthi.append([(lord,), utils.jd_to_gregorian(jd1)])
            continue

        # L2 (Maha + Antara): reuse your existing antara helper for exact legacy starts
        if dhasa_level_index == const.MAHA_DHASA_DEPTH.ANTARA:
            for lord in dashas:
                bhukthis = ashtottari_bhukthi(lord, dashas[lord], antardhasa_option)
                for blord in bhukthis:
                    jd1 = bhukthis[blord]
                    dhasa_bhukthi.append([(lord, blord), utils.jd_to_gregorian(jd1)])
            continue

        # L3..L6: nested expansion using the same antara rule at each level
        def _recurse(level, parent_lord, parent_start_jd, parent_years, prefix, out_rows):
            # Base case: when we've reached the requested depth, emit THIS node
            if level == dhasa_level_index:
                out_rows.append([prefix, utils.jd_to_gregorian(parent_start_jd)])
                return
        
            # Otherwise, expand exactly one child cycle and go deeper
            for clord, cstart, cyears in _children_of(parent_lord, parent_start_jd, parent_years):
                _recurse(level + 1, clord, cstart, cyears, prefix + (clord,), out_rows)
        
        for lord in dashas:
            maha_start = dashas[lord]
            maha_years = ashtottari_adhipathi_dict[lord][1]  # (tribhāgī-scaled already if used)
        
            if dhasa_level_index == const.MAHA_DHASA_DEPTH.PRATYANTARA:
                # Fast path for L3: expand one level beyond antara
                for blord, bstart, byears in _children_of(lord, maha_start, maha_years):
                    for plord, pstart, _py in _children_of(blord, bstart, byears):
                        dhasa_bhukthi.append([(lord, blord, plord), utils.jd_to_gregorian(pstart)])
            else:
                # Generic recursion for L4..L6, start depth aligned with the prefix (MAHĀ = level 1)
                _recurse(
                    level=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,  # 1
                    parent_lord=lord,
                    parent_start_jd=maha_start,
                    parent_years=maha_years,
                    prefix=(lord,),  # tuple
                    out_rows=dhasa_bhukthi
                )

    return dhasa_bhukthi
def tithi_ashtottari_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float years (one of duration or end must be provided)
    parent_end=None,             # (Y, M, D, fractional_hour)
    *,
    jd_at_dob,
    place,
    antardhasa_option: int = 3,  # same default as your base
    use_tribhagi_variation: bool = False,  # accepted for parity; tiler reads current globals
    **kwargs
):
    """
    Tithi Aṣṭottarī — returns ONLY the immediate (p -> p+1) children within a given parent span.

    Matches your base rules:
      • Start child & direction by `antardhasa_option`
      • Proportional split: child_years = parent_years * (Y(child) / H),
        where H=human_life_span_for_ashtottari_dhasa and Y(child)=ashtottari_adhipathi_dict[child][1]
      • Exact tiling of [parent_start, parent_end)

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

    # ---- resolve parent span
    start_jd = _tuple_to_jd(parent_start)
    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration (years) or parent_end (tuple).")

    YEAR_DAYS = const.sidereal_year  # same basis your module uses via year_duration

    if parent_end is None:
        parent_years = float(parent_duration)
        end_jd = start_jd + parent_years * YEAR_DAYS
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_years = (end_jd - start_jd) / YEAR_DAYS

    if end_jd <= start_jd:
        return []

    # ---- reuse your base's start & direction rule
    def _child_start_and_dir(parent_lord_local):
        lord = parent_lord_local
        if antardhasa_option in [3, 4]:
            lord = _ashtottari_next_adhipati(parent_lord_local, dirn=1)
        elif antardhasa_option in [5, 6]:
            lord = _ashtottari_next_adhipati(parent_lord_local, dirn=-1)
        dirn = 1 if antardhasa_option in [1, 3, 5] else -1
        return lord, dirn

    # ---- proportional split (one full cycle)
    H = float(human_life_span_for_ashtottari_dhasa)  # may be tribhāgī-scaled already by the caller
    start_lord, dirn = _child_start_and_dir(parent_lord)
    jd_cursor = start_jd
    lord = start_lord

    children = []
    N = len(ashtottari_adhipathi_list)
    for i in range(N):
        Y = float(ashtottari_adhipathi_dict[lord][1])  # years for this child (possibly tribhāgī-scaled externally)
        child_years = parent_years * (Y / H)
        # last child → clamp to parent end for numeric closure
        if i == N - 1:
            child_end = end_jd
        else:
            child_end = jd_cursor + child_years * YEAR_DAYS

        children.append([
            path + (lord,),
            _jd_to_tuple(jd_cursor),
            _jd_to_tuple(child_end),
        ])

        jd_cursor = child_end
        if jd_cursor >= end_jd:
            break
        lord = _ashtottari_next_adhipati(lord, dirn)

    if children:
        children[-1][2] = _jd_to_tuple(end_jd)  # exact closure

    return children
def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
    *,
    tithi_index: int = 1,
    antardhasa_option: int = 3,         # same default as your base
    use_tribhagi_variation: bool = False,
    round_duration: bool = False,       # runner uses exact start/end, not rounded
    **kwargs
):
    """
    Tithi Aṣṭottarī — narrow Mahā -> … -> target depth and return the full running ladder:

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
        filtered = [r for r in children_rows if not _is_zero_length(r[1], r[2], eps_seconds)]
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

    # ---- Level 1: Mahā via your BASE Tithi-Aṣṭottarī generator
    maha_rows = get_dhasa_bhukthi(
        jd=jd_at_dob,
        place=place,
        use_tribhagi_variation=use_tribhagi_variation,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        tithi_index=tithi_index,
        antardhasa_option=antardhasa_option
    )
    # normalize for utils: (lords_tuple, start_tuple)
    maha_for_utils = []
    for row in maha_rows:
        # base returns: [(lord,), start_tuple] at L1
        lords_any, start_t = row[0], row[1]
        maha_for_utils.append((_as_tuple_lords(lords_any), start_t))

    # Running Mahā
    rd1 = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    running = [_as_tuple_lords(rd1[0]), rd1[1], rd1[2]]
    running_all.append(running)

    if target_depth == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return running_all

    # ---- Levels 2..target: expand only the running parent at each step
    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        # produce (p -> p+1) children by proportional rule Y/H, with the same antara start+dir
        children = tithi_ashtottari_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            antardhasa_option=antardhasa_option,
            use_tribhagi_variation=use_tribhagi_variation,
            **kwargs
        )

        if not children:
            # no children under this parent: represent as zero-length at the boundary
            running = [parent_lords + (parent_lords[-1],), parent_end, parent_end]
            running_all.append(running)
            break

        # utils selection with strictly increasing starts + sentinel(parent_end)
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

'------ main -----------'
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
    ad = get_dhasa_bhukthi(jd_at_dob, place,dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,const.MAHA_DHASA_DEPTH.DEHA,
                                                               extract_running_period_for_all_levels=True))
    print('old method elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    const.use_24hour_format_in_to_dms = False
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.tithi_ashtottari_tests()
    