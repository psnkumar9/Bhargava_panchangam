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
sidereal_year = const.sidereal_year
""" Applicability: The 10th lord in 10th """

#seed_star = 15 # Swaathi
seed_lord = 0
dhasa_adhipathi_list = {k:12 for k in const.SUN_TO_SATURN} # duration 12 years Total 84 years
#dhasa_adhipathi_dict = {0: [15, 22, 2, 9], 1: [16, 23, 3, 10], 2: [17, 24, 4, 11], 3: [18, 25, 5, 12], 4: [19, 26, 6, 13], 5: [20, 27, 7, 14], 6: [21, 1, 8]}
count_direction = 1 # 1> base star to birth star zodiac -1> base star to birth star antizodiac
def applicability_check(planet_positions):
    """ 10th Lord in 10th House """
    from jhora.horoscope.chart import house
    asc_house = planet_positions[0][1][0]
    #print('asc_house',asc_house)
    tenth_house = (asc_house+9)%12; tenth_lord = house.house_owner_from_planet_positions(planet_positions, tenth_house)
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    #print('tenth_house',tenth_house,'tenth_lord',tenth_lord,p_to_h[tenth_lord])
    return p_to_h[tenth_lord]==tenth_house
def _next_adhipati(lord,dirn=1):
    """Returns next lord after `lord` in the adhipati_list"""
    current = list(dhasa_adhipathi_list.keys()).index(lord)
    next_lord = list(dhasa_adhipathi_list.keys())[((current + dirn) % len(dhasa_adhipathi_list))]
    return next_lord
def _get_dhasa_dict(seed_star=15):
    dhasa_dict = {k:[] for k in dhasa_adhipathi_list.keys()}
    nak = seed_star-1
    lord = seed_lord
    lord_index = list(dhasa_adhipathi_list.keys()).index(lord)
    for _ in range(27):
        dhasa_dict[lord].append(nak+1)
        nak = (nak+1*count_direction)%27
        lord_index = (lord_index+1) % len(dhasa_adhipathi_list)
        lord = list(dhasa_adhipathi_list.keys())[lord_index]
    return dhasa_dict
#dhasa_adhipathi_dict = _get_dhasa_dict()

def _maha_dhasa(nak,seed_star=15):
    dhasa_adhipathi_dict = _get_dhasa_dict(seed_star)
    return [(_dhasa_lord, dhasa_adhipathi_list[_dhasa_lord]) for _dhasa_lord,_star_list in dhasa_adhipathi_dict.items() if nak in _star_list][0]
def _antardhasa(lord,antardhasa_option=1):
    if antardhasa_option in [3,4]:
        lord = _next_adhipati(lord, dirn=1) 
    elif antardhasa_option in [5,6]:
        lord = _next_adhipati(lord, dirn=-1) 
    dirn = 1 if antardhasa_option in [1,3,5] else -1
    _bhukthis = []
    for _ in range(len(dhasa_adhipathi_list)):
        _bhukthis.append(lord)
        lord = _next_adhipati(lord,dirn)
    return _bhukthis
def _dhasa_start(jd,place,divisional_chart_factor=1,chart_method=1,star_position_from_moon=1,
                 seed_star=15,dhasa_starting_planet=1):
    one_star = (360 / 27.)        # 27 nakshatras span 360°
    planet_long = charts.get_chart_element_longitude(jd, place, divisional_chart_factor, chart_method,
                                        star_position_from_moon, dhasa_starting_planet)
    nak = int(planet_long / one_star); rem = (planet_long - nak * one_star)
    lord,res = _maha_dhasa(nak+1,seed_star)          # ruler of current nakshatra
    period = res
    period_elapsed = rem / one_star * period # years
    #print('period_elapsed',period_elapsed,rem/one_star)
    period_elapsed *= sidereal_year        # days
    start_date = jd - period_elapsed      # so many days before current day
    return [lord, start_date,res]

