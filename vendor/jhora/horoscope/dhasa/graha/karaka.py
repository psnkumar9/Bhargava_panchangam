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
from jhora.horoscope.chart import charts, house

year_duration = const.sidereal_year
_KARAKA_LIST = const.chara_karaka_names # ['Ak','AmK','BK','Mk','PiK','PuK','GK','DK']

def get_dhasa_antardhasa(
    dob, tob, place,
    divisional_chart_factor=1, chart_method=1,
    years=1, months=1, sixty_hours=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
    round_duration=True,show_karaka_as_pair=2 #None=>Dont Show as pair, 1=>Show only karaka index 1,2,3 for NLS Support, 
):
    """
        provides karaka dhasa bhukthi for a given date in julian day (includes birth time)
        @param: show_karaka_as_pair
            None=>Dont Show as pair - return format: (dhasa_lord(s),start_str,duration)
            1=>Show karaka index 1,2,3 for NLS Support - return format: ((karaka_index,dhasa_lord),start_str,duration)
            2=>Show karaka Name Ak,Amk etc  - return format: ((karaka_name,dhasa_lord),start_str,duration)
        @return:
          if dhasa_level_index==1:
            [ (dhasa_lord, start_str, duration_years), ... ]
          else:
            [ (l1, l2, [...], start_str, dd_at_leaf), ... ]
          (leaf still returns `dd` exactly like your original antara output)
    """
    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha).")

    jd_at_dob = utils.julian_day_number(dob, tob)
    planet_positions = charts.divisional_chart(
        jd_at_dob, place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        years=years, months=months, sixty_hours=sixty_hours
    )[:const._pp_count_upto_ketu]

    karakas = house.chara_karakas(planet_positions)
    karaka_name_by_planet = {pl: _KARAKA_LIST[i] for i, pl in enumerate(karakas)}
    karaka_index_by_planet = {pl: i for i, pl in enumerate(karakas)}
    _karaka_pair = lambda lord, show_karaka_as_pair: (lord if show_karaka_as_pair is None else
                    (karaka_name_by_planet[lord],lord) if show_karaka_as_pair==2 else
                    (karaka_index_by_planet[lord],lord) )
    asc_house = planet_positions[0][1][0]

    def _dd(pl):
        # distance (in signs) from Lagna to the planet’s sign (0..11)
        return (planet_positions[pl+1][1][0] - asc_house + 12) % 12

    human_life_span = sum(_dd(k) for k in karakas)

    def _bhukthis_for(parent_lord):
        ki = karakas.index(parent_lord)
        kl = len(karakas)
        return karakas[ki+1:kl] + karakas[0:ki+1]

    dhasa_info = []
    start_jd = jd_at_dob

    def _recurse(level, parent_lord, parent_start_jd, parent_duration_years, prefix):
        """
        Nested partition at each level using the same antara rule:
        child_years = parent_years * dd(child) / human_life_span
        """
        bhukthis = _bhukthis_for(parent_lord)
        if not bhukthis:
            return

        jd_cursor = parent_start_jd
        for blord in bhukthis:
            dd_child = _dd(blord)
            blord_pair = _karaka_pair(blord,show_karaka_as_pair)
            child_years_unrounded = parent_duration_years * (dd_child / float(human_life_span))

            if level < dhasa_level_index:
                _recurse(level + 1, blord, jd_cursor, child_years_unrounded, prefix + (blord_pair,))
            else:
                start_str = utils.jd_to_gregorian(jd_cursor)
                dur_out = (round(child_years_unrounded, dhasa_level_index+1)
                           if round_duration else child_years_unrounded)
                dhasa_info.append((prefix + (blord_pair,), start_str, dur_out))

            jd_cursor += child_years_unrounded * year_duration  # year_duration == const.sidereal_year

    # Top-level traversal (Maha)
    for k in karakas:
        lord_pair = _karaka_pair(k,show_karaka_as_pair)
        maha_years_unrounded = _dd(k)  # same as your original 'duration = (k_h - asc + 12) % 12'
        if dhasa_level_index == 1:
            start_str = utils.jd_to_gregorian(start_jd)
            durn = round(maha_years_unrounded, dhasa_level_index+1) if round_duration else maha_years_unrounded
            dhasa_info.append(((lord_pair,), start_str, durn))
            start_jd += maha_years_unrounded * year_duration
        else:
            _recurse(level=2, parent_lord=k, parent_start_jd=start_jd, parent_duration_years=maha_years_unrounded, prefix=(lord_pair,))
            start_jd += maha_years_unrounded * year_duration

    return dhasa_info
