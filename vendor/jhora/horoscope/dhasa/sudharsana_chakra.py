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
from jhora.horoscope.chart import charts
from jhora import const, utils
from jhora.panchanga import drik
def sudharshana_chakra_chart(jd_at_dob,place,dob,years_from_dob=1,divisional_chart_factor=1):
    jd_at_years = drik.next_solar_date(jd_at_dob, place, years=years_from_dob)
    planet_positions = charts.divisional_chart(jd_at_years,place,divisional_chart_factor=divisional_chart_factor)
    #retrograde_planets = charts.planets_in_retrograde(planet_positions)
    retrograde_planets = drik.planets_in_retrograde(jd_at_years,place)
    natal_chart = utils.get_house_planet_list_from_planet_positions(planet_positions)
    #print('natal_chart',natal_chart)
    lagna_house = planet_positions[0][1][0]
    moon_house = planet_positions[2][1][0]
    sun_house = planet_positions[1][1][0]
    #print('lagna/moon/sun house natal chart',lagna_house,moon_house,sun_house)
    lagna_chart = [((p+lagna_house)%12,natal_chart[(p+lagna_house)%12]) for p in range(12)]
    #print('lagna_chart',lagna_chart)
    moon_chart = [((p+moon_house)%12,natal_chart[(p+moon_house)%12]) for p in range(12)]
    #print('moon_chart',moon_chart)
    sun_chart = [((p+sun_house)%12,natal_chart[(p+sun_house)%12]) for p in range(12)]
    #print('sun_chart',sun_chart)
    return [lagna_chart,moon_chart,sun_chart,retrograde_planets]

def _sudharsana_antardhasa_seeds(dhasa_triple,planet_positions=None,antardhasa_from_lord_of_dhasa_sign=False):
    dl1,dl2,dl3 = dhasa_triple
    if not antardhasa_from_lord_of_dhasa_sign:
        return [[(dl1+h)%12,(dl2+h)%12,(dl3+h)%12] for h in range(12)]
    antardhasa_lords = [const._house_owners_list[ds] for ds in dhasa_triple]
    antardhasa_triple = [planet_positions[al+1][1][0] for al in antardhasa_lords]
    dl1,dl2,dl3 = antardhasa_triple
    return [[(dl1+h)%12,(dl2+h)%12,(dl3+h)%12] for h in range(12) ]
from functools import lru_cache