def get_dhasa_bhukthi(
    dob, tob, place,
    divisional_chart_factor=1,
    chart_method=1,
    star_position_from_moon=1,
    use_tribhagi_variation=False,
    seed_star=15,
    dhasa_starting_planet=1,
    antardhasa_option=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
    round_duration = True
):
    """
        returns a list of dasha at selected depth (L1..L6)

        @param dob: Date Struct (year,month,day)
        @param tob: time tuple (h,m,s)
        @param place: Place as tuple (place name, latitude, longitude, timezone)
        @param divisional_chart_factor Default=1
            1=Raasi, 9=Navamsa. See const.division_chart_factors for options
        @param chart_method: Default=1, various chart methods available for each div chart. See charts module
        @param dhasa_level_index: Depth (1..6) — 1=Maha only (no Antara),
                                  2=+Antara (Bhukthi), 3=+Pratyantara, 4=+Sookshma, 5=+Prana, 6=+Deha
        @param star_position_from_moon:
            1 => Default - moon
            4 => Kshema Star (4th constellation from moon)
            5 => Utpanna Star (5th constellation from moon)
            8 => Adhana Star (8th constellation from moon)
        @param use_tribhagi_variation: False (default), True means dhasa bhukthi duration in three phases
        @param seed_star 1..27. Default = 15
        @param antardhasa_option:
            1 => dhasa lord - forward (Default)
            2 => dhasa lord - backward
            3 => next dhasa lord - forward
            4 => next dhasa lord - backward
            5 => prev dhasa lord - forward
            6 => prev dhasa lord - backward
        @param dhasa_starting_planet 0=Sun 1=Moon(default)...8=Ketu, 'L'=Lagna
                                    M=Maandi, G=Gulika, T=Trisphuta, B=Bhindu, I=Indu, P=Pranapada

        @return:
            if dhasa_level_index == 1:
                [ (l1, start_str, dur_years), ... ]
            else:
                [ (l1, l2, ..., start_str, leaf_dur_years), ... ]
            (leaf tuple includes duration; structure grows by one lord per requested level)
    """
    # --- keep original variables/logic intact ---
    _tribhagi_factor = 1.
    _dhasa_cycles = 1
    if use_tribhagi_variation:
        _tribhagi_factor = 1./3.; _dhasa_cycles = int(_dhasa_cycles/_tribhagi_factor)

    # Validate depth
    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha).")

    jd = utils.julian_day_number(dob, tob)
    dhasa_lord, start_jd, _ = _dhasa_start(
        jd, place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        star_position_from_moon=star_position_from_moon,
        seed_star=seed_star,
        dhasa_starting_planet=dhasa_starting_planet
    )

    retval = []

    # Helper: children sequence at any level — order/direction from your existing antara logic
    def _children_of(parent_lord):
        """
        Returns the list of child lords under 'parent_lord' using the SAME order rule as your current Antara:
        _antardhasa(parent_lord, antardhasa_option)
        """
        return list(_antardhasa(parent_lord, antardhasa_option))

    # Recursive expander: equal split of IMMEDIATE PARENT (so sum(children)=parent)
    def _recurse(level, parent_lord, parent_start_jd, parent_duration_years, prefix):
        """
        level: current level to build (>=2). prefix already contains lords up to previous level.
        """
        bhukthis = _children_of(parent_lord)
        if not bhukthis:
            return
        child_dur = parent_duration_years / len(bhukthis)  # equal split (same as your Antara logic)
        jd_cursor = parent_start_jd

        if level < dhasa_level_index:
            # go deeper: each child becomes the parent for next level
            for blord in bhukthis:
                _recurse(level + 1, blord, jd_cursor, child_dur, prefix + (blord,))
                jd_cursor += child_dur * sidereal_year
        else:
            # leaf rows: emit tuples with (lords..., start_str, leaf_dur)
            for blord in bhukthis:
                start_str = utils.jd_to_gregorian(jd_cursor)
                retval.append((prefix + (blord,), start_str, child_dur))
                jd_cursor += child_dur * sidereal_year

    for _ in range(_dhasa_cycles):
        for _ in range(len(dhasa_adhipathi_list)):
            # Maha duration (keep your rounding behavior at Maha)
            maha_dur = dhasa_adhipathi_list[dhasa_lord] * _tribhagi_factor
            durn = round(maha_dur,dhasa_level_index) if round_duration else maha_dur
            if dhasa_level_index == 1:
                # Maha only (unchanged, just use centralized formatter)
                start_str = utils.jd_to_gregorian(start_jd)
                retval.append(((dhasa_lord,), start_str, durn))
                start_jd += maha_dur * sidereal_year
            else:
                # Depth >= 2: expand down using the same antara ordering rule at EACH level (equal split)
                _recurse(level=2, parent_lord=dhasa_lord, parent_start_jd=start_jd,
                         parent_duration_years=maha_dur, prefix=(dhasa_lord,))
                # advance master clock by Maha
                start_jd += maha_dur * sidereal_year

            dhasa_lord = _next_adhipati(dhasa_lord)

    return retval
