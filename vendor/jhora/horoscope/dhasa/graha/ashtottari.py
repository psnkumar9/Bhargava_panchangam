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
Calculates Ashtottari (=108) Dasha-bhukthi-antara-sukshma-prana
"""

from collections import OrderedDict as Dict
from jhora import const, utils
from jhora.panchanga import drik
from jhora.horoscope.chart import house,charts

year_duration = const.sidereal_year  # const.tropical_year  # some say 360 days, others 365.25 or 365.2563 etc
human_life_span_for_ashtottari_dhasa = const.human_life_span_for_ashtottari_dhasa
one_star = (360 / 27.0)  # 27 nakshatras span 360°
# Reuse your ONE_NAK constant from above.

def _norm27(x):
    """Normalize any integer to the 1..27 range (treat 0 as 27)."""
    x = x % 27
    return 27 if x == 0 else x

def ashtottari_md_segment_angles(md_lords, seed_star=6, one_nak=one_star, get_mapping_fn=None):
    """
    Build per-Mahadasa angle spans (in degrees) for Ashtottari, honoring `seed_star`.

    Args:
      md_lords: iterable of lord IDs in the **same order** as your Mahadasa `jds` boundaries.
      seed_star: int in 0..26 (0 ≡ 27). This rotates the lord→nakshatra-block mapping.
      one_nak: angle of one nakshatra (defaults to 360/27).
      get_mapping_fn: a function compatible with your `_get_dhasa_dict(seed_star)`
                      that returns the working dict {lord: [(start_star, end_star), duration_years]}.
                      If None, it will try to call `_get_dhasa_dict` from the current scope.

    Returns:
      A list of angles (degrees), one per **Mahadasa** (same length as `md_lords`),
      where each entry is 3 × ONE_NAK or 4 × ONE_NAK depending on the lord's block size.
      NOTE: When calling `degrees_between_jds`, you will pass `angles[:len(jds)-1]`.
    """
    # Resolve mapping function
    if get_mapping_fn is None:
        try:
            get_mapping_fn = _get_dhasa_dict  # expects it to exist in your module's scope
        except NameError:
            raise ValueError("Provide `get_mapping_fn` or ensure `_get_dhasa_dict` is in scope.")

    # Normalize seed_star to 1..27
    seed = _norm27(seed_star)

    # Build the working dict rotated to this seed
    mapping = get_mapping_fn(seed)

    angles = []
    for lord in md_lords:
        (sb, se), _ = mapping[lord]  # (start_star, end_star), inclusive
        sb = _norm27(sb)
        se = _norm27(se)
        # Count how many nakshatras are covered, inclusive, with wrap
        if se < sb:
            count = (se + 27) - sb + 1
        else:
            count = se - sb + 1
        angles.append(count * one_nak)

    return angles
""" 
    {ashtottari adhipati:[(starting_star_number,ending_star_number),dasa_length]} 
        ashtottari longitude range: (starting_star_number-1) * 360/27 TO (ending_star_number) * 360/27
        Example: 66.67 to 120.00 = 53 deg 20 min range