def karaka_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float years (optional)
    parent_end=None,             # (Y, M, D, fractional_hour) (optional)
    *,
    jd_at_dob,
    place,
    divisional_chart_factor: int = 1,
    chart_method: int = 1,
    years: int = 1,
    months: int = 1,
    sixty_hours: int = 1,
    show_karaka_as_pair: int | None = 2,  # None, 1, or 2 (same meaning as base)
    **kwargs
):
    """
    Karaka Daśā — return ONLY the immediate (p -> p+1) children for the given parent span.

    Matches your base logic:
      • Karakas: house.chara_karakas(planet_positions)
      • dd(pl) = distance (signs) from Lagna to planet sign
      • human_life_span = sum(dd(k) for k in karakas)
      • children order = rotation of karakas starting AFTER parent_lord and wrapping
      • child_years = parent_years * dd(child) / human_life_span
    Output rows:
      [ (lords_tuple_with_child), child_start_tuple, child_end_tuple ]
    """
    # ---- normalize lords path
    if isinstance(parent_lords, int):
        path = (parent_lords,)
    elif isinstance(parent_lords, (list, tuple)) and parent_lords:
        path = tuple(parent_lords)
    else:
        raise ValueError("parent_lords must be int or non-empty tuple/list")

    # the last label may be a pair (name/index, planet) or just planet id
    def _extract_planet_id(label):
        if isinstance(label, tuple) and len(label) == 2 and isinstance(label[1], int):
            return label[1]
        if isinstance(label, int):
            return label
        raise ValueError(f"Unsupported lord label for Karaka daśā: {label}")

    parent_planet = _extract_planet_id(path[-1])

    # ---- tuple <-> JD helpers
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    # ---- resolve parent span
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
        return []

    # ---- chart & karakas (exactly as your base)
    planet_positions = charts.divisional_chart(
        jd_at_dob, place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        years=years, months=months, sixty_hours=sixty_hours,
    )[:const._pp_count_upto_ketu]

    karakas = house.chara_karakas(planet_positions)  # list of planet ids in karaka order
    karaka_name_by_planet  = {pl: _KARAKA_LIST[i] for i, pl in enumerate(karakas)}
    karaka_index_by_planet = {pl: i for i, pl in enumerate(karakas)}

    asc_house = planet_positions[0][1][0]

    def _dd(pl):
        # distance in signs from Lagna to planet sign
        return (planet_positions[pl + 1][1][0] - asc_house + 12) % 12

    human_life_span = float(sum(_dd(k) for k in karakas)) or 1.0  # avoid div-by-zero

    # children order: rotate after parent and wrap incl. parent at the end
    def _bhukthis_for(parent_pl):
        ki = karakas.index(parent_pl)
        return karakas[ki + 1:] + karakas[:ki + 1]

    def _label(pl):
        if show_karaka_as_pair is None:
            return pl
        if show_karaka_as_pair == 2:
            return (karaka_name_by_planet[pl], pl)
        # show_karaka_as_pair == 1 (NLS index)
        return (karaka_index_by_planet[pl], pl)

    child_planets = _bhukthis_for(parent_planet)
    if not child_planets:
        return []

    # ---- tile children with proportional dd weights
    children = []
    jd_cursor = start_jd
    for i, blord in enumerate(child_planets):
        share = _dd(blord) / human_life_span
        child_years = parent_years * share
        if i == len(child_planets) - 1:
            child_end = end_jd
        else:
            child_end = jd_cursor + child_years * const.sidereal_year

        children.append([
            path + (_label(blord),),
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
    divisional_chart_factor: int = 1,
    chart_method: int = 1,
    years: int = 1,
    months: int = 1,
    sixty_hours: int = 1,
    show_karaka_as_pair: int | None = 2,
    round_duration: bool = False,   # runner uses exact start/end
    **kwargs
):
    """
    Karaka Daśā — narrow Mahā -> … -> target level and return the full running ladder:

      [
        [(l1,),              start1, end1],
        [(l1,l2),            start2, end2],
        [(l1,l2,l3),         start3, end3],
        [(l1,l2,l3,l4),      start4, end4],
        [(l1,l2,l3,l4,l5),   start5, end5],
        [(l1,l2,l3,l4,l5,l6),start6, end6],
      ]
    """

    # ---- depth normalization
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
        filtering zero-length rows and enforcing strictly increasing starts for utils.
        """
        # filter zero-length
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
        return (x,) if (isinstance(x, int) or (isinstance(x, tuple) and len(x)==2 and isinstance(x[1], int))) else tuple(x)

    # ---- derive dob/tob for base
    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)

    running_all = []

    # ---- Level 1: Mahā via your base Karaka dasha
    maha_rows = get_dhasa_antardhasa(
        dob, tob, place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        years=years, months=months, sixty_hours=sixty_hours,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        round_duration=False,
        show_karaka_as_pair=show_karaka_as_pair,
    )
    # base returns just `dhasa_info` (no type paired) for L1; normalize for utils
    maha_for_utils = []
    for row in maha_rows:
        # row: ((lord_label,), start_tuple, duration)
        lords_any, start_t = row[0], row[1]
        # Keep whatever label form is used (pair or int)
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

        # Expand immediate children with the same karaka labelling rule
        children = karaka_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
            years=years, months=months, sixty_hours=sixty_hours,
            show_karaka_as_pair=show_karaka_as_pair,
        )

        if not children:
            # represent as zero-length block at parent_end
            running = [parent_lords + (parent_lords[-1],), parent_end, parent_end]
            running_all.append(running)
            continue

        # Prepare for utils: (lords, start) + sentinel(parent_end)
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
    DLI = const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY
    import time
    start_time = time.time()
    print("Dehā        :", get_running_dhasa_for_given_date(current_jd, jd_at_dob, place, dhasa_level_index=6))
    print('new method elapsed time',time.time()-start_time)
    start_time = time.time()
    ad = get_dhasa_antardhasa(dob,tob, place,dhasa_level_index=DLI)
    if DLI <= const.MAHA_DHASA_DEPTH.ANTARA:
        for lords,ds,durn in ad:
            print(lords,ds,durn)
        exit()
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,DLI,
                                                               extract_running_period_for_all_levels=True))
    print('old method elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.karaka_dhasa_test()
    dob = (1996,12,7); tob = (10,34,0); place = drik.Place('Chennai',13.0878,80.2785,5.5)
    jd = utils.julian_day_number(dob, tob)
    for dli in range(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY, const.MAHA_DHASA_DEPTH.DEHA+1):
        gd = get_dhasa_antardhasa(dob, tob, place,dhasa_level_index=dli,round_duration=False)
        gd_sum = [sum([row[-1] for row in gd])]
        if dli == 1:
            expected_list = gd_sum
            continue
        else:
            pvr_tests.compare_lists_within_tolerance("karaka_dhasa Level Duration Test ", 
                                       expected_list, gd_sum, pvr_tests._tolerance,"Level",dli)    