def nakshathra_dhasa_progression(
    jd_at_dob, place, jd_current,
    star_position_from_moon=1,
    use_tribhagi_variation=False,
    divisional_chart_factor=1,
    chart_method=1,
    seed_star=3,
    antardhasa_option=1,
    dhasa_starting_planet=1,
    dhasa_level_index = const.MAHA_DHASA_DEPTH.ANTARA,
    get_running_dhasa = True,
):
    """
        For nakshathra dhasa calculations for divisional charts - first calculate progression for raasi
        Then do varga division to progressed raasi longitudes
    """
    y,m,d,fh = utils.jd_to_gregorian(jd_at_dob); dob = drik.Date(y,m,d); tob=(fh,0,0)
    DLI = dhasa_level_index
    vd = get_dhasa_bhukthi(dob,tob, place, star_position_from_moon=star_position_from_moon,
                    use_tribhagi_variation=use_tribhagi_variation,divisional_chart_factor=divisional_chart_factor,
                    chart_method=chart_method,seed_star=seed_star, antardhasa_option=antardhasa_option,
                    dhasa_starting_planet=dhasa_starting_planet, dhasa_level_index=DLI)
    if get_running_dhasa: 
        vdc = utils.get_running_dhasa_for_given_date(jd_current, vd)
        print(vdc)
    jds = [utils.julian_day_number(drik.Date(y,m,d),(fh,0,0)) for _,(y,m,d,fh),_ in vd]
    """ Note: First we get rasi positions and then find varga division so for rasi we pass divisional_chart_factor=1"""
    planet_long = charts.get_chart_element_longitude(jd_at_dob, place, divisional_chart_factor=1, chart_method=chart_method,
                                        star_position_from_moon=star_position_from_moon,
                                        dhasa_starting_planet=dhasa_starting_planet)

    birth_star_index = int((planet_long % 360.0) // utils.ONE_NAK)
    prog_long = utils.progressed_abs_long_general(jds, jd_current, birth_star_index,
                                                  dhasa_level_index=DLI,
                                                  total_lords_in_dhasa=len(const.vimsottari_adhipati_list))
    progression_correction = utils.norm360(prog_long - planet_long)
    print('dhasa_start planet',dhasa_starting_planet,'progression correction',progression_correction,
          'divisional_chart_factor',divisional_chart_factor)
    #"""
    if get_running_dhasa:
        return progression_correction, vdc
    else:
        return progression_correction
    #"""
    ppl = charts.get_nakshathra_dhasa_progression_longitudes(jd_at_dob, place, planet_progression_correction=progression_correction,
                                                             divisional_chart_factor=divisional_chart_factor,
                                                             chart_method=chart_method)
    return ppl
def chathuraaseethi_sama_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float years (optional)
    parent_end=None,             # (Y, M, D, fractional_hour) (optional)
    antardhasa_option=1,
    **kwargs,
):
    """
    Returns ONLY the immediate (p->p+1) children under a given parent span,
    following the same antara order & equal-split rule as your get_dhasa_bhukthi().

    Output rows:
        [ (lords_tuple_with_child), child_start_tuple, child_end_tuple ]
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

    # ---- canonical tuple <-> JD helpers
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
        # zero-length parent → no children to select
        return []

    # ---- child sequence from your antara rule (order/direction)
    # Derive per-node child order using current antara setting.
    # We call your existing internal helper exactly as you do in get_dhasa_bhukthi().
    def _children_of(pl):
        return list(_antardhasa(pl, antardhasa_option))

    child_lords = _children_of(parent_lord)
    if not child_lords:
        return []

    # ---- equal split at this level (sum(children) == parent)
    sub_len = len(child_lords)
    child_years = parent_years / sub_len

    # ---- tile children within the parent span
    children = []
    cursor = start_jd
    for idx, cl in enumerate(child_lords):
        if idx == sub_len - 1:
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

    # force numeric closure
    if children:
        children[-1][2] = _jd_to_tuple(end_jd)

    return children
def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
    **kwargs
):
    """
    Narrow Mahā → … → target depth and return the full running ladder:

        [
          [(l1,),              start1, end1],
          [(l1,l2),            start2, end2],
          [(l1,l2,l3),         start3, end3],
          [(l1,l2,l3,l4),      start4, end4],
          [(l1,l2,l3,l4,l5),   start5, end5],
          [(l1,l2,l3,l4,l5,l6),start6, end6],
        ]

    Uses your get_dhasa_bhukthi() for L1 (Mahā) and dhasa_immediate_children() at deeper levels.
    """

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

    # ---- clamp level
    try:
        target_depth = int(dhasa_level_index)
    except Exception:
        target_depth = const.MAHA_DHASA_DEPTH.DEHA
    target_depth = max(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY, min(const.MAHA_DHASA_DEPTH.DEHA, target_depth))

    # ---- derive dob/tob (if ever needed elsewhere)
    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)

    # ---- unpack options to forward to base & immediate-children
    divisional_chart_factor = kwargs.get("divisional_chart_factor", 1)
    chart_method            = kwargs.get("chart_method", 1)
    star_position_from_moon = kwargs.get("star_position_from_moon", 1)
    use_tribhagi_variation  = kwargs.get("use_tribhagi_variation", False)
    seed_star               = kwargs.get("seed_star", 15)
    dhasa_starting_planet   = kwargs.get("dhasa_starting_planet", 1)
    antardhasa_option       = kwargs.get("antardhasa_option", 1)
    round_duration          = kwargs.get("round_duration", True)

    # ---- Level 1 (Mahā) via your base generator
    maha_rows = get_dhasa_bhukthi(
        dob, tob, place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        star_position_from_moon=star_position_from_moon,
        use_tribhagi_variation=use_tribhagi_variation,
        seed_star=seed_star,
        dhasa_starting_planet=dhasa_starting_planet,
        antardhasa_option=antardhasa_option,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        round_duration=False,  # runner works on starts/ends; keep timelines exact
    )
    # normalize for utils: (lords_tuple, start_tuple)
    maha_for_utils = []
    for row in maha_rows:
        # row: ((lord,), start_tuple, duration_years)
        lords_any, start_t = row[0], row[1]
        maha_for_utils.append((_as_tuple_lords(lords_any), start_t))

    running_all = []

    # Running Mahā
    rd = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    lords = _as_tuple_lords(rd[0])
    running = [lords, rd[1], rd[2]]
    running_all.append(running)

    if target_depth == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
        return running_all

    # ---- Levels 2..target
    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        # Expand only this parent (equal split + antara order per your rule)
        children = chathuraaseethi_sama_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
            star_position_from_moon=star_position_from_moon,
            use_tribhagi_variation=use_tribhagi_variation,
            seed_star=seed_star,
            dhasa_starting_planet=dhasa_starting_planet,
            antardhasa_option=antardhasa_option,
        )
        if not children:
            # no children to select (zero-length parent). Represent as zero-length at parent_end.
            running = [parent_lords + (parent_lords[-1],), parent_end, parent_end]
            running_all.append(running)
            continue

        # Prepare for utils: (lords, start) + sentinel(parent_end)
        periods_for_utils = _to_utils_periods(children, parent_end_tuple=parent_end)
        if not periods_for_utils:
            # All zero-length; pick the last child as a zero-length boundary at parent_end
            last = children[-1]
            running = [last[0], last[1], last[1]]
        else:
            rd_k = utils.get_running_dhasa_for_given_date(current_jd, periods_for_utils)
            lords_k = _as_tuple_lords(rd_k[0])
            running = [lords_k, rd_k[1], rd_k[2]]

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
    ad = get_dhasa_bhukthi(dob,tob, place,dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad, 6,extract_running_period_for_all_levels=True))
    print('old method elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.chathuraseethi_sama_tests()
