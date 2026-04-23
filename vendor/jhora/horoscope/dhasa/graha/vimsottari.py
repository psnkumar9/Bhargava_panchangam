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
Calculates Vimshottari (=120) Dasha-bhukthi-antara-sukshma-prana
"""
from collections import OrderedDict as Dict
from jhora import const, utils
from jhora.panchanga import drik
from jhora.horoscope.chart import charts

year_duration = const.sidereal_year  # const.tropical_year  # some say 360 days, others 365.25 or 365.2563 etc
one_star = (360 / 27.0)  # 27 nakshatras span 360°

vimsottari_adhipati = (
    lambda nak, seed_star=3: const.vimsottari_adhipati_list[
        (nak - seed_star + 3) % (len(const.vimsottari_adhipati_list))
    ]
)

# IMPORTANT: decouple from const to avoid mutating the library-wide constants object
vimsottari_dict = const.vimsottari_dict.copy()

human_life_span_for_vimsottari_dhasa = const.human_life_span_for_vimsottari_dhasa


### --- Vimsottari functions
def vimsottari_next_adhipati(lord, direction=1):
    """Returns next guy after `lord` in the adhipati_list"""
    current = const.vimsottari_adhipati_list.index(lord)
    next_index = (current + direction) % len(const.vimsottari_adhipati_list)
    return const.vimsottari_adhipati_list[next_index]

def vimsottari_dasha_start_date(
    jd,
    place,
    divisional_chart_factor=1,
    chart_method=1,
    star_position_from_moon=1,
    seed_star=3,
    dhasa_starting_planet=1,
):
    """Returns the start date of the mahadasa which occured on or before `jd`"""
    y, m, d, fh = utils.jd_to_gregorian(jd)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)
    planet_long = charts.get_chart_element_longitude(jd, place, divisional_chart_factor, chart_method,
                                        star_position_from_moon, dhasa_starting_planet)
    nak = int(planet_long / one_star)
    rem = (planet_long - nak * one_star)
    lord = vimsottari_adhipati(nak, seed_star)  # ruler of current nakshatra
    period = vimsottari_dict[lord]              # total years of nakshatra lord

    period_elapsed = rem / one_star * period  # years
    period_elapsed *= year_duration           # days
    start_date = jd - period_elapsed          # so many days before current day
    return [lord, start_date]


def vimsottari_mahadasa(
    jd, place, divisional_chart_factor=1, chart_method=1, star_position_from_moon=1, seed_star=3, dhasa_starting_planet=1
):
    """List all mahadashas and their start dates"""
    lord, start_date = vimsottari_dasha_start_date(
        jd, place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        star_position_from_moon=star_position_from_moon,
        seed_star=seed_star,
        dhasa_starting_planet=dhasa_starting_planet
    )
    retval = Dict()
    for i in range(9):
        retval[lord] = start_date
        start_date += vimsottari_dict[lord] * year_duration
        lord = vimsottari_next_adhipati(lord)

    return retval


def _vimsottari_rasi_bhukthi(maha_lord, maha_lord_rasi, start_date):
    """Compute all bhuktis of given nakshatra-lord of Mahadasa using rasi bhukthi variation
    and its start date"""
    retval = Dict()
    bhukthi_duration = vimsottari_dict[maha_lord] / 12
    for bhukthi_rasi in [(maha_lord_rasi + h) % 12 for h in range(12)]:
        retval[bhukthi_rasi] = start_date
        start_date += bhukthi_duration * year_duration
    return retval


def _vimsottari_bhukti(maha_lord, start_date, antardhasa_option=1):
    """Compute all bhuktis of given nakshatra-lord of Mahadasa and its start date"""
    global human_life_span_for_vimsottari_dhasa, vimsottari_dict
    lord = maha_lord
    if antardhasa_option in [3, 4]:
        lord = vimsottari_next_adhipati(lord, direction=1)
    elif antardhasa_option in [5, 6]:
        lord = vimsottari_next_adhipati(lord, direction=-1)
    dirn = 1 if antardhasa_option in [1, 3, 5] else -1
    retval = Dict()
    for i in range(9):
        retval[lord] = start_date
        factor = vimsottari_dict[lord] * vimsottari_dict[maha_lord] / human_life_span_for_vimsottari_dhasa
        start_date += factor * year_duration
        lord = vimsottari_next_adhipati(lord, dirn)

    return retval


# North Indian tradition: dasa-antardasa-pratyantardasa
# South Indian tradition: dasa-bhukti-antara-sukshma
def _vimsottari_antara(maha_lord, bhukti_lord, start_date):
    """Compute all antaradasas from given bhukti's start date.
    The bhukti's lord and its lord (mahadasa lord) must be given"""
    global human_life_span_for_vimsottari_dhasa, vimsottari_dict
    lord = bhukti_lord
    retval = Dict()
    for i in range(9):
        retval[lord] = start_date
        factor = vimsottari_dict[lord] * (vimsottari_dict[maha_lord] / human_life_span_for_vimsottari_dhasa)
        factor *= (vimsottari_dict[bhukti_lord] / human_life_span_for_vimsottari_dhasa)
        start_date += factor * year_duration
        lord = vimsottari_next_adhipati(lord)

    return retval