"""
ashtottari_adhipathi_list = [0, 1, 2, 3, 6, 4, 7, 5]
ashtottari_adhipathi_dict_seed = {
    0: [(6, 9), 6],
    1: [(10, 12), 15],
    2: [(13, 16), 8],
    3: [(17, 19), 17],
    6: [(20, 22), 10],
    4: [(23, 25), 19],
    7: [(26, 2), 12],
    5: [(3, 5), 21],
}


def applicability_check(planet_positions):
    asc_house = planet_positions[0][1][0]
    lagna_lord = house.house_owner_from_planet_positions(planet_positions, asc_house)
    house_of_lagna_lord = planet_positions[lagna_lord + 1][1][0]
    rahu_house = planet_positions[const.RAHU_ID + 1][1][0]
    chk1 = rahu_house in house.trines_of_the_raasi(house_of_lagna_lord) and rahu_house != asc_house
    chk2 = rahu_house in house.quadrants_of_the_raasi(house_of_lagna_lord) and rahu_house != asc_house
    return chk1 or chk2
def _get_dhasa_dict(seed_star=6):
    if seed_star == 6:
        return ashtottari_adhipathi_dict_seed
    ashtottari_adhipathi_dict = {}
    nak = seed_star
    for p, [(nb, ne), durn] in ashtottari_adhipathi_dict_seed.items():
        nak_diff = ne - nb
        nsb = nak
        nse = (nsb + nak_diff) % 28
        ashtottari_adhipathi_dict[p] = [(nsb, nse), durn]
        nak = (nse + 1) % 28
    return ashtottari_adhipathi_dict


# Initialize default mapping once so other functions are safe to call even
# if get_ashtottari_dhasa_bhukthi() hasn’t set a custom mapping yet.
ashtottari_adhipathi_dict = _get_dhasa_dict(seed_star=6)


def ashtottari_adhipathi(nak):
    global ashtottari_adhipathi_dict
    for key, value in ashtottari_adhipathi_dict.items():
        starting_star = value[0][0]
        ending_star = value[0][1]
        nak1 = nak
        if ending_star < starting_star:
            ending_star += 27
            if nak1 < starting_star:
                nak1 += 27
        if starting_star <= nak1 <= ending_star:
            return key, value


def ashtottari_dasha_start_date(
    jd,
    place,
    divisional_chart_factor=1,
    chart_method=1,
    star_position_from_moon=1,
    dhasa_starting_planet=1,
):
    planet_long = charts.get_chart_element_longitude(jd, place, divisional_chart_factor, chart_method,
                                        star_position_from_moon, dhasa_starting_planet)
    #print('Natal Planet Longitude',utils.deg_to_sign_str(planet_long))
    nak = int(planet_long / one_star)
    lord, res = ashtottari_adhipathi(nak + 1)  # ruler of current nakshatra
    period = res[1]
    start_nak = res[0][0]
    end_nak = res[0][1]
    period_elapsed = (planet_long - (start_nak - 1) * one_star) / ((end_nak - start_nak + 1) * one_star)
    period_elapsed *= (period * year_duration)  # days
    start_date = jd - period_elapsed  # so many days before current day
    return [lord, start_date]


def ashtottari_next_adhipati(lord, dirn=1):
    """Returns next lord after `lord` in the adhipati_list"""
    current = ashtottari_adhipathi_list.index(lord)
    next_index = (current + dirn) % len(ashtottari_adhipathi_list)
    return ashtottari_adhipathi_list[next_index]


def ashtottari_mahadasa(
    jd, place, divisional_chart_factor=1, chart_method=1, star_position_from_moon=1, dhasa_starting_planet=1
):
    """
        returns a dictionary of all mahadashas and their start dates
        @return {mahadhasa_lord_index, (starting_year,starting_month,starting_day,starting_time_in_hours)}
    """
    lord, start_date = ashtottari_dasha_start_date(
        jd,
        place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        star_position_from_moon=star_position_from_moon,
        dhasa_starting_planet=dhasa_starting_planet,
    )
    retval = Dict()
    for _ in range(len(ashtottari_adhipathi_list)):
        retval[lord] = start_date
        lord_duration = ashtottari_adhipathi_dict[lord][1]
        start_date += lord_duration * year_duration
        lord = ashtottari_next_adhipati(lord)
    return retval


def ashtottari_bhukthi(dhasa_lord, start_date, antardhasa_option=1):
    """
        Compute all bhukthis of given nakshatra-lord of Mahadasa and its start date
    """
    global human_life_span_for_ashtottari_dhasa, ashtottari_adhipathi_dict
    lord = dhasa_lord
    if antardhasa_option in [3, 4]:
        lord = ashtottari_next_adhipati(dhasa_lord, dirn=1)
    elif antardhasa_option in [5, 6]:
        lord = ashtottari_next_adhipati(dhasa_lord, dirn=-1)
    dirn = 1 if antardhasa_option in [1, 3, 5] else -1
    retval = Dict()
    dhasa_lord_duration = ashtottari_adhipathi_dict[lord][1]
    for _ in range(len(ashtottari_adhipathi_list)):
        retval[lord] = start_date
        lord_duration = ashtottari_adhipathi_dict[lord][1]
        factor = lord_duration * dhasa_lord_duration / human_life_span_for_ashtottari_dhasa
        start_date += factor * year_duration
        lord = ashtottari_next_adhipati(lord, dirn)
    return retval


def ashtottari_anthara(dhasa_lord, bhukthi_lord, bhukthi_lord_start_date):
    """
        Compute all bhukthis of given nakshatra-lord of Mahadasa, its bhukthi lord and bhukthi_lord's start date
    """
    global human_life_span_for_ashtottari_dhasa, ashtottari_adhipathi_dict
    dhasa_lord_duration = ashtottari_adhipathi_dict[dhasa_lord][1]
    retval = Dict()
    lord = bhukthi_lord
    for i in range(len(ashtottari_adhipathi_list)):
        retval[lord] = bhukthi_lord_start_date
        lord_duration = ashtottari_adhipathi_dict[lord][1]
        factor = lord_duration * dhasa_lord_duration / human_life_span_for_ashtottari_dhasa
        bhukthi_lord_start_date += factor * year_duration
        lord = ashtottari_next_adhipati(lord)
    return retval


def get_ashtottari_dhasa_bhukthi(
    jd,
    place,
    divisional_chart_factor=1,
    chart_method=1,
    star_position_from_moon=1,
    use_tribhagi_variation=False,
    antardhasa_option=1,
    dhasa_starting_planet=1,
    seed_star=6,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
):
    """
    Provides Ashtottari dhasa at selected depth for a given birth Julian day (includes birth time).

    RETURNS (for ALL levels 1..6):
        [ (lords_tuple), (Y, M, D, fractional_hour), duration_years_float ]

    Conventions:
      - lords_tuple:
          * Level 1 (Mahā): (lord,)
          * Level >= 2:     (l1, l2, ..., lN) up to requested depth
      - Time is NOT a string; it is a tuple (Y, M, D, fractional_hour).
      - duration_years is a float in YEARS (sidereal basis via your `year_duration`).
    """
    global human_life_span_for_ashtottari_dhasa, ashtottari_adhipathi_dict


    # ---- SNAPSHOT GLOBALS (avoid cross-call leakage) -------------------
    _orig_H = human_life_span_for_ashtottari_dhasa
    _orig_dict = ashtottari_adhipathi_dict.copy()

    try:
        # ---- Working dict for this call (seed rotation) -----------------
        _working_dict = _get_dhasa_dict(seed_star)

        # Effective life span H (+ tribhagi scaling applied to durations in the dict)
        if use_tribhagi_variation:
            _trib = 1.0 / 3.0
            H = _orig_H * _trib
            # scale durations inside a fresh dict (keeps Y/H ratios invariant)
            _working_dict = {k: [v[0], v[1] * _trib] for k, v in _working_dict.items()}
        else:
            H = _orig_H

        # Patch globals so helpers see correct mapping & H during *this* call
        human_life_span_for_ashtottari_dhasa = H
        ashtottari_adhipathi_dict = _working_dict

        # Mahadashas: {lord -> start_jd} in sequence order
        dashas = ashtottari_mahadasa(
            jd,
            place,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
            star_position_from_moon=star_position_from_moon,
            dhasa_starting_planet=dhasa_starting_planet,
        )

        dhasa_bhukthi = []

        # ---- antara rules (same as your code) ---------------------------
        def _child_start_and_dir(parent_lord):
            lord = parent_lord
            if antardhasa_option in [3, 4]:
                lord = ashtottari_next_adhipati(parent_lord, dirn=1)
            elif antardhasa_option in [5, 6]:
                lord = ashtottari_next_adhipati(parent_lord, dirn=-1)
            dirn = 1 if antardhasa_option in [1, 3, 5] else -1
            return lord, dirn

        # ---- children generator (your proportional rule) ----------------
        def _children_of(parent_lord, parent_start_jd, parent_duration_years):
            """
            Yields tuples: (child_lord, child_start_jd, child_duration_years) for 8 segments.
            """
            start_lord, dirn = _child_start_and_dir(parent_lord)
            jd_cursor = parent_start_jd
            lord = start_lord
            for _ in range(len(ashtottari_adhipathi_list)):
                Y = ashtottari_adhipathi_dict[lord][1]        # child share (years)
                dur_yrs = parent_duration_years * (Y / H)     # proportional partition
                yield (lord, jd_cursor, dur_yrs)
                jd_cursor += dur_yrs * year_duration
                lord = ashtottari_next_adhipati(lord, dirn)

        # --- emit helper: unified 3-field row ----------------------------
        def _emit_row(lords_tuple, start_jd, duration_years):
            dhasa_bhukthi.append([lords_tuple, utils.jd_to_gregorian(start_jd), float(duration_years)])

        # --- recursion to requested depth (unchanged logic) --------------
        def _descend(target_depth, lords_tuple, start_jd, duration_years, current_depth):
            if current_depth == target_depth:
                _emit_row(lords_tuple, start_jd, duration_years)
                return
            parent_lord = lords_tuple[-1]
            for child_lord, child_start_jd, child_dur in _children_of(parent_lord, start_jd, duration_years):
                _descend(
                    target_depth=target_depth,
                    lords_tuple=lords_tuple + (child_lord,),
                    start_jd=child_start_jd,
                    duration_years=child_dur,
                    current_depth=current_depth + 1,
                )

        # ---- Build output for requested depth ---------------------------
        if dhasa_level_index == 1:
            # Mahadasha: emit [(lord,), start_tuple, duration_years]
            for lord in dashas:
                maha_start = dashas[lord]
                maha_years = ashtottari_adhipathi_dict[lord][1]  # already tribhagi-scaled if applicable
                _emit_row((lord,), maha_start, maha_years)
            return dhasa_bhukthi

        # Levels >= 2: descend per Mahā to target depth; emit nodes at that depth
        for lord in dashas:
            maha_start = dashas[lord]
            maha_years = ashtottari_adhipathi_dict[lord][1]
            _descend(
                target_depth=dhasa_level_index,
                lords_tuple=(lord,),
                start_jd=maha_start,
                duration_years=maha_years,
                current_depth=1,
            )

        return dhasa_bhukthi

    finally:
        # Restore globals
        human_life_span_for_ashtottari_dhasa = _orig_H
        ashtottari_adhipathi_dict = _orig_dict
        
def nakshathra_dhasa_progression(
    jd_at_dob, place, jd_current,
    star_position_from_moon=1,
    use_tribhagi_variation=False,
    divisional_chart_factor=1,
    chart_method=1,
    seed_star=6,
    antardhasa_option=1,
    dhasa_starting_planet=1,
    dhasa_level_index = const.MAHA_DHASA_DEPTH.ANTARA,
    get_running_dhasa = True,
):
    DLI = dhasa_level_index
    vd = get_ashtottari_dhasa_bhukthi(jd_at_dob, place, divisional_chart_factor, chart_method,
                                      star_position_from_moon, use_tribhagi_variation, antardhasa_option,
                                      dhasa_starting_planet, seed_star, 
                                      dhasa_level_index=DLI)
    vdc = utils.get_running_dhasa_for_given_date(jd_current, vd)
    if get_running_dhasa: 
        vdc = utils.get_running_dhasa_for_given_date(jd_current, vd)
        print(vdc)
    jds = [utils.julian_day_number(drik.Date(y,m,d),(fh,0,0)) for _,(y,m,d,fh) in vd]
    planet_long = charts.get_chart_element_longitude(jd_at_dob, place, divisional_chart_factor=1, chart_method=chart_method,
                                        star_position_from_moon=star_position_from_moon,
                                        dhasa_starting_planet=dhasa_starting_planet)
    birth_star_index = int((planet_long % 360.0) // utils.ONE_NAK)
    prog_long = utils.progressed_abs_long_general(jds, jd_current, birth_star_index,
                                                  dhasa_level_index=DLI,
                                                  total_lords_in_dhasa=len(ashtottari_adhipathi_list))
    #adhipathi_dict = {k:v for k,(_,v) in ashtottari_adhipathi_dict.items()}
    #prog_long = utils.progressed_longitude_for_period(vdc, adhipathi_dict, birth_star_index, jd_current)
    progression_correction = (prog_long - planet_long)%360
    #"""
    if get_running_dhasa:
        return progression_correction, vdc
    else:
        return progression_correction
    #"""
    pnak = drik.nakshatra_pada(prog_long)
    #print('birth_star_index',utils.NAKSHATRA_LIST[birth_star_index],dhasa_starting_planet,'Progressed_longitude',
    #      utils.NAKSHATRA_LIST[pnak[0]-1],utils.deg_to_sign_str(prog_long),
    #      'correction',progression_correction)
    ppl = charts.get_nakshathra_dhasa_progression_longitudes(jd_at_dob, place, 
                                                             planet_progression_correction=progression_correction,
                                                             divisional_chart_factor=divisional_chart_factor,
                                                             chart_method=chart_method)
    return ppl