def sudharsana_chakra_dhasa_for_divisional_chart(
    jd_at_dob,
    place,
    divisional_chart_factor=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,   # 1=Maha, 2=Antara, 3=Pratyantara, 4=Sukshma, 5=Prana, 6=Dehantara
    antardhasa_from_lord_of_dhasa_sign=False,
    years_from_dob = 1,
    chart_method=1,
    use_sidereal=False
):
    """
    Returns rows shaped as:
      [ [triple_lvl1, triple_lvl2, ..., triple_lvlN], (Y, M, D, fractional_hours), duration_in_years ]

    Where each triple is a tuple: (lagna_house, moon_house, sun_house) for that level.
    """

    # --- Depth
    try:
        depth = int(dhasa_level_index)
    except Exception:
        depth = const.MAHA_DHASA_DEPTH.ANTARA
    depth = max(1, min(depth, 6))  # clamp 1..6

    # --- Base chart & roots (Lagna, Moon, Sun)
    planet_positions = charts.divisional_chart(
        jd_at_dob, place, divisional_chart_factor=divisional_chart_factor, chart_method=chart_method
    )
    lagna_house = planet_positions[0][1][0]
    moon_house  = planet_positions[const.MOON_ID + 1][1][0]
    sun_house   = planet_positions[const.SUN_ID + 1][1][0]
    base_triple = (lagna_house, moon_house, sun_house)  # tuple for cache keys

    # --- Year length & stepping
    year_len = const.sidereal_year if use_sidereal else const.tropical_year

    # Anchor to the first year start; this equals jd_at_dob for years_from_dob=1
    jd0 = drik.next_solar_date(jd_at_dob, place, years=years_from_dob, use_sidereal=use_sidereal)

    # Constant step between **leaf** periods (in JD days)
    step_jd = year_len / (12 ** (depth - 1))

    # Exact duration in years for the **leaf** level
    duration_years = 1.0 / (12 ** (depth - 1))

    # --- Utilities
    def _roll_triple(tri, k):
        """Rotate a triple by +k mod 12 (used ONLY for Maha rotation per year)."""
        return ((tri[0] + k) % 12, (tri[1] + k) % 12, (tri[2] + k) % 12)

    @lru_cache(maxsize=None)
    def _seeds_for(tri):
        """
        Return the 12 triples for the next level, computed ONCE for a triple.
        """
        seed_list = _sudharsana_antardhasa_seeds(
            list(tri),  # original helper expects list-like
            planet_positions=planet_positions,
            antardhasa_from_lord_of_dhasa_sign=antardhasa_from_lord_of_dhasa_sign
        )
        # Normalize to tuples for hashability/caching
        return tuple(tuple(s) for s in seed_list)

    # Positional weight for a digit at level L (1-based), in base-12 number of length=depth
    # k = Σ (i_L * 12^(depth - L)), with i_L ∈ {0..11}
    def _weight(level_1_based):
        return 12 ** (depth - level_1_based)

    results = []

    # --- Recursive descent across levels (choosing base-12 digits i ∈ {0..11})
    def _recurse(level, parent_triple, path_triples, k_so_far):
        """
        level: 1..depth
        parent_triple:
          - For level==1, this is the BASE triple (we'll rotate it)
          - For level>=2, this is the triple at the previous level used to compute seeds
        path_triples: list of triples collected so far (each triple is a tuple)
        k_so_far: accumulated flat index from higher levels (0-based)
        """
        if level == 1:
            # Level 1 (Maha): 12 years, rotate base triple by year index (0..11)
            w = _weight(level)  # 12^(depth-1)
            for i1 in range(12):
                triple1 = _roll_triple(parent_triple, i1)
                k1 = k_so_far + i1 * w
                if depth == 1:
                    # Leaf at Level 1
                    start_jd = jd0 + k1 * step_jd
                    # *** CHANGED: wrap the path (which is [triple1]) ***
                    results.append([[triple1], utils.jd_to_gregorian(start_jd), duration_years])
                else:
                    _recurse(level + 1, triple1, [triple1], k1)
            return

        # Level >= 2:
        # Compute the 12 next-level triples ONCE for this level's parent triple
        seeds = _seeds_for(parent_triple)
        w = _weight(level)  # 12^(depth - level)
        for i in range(12):
            triple_i = seeds[i]  # USE AS-IS (no extra rotations!)
            k_i = k_so_far + i * w
            new_path = path_triples + [triple_i]
            if level == depth:
                # Leaf: produce one row
                start_jd = jd0 + k_i * step_jd
                # *** CHANGED: wrap the full path in a list as the first element ***
                results.append([new_path, utils.jd_to_gregorian(start_jd), duration_years])
            else:
                _recurse(level + 1, triple_i, new_path, k_i)

    # Kick off recursion at Level 1 with the base triple (unrotated); rotation happens inside
    _recurse(level=1, parent_triple=base_triple, path_triples=[], k_so_far=0)

    # Already generated in strict base-12 order → strictly increasing start times
    return results

if __name__ == "__main__":
    utils.set_language('en')
    chart_72 = ['','','7','5/0','3','2','','','8','6','1','4/L']
    print('chart_72',chart_72)
    chart_72_lagna = []
    dob = (1963,8,7)
    tob = (21,14,0)
    place = drik.Place('unknown',21+27.0/60, 83+58.0/60, +5.5)
    dob = drik.Date(1996,12,7); tob = (10,34,0); place = drik.Place('Chennai,India',13.03862,80.261818,5.5)
    jd = utils.julian_day_number(dob,tob);jd_utc = jd - place.timezone/24.0
    years_from_dob = 1 # 17
    divisional_chart_factor = 1
    jd_at_dob = utils.julian_day_number(dob, tob)
    pp = charts.divisional_chart(jd_at_dob, place, divisional_chart_factor)
    jd_at_years = jd_at_dob + years_from_dob * const.sidereal_year
    lsd,msd,ssd,_ = sudharshana_chakra_chart(jd_at_dob, place, dob, years_from_dob, divisional_chart_factor)
    print(lsd,'\n',msd,'\n',ssd)
    scd = sudharsana_chakra_dhasa_for_divisional_chart(jd_at_dob,place,divisional_chart_factor,
                                                       dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
                                                       antardhasa_from_lord_of_dhasa_sign=True)
    for row in scd:
        print(row)