def _where_occurs(jd, some_dict):
    """Returns minimum key such that some_dict[key] < jd"""
    # It is assumed that the dict is sorted in ascending order
    # i.e. some_dict[i] < some_dict[j]  where i < j
    for key in reversed(list(some_dict.keys())):
        if some_dict[key] < jd:
            return key


def compute_vimsottari_antara_from(jd, mahadashas):
    """Returns antaradasha within which given `jd` falls"""
    # Find mahadasa where this JD falls
    i = _where_occurs(jd, mahadashas)
    # Compute all bhuktis of that mahadasa
    bhuktis = _vimsottari_bhukti(i, mahadashas[i])
    # Find bhukti where this JD falls
    j = _where_occurs(jd, bhuktis)
    # JD falls in i-th dasa / j-th bhukti
    # Compute all antaras of that bhukti
    antara = _vimsottari_antara(i, j, bhuktis[j])
    return (i, j, antara)


def get_vimsottari_dhasa_bhukthi(
    jd, place,
    star_position_from_moon=1,
    use_tribhagi_variation=False,
    use_rasi_bhukthi_variation=False,
    divisional_chart_factor=1,
    chart_method=1,
    seed_star=3,
    antardhasa_option=1,
    dhasa_starting_planet=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,  # 1..6
):
    """
    Provides Vimsottari dhasa at selected depth for a given birth Julian day (includes birth time).

    RETURNS (for ALL levels 1..6):
        [ (lords_tuple), (Y, M, D, fractional_hour), duration_years_float ]
    """
    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha).")

    global human_life_span_for_vimsottari_dhasa, vimsottari_dict

    # ---- SNAPSHOT GLOBALS (avoid cross-test leakage) -------------------
    _orig_H = human_life_span_for_vimsottari_dhasa
    _orig_dict = vimsottari_dict.copy()

    try:
        # ---- Build call-local working dict & H --------------------------
        _working_dict = _orig_dict
        if use_tribhagi_variation:
            _trib = 1.0 / 3.0
            H = _orig_H * _trib
            # scale durations inside a fresh dict (no mutation to _orig_dict)
            _working_dict = {k: round(v * _trib, 6) for k, v in _orig_dict.items()}
            _dhasa_cycles = int(1 / _trib)
        else:
            H = _orig_H
            _dhasa_cycles = 1

        # Patch module-level globals so legacy helpers see the correct values
        human_life_span_for_vimsottari_dhasa = H
        vimsottari_dict = _working_dict

        # --- Ordered MD starts (OrderedDict) -----------------------------
        dashas = vimsottari_mahadasa(
            jd, place,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
            star_position_from_moon=star_position_from_moon,
            seed_star=seed_star,
            dhasa_starting_planet=dhasa_starting_planet
        )

        # Vimśottarī balance (unchanged return in first tuple)
        dl = list(dashas.values())
        de = dl[1]
        y, m, d, _ = utils.jd_to_gregorian(jd); p_date1 = drik.Date(y, m, d)
        y, m, d, _ = utils.jd_to_gregorian(de); p_date2 = drik.Date(y, m, d)
        vim_bal = utils.panchanga_date_diff(p_date1, p_date2)

        dhasa_bhukthi = []

        # --- helpers -----------------------------------------------------
        def _start_and_dir(parent_lord):
            lord = parent_lord
            if antardhasa_option in [3, 4]:
                lord = vimsottari_next_adhipati(lord, direction=+1)
            elif antardhasa_option in [5, 6]:
                lord = vimsottari_next_adhipati(lord, direction=-1)
            dirn = +1 if antardhasa_option in [1, 3, 5] else -1
            return lord, dirn

        def _children_planetary(parent_lord, parent_start_jd, parent_years):
            """Yield (child_lord, child_start_jd, child_years) for 9 children under parent_lord."""
            start_lord, dirn = _start_and_dir(parent_lord)
            jd_cursor = parent_start_jd
            lord = start_lord
            for _ in range(len(const.vimsottari_adhipati_list)):
                Y = float(vimsottari_dict[lord])  # already tribhagi-scaled if enabled
                dur_yrs = parent_years * (Y / H)
                yield (lord, jd_cursor, dur_yrs)
                jd_cursor += dur_yrs * year_duration
                lord = vimsottari_next_adhipati(lord, direction=dirn)

        # Emit helper (unified 3-field format)
        def _emit_row(lords_tuple, start_jd, duration_years):
            dhasa_bhukthi.append([lords_tuple, utils.jd_to_gregorian(start_jd), float(duration_years)])

        # Convenience: compute durations from consecutive starts (last -> parent_end)
        def _emit_children_from_starts(parent_tuple, starts_list, parent_end_jd):
            """
            starts_list: ordered list of (child_lord, child_start_jd)
            Emits rows [(parent_tuple + child_lord), start_tuple, duration_years].
            """
            for idx, (clord, cstart) in enumerate(starts_list):
                cend = parent_end_jd if idx == len(starts_list) - 1 else starts_list[idx + 1][1]
                dur_years = (cend - cstart) / year_duration
                _emit_row(parent_tuple + (clord,), cstart, dur_years)

        # An ordered list of (md_lord, md_start_jd)
        md_items = list(dashas.items())

        for _ in range(_dhasa_cycles):
            N = len(md_items)
            for idx, (md_lord, md_start_jd) in enumerate(md_items):
                # --- Compute MD end & duration years
                if idx < N - 1:
                    md_end_jd = md_items[idx + 1][1]
                else:
                    # fallback to nominal duration when next start not available
                    md_end_jd = md_start_jd + float(vimsottari_dict[md_lord]) * year_duration
                md_years = (md_end_jd - md_start_jd) / year_duration

                if dhasa_level_index == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
                    # L1: [(lord,), start_tuple, duration_years]
                    _emit_row((md_lord,), md_start_jd, md_years)

                elif dhasa_level_index == const.MAHA_DHASA_DEPTH.ANTARA:
                    # L2: planetary or rasi-bhukthi variation
                    if use_rasi_bhukthi_variation:
                        planet_positions = charts.divisional_chart(jd, place, divisional_chart_factor=1)
                        maha_lord_rasi = planet_positions[md_lord + 1][1][0]
                        bhuktis = _vimsottari_rasi_bhukthi(md_lord, maha_lord_rasi, md_start_jd)
                    else:
                        bhuktis = _vimsottari_bhukti(md_lord, md_start_jd, antardhasa_option=antardhasa_option)

                    # Emit durations by consecutive starts; last ends at md_end_jd
                    starts_list = list(bhuktis.items())  # Ordered
                    _emit_children_from_starts((md_lord,), starts_list, md_end_jd)

                elif dhasa_level_index == const.MAHA_DHASA_DEPTH.PRATYANTARA:
                    if use_rasi_bhukthi_variation:
                        raise ValueError(
                            "L3+ not supported with use_rasi_bhukthi_variation=True. "
                            "Keep depth at L2 or specify a custom L3 rule."
                        )
                    # L2 starts (planetary bhukti)
                    bhuktis = _vimsottari_bhukti(md_lord, md_start_jd, antardhasa_option=antardhasa_option)
                    bh_list = list(bhuktis.items())

                    for b_idx, (blord, bstart) in enumerate(bh_list):
                        bend = md_end_jd if b_idx == len(bh_list) - 1 else bh_list[b_idx + 1][1]
                        # L3: antara under this bhukti, durations via consecutive starts; last ends at 'bend'
                        antara = _vimsottari_antara(md_lord, blord, bstart)
                        a_list = list(antara.items())
                        _emit_children_from_starts((md_lord, blord), a_list, bend)

                else:
                    if use_rasi_bhukthi_variation:
                        raise ValueError(
                            "L3+ not supported with use_rasi_bhukthi_variation=True. "
                            "Keep depth at L2 or specify a custom L3/L4 rule."
                        )

                    # L4..L6 via proportional planetary recursion (durations available)
                    def _recurse_to_depth(level, parent_lord, parent_start_jd, parent_years, prefix):
                        if level == dhasa_level_index:
                            # Final node at requested depth
                            _emit_row(tuple(prefix), parent_start_jd, parent_years)
                            return
                        # Expand one level down using proportional rule
                        for clord, cstart, cyears in _children_planetary(parent_lord, parent_start_jd, parent_years):
                            _recurse_to_depth(level + 1, clord, cstart, cyears, prefix + [clord])

                    # Start at level=1 (Mahā), go down to requested depth
                    _recurse_to_depth(
                        level=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,  # i.e., 1
                        parent_lord=md_lord,
                        parent_start_jd=md_start_jd,
                        parent_years=md_years,
                        prefix=[md_lord]
                    )

        return vim_bal, dhasa_bhukthi

    finally:
        # ---- RESTORE GLOBALS (guaranteed) --------------------------------
        human_life_span_for_vimsottari_dhasa = _orig_H
        vimsottari_dict = _orig_dict