def ashtottari_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, hour.frac)
    parent_duration_years=None,  # float
    parent_end=None,             # (Y, M, D, hour.frac)
    antardhasa_option=1,
):
    """
    Returns ONLY the immediate (p+1) children under a given Aṣṭottarī parent period.

    Input:
      parent_lords           : int or tuple/list[int]; if tuple, last element is the parent lord
      parent_start           : (Y, M, D, hour.frac)
      parent_duration_years  : float    [provide exactly one of duration or end]
      parent_end             : (Y, M, D, hour.frac)
      antardhasa_option      : 1..6 (same meaning as get_ashtottari_dhasa_bhukthi)

    Output:
      A list of [ (l1,...,lp, child), start_tuple, end_tuple ] rows,
      where start/end are (Y, M, D, hour.frac), strictly inside the parent span.
    """
    # ---- Normalize parent lord path & target parent lord
    if isinstance(parent_lords, int):
        path = (parent_lords,)
    elif isinstance(parent_lords, (list, tuple)):
        if len(parent_lords) == 0:
            raise ValueError("parent_lords cannot be empty")
        path = tuple(parent_lords)
    else:
        raise TypeError("parent_lords must be int or tuple/list of ints")

    parent_lord = path[-1]
    if parent_lord not in ashtottari_adhipathi_list:
        raise ValueError(f"Parent lord {parent_lord} not in Aṣṭottarī sequence {ashtottari_adhipathi_list}")

    # ---- Tuple <-> JD helpers (uses your utils)
    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y,m,d),(fh,0,0))
        base = utils.gregorian_to_jd(y, m, d)   # JD at 00:00 local (your util)
        return base + (fh / 24.0)

    # ---- Parent start/end in JD
    start_jd = _tuple_to_jd(parent_start)
    if (parent_duration_years is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration_years or parent_end")

    if parent_end is None:
        end_jd = start_jd + (parent_duration_years * year_duration)
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_duration_years = (end_jd - start_jd) / year_duration

    if end_jd <= start_jd:
        return []

    # ---- Determine child start lord and direction (your antara rules)
    lord = parent_lord
    if antardhasa_option in (3, 4):
        lord = ashtottari_next_adhipati(parent_lord, dirn=1)
    elif antardhasa_option in (5, 6):
        lord = ashtottari_next_adhipati(parent_lord, dirn=-1)
    dirn = 1 if antardhasa_option in (1, 3, 5) else -1

    # ---- Proportional partition within the parent span
    H = human_life_span_for_ashtottari_dhasa  # ratio Y/H is invariant even if tribhagi used upstream
    jd_cursor = start_jd
    out = []

    for _ in range(len(ashtottari_adhipathi_list)):
        Y = ashtottari_adhipathi_dict[lord][1]                   # child years weight
        child_years = parent_duration_years * (Y / H)
        child_end = jd_cursor + child_years * year_duration

        # Clamp to parent range
        if child_end > end_jd:
            child_end = end_jd

        if child_end > jd_cursor:
            out.append([path + (lord,), utils.jd_to_gregorian(jd_cursor), utils.jd_to_gregorian(child_end)])

        jd_cursor = child_end
        if jd_cursor >= end_jd:
            break

        lord = ashtottari_next_adhipati(lord, dirn)

    # Ensure last child ends exactly at parent end (numeric closure)
    if out:
        out[-1][2] = utils.jd_to_gregorian(end_jd)

    return out
def get_running_dhasa_for_given_date(
    current_jd,
    jd,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
    **kwargs
):
    """
    Ashtottari-specific recursive runner that finds the running daśā at the requested depth.

    Parameters
    ----------
    current_jd : float
        Julian day of the date/time to evaluate.
    jd : float
        Birth Julian day (with time).
    place : drik.Place
        Birth place object.
    dhasa_level_index : int, default 6
        Target depth (1=Mahā, 2=Antara, 3=Pratyantara, 4=Sūkṣma, 5=Prāṇa, 6=Dehā).
        Values <1 are promoted to 1, >6 are clamped to 6.
    **kwargs :
        Passed through to get_ashtottari_dhasa_bhukthi, e.g.:
          - divisional_chart_factor=1
          - chart_method=1
          - star_position_from_moon=1
          - use_tribhagi_variation=False
          - antardhasa_option=1
          - dhasa_starting_planet=1
          - seed_star=6

    Returns
    -------
    (lords_tuple, start_tuple, end_tuple)
        The running period at the requested depth, where:
          - lords_tuple is a tuple of ints (length == dhasa_level_index)
          - start_tuple and end_tuple are (Y, M, D, fractional_hour)
        Intervals follow your utils semantics (half-open [start, next_start)).

    Notes
    -----
    - This function relies on:
        - get_ashtottari_dhasa_bhukthi(...) for Mahā starts
        - ashtottari_immediate_children(parent_lords, parent_start, parent_end=...) for child layers
        - utils.get_running_dhasa_for_given_date(jd_given, periods) for selection
    - `utils.get_running_dhasa_for_given_date` expects inputs as a list of (lords, start_tuple) *only*,
      and infers end from the next start. Therefore at each child level we append a sentinel with
      start == parent_end to properly bound the last child.
    """

    # ---------- helpers ----------
    def _to_utils_periods(children_rows, parent_end_tuple):
        """
        children_rows: list of [lords_tuple, start_tuple, end_tuple]
        Return: list of (lords_tuple, start_tuple) + sentinel (any lords, parent_end_tuple)
        so that utils can infer [start, next_start) at all positions, including the last child.
        """
        if not children_rows:
            return []
        out = [(row[0], row[1]) for row in children_rows]  # drop end; utils ignores it
        # Append sentinel row with start == parent_end
        out.append((children_rows[-1][0], parent_end_tuple))
        return out

    def _as_tuple_lords(x):
        return (x,) if isinstance(x, int) else tuple(x)

    def _normalize_maha_rows_for_utils(maha_rows):
        """
        Accepts either:
          - current 2-field shape: [lord_scalar, start_tuple]
          - future 3-field shape: [(lord,), start_tuple, duration_years]
        Returns list of (lords_tuple, start_tuple) for utils.
        """
        out = []
        for row in maha_rows:
            if isinstance(row, (list, tuple)) and len(row) == 2:
                lords_any, start_t = row
            elif isinstance(row, (list, tuple)) and len(row) == 3:
                lords_any, start_t, _third = row
            else:
                raise ValueError(f"Unexpected Mahā row shape: {row}")
            out.append((_as_tuple_lords(lords_any), start_t))
        return out

    # ---------- clamp level ----------
    if dhasa_level_index is None:
        dhasa_level_index = const.MAHA_DHASA_DEPTH.DEHA
    try:
        target_depth = int(dhasa_level_index)
    except Exception:
        target_depth = const.MAHA_DHASA_DEPTH.DEHA
    if target_depth < const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
        target_depth = const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY
    if target_depth > const.MAHA_DHASA_DEPTH.DEHA:
        target_depth = const.MAHA_DHASA_DEPTH.DEHA

    # ---------- Level 1: Mahā ----------
    maha_rows_raw = get_ashtottari_dhasa_bhukthi(
        jd=jd,
        place=place,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,     # Mahā only
        **kwargs
    )
    maha_rows_for_utils = _normalize_maha_rows_for_utils(maha_rows_raw)
    running_all = []
    # Select running Mahā
    rd = utils.get_running_dhasa_for_given_date(current_jd, maha_rows_for_utils)
    # rd: (lords_or_scalar, start_tuple, end_tuple)
    lords = _as_tuple_lords(rd[0])
    running = [lords, rd[1], rd[2]]

    if target_depth == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
        return (running[0], running[1], running[2])
    running_all.append(running)
    # ---------- Levels 2..target_depth ----------
    for _depth in range(const.MAHA_DHASA_DEPTH.ANTARA, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        # Expand only this parent to immediate children
        # ashtottari_immediate_children returns: [ (lords_with_child), start_tuple, end_tuple ]
        children = ashtottari_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end
        )
        if not children:
            raise ValueError("No children generated for the given parent period.")

        # Prepare (lords, start) + sentinel for utils
        periods_for_utils = _to_utils_periods(children, parent_end_tuple=parent_end)

        # Select running child at this depth
        rd_k = utils.get_running_dhasa_for_given_date(current_jd, periods_for_utils)
        lords_k = _as_tuple_lords(rd_k[0])
        running = [lords_k, rd_k[1], rd_k[2]]
        running_all.append(running)
    # Return the running period at requested depth
    return running_all
    return (running[0], running[1], running[2])

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
    print('elapsed time',time.time()-start_time)
    start_time = time.time()
    ad = get_ashtottari_dhasa_bhukthi(jd_at_dob, place,dhasa_level_index=6)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad, 6,extract_running_period_for_all_levels=True))
    print('elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.ashtottari_tests()