def _start_lord_and_dir(parent_lord: int, antardhasa_option: int) -> tuple[int, int]:
    """
    Replicates your existing option handling:
      1 => dhasa lord - forward (Default)
      2 => dhasa lord - backward
      3 => next dhasa lord - forward
      4 => next dhasa lord - backward
      5 => prev dhasa lord - forward
      6 => prev dhasa lord - backward
    """
    lord = parent_lord
    if antardhasa_option in [3, 4]:
        lord = vimsottari_next_adhipati(lord, direction=+1)
    elif antardhasa_option in [5, 6]:
        lord = vimsottari_next_adhipati(lord, direction=-1)
    dirn = +1 if antardhasa_option in [1, 3, 5] else -1
    return lord, dirn


def vimsottari_immediate_children(
    parent_lords,
    parent_start,                # (Y, M, D, fractional_hour)
    parent_duration=None,        # float, years (optional)
    parent_end=None,             # (Y, M, D, fractional_hour) (optional)
    *,
    antardhasa_option=1,
    use_rasi_bhukthi_variation=False,
    jd=None,                     # required only if use_rasi_bhukthi_variation=True and len(parent_lords)==1
    place=None,                  # required only if use_rasi_bhukthi_variation=True and len(parent_lords)==1
    divisional_chart_factor=1,   # used only for rasi-bhukthi path
):
    """
    Returns ONLY the immediate (p->p+1) children under a given Vimśottarī parent period.

    Input
    -----
    parent_lords : int | tuple/list[int]
        The parent path; the parent lord is the last element.
        - (l1, l2, ..., lp) -> parent is lp
        - int or (int,) also OK
    parent_start : (Y, M, D, fractional_hour)
        Parent start timestamp tuple.
    parent_duration : float (years), optional
        Provide exactly one of (parent_duration, parent_end).
    parent_end : (Y, M, D, fractional_hour), optional
        Provide exactly one of (parent_duration, parent_end).
    antardhasa_option : int (1..6)
        Planetary ordering rule:
          1 => start from parent, forward      | 2 => start from parent, backward
          3 => start from next,   forward      | 4 => start from next,   backward
          5 => start from prev,   forward      | 6 => start from prev,   backward
        Ignored for rasi-bhukthi (which defines its own order).
    use_rasi_bhukthi_variation : bool
        If True and len(parent_lords)==1 (Mahā->antara), use rāśi-bhukthi starts.
        Requires jd/place to determine Mahā lord's rāśi.
    jd, place, divisional_chart_factor
        Used only when use_rasi_bhukthi_variation=True and len(parent_lords)==1.

    Output
    ------
    List of rows:
        [ (lords_tuple_with_child), child_start_tuple, child_end_tuple ]
    fully tiled within the given parent span. The last child's end is forced to parent_end
    to ensure numeric closure.

    Notes
    -----
    - Planetary partition uses proportional durations:
        child_years = parent_years * (Y_child / H),
      where Y_child is from vimsottari_dict and H = human_life_span_for_vimsottari_dhasa.
    - Time math uses sidereal `year_duration` (consistent with the rest of your codebase).
    - Rāśi-bhukthi is available ONLY at L2 (Mahā -> antara) as per your implementation.
    """
    # -------- normalize lords path & parent lord -------------------------
    if isinstance(parent_lords, int):
        path = (parent_lords,)
    elif isinstance(parent_lords, (list, tuple)):
        if len(parent_lords) == 0:
            raise ValueError("parent_lords cannot be empty")
        path = tuple(parent_lords)
    else:
        raise TypeError("parent_lords must be int or tuple/list of ints")

    parent_lord = path[-1]

    # -------- tuple <-> JD conversions ----------------------------------
    def _tuple_to_jd(t):
        y,m,d,fh = t
        return utils.julian_day_number(drik.Date(y, m, d),(fh,0,0))

    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    # -------- parent start/end in JD ------------------------------------
    start_jd = _tuple_to_jd(parent_start)

    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration (years) or parent_end (tuple).")

    if parent_end is None:
        parent_years = float(parent_duration)
        end_jd = start_jd + parent_years * year_duration
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_years = (end_jd - start_jd) / year_duration

    if end_jd <= start_jd:
        return []

    children = []

    # -------- Rāśi-bhukthi (only for L2) --------------------------------
    if use_rasi_bhukthi_variation and len(path) == 1:
        if jd is None or place is None:
            raise ValueError("jd and place are required for rasi-bhukthi at L2.")
        # Determine Mahā lord's rāśi from birth chart (D1 unless overridden)
        planet_positions = charts.divisional_chart(jd, place, divisional_chart_factor=divisional_chart_factor)
        maha_lord_rasi = planet_positions[parent_lord + 1][1][0]

        # Get ordered starts of rāśi-bhukthi for this Mahā
        # Expected: OrderedDict-like {child_lord: child_start_jd, ...}
        rasi_bhuktis = _vimsottari_rasi_bhukthi(parent_lord, maha_lord_rasi, start_jd)
        if not rasi_bhuktis:
            return []

        items = list(rasi_bhuktis.items())
        for idx, (child_lord, child_start_jd) in enumerate(items):
            # next start or parent end
            child_end_jd = end_jd if idx == len(items) - 1 else items[idx + 1][1]
            # Emit row
            children.append([
                path + (child_lord,),
                _jd_to_tuple(child_start_jd),
                _jd_to_tuple(child_end_jd),
            ])

        # Force numeric closure just in case
        if children:
            children[-1][2] = _jd_to_tuple(end_jd)

        return children

    # -------- Planetary partition (default) ------------------------------
    # Ordering/direction per antardhasa_option
    lord = parent_lord
    if antardhasa_option in (3, 4):
        lord = vimsottari_next_adhipati(parent_lord, direction=+1)
    elif antardhasa_option in (5, 6):
        lord = vimsottari_next_adhipati(parent_lord, direction=-1)
    dirn = +1 if antardhasa_option in (1, 3, 5) else -1

    H = float(human_life_span_for_vimsottari_dhasa)
    jd_cursor = start_jd

    # Iterate over 9 lords (Vimśottarī cycle)
    for _ in range(len(const.vimsottari_adhipati_list)):
        Y = float(vimsottari_dict[lord])  # already tribhagi-scaled if that mode was used upstream
        child_years = parent_years * (Y / H)
        child_end_jd = jd_cursor + child_years * year_duration

        # Clamp to parent end
        if child_end_jd > end_jd:
            child_end_jd = end_jd

        if child_end_jd > jd_cursor:
            children.append([
                path + (lord,),
                _jd_to_tuple(jd_cursor),
                _jd_to_tuple(child_end_jd),
            ])

        jd_cursor = child_end_jd
        if jd_cursor >= end_jd:
            break

        # Next child lord
        lord = vimsottari_next_adhipati(lord, direction=dirn)

    # Ensure exact closure
    if children:
        children[-1][2] = _jd_to_tuple(end_jd)
    return children
def get_running_dhasa_for_given_date(
    current_jd,
    jd,
    place,
    dhasa_level_index=6,
    **kwargs
):
    """
    Vimśottarī-specific runner that finds the running daśā at the requested depth.

    Parameters
    ----------
    current_jd : float
        Julian day of the date/time to evaluate.
    jd : float
        Birth Julian day (with time).
    place : drik.Place
        Birth place object.
    dhasa_level_index : int, default 6
        Target depth:
          1=Mahā, 2=Antara, 3=Pratyantara, 4=Sūkṣma, 5=Prāṇa, 6=Dehā
    **kwargs :
        Passed through to get_vimsottari_dhasa_bhukthi and vimsottari_immediate_children, e.g.:
          - star_position_from_moon=1
          - use_tribhagi_variation=False
          - use_rasi_bhukthi_variation=False      # only applies at L2 (Mahā → Antara)
          - divisional_chart_factor=1
          - chart_method=1
          - seed_star=3
          - antardhasa_option=1
          - dhasa_starting_planet=1

    Returns
    -------
    (lords_tuple, start_tuple, end_tuple)
        The running period at the requested depth, where:
          - lords_tuple is a tuple of ints (length == dhasa_level_index)
          - start_tuple and end_tuple are (Y, M, D, fractional_hour)
        Intervals follow utils’ half-open semantics via the sentinel pattern.
    """

    # -------- helpers ----------------------------------------------------
    def _as_tuple_lords(x):
        return (x,) if isinstance(x, int) else tuple(x)

    def _normalize_level1_rows_for_utils(maha_rows):
        """
        Accepts either:
          - current 2-field shape: [lord_scalar, start_tuple]
          - standardized 3-field shape: [(lord,), start_tuple, duration_years]
        Returns: list of (lords_tuple, start_tuple) for utils.
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

    def _to_utils_periods(children_rows, parent_end_tuple):
        """
        children_rows: list of [lords_tuple, start_tuple, end_tuple]
        -> returns list of (lords_tuple, start_tuple) **plus** a sentinel
           (any_lords, parent_end_tuple) so utils can infer [start, next_start)
           for the final child as well.
        """
        if not children_rows:
            return []
        proj = [(row[0], row[1]) for row in children_rows]
        # Append sentinel row with start == parent_end (lords won’t be selected)
        proj.append((children_rows[-1][0], parent_end_tuple))
        return proj

    # -------- clamp target depth ----------------------------------------
    try:
        target_depth = int(dhasa_level_index)
    except Exception:
        target_depth = 6
    target_depth = max(1, min(6, target_depth))

    # -------- Level 1: Mahā ---------------------------------------------
    # get_vimsottari_dhasa_bhukthi returns (vim_bal, rows)
    _vim_bal, maha_rows_raw = get_vimsottari_dhasa_bhukthi(
        jd=jd,
        place=place,
        dhasa_level_index=1,  # Mahā only
        **kwargs
    )
    maha_for_utils = _normalize_level1_rows_for_utils(maha_rows_raw)
    running_all = []
    # Running Mahā
    rd = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    # rd: (lords_or_scalar, start_tuple, end_tuple)
    lords = _as_tuple_lords(rd[0])
    running = [lords, rd[1], rd[2]]
    running_all.append(running)
    if target_depth == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
        return running_all

    # -------- Levels 2..target_depth ------------------------------------
    # Unpack options used by vimsottari_immediate_children
    antardhasa_option = kwargs.get("antardhasa_option", 1)
    use_rasi_bhukthi_variation = kwargs.get("use_rasi_bhukthi_variation", False)
    divisional_chart_factor = kwargs.get("divisional_chart_factor", 1)

    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        # For L2 only, optionally use rāśi-bhukthi variation if requested.
        use_rasi = (use_rasi_bhukthi_variation and len(parent_lords) == 1 and depth == 2)

        # Expand only this parent (children come back as [(lords_with_child), start, end])
        children = vimsottari_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            antardhasa_option=antardhasa_option,
            use_rasi_bhukthi_variation=use_rasi,
            jd=jd if use_rasi else None,
            place=place if use_rasi else None,
            divisional_chart_factor=divisional_chart_factor if use_rasi else 1,
        )

        if not children:
            raise ValueError("No children generated; check parent span or child generator options.")

        # Prepare (lords, start) + sentinel for utils
        periods_for_utils = _to_utils_periods(children, parent_end_tuple=parent_end)

        # Select running child at this depth
        rd_k = utils.get_running_dhasa_for_given_date(current_jd, periods_for_utils)
        lords_k = _as_tuple_lords(rd_k[0])
        running = [lords_k, rd_k[1], rd_k[2]]
        running_all.append(running)
    return running_all

def nakshathra_dhasa_progression(
    jd_at_dob, place, jd_current,
    star_position_from_moon=1,
    use_tribhagi_variation=False,
    use_rasi_bhukthi_variation=False,
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
    
    DLI = dhasa_level_index
    _,vd = get_vimsottari_dhasa_bhukthi(jd_at_dob, place, star_position_from_moon, use_tribhagi_variation, 
                                         use_rasi_bhukthi_variation, divisional_chart_factor=divisional_chart_factor, 
                                         chart_method=chart_method, 
                                         seed_star=seed_star, antardhasa_option=antardhasa_option,
                                         dhasa_starting_planet=dhasa_starting_planet, 
                                         dhasa_level_index=DLI)
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
    progression_correction = (prog_long - planet_long)%360
    print('dhasa_start planet',dhasa_starting_planet,'progression correction',progression_correction,
          'divisional_chart_factor',divisional_chart_factor)
    if get_running_dhasa:
        return progression_correction, vdc
    else:
        return progression_correction
    """
    pnak = drik.nakshatra_pada(prog_long)
    #print(dhasa_starting_planet,'Progressed_longitude',utils.NAKSHATRA_LIST[pnak[0]-1],utils.deg_to_sign_str(prog_long),
    #      'correction',progression_correction)
    #mpl += anchor_correction
    ppl = charts.get_nakshathra_dhasa_progression_longitudes(jd_at_dob, place, planet_progression_correction=progression_correction,
                                                             divisional_chart_factor=divisional_chart_factor,
                                                             chart_method=chart_method)
    return ppl
    """
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
    DLI = const.MAHA_DHASA_DEPTH.DEHA; rb_var = True
    print("Dehā        :", get_running_dhasa_for_given_date(current_jd, jd_at_dob, place, dhasa_level_index=DLI,
                                                            use_rasi_bhukthi_variation=rb_var))
    print('new method elapsed time',time.time()-start_time)
    start_time = time.time()
    _,ad = get_vimsottari_dhasa_bhukthi(jd_at_dob, place,dhasa_level_index=DLI,use_rasi_bhukthi_variation=rb_var)
    print(utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad, DLI,extract_running_period_for_all_levels=True))
    print('old method elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.vimsottari_tests()
