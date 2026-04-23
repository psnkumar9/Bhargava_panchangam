
#!/usr/bin/env python
"""
        STILL  UNDER EXPERIMENTATION - DO NOT USE THIS YET
"""
# -*- coding: UTF-8 -*-
# GNU Affero General Public License v3 or later
# See <http://www.gnu.org/licenses/>.

from datetime import datetime, timedelta
import swisseph as swe

# PyJHora stack
from jhora import const, utils
from jhora.panchanga import drik
from jhora.horoscope.chart import charts, house, arudhas
from jhora.horoscope.dhasa.graha import vimsottari
from jhora.horoscope.dhasa.raasi import kalachakra
from jhora.horoscope.dhasa.annual import patyayini
from jhora.horoscope.transit.tajaka import annual_chart, both_planets_within_their_deeptamsa
from jhora.horoscope.transit.saham import vivaha_saham_from_jd_place

# ---------- Config ----------
_marriage_age_year_range = (20, 32)

# Defaults; can be overridden via function params
STRICT_PVR_MODE_DEFAULT = True
EXPLORATORY_TOP_K = 5

# Strict criteria thresholds (general defaults, not overfit)
STRICT_VS_TIER_MIN = 0                 # Venus–Saham @ VF start is context (not a hard criterion)
STRICT_REQUIRE_PATYAYINI = True        # require Patyayini *major* lord month
STRICT_REQUIRE_ITHASALA_OR_JUPITER = True

# Month-level transiting Venus vs annual Saham proximity (ON by default; useful to pin month/day)
USE_TRANSITING_VENUS_SAHAM_PROXIMITY = True
VENUS_SAHAM_TIER2 = 2.0   # degrees
VENUS_SAHAM_TIER1 = 5.0   # degrees

# Year-evidence minimum required by strict
YEAR_EVIDENCE_MIN = 2

# ---- NEW toggles per discussion ----
# Prefer Saturn AD in strict mode when D-9 shows Saturn aspects D-9 7th or its lord
PREFER_SATURN_AD_WHEN_D9_SUPPORTS = True
# Keep slow-planet (Jupiter/Saturn) aspect 'closeness' out of month/day ranking (we already do)
EXCLUDE_SLOW_ASPECTS_FROM_MONTH = True

# --- Debug toggle for PVR verification ---
DEBUG_PVR = False

SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

def _dbg(*args):
    if DEBUG_PVR:
        print(*args)

def _pname(pid):
    try:
        names = getattr(utils, 'PLANET_NAMES', None)
        if names and isinstance(pid, int) and 0 <= pid < len(names):
            return names[pid]
    except Exception:
        pass
    fallback = {
        const.SUN_ID: "Sun", const.MOON_ID: "Moon", const.MARS_ID: "Mars",
        const.MERCURY_ID: "Mercury", const.JUPITER_ID: "Jupiter",
        const.VENUS_ID: "Venus", const.SATURN_ID: "Saturn",
        getattr(const, 'RAHU_ID', 7): "Rahu", getattr(const, 'KETU_ID', 8): "Ketu"
    }
    if pid == 'L': return "Lagna"
    return fallback.get(pid, str(pid))

# ---------------- Feature-based scoring layer ----------------

DEFAULT_WEIGHTS = {
    # Year weights (independent confirmers)
    'yr.scd_jup_match': 3.0,    # strong year confirmer (Jupiter == SCD(D9) seed) (kept for transparency)
    'yr.scd_ven_match': 1.0,    # soft year confirmer (Venus == SCD(D9) seed)
    'yr.md_viable':      2.0,
    'yr.ad_viable':      1.0,
    'yr.tajaka_year_tier': 0.5,  # annual Venus–Saham is *context*, not decider
    'yr.kcd_support':    0.5,
    'yr.nd9_support':    0.0,    # keep 0 unless you wire it

    # Month weights
    'mo.major_role':     3.0,    # 3>Saham/Muntha month > 2>Venus/7L/UL/VS-lord > 1>other MAJOR > 0
    'mo.ithasala_tier':  1.5,    # poorna/weak help crystallize month
    'mo.jupiter_transit':1.0,    # 0..3
    'mo.subslice_presence': 0.2, # small nudge (info)
    'mo.cultural':       0.1,    # placeholder
    'mo.vs_month_tier':  1.0,    # transiting Venus vs annual Saham mid-month proximity
    'mo.in_scd_jup_year': 0.75   # NEW: prefer months inside the SCD(Jupiter) VF year
}

def _infer_major_role_from_dt(decision_trace: dict) -> int:
    """
    Map MAJOR month → role tier (3,2,1,0), using computed weight:
      3 = Saham-lord or Muntha-lord month
      2 = Venus/7L/UL/VS-lord month
      1 = other MAJOR
      0 = no MAJOR overlap
    """
    return int(decision_trace.get('patyayini_major_weight', 0))

def _extract_features_for_candidate(c, derived, enable_vs_month=False):
    yr, mo = c['_rank_key']
    md_pass, ad_pass, scd_score, taj_tier = yr

    reasons = c['reasons']
    dt = reasons.get('decision_trace', {})

    scd_jup_match = 1 if reasons.get('scd_jup_match', 0) else 0
    scd_ven_match = 1 if reasons.get('scd_ven_match', 0) else 0

    kcd_support = int(reasons.get('kcd', 0))
    nd9_support = int(reasons.get('cnd9', 0))

    # Month-level
    ith_orb = reasons.get('ithasala_orb', 999)
    ith_tier = 2 if ith_orb == 0 else (1 if ith_orb == 1 else 0)
    jup = int(reasons.get('jupiter_transit', 0))
    subslice = 1 if reasons.get('patyayini_hit', False) else 0
    cultural = 1 if reasons.get('cultural', 0) else 0
    major_role = _infer_major_role_from_dt(dt)

    vs_month_tier = 0
    if enable_vs_month:
        vs_month_tier = int(dt.get('vs_month_tier', 0))

    in_scd_jup_year = int(dt.get('in_scd_jup_year', 0))  # NEW

    feats = {
        # Year
        'yr.scd_jup_match': scd_jup_match,
        'yr.scd_ven_match': scd_ven_match,
        'yr.md_viable': int(bool(md_pass)),
        'yr.ad_viable': int(bool(ad_pass)),
        'yr.tajaka_year_tier': int(taj_tier),
        'yr.kcd_support': kcd_support,
        'yr.nd9_support': nd9_support,

        # Month
        'mo.major_role': int(major_role),
        'mo.ithasala_tier': int(ith_tier),
        'mo.jupiter_transit': jup,
        'mo.subslice_presence': subslice,
        'mo.cultural': cultural,
        'mo.vs_month_tier': int(vs_month_tier),
        'mo.in_scd_jup_year': in_scd_jup_year,  # NEW
    }
    return feats

def _score_from_features(feats, weights=None):
    w = weights or DEFAULT_WEIGHTS
    return sum(feats.get(k, 0) * w.get(k, 0.0) for k in feats.keys())

# ---------------- Year evidence aggregator ----------------

def _year_evidence(yr_tuple, reasons):
    """
    Aggregate *independent* year confirmers into a single integer score and an explanation vector.
    yr_tuple = (md_pass, ad_pass, scd_score, taj_tier)
    reasons  includes: scd_jup_match, scd_ven_match, kcd, etc.

    PVR-hierarchy tweak:
      - SCD(Jupiter) counts as +2 (dominant year confirmer)
      - SCD(Venus) counts as +1 (soft)
    """
    md, ad, scd, taj = yr_tuple
    ev = 0
    vec = {}

    jup = int(bool(reasons.get('scd_jup_match', 0)))
    ven = int(bool(reasons.get('scd_ven_match', 0)))

    if jup:
        ev += 2; vec['scd_jup'] = 2
    elif ven:
        ev += 1; vec['scd_ven'] = 1

    if md: ev += 1; vec['md'] = 1
    if ad: ev += 1; vec['ad'] = 1

    if int(taj) >= 1: ev += 1; vec['vf_vs_tier'] = int(taj)  # annual Venus–Saham ≤5°/≤2°
    kcd = int(reasons.get('kcd', 0))
    if kcd >= 1: ev += 1; vec['kcd'] = kcd

    return ev, vec

# ---------- Public wrapper (jd/place) ----------
def predict_marriage_windows_from_jd_place(
    jd, place, start_year=None, end_year=None, divisional_chart_factor=1,
    marriage_age_range=None,
    strict=None,            # override strict behavior for this call
    top_k=None              # override top-K size for this call
):
    """
    Orchestrates over a year range with feature-model strict-first → exploratory fallback.
    """
    # ---- behavior defaults ----
    if strict is None:
        strict = STRICT_PVR_MODE_DEFAULT
    if top_k is None:
        top_k = EXPLORATORY_TOP_K

    # ---- Inputs / defaults ----
    marriage_age_range = _marriage_age_year_range if marriage_age_range is None else marriage_age_range
    yb, _, _, _ = utils.jd_to_gregorian(jd)

    allowed_min_year = yb + marriage_age_range[0]
    allowed_max_year = yb + marriage_age_range[1]

    if start_year is None:
        start_year = allowed_min_year
    if end_year is None:
        end_year = allowed_max_year

    iter_start_year = max(start_year, allowed_min_year)
    iter_end_year   = min(end_year, allowed_max_year)
    if iter_start_year > iter_end_year:
        return []

    # ---- collect chart information  ----
    rasi_planet_positions = charts.divisional_chart(jd, place, divisional_chart_factor=1)
    chart_1d_rasi = utils.get_house_planet_list_from_planet_positions(rasi_planet_positions)
    p_to_h_rasi = utils.get_planet_house_dictionary_from_planet_positions(rasi_planet_positions)

    navamsa_planet_positions = charts.divisional_chart(jd, place, divisional_chart_factor=9)
    chart_1d_d9 = utils.get_house_planet_list_from_planet_positions(navamsa_planet_positions)
    p_to_h_d9 = utils.get_planet_house_dictionary_from_planet_positions(navamsa_planet_positions)

    derived = _collect_marriage_primitives(
        jd, place,
        rasi_planet_positions, chart_1d_rasi, p_to_h_rasi,
        navamsa_planet_positions, chart_1d_d9, p_to_h_d9
    )

    # Vimshottari segments (MD/AD time ranges)
    _, vdb_info = vimsottari.get_vimsottari_dhasa_bhukthi(jd, place, divisional_chart_factor=divisional_chart_factor)
    segments = _expand_to_md_ad_segments(vdb_info)

    candidates = []
    cand_counter = 0

    for year in range(iter_start_year, iter_end_year + 1):
        # Build both VF contexts (current and previous) for this calendar year
        scd_cur  = _sudarsana_chakra_year_info(jd, place, year,   chart_1d_d9)
        scd_prev = _sudarsana_chakra_year_info(jd, place, year-1, chart_1d_d9)

        tajaka_cur  = _get_varshaphala_marriage_triggers(jd, place, year,   derived)
        tajaka_prev = _get_varshaphala_marriage_triggers(jd, place, year-1, derived)

        # Year-level debug (for current VF)
        _dbg(f"[PVR-CHK][YEAR] y={year} SCD(D9)={scd_cur.get('scd_rasi_d9')} "
             f"annD9 Jup={scd_cur.get('vf_jupiter_sign_d9')} Ven={scd_cur.get('vf_venus_sign_d9')} | "
             f"D1 VS(sign)={tajaka_cur.get('vivaha_saham_sign')} Muntha_lord={_pname(tajaka_cur.get('muntha_lord'))}")

        # Calendar-year Vimshottari slice (dominant)
        year_start = datetime(year, 1, 1, 0, 0, 0)
        year_end   = datetime(year, 12, 31, 23, 59, 59)
        md_ad_pd_year = _active_vimsottari_in_window(segments, year_start, year_end)
        md_pass = _passes_md_gate(md_ad_pd_year['md'], derived) if md_ad_pd_year else False
        ad_pass = _passes_ad_gate(md_ad_pd_year['ad'], derived) if md_ad_pd_year else False

        # Optional year confirmers (calendar-year basis)
        kcd_score = _score_kalachakra_support(jd, place, year, derived)
        nd9_score = _score_compressed_d9_narayana(jd, place, year_start, year_end, derived)

        # --- Month loop (per-month VF selection) ---
        for month in range(1, 13):
            month_start = datetime(year, month, 1)
            month_end = _end_of_month(year, month)

            # Choose the VF year applicable to this month
            use_prev = (month_end < tajaka_cur['vf_start'])
            use_tajaka = tajaka_prev if use_prev else tajaka_cur
            use_scd    = scd_prev if use_prev else scd_cur

            # Year tuple for the *selected* VF (tajaka year strength is from the selected bundle)
            taj_year_strength, taj_year_meta = _year_strength_from_tajaka(use_tajaka, derived)
            scd_score = _score_scd_year_support(use_scd, derived)
            year_tuple_val = (int(md_pass), int(ad_pass), int(scd_score), int(taj_year_strength))

            # --- Month-level signals ---
            md_ad_pd = _active_vimsottari_in_window(segments, month_start, month_end)
            if not md_ad_pd:
                continue

            # Monthly Jupiter transit: with verbose debug
            jup_score, jup_dbg = _get_monthly_jupiter_transit_support_with_dbg(jd, place, year, month, derived)

            tajaka_score, tajaka_detail = _score_tajaka_month(use_tajaka, month_start, month_end, place, derived)
            cultural = _score_cultural_month(month_start, month_end)

            # Build month tuple (for transparency/debug)
            ith_tier = _ithasala_tier_from_detail(tajaka_detail)
            vs_tier  = _venus_saham_tier_from_detail(tajaka_detail)
            paty_hit = bool(tajaka_detail.get('patyayini_hit', False))

            month_tuple_val = (int(paty_hit), int(vs_tier), int(ith_tier), int(jup_score), int(bool(cultural)))

            # Major-lord flags from detail and MAJOR-first ranking elements
            major_hit    = bool(tajaka_detail.get('patyayini_major_hit', False))
            major_lord   = tajaka_detail.get('patyayini_major_lord', None)
            major_weight = int(tajaka_detail.get('patyayini_major_weight', 0))
            vs_month_tier = int(tajaka_detail.get('vs_month_tier', 0))

            # Rank tuple (for introspection/debug only)
            rank_month = (major_weight, int(major_hit)) + month_tuple_val

            # Explanations / reasons
            reasons = _collect_reasons(md_ad_pd, jup_score, use_scd, tajaka_detail, kcd_score, nd9_score, cultural, derived)
            reasons['jupiter_transit_debug'] = jup_dbg  # attach PVR-like transit logs

            scd_jup_flag = 1 if reasons.get('scd_jup_match', 0) else 0  # NEW
            reasons['decision_trace'] = {
                'year_tuple': year_tuple_val,
                'month_tuple': month_tuple_val,
                'md_gate': md_pass,
                'ad_gate_year': ad_pass,
                'tajaka_year_strength': taj_year_strength,
                'year_meta': taj_year_meta,
                'patyayini_major_lord': major_lord,
                'patyayini_major_hit': major_hit,
                'patyayini_major_weight': major_weight,
                'vs_month_tier': vs_month_tier,
                'in_scd_jup_year': scd_jup_flag,   # NEW: month belongs to SCD(Jup) VF bundle
            }

            cand_counter += 1
            # Add candidate
            candidates.append({
                'year': year,
                'month': month,
                'window': (month_start, month_end),
                'score': 0,  # legacy field; model score will be computed below
                'reasons': reasons,
                '_rank_key': (year_tuple_val, rank_month),
                '_tajaka': use_tajaka,
                'candidate_id': f"{cand_counter}"
            })

    if not candidates:
        return []

    # --------- Feature model scoring + year-evidence + global sort ----------
    for c in candidates:
        feats = _extract_features_for_candidate(c, derived, enable_vs_month=USE_TRANSITING_VENUS_SAHAM_PROXIMITY)
        c['_feats'] = feats
        c['_score_model'] = _score_from_features(feats, DEFAULT_WEIGHTS)

        # year evidence (primary year selector)
        yr = c['_rank_key'][0]
        ev, ev_vec = _year_evidence(yr, c['reasons'])
        c['_year_ev'] = ev
        c['reasons']['year_evidence'] = {'score': ev, 'vector': ev_vec}

    # NEW: Prioritize SCD-Jupiter years globally
    candidates.sort(
        key=lambda c: (
            -(1 if c['reasons'].get('scd_jup_match', 0) else 0),  # PRIMARY: SCD-Jupiter year first
            -c['_year_ev'],                                       # then year evidence
            -c['_score_model'],                                   # then model score
            c['year'], c['month']                                 # earliest among equals
        )
    )

    # --- Strict attempt (scan pool; pick best strict-passing by the same ordering) ---
    def _passes_strict_generic(c):
        yr, mo = c['_rank_key']
        reasons = c['reasons']
        dt = reasons.get('decision_trace', {})

        # Year evidence minimum
        if c.get('_year_ev', 0) < YEAR_EVIDENCE_MIN:
            return False

        # Month: require a Patyayini MAJOR month (role >= 1)
        major_role = _infer_major_role_from_dt(dt)    # 0..3
        if STRICT_REQUIRE_PATYAYINI and major_role < 1:
            return False

        # Require Ithasala or Jupiter month support (configurable)
        ith_orb = reasons.get('ithasala_orb', 999)
        ith_tier = 2 if ith_orb == 0 else (1 if ith_orb == 1 else 0)
        jup = reasons.get('jupiter_transit', 0)
        if STRICT_REQUIRE_ITHASALA_OR_JUPITER and not (ith_tier >= 1 or jup >= 1):
            return False

        # ---- NEW: Strict Saturn-AD enforcement when D-9 supports Saturn ----
        if PREFER_SATURN_AD_WHEN_D9_SUPPORTS and derived.get('d9_saturn_flag', False):
            ad_lord = reasons.get('md_ad_pd', {}).get('ad')
            if ad_lord != const.SATURN_ID:
                return False

        return True

    if strict:
        # NEW: If any SCD-Jupiter years exist, restrict the strict pool to them
        any_scd_jup = any(c['reasons'].get('scd_jup_match', 0) for c in candidates)
        pool = [c for c in candidates if (c['reasons'].get('scd_jup_match', 0) or not any_scd_jup)]

        strict_hits = [c for c in pool if _passes_strict_generic(c)]
        if strict_hits:
            strict_hits.sort(
                key=lambda c: (
                    -(1 if c['reasons'].get('scd_jup_match', 0) else 0),
                    -c['_year_ev'], -c['_score_model'],
                    c['year'], c['month']
                )
            )
            best = strict_hits[0]
            yev = best['_year_ev']; yvec = best['reasons']['year_evidence']['vector']
            dt  = best['reasons']['decision_trace']
            _dbg(f"[PVR-DBG][STRICT] Pick {best['year']}-{best['month']:02d} | year_ev={yev} {yvec} | "
                 f"MAJOR_role={dt.get('patyayini_major_weight')} | ith_tier={dt['month_tuple'][2]} | jup={dt['month_tuple'][3]}")

            # Derive one day from Pātyāyinī sub-slices with target priority
            tajaka = best.get('_tajaka')
            annual_pp = tajaka.get('annual_planet_positions') if tajaka else None
            L7 = tajaka.get('annual_7l') if tajaka else None
            ul_sign = derived['ul_d1']
            ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign) if annual_pp is not None else None
            vs_lord = house.house_owner_from_planet_positions(annual_pp, tajaka.get('vivaha_saham_sign')) if tajaka else None
            m_lord  = tajaka.get('muntha_lord') if tajaka else None

            targets = [const.VENUS_ID] + [x for x in [L7, ul_lord, vs_lord, m_lord] if x is not None]
            day, day_meta = _suggest_day_from_patyayini(tajaka, best['window'][0], best['window'][1], targets)

            best['reasons']['final_day'] = day
            best['reasons']['final_day_meta'] = day_meta
            best['reasons']['mode'] = 'strict_single'

            # cleanup
            best.pop('_rank_key', None); best.pop('_tajaka', None)
            best.pop('_feats', None); best.pop('_score_model', None)

            # Pretty candidate label
            best['candidate_id'] = f"{best.get('candidate_id', '?')} of {cand_counter}"
            return [best]

    # --- Fallback: exploratory shortlist (top-K by model score within year-evidence ordering) ---
    candidates.sort(
        key=lambda c: (
            -(1 if c['reasons'].get('scd_jup_match', 0) else 0),
            -c['_year_ev'], -c['_score_model'], c['year'], c['month']
        )
    )
    top = []
    for c in candidates[:top_k]:
        tajaka = c.get('_tajaka')
        annual_pp = tajaka.get('annual_planet_positions') if tajaka else None
        L7 = tajaka.get('annual_7l') if tajaka else None
        ul_sign = derived['ul_d1']
        ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign) if annual_pp is not None else None
        vs_lord = house.house_owner_from_planet_positions(annual_pp, tajaka.get('vivaha_saham_sign')) if tajaka else None
        m_lord  = tajaka.get('muntha_lord') if tajaka else None
        targets = [const.VENUS_ID] + [x for x in [L7, ul_lord, vs_lord, m_lord] if x is not None]

        day, day_meta = _suggest_day_from_patyayini(tajaka, c['window'][0], c['window'][1], targets)
        c['reasons']['suggested_day'] = day
        c['reasons']['suggested_day_meta'] = day_meta
        c['reasons']['mode'] = 'fallback_exploratory'

        # cleanup/debug fields out
        c.pop('_rank_key', None); c.pop('_tajaka', None)
        c.pop('_feats', None); c.pop('_score_model', None)

        c['candidate_id'] = f"{c.get('candidate_id', '?')} of {cand_counter}"
        top.append(c)
    return top

# ---------- Calculation primitives & adapters ----------

def _collect_marriage_primitives(jd, place, pp_rasi, chart_1d_rasi, p_to_h_rasi, pp_d9, chart_1d_d9, p_to_h_d9):
    out = {}
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    out['birth_year'] = by

    # --- D1 core ---
    out['lagna_sign_d1'] = p_to_h_rasi[const._ascendant_symbol]
    out['seventh_house_sign_d1'] = (out['lagna_sign_d1'] + const.HOUSE_7) % 12
    out['seventh_lord_d1'] = house.house_owner_from_planet_positions(pp_rasi, out['seventh_house_sign_d1'])

    out['venus_sign_d1'] = p_to_h_rasi[const.VENUS_ID]
    out['seventh_from_venus_sign_d1'] = (out['venus_sign_d1'] + 6) % 12

    ck_list = house.chara_karakas(pp_rasi)
    out['dk'] = ck_list[-1] if isinstance(ck_list, (list, tuple)) else ck_list

    # UL (A12) in D1 & D9
    al_ul_d1 = arudhas.bhava_arudhas_from_planet_positions(pp_rasi)
    out['ul_d1'] = al_ul_d1[-1]
    al_ul_d9 = arudhas.bhava_arudhas_from_planet_positions(pp_d9)
    out['ul_d9'] = al_ul_d9[-1]

    out['seventh_lord_sign_d1'] = p_to_h_rasi[out['seventh_lord_d1']]
    try:
        out['ul_lord_d1'] = house.house_owner_from_planet_positions(pp_rasi, out['ul_d1'])
    except Exception:
        out['ul_lord_d1'] = None

    ul = out['ul_d1']
    out['ul_supportive_houses_d1'] = {ul, (ul + 2) % 12, (ul + 7) % 12}
    out['ul_terminal_houses_d1'] = {(ul + 1) % 12, (ul + 6) % 12}

    # D9
    out['lagna_sign_d9'] = p_to_h_d9[const._ascendant_symbol]
    out['seventh_house_sign_d9'] = (out['lagna_sign_d9'] + const.HOUSE_7) % 12
    out['seventh_lord_d9'] = house.house_owner_from_planet_positions(pp_d9, out['seventh_house_sign_d9'])

    # Store maps and planet positions and charts
    out['p_to_h_rasi'] = p_to_h_rasi
    out['p_to_h_d9'] = p_to_h_d9
    out['pp_rasi'] = pp_rasi
    out['pp_d9'] = pp_d9
    out['chart_1d_rasi'] = chart_1d_rasi
    out['chart_1d_d9'] = chart_1d_d9

    # D1 & D9 Lagna Lords
    out['ll_d1'] = house.house_owner_from_planet_positions(pp_rasi, out['lagna_sign_d1'])
    out['ll_d9'] = house.house_owner_from_planet_positions(pp_d9, out['lagna_sign_d9'])

    _dbg(f"[PVR-DBG][INIT] Stored pp_rasi={len(pp_rasi)} entries; pp_d9={len(pp_d9)} entries")

    # Night/day flag (Vivaha Saham logic) with fallback (used only for natal contexts)
    try:
        out['night_time_birth'] = drik.is_night_birth(jd, place)
    except Exception:
        y, m, d, hours_local = utils.jd_to_gregorian(jd)
        sunrise_hours = drik.sunrise(jd, place)[0]
        sunset_hours  = drik.sunset(jd, place)[0]
        out['night_time_birth'] = not (sunrise_hours <= hours_local <= sunset_hours)

    # ---- NEW: D-9 Saturn aspects flag for strict AD preference ----
    try:
        sat_asp_7h, sat_asp_7l = _aspect_flags_for(
            const.SATURN_ID,
            chart=out['chart_1d_d9'],
            seventh_house_sign=out['seventh_house_sign_d9'],
            seventh_lord_planet=out['seventh_lord_d9'],
            ctx="D9",
            emit_dbg=False,
            cache={}
        )
        out['d9_saturn_flag'] = bool(sat_asp_7h or sat_asp_7l)
        _dbg(f"[PVR-DBG][INIT] D9 Saturn aspect flag: {out['d9_saturn_flag']} (7H={sat_asp_7h}, 7L={sat_asp_7l})")
    except Exception:
        out['d9_saturn_flag'] = False

    return out

def _expand_to_md_ad_segments(vdb_info):
    """
    vdb_info: [ [md:int, ad:int, 'YYYY-MM-DD ...'], ... ]  (chronological)
    Returns: [{'md':int,'ad':int,'start':datetime,'end':datetime}, ...]
    """
    segs = []
    if not vdb_info:
        return segs
    starts = []
    for row in vdb_info:
        md, ad, s = row
        s = s.split()[0].strip()  # remove time
        y, m, d = map(int, s.split('-'))
        starts.append((md, ad, datetime(y, m, d)))

    for i, (md, ad, start_dt) in enumerate(starts):
        if i < len(starts) - 1:
            end_dt = starts[i+1][2] - timedelta(seconds=1)
        else:
            end_dt = datetime(9999, 12, 31, 23, 59, 59)
        segs.append({'md': md, 'ad': ad, 'pd': None, 'start': start_dt, 'end': end_dt})
    return segs

def _active_vimsottari_in_window(segments, win_start, win_end):
    hits = [s for s in segments if not (s['end'] < win_start or s['start'] > win_end)]
    if not hits:
        return None
    best = max(hits, key=lambda s: (min(s['end'], win_end) - max(s['start'], win_start)).total_seconds())
    return {'md': best['md'], 'ad': best['ad'], 'pd': best.get('pd')}

# ---- Vimshottari gating/scoring ----

def _passes_md_gate(md, derived):
    if md is None:
        return False
    sc = score_planet_marriage_capability(md, derived, tier='md')
    _dbg(f"[PVR-DBG][VIM][MD] {_pname(md)} capability score = {sc}")
    return sc >= 3

def _passes_ad_gate(ad, derived):
    if ad is None:
        return False
    sc = score_planet_marriage_capability(ad, derived, tier='ad')
    _dbg(f"[PVR-DBG][VIM][AD] {_pname(ad)} capability score = {sc}")
    return sc >= 2

def _aspect_flags_for(
    planet,
    *,
    chart,
    seventh_house_sign,
    seventh_lord_planet,
    ctx="D1",
    emit_dbg=True,
    cache=None
):
    """
    Returns (aspects_7th_house, aspects_7th_lord) using PyJHora graha-drishti APIs.
    Keyword-only to prevent accidental positional misuse.
    """
    if cache is None:
        cache = {}
    if chart is None:
        raise ValueError(f"_aspect_flags_for[{ctx}] called without chart")

    cache_key = (ctx, planet)
    if cache_key in cache:
        hit_h, hit_l = cache[cache_key]
        if emit_dbg:
            _dbg(f"[PVR-DBG][ASP][{ctx}] {_pname(planet)} (cached) aspects 7H? {hit_h}; 7L? {hit_l}")
        return hit_h, hit_l

    try:
        if emit_dbg:
            _dbg(f"[PVR-DBG][ASP][{ctx}] Check aspects for {_pname(planet)} | "
                 f"7H={SIGN_NAMES[seventh_house_sign]} | 7L={_pname(seventh_lord_planet)}")
        asp_7h = set(house.planets_aspecting_the_raasi(chart, seventh_house_sign) or [])
        asp_7l = set(house.planets_aspecting_the_planet(chart, seventh_lord_planet) or [])
        if DEBUG_PVR:
            print('asp_7h', asp_7h)
            print('asp_7l', asp_7l)
        hit_h = planet in asp_7h
        hit_l = planet in asp_7l

        if emit_dbg:
            _dbg(f"[PVR-DBG][ASP][{ctx}] 7H {SIGN_NAMES[seventh_house_sign]} aspectors: {[ _pname(p) for p in asp_7h ]}")
            _dbg(f"[PVR-DBG][ASP][{ctx}] 7L {_pname(seventh_lord_planet)} aspectors: {[ _pname(p) for p in asp_7l ]}")
            _dbg(f"[PVR-DBG][ASP][{ctx}] → {_pname(planet)} aspects 7H? {hit_h}; 7L? {hit_l}")

        cache[cache_key] = (hit_h, hit_l)
        return hit_h, hit_l

    except Exception as e:
        if emit_dbg:
            _dbg(f"[PVR-DBG][ASP][{ctx}][ERROR] while checking {_pname(planet)}: {e!r}")
        cache[cache_key] = (False, False)
        return (False, False)

def score_planet_marriage_capability(planet, derived, tier='md'):
    """
    D1 (primary) + D9 (supporting) evidence:
      - D1: 7L, Venus, DK, D1 7H occupancy, D9-good placements, 7-from-Venus, UL sign/lord, UL supportive houses
      - D1: LL, LL-in-11th, aspects to 7H/7L  (PVR-style)
      - D9: LL, LL-in-11th (light), aspects to 7H/7L (light)
    """
    if planet is None:
        return 0

    _dbg(f"[PVR-DBG][VIM][{tier.upper()}] Evaluating {_pname(planet)} for marriage capability...")

    base_if_7L = {'md': 3, 'ad': 3, 'pd': 2}.get(tier, 2)
    bonus = {'md': 1, 'ad': 1, 'pd': 1}.get(tier, 1)

    p_to_h_rasi = derived['p_to_h_rasi']
    p_to_h_d9 = derived['p_to_h_d9']

    score = 0

    # 7th lord in D1
    if planet == derived['seventh_lord_d1']:
        score += base_if_7L
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} is 7th lord in D1 → +{base_if_7L}")

    # Venus / DK connections
    if planet == const.VENUS_ID:
        score += bonus
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} is Venus → +{bonus}")
    if planet == derived['dk']:
        score += bonus
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} is Darakaraka → +{bonus}")

    # Occupying D1 7th house
    if p_to_h_rasi.get(planet, -99) == derived['seventh_house_sign_d1']:
        score += bonus
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} placed in D1 7th house ({SIGN_NAMES[derived['seventh_house_sign_d1']]}) → +{bonus}")

    # Good in D9: Lagna/5/9 and 7th house
    d9_lagna = derived['lagna_sign_d9']
    d9_good = {d9_lagna, (d9_lagna + 4) % 12, (d9_lagna + 8) % 12, derived['seventh_house_sign_d9']}
    if p_to_h_d9.get(planet, -99) in d9_good:
        score += bonus
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} favorably placed in D9 (L/5/9/7H) → +{bonus}")

    # 7th-from-Venus (D1)
    s7v = derived.get('seventh_from_venus_sign_d1')
    if s7v is not None and p_to_h_rasi.get(planet, -99) == s7v:
        score += bonus
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} in D1 7th-from-Venus ({SIGN_NAMES[s7v]}) → +{bonus}")

    # UL sign and UL lord (D1)
    ul_sign = derived.get('ul_d1')
    if ul_sign is not None and p_to_h_rasi.get(planet, -99) == ul_sign:
        score += bonus
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} in UL sign ({SIGN_NAMES[ul_sign]}) → +{bonus}")
    if planet == derived.get('ul_lord_d1'):
        score += bonus
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} is UL lord → +{bonus}")

    # UL supportive houses (1/3/8) tiny nudge
    if p_to_h_rasi.get(planet, -99) in derived.get('ul_supportive_houses_d1', set()):
        score += 1
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} in UL supportive houses (1/3/8 from UL) → +1")

    # ------------------------------------------------------------------
    # PVR-style additions: D1 (primary) + D9 (supporting) evidence
    # ------------------------------------------------------------------

    asp_cache = {}

    # D1 Lagna Lord and LL-in-11th (stronger)
    ll_d1 = derived.get('ll_d1')
    lagna_d1 = derived['lagna_sign_d1']

    if planet == ll_d1:
        score += bonus  # planet IS Lagna Lord (D1)
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} is Lagna Lord in D1 → +{bonus}")
        if p_to_h_rasi.get(planet, -99) == (lagna_d1 + const.HOUSE_11) % 12:
            score += (bonus + 1)  # slightly stronger than a single bonus
            _dbg(f"[PVR-DBG][VIM] {_pname(planet)} (LL) in D1 11th ({SIGN_NAMES[(lagna_d1+const.HOUSE_11)%12]}) → +{bonus+1}")

    # D1 natal aspects to 7th house and 7th lord
    asp7h_d1, asp7l_d1 = _aspect_flags_for(
        planet,
        chart=derived.get('chart_1d_rasi'),
        seventh_house_sign=derived['seventh_house_sign_d1'],
        seventh_lord_planet=derived['seventh_lord_d1'],
        ctx="D1",
        emit_dbg=True,
        cache=asp_cache
    )
    if asp7h_d1:
        score += bonus
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} aspects D1 7th house ({SIGN_NAMES[derived['seventh_house_sign_d1']]}) → +{bonus}")
    if asp7l_d1:
        score += bonus
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} aspects D1 7th lord {_pname(derived['seventh_lord_d1'])} → +{bonus}")

    # D9 Lagna Lord and LL-in-11th (lighter nudge)
    ll_d9 = derived.get('ll_d9')
    lagna_d9 = derived['lagna_sign_d9']

    if planet == ll_d9:
        score += 1  # small nudge for being D9 Lagna Lord
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} is Lagna Lord in D9 → +1")
        if derived['p_to_h_d9'].get(planet, -99) == (lagna_d9 + const.HOUSE_11) % 12:
            score += 1  # small extra nudge for D9 LL in 11th
            _dbg(f"[PVR-DBG][VIM] {_pname(planet)} (LL) in D9 11th ({SIGN_NAMES[(lagna_d9+const.HOUSE_11)%12]}) → +1")

    # D9 natal aspects to 7th house and 7th lord (lighter nudges)
    asp7h_d9, asp7l_d9 = _aspect_flags_for(
        planet,
        chart=derived.get('chart_1d_d9'),
        seventh_house_sign=derived['seventh_house_sign_d9'],
        seventh_lord_planet=derived['seventh_lord_d9'],
        ctx="D9",
        emit_dbg=True,
        cache=asp_cache
    )
    if asp7h_d9:
        score += 1
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} aspects D9 7th house ({SIGN_NAMES[derived['seventh_house_sign_d9']]}) → +1")
    if asp7l_d9:
        score += 1
        _dbg(f"[PVR-DBG][VIM] {_pname(planet)} aspects D9 7th lord {_pname(derived['seventh_lord_d9'])} → +1")

    return score

# ---- Monthly Jupiter transit (with verbose debug) ----
def _get_monthly_jupiter_transit_support_with_dbg(jd, place, year, month, derived):
    """
    Returns (score, debug_lines:list[str]).
      score 0..3:
        +1 Jupiter in Lagna/5/7/9 from D1 Lagna
        +1 Jupiter graha-drishti to D1 7th house
        +1 Jupiter hits 7L-sign OR UL-sign OR 7th-from-Venus (or is in those signs)
      debug_lines emulate PVR narrative: transit sign, aspects to 7H / 7L-sign etc.
    """
    lines = []
    start = datetime(year, month, 1, 12, 0, 0)
    end = _end_of_month(year, month)
    mid = start + (end - start) / 2

    jd_mid_local = swe.julday(mid.year, mid.month, mid.day, mid.hour + mid.minute/60.0 + mid.second/3600.0)
    jd_utc = jd_mid_local - (place.timezone / 24.0)

    jup_lon_abs = drik.sidereal_longitude(jd_utc, const._JUPITER)  # 0..360
    jup_sign, _ = drik.dasavarga_from_long(jup_lon_abs)

    lagna = derived['lagna_sign_d1']
    h7    = derived['seventh_house_sign_d1']
    l7sg  = derived['seventh_lord_sign_d1']
    ulsg  = derived['ul_d1']
    s7v   = derived.get('seventh_from_venus_sign_d1')

    score = 0
    hit_msgs = []

    # 1) Jupiter in Lagna/5/7/9 from Lagna
    good = {lagna, (lagna+4) % 12, (lagna+6) % 12, (lagna+8) % 12}
    if jup_sign in good:
        score += 1
        hit_msgs.append(f"in {SIGN_NAMES[jup_sign]} (L/5/7/9 from Lagna)")

    # 2) Jupiter graha drishti 5/7/9 to 7th house sign
    jup_aspects = {(jup_sign + 4) % 12, (jup_sign + 6) % 12, (jup_sign + 8) % 12}
    if h7 in jup_aspects:
        score += 1
        hit_msgs.append(f"aspects 7th house {SIGN_NAMES[h7]}")

    # 3) Hit 7L-sign OR UL-sign OR 7th-from-Venus
    s7v_hit = (s7v is not None) and (s7v in jup_aspects or jup_sign == s7v)
    l7_hit = (l7sg in jup_aspects or jup_sign == l7sg)
    ul_hit = (ulsg in jup_aspects or jup_sign == ulsg)

    if l7_hit or ul_hit or s7v_hit:
        score += 1
        sub = []
        if l7_hit:
            sub.append(f"7th-lord sign {SIGN_NAMES[l7sg]}")
        if ul_hit:
            sub.append(f"UL sign {SIGN_NAMES[ulsg]}")
        if s7v_hit:
            sub.append(f"7th-from-Venus {SIGN_NAMES[s7v]}")
        hit_msgs.append("hits " + " & ".join(sub))

    if hit_msgs:
        lines.append(f"[PVR-DBG][JUP] Jupiter transit in {SIGN_NAMES[jup_sign]} → " + "; ".join(hit_msgs))
    else:
        lines.append(f"[PVR-DBG][JUP] Jupiter transit in {SIGN_NAMES[jup_sign]} – no supportive aspects")

    return score, lines

# ---- SCD (D9) year info ----
def _sudarsana_chakra_year_info(jd, place, year, chart_1d_d9):
    """
    SCD (D9) year info:
      - offset = (year - birth_year) % 12 = (running_year - 1) % 12
      - seed = natal D9 Lagna + offset
      - we also compute annual D9 at Varshaphala start to read Jup/Ven signs
    """
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    years_from_dob = (year - by)
    running_year   = years_from_dob + 1
    house_offset   = years_from_dob % 12

    # Natal D9 Lagna sign from provided chart_1d_d9
    lagna_sign_d9 = 0
    for sgn, token in enumerate(chart_1d_d9):
        if token and 'L' in token.split('/'):
            lagna_sign_d9 = sgn
            break

    scd_rasi_d9 = (lagna_sign_d9 + house_offset) % 12

    # Annual D9 at VF start
    annual_pp_d9, (vf_y_m_d, vf_hours_local) = annual_chart(
        jd_at_dob=jd, place=place, divisional_chart_factor=9, years=running_year
    )
    vf_hours = _safe_extract_float_hours(vf_hours_local)
    H, M, S = _hours_to_hms(vf_hours)
    vf_start = datetime(vf_y_m_d[0], vf_y_m_d[1], vf_y_m_d[2], H, M, S)

    def _sign_from_pp(pp, pid):
        for pl, (sg, lon) in pp:
            if pl == pid:
                return sg
        return None

    vf_jupiter_sign_d9 = _sign_from_pp(annual_pp_d9, const.JUPITER_ID)
    vf_venus_sign_d9   = _sign_from_pp(annual_pp_d9, const.VENUS_ID)

    _dbg(
        f"[PVR-CHK][SCD] year={year} running_year={running_year} "
        f"offset={house_offset} natal_D9_Lagna={lagna_sign_d9} SCD(D9)={scd_rasi_d9} | "
        f"annual_D9 Jup={vf_jupiter_sign_d9} Ven={vf_venus_sign_d9} vf_start={vf_start}"
    )

    return {
        'running_year': running_year,
        'house_offset': house_offset,
        'scd_rasi_d9': scd_rasi_d9,
        'vf_start': vf_start,
        'vf_jupiter_sign_d9': vf_jupiter_sign_d9,
        'vf_venus_sign_d9': vf_venus_sign_d9
    }

def _score_scd_year_support(scd_info, derived):
    """
    Weighted SCD year confirmers (generalizable default):
      +3 if (annual D9) Jupiter == SCD(D9) seed
      +1 if (annual D9) Venus  == SCD(D9) seed
    """
    if not scd_info:
        return 0
    scd_rasi = scd_info.get('scd_rasi_d9')
    if scd_rasi is None:
        return 0
    score = 0
    if scd_info.get('vf_jupiter_sign_d9') == scd_rasi:
        score += 3
    if scd_info.get('vf_venus_sign_d9') == scd_rasi:
        score += 1
    return score

# ---------- Tajaka (Varshaphala) bundle ----------
def _get_varshaphala_marriage_triggers(jd, place, year, derived):
    """
    Annual (Varshaphala) bundle for the target year (running_year).
    """
    by, bm, bd, bh = utils.jd_to_gregorian(jd)
    years_from_dob = (year - by)
    running_year   = years_from_dob + 1  # e.g., 1998 -> 26th

    # Annual D1 chart for the running year
    annual_pp_d1, (vf_y_m_d, vf_hours_local) = annual_chart(
        jd_at_dob=jd, place=place, divisional_chart_factor=1, years=running_year
    )
    vf_hours = _safe_extract_float_hours(vf_hours_local)
    H, M, S = _hours_to_hms(vf_hours)
    vf_start = datetime(vf_y_m_d[0], vf_y_m_d[1], vf_y_m_d[2], H, M, S)

    # Solar return instant
    jd_years = drik.next_solar_date(jd, place, years=running_year)

    # Vivaha Saham (annual D1) from the annual instant (returns ABS longitude)
    vs_abs_long = vivaha_saham_from_jd_place(jd_years, place, divisional_chart_factor=1)
    vs_sign, vs_lon_in_sign = drik.dasavarga_from_long(vs_abs_long)

    # Venus absolute longitude in annual D1
    ven_abs_long = _get_planet_abs_long_from_positions(annual_pp_d1, const.VENUS_ID)

    # Annual D1: Jup/Ven signs (reference)
    jup_sign = _get_planet_sign_from_annual(annual_pp_d1, const.JUPITER_ID)
    ven_sign = _get_planet_sign_from_annual(annual_pp_d1, const.VENUS_ID)

    # Annual D1: Lagna, LL, 7L
    annual_lagna_sign = _find_lagna_sign_from_positions(annual_pp_d1)
    annual_h7_sign = (annual_lagna_sign + const.HOUSE_7) % 12
    annual_ll = house.house_owner_from_planet_positions(annual_pp_d1, annual_lagna_sign)
    annual_7l = house.house_owner_from_planet_positions(annual_pp_d1, annual_h7_sign)

    # Muntha (natal Lagna + completed years), lord in annual D1
    natal_lagna_sign = derived['lagna_sign_d1']
    muntha_sign = (natal_lagna_sign + years_from_dob) % 12
    muntha_lord = house.house_owner_from_planet_positions(annual_pp_d1, muntha_sign)

    # Patyayini anchored at the SAME solar return instant
    patyayini_raw = patyayini.get_dhasa_bhukthi(jd_years, place, divisional_chart_factor=1, chart_method=1)
    patyayini_schedule = _expand_patyayini_schedule(patyayini_raw)              # sub-slices
    patyayini_major_schedule = _expand_patyayini_major_schedule(patyayini_raw)  # majors

    _dbg(
        f"[PVR-CHK][TAJAKA] year={year} running_year={running_year} vf_start={vf_start} | "
        f"D1 Jup={jup_sign} Ven={ven_sign} | VS(sign,abs)=({vs_sign},{round(vs_abs_long,3)}) | "
        f"Muntha_sign={SIGN_NAMES[muntha_sign]} Muntha_lord={_pname(muntha_lord)} | patyayini_slices={0 if not patyayini_schedule else len(patyayini_schedule)}"
    )
    if patyayini_major_schedule:
        _dbg(f"[PVR-CHK][PATY-MAJOR] {[(d['lord'], d['start'].date(), d['end'].date()) for d in patyayini_major_schedule]}")

    tajaka = {
        'vf_start': vf_start,
        'years_after_dob': years_from_dob,
        'annual_planet_positions': annual_pp_d1,
        'jupiter_sign': jup_sign,
        'venus_sign': ven_sign,
        'annual_lagna_sign': annual_lagna_sign,
        'annual_ll': annual_ll,
        'annual_7l': annual_7l,
        'vivaha_saham_sign': vs_sign,
        'vivaha_saham_abs_long': vs_abs_long,
        'venus_abs_long': ven_abs_long,
        'muntha_sign': muntha_sign,
        'muntha_lord': muntha_lord,
        'patyayini_schedule': patyayini_schedule,
        'patyayini_major_schedule': patyayini_major_schedule,
        'retro_flags': None,
    }
    return tajaka

# ---------- Patyayini helpers ----------

def _normalize_paty_lord(pid):
    """
    Normalize Patyayini lord IDs:
    - numpy integer -> int
    - keep 'L' (Lagna) as string
    """
    try:
        import numpy as np
        if isinstance(pid, (np.integer,)):
            return int(pid)
    except Exception:
        pass
    return pid

def _patyayini_month_hit(paty_schedule, month_start, month_end, targets=None):
    """
    True if ANY Patyayini sub-slice overlaps [month_start, month_end].
    If 'targets' is provided (set of lords), restrict to those lords.
    """
    if not paty_schedule:
        return False
    for sl in paty_schedule:
        lord = _normalize_paty_lord(sl.get('lord'))
        s = sl.get('start'); e = sl.get('end')
        if s is None or e is None:
            continue
        if e < month_start or s > month_end:
            continue
        if (targets is None) or (lord in targets):
            return True
    return False

def _patyayini_major_lord_for_month(paty_major, month_start, month_end):
    """
    Return the MAJOR lord whose period has the largest overlap with [month_start, month_end],
    or None if no major period overlaps.
    """
    if not paty_major:
        return None

    best_lord = None
    best_overlap = -1.0

    for sl in paty_major:
        s = sl.get('start'); e = sl.get('end')
        if s is None or e is None:
            continue
        if e < month_start or s > month_end:
            continue

        lord = _normalize_paty_lord(sl.get('lord'))
        overlap = (min(e, month_end) - max(s, month_start)).total_seconds()
        if overlap > best_overlap:
            best_overlap = overlap
            best_lord = lord

    return best_lord

def _expand_patyayini_schedule(patyayini_raw):
    if not patyayini_raw:
        return None

    first = patyayini_raw[0]
    out = []

    def _parse_dt_str(s):
        try:
            return datetime.fromisoformat(s)
        except Exception:
            try:
                return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.strptime(s.strip().split()[0], "%Y-%m-%d")

    # Format with embedded sub-schedules
    if (
        isinstance(first, (list, tuple))
        and len(first) == 3
        and isinstance(first[1], list)
        and first[1]
        and isinstance(first[1][0], (list, tuple))
        and len(first[1][0]) == 2
        and isinstance(first[1][0][1], str)
    ):
        flat = []
        total_days = 0.0
        for major_lord, bhukthi_list, major_days in patyayini_raw:
            total_days += float(major_days)
            for (sub_lord, start_str) in bhukthi_list:
                start_dt = _parse_dt_str(start_str)
                flat.append((_normalize_paty_lord(sub_lord), start_dt))
        flat.sort(key=lambda t: t[1])
        if not flat:
            return None

        first_start = flat[0][1]
        for i, (lord, start_dt) in enumerate(flat):
            if i < len(flat) - 1:
                end_dt = flat[i+1][1] - timedelta(seconds=1)
            else:
                candidate_end = first_start + timedelta(days=total_days)
                end_dt = max(candidate_end, start_dt + timedelta(seconds=1))
            days = (end_dt - start_dt).total_seconds() / 86400.0
            out.append({'lord': lord, 'start': start_dt, 'end': end_dt, 'days': days})
        return out

    # Flat format
    else:
        starts = []
        for row in patyayini_raw:
            try:
                planet, (y, m, d), days = row
                start_dt = datetime(int(y), int(m), int(d), 0, 0, 0)
                starts.append((_normalize_paty_lord(planet), start_dt, float(days)))
            except Exception:
                continue

        starts.sort(key=lambda t: t[1])
        for i, (planet, start_dt, days) in enumerate(starts):
            if i < len(starts) - 1:
                end_dt = starts[i+1][1] - timedelta(seconds=1)
            else:
                end_dt = start_dt + timedelta(days=days)
            out.append({'lord': planet, 'start': start_dt, 'end': end_dt, 'days': (end_dt - start_dt).total_seconds() / 86400.0})

        return out

def _expand_patyayini_major_schedule(patyayini_raw):
    """
    Extracts MAJOR periods from Patyayini raw format.
    """
    if not patyayini_raw:
        return None

    first = patyayini_raw[0]
    if not (
        isinstance(first, (list, tuple))
        and len(first) == 3
        and isinstance(first[1], list)
        and first[1]
        and isinstance(first[1][0], (list, tuple))
        and len(first[1][0]) == 2
        and isinstance(first[1][0][1], str)
    ):
        return None

    def _parse_dt_str(s):
        try:
            return datetime.fromisoformat(s)
        except Exception:
            try:
                return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S")
            except Exception:
                return datetime.strptime(s.strip().split()[0], "%Y-%m-%d")

    majors = []
    for major_lord, bhukthi_list, major_days in patyayini_raw:
        if not bhukthi_list:
            continue
        start_dt = _parse_dt_str(bhukthi_list[0][1])  # major starts at first sub-lord start
        end_dt   = start_dt + timedelta(days=float(major_days))
        majors.append({'lord': _normalize_paty_lord(major_lord) if 'not_defined' else _normalize_paty_lord(major_lord), 'start': start_dt, 'end': end_dt, 'days': float(major_days)})

    majors.sort(key=lambda d: d['start'])
    return majors

# ---------- Tajaka month scoring ----------
def _score_tajaka_month(tajaka, month_start, month_end, place, derived):
    if not tajaka:
        return 0, {'ithasala_orb': 999, 'venus_saham_delta': 999}

    annual_pp = tajaka['annual_planet_positions']
    score = 0
    ithasala_best = 999  # 0 for poorna, 1 for weaker, 999 if none

    ven_abs = tajaka['venus_abs_long']
    vs_abs = tajaka['vivaha_saham_abs_long']
    venus_saham_delta = _angle_delta_deg(ven_abs, vs_abs)

    # Year-level Venus–Saham proximity (annual, fixed)
    if venus_saham_delta <= 2.0:
        score += 3
    elif venus_saham_delta <= 5.0:
        score += 2

    # Optional: month-level *transiting Venus* vs annual Saham proximity (mid-month)
    vs_month_tier = 0
    if USE_TRANSITING_VENUS_SAHAM_PROXIMITY:
        mid = month_start + (month_end - month_start) / 2
        jd_mid_local = swe.julday(mid.year, mid.month, mid.day, mid.hour + mid.minute/60.0 + mid.second/3600.0)
        jd_utc = jd_mid_local - (place.timezone / 24.0)
        ven_tr_abs = drik.sidereal_longitude(jd_utc, const._VENUS)
        delta_tr = _angle_delta_deg(ven_tr_abs, vs_abs)
        if delta_tr <= VENUS_SAHAM_TIER2:
            score += 3
            venus_saham_delta = min(venus_saham_delta, delta_tr)
            vs_month_tier = 2
            _dbg(f"[PVR-DBG][VEN] Transiting Venus within 2° of annual Saham at mid-month → +3")
        elif delta_tr <= VENUS_SAHAM_TIER1:
            score += 2
            venus_saham_delta = min(venus_saham_delta, delta_tr)
            vs_month_tier = 1
            _dbg(f"[PVR-DBG][VEN] Transiting Venus within 5° of annual Saham at mid-month → +2")

    # Ithasāla conditions in annual D1
    LL = tajaka['annual_ll']
    L7 = tajaka['annual_7l']
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, LL, L7)
    if has_it:
        if it_type == 3:
            score += 3
            ithasala_best = 0
            _dbg(f"[PVR-DBG][ITH] Poorna Ithasala LL↔7L in annual D1 → +3")
        else:
            score += 1
            ithasala_best = min(ithasala_best, 1)
            _dbg(f"[PVR-DBG][ITH] Weak Ithasala LL↔7L in annual D1 → +1")

    m_lord = tajaka['muntha_lord']
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, m_lord)
    if has_it:
        if it_type == 3:
            score += 2
            ithasala_best = 0
            _dbg(f"[PVR-DBG][ITH] Poorna Ithasala Venus↔Muntha-lord → +2")
        else:
            score += 1
            ithasala_best = min(ithasala_best, 1)
            _dbg(f"[PVR-DBG][ITH] Weak Ithasala Venus↔Muntha-lord → +1")

    vs_sign = tajaka['vivaha_saham_sign']
    vs_lord = house.house_owner_from_planet_positions(annual_pp, vs_sign)
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, vs_lord)
    if has_it:
        if it_type == 3:
            score += 2
            ithasala_best = 0
            _dbg(f"[PVR-DBG][ITH] Poorna Ithasala Venus↔Saham-lord → +2")
        else:
            score += 1
            ithasala_best = min(ithasala_best, 1)
            _dbg(f"[PVR-DBG][ITH] Weak Ithasala Venus↔Saham-lord → +1")

    ul_sign = derived['ul_d1']
    ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign)
    has_it, it_type = both_planets_within_their_deeptamsa(annual_pp, const.VENUS_ID, ul_lord)
    if has_it:
        score += 1
        ithasala_best = min(ithasala_best, 0 if it_type == 3 else 1)
        _dbg(f"[PVR-DBG][ITH] Ithasala Venus↔UL-lord → +1")

    # --- Patyayini: sub-slice presence (info), major-lord boost & role tier (0..3) ---
    paty = tajaka.get('patyayini_schedule')
    paty_major = tajaka.get('patyayini_major_schedule')

    # Sub-slice info (info only)
    paty_hit = False
    paty_lords = []
    if paty and _patyayini_month_hit(paty, month_start, month_end):
        paty_hit = True
        paty_lords = sorted({
            _normalize_paty_lord(sl['lord']) for sl in paty
            if not (sl['end'] < month_start or sl['start'] > month_end)
        }, key=str)
        _dbg(f"[PVR-DBG][PATY] Sub-slices present in month; lords={paty_lords}")

    # Major lord for the month
    major_lord = _patyayini_major_lord_for_month(paty_major, month_start, month_end)

    # Target set for role classification
    vs_sign = tajaka['vivaha_saham_sign']
    annual_pp = tajaka['annual_planet_positions']
    vs_lord = house.house_owner_from_planet_positions(annual_pp, vs_sign)
    m_lord = tajaka['muntha_lord']
    L7 = tajaka['annual_7l']
    ul_sign = derived['ul_d1']
    ul_lord = house.house_owner_from_planet_positions(annual_pp, ul_sign)
    target_lords = {const.VENUS_ID, L7, ul_lord, vs_lord, m_lord}

    major_hit = (major_lord in target_lords) if (major_lord is not None) else False

    # Determine MAJOR role tier (0..3): 3 if Saham/Muntha, 2 if Venus/7L/UL/VS-lord, 1 other major
    major_weight = 0
    if major_lord is not None:
        if major_lord == m_lord or major_lord == vs_lord:
            major_weight = 3
        elif major_lord in {const.VENUS_ID, L7, ul_lord, vs_lord}:
            major_weight = 2
        else:
            major_weight = 1
    score += major_weight

    if major_lord is not None:
        role_txt = {3: "Saham/Muntha month", 2: "Venus/7L/UL/VS-lord month", 1: "Other MAJOR"}.get(major_weight, "No MAJOR")
        _dbg(f"[PVR-DBG][PATY] MAJOR lord={_pname(major_lord)} → role={role_txt} (+{major_weight})")

    detail = {
        'ithasala_orb': ithasala_best,
        'venus_saham_delta': round(venus_saham_delta, 2),
        'patyayini_major_lord': major_lord,
        'patyayini_major_hit': major_hit,
        'patyayini_major_weight': major_weight,
        'patyayini_hit': paty_hit,
        'patyayini_lords_in_month': paty_lords,
        'vs_month_tier': vs_month_tier,
    }
    return score, detail

# ---------- Helpers ----------
def _get_planet_sign_from_annual(annual_pp, planet_id):
    for pl, (sg, lon) in annual_pp:
        if pl == planet_id:
            return sg
    return None

def _get_planet_abs_long_from_positions(pp, planet_id):
    for pl, (sg, lon) in pp:
        if pl == planet_id:
            return (sg * 30.0) + float(lon)
    return None

def _find_lagna_sign_from_positions(pp):
    for pl, (sg, lon) in pp:
        if pl == 'L':
            return sg
    return 0

def _angle_delta_deg(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)

def _end_of_month(y, m):
    if m == 12:
        return datetime(y, 12, 31, 23, 59, 59)
    return datetime(y, m+1, 1) - timedelta(seconds=1)

def _hours_to_hms(hours_float):
    h = int(hours_float); m = int((hours_float - h) * 60.0)
    s = int(round((((hours_float - h) * 60.0) - m) * 60.0))
    if s == 60: s = 0; m += 1
    if m == 60: m = 0; h += 1
    return h, m, s

def _safe_extract_float_hours(vf_time):
    if isinstance(vf_time, (int, float)):
        return float(vf_time)
    t = str(vf_time).strip().replace('°', ':').replace(' ', ':')
    parts = [p for p in t.split(':') if p != '']
    try:
        h = float(parts[0]) if len(parts) > 0 else 0.0
        m = float(parts[1]) if len(parts) > 1 else 0.0
        s = float(parts[2]) if len(parts) > 2 else 0.0
    except Exception:
        return 0.0
    return h + (m / 60.0) + (s / 3600.0)

def _collect_reasons(md_ad_pd, jtransit, scd_info, tajaka_detail, kcd_score, cnd9_score, cultural, derived):
    """
    Assemble an explanation blob. We *explicitly* include scd_jup_match/scd_ven_match flags
    so feature extraction does not have to guess from the numeric SCD score.
    """
    out = {
        'md_ad_pd': md_ad_pd,
        'ithasala_orb': tajaka_detail.get('ithasala_orb', 999),
        'venus_saham_delta': tajaka_detail.get('venus_saham_delta', 999),
        'kcd': kcd_score,
        'cnd9': cnd9_score,
        'cultural': cultural
    }
    out['jupiter_transit'] = jtransit

    # SCD year confirmers
    scd_score = _score_scd_year_support(scd_info, derived)
    out['scd_score'] = scd_score
    scd_rasi = scd_info.get('scd_rasi_d9')
    out['scd_jup_match'] = 1 if scd_info.get('vf_jupiter_sign_d9') == scd_rasi else 0
    out['scd_ven_match'] = 1 if scd_info.get('vf_venus_sign_d9') == scd_rasi else 0

    # NEW: persist D-9 Saturn support flag
    out['d9_saturn_flag'] = bool(derived.get('d9_saturn_flag', False))

    if 'patyayini_hit' in tajaka_detail:
        out['patyayini_hit'] = tajaka_detail['patyayini_hit']
    if 'patyayini_lords_in_month' in tajaka_detail:
        out['patyayini_lords_in_month'] = tajaka_detail['patyayini_lords_in_month']

    out['md_ad_pd_names'] = {
        'md': _pname(md_ad_pd.get('md')) if md_ad_pd else 'None',
        'ad': _pname(md_ad_pd.get('ad')) if md_ad_pd else 'None',
        'pd': _pname(md_ad_pd.get('pd')) if md_ad_pd else 'None'
    }
    if out.get('patyayini_lords_in_month'):
        out['patyayini_lords_in_month_names'] = [
            _pname(pid) for pid in out['patyayini_lords_in_month']
        ]

    return out

# ---------- Tuple → tiers ----------
def _year_strength_from_tajaka(tajaka, derived):
    if not tajaka:
        return 0, {}
    ven_abs = tajaka.get('venus_abs_long')
    vs_abs  = tajaka.get('vivaha_saham_abs_long')
    if ven_abs is None or vs_abs is None:
        return 0, {}
    delta = _angle_delta_deg(ven_abs, vs_abs)
    tier  = 2 if delta <= 2.0 else (1 if delta <= 5.0 else 0)
    return tier, {'venus_saham_delta_at_vf': round(delta, 2)}

def _ithasala_tier_from_detail(tajaka_detail):
    orb = tajaka_detail.get('ithasala_orb', 999)
    if orb == 0: return 2
    if orb == 1: return 1
    return 0

def _venus_saham_tier_from_detail(tajaka_detail):
    delta = tajaka_detail.get('venus_saham_delta', 999)
    if delta <= 2.0: return 2
    if delta <= 5.0: return 1
    return 0

def _suggest_day_from_patyayini(tajaka, month_start, month_end, targets_priority):
    """
    Pick the center day of the best Patyayini sub-slice overlapping [month_start, month_end]
    preferring Venus → 7L → UL-lord → Saham-lord → Muntha-lord.
    """
    paty = tajaka.get('patyayini_schedule') if tajaka else None
    if not paty:
        return None, {'reason': 'no_patyayini'}

    overlapping = [sl for sl in paty if not (sl['end'] < month_start or sl['start'] > month_end)]
    if not overlapping:
        return None, {'reason': 'no_overlap'}

    for pid in targets_priority:
        slices = [sl for sl in overlapping if sl['lord'] == pid]
        if slices:
            best = max(slices, key=lambda sl: (min(sl['end'], month_end) - max(sl['start'], month_start)).total_seconds())
            center = max(best['start'], month_start) + (min(best['end'], month_end) - max(best['start'], month_start)) / 2
            return center.date(), {'reason': 'patyayini_center', 'lord': pid, 'slice': {'start': best['start'], 'end': best['end']}}
    return None, {'reason': 'no_target_lord'}

# ---------- Optional TODOs ----------
def _score_compressed_d9_narayana(jd, place, month_start, month_end, derived):
    return 0

def _score_cultural_month(month_start, month_end):
    return 0

# ---------- Kalachakra Dasha support ----------
def _score_kalachakra_support(jd, place, year, derived):
    """
    Uses your kalachakra_dhasa, returns 0..2 support.
    """
    try:
        jd_utc_birth = jd - (place.timezone / 24.0)
        moon_long = drik.sidereal_longitude(jd_utc_birth, const._MOON)

        rows = kalachakra.kalachakra_dhasa(moon_long, jd, include_antardhasa=True)
        if not rows:
            return 0

        segs = []
        for md_rasi, ad_rasi, start_str, dur_years in rows:
            s = start_str.split()[0].strip()
            try:
                y, m, d = map(int, s.split('-'))
                start_dt = datetime(y, m, d)
            except Exception:
                continue
            dur_days = float(dur_years) * const.sidereal_year
            end_dt = start_dt + timedelta(days=dur_days) - timedelta(seconds=1)
            segs.append({'md': md_rasi, 'ad': ad_rasi, 'start': start_dt, 'end': end_dt})

        if not segs:
            return 0

        win_start = datetime(year, 1, 1, 0, 0, 0)
        win_end = datetime(year, 12, 31, 23, 59, 59)

        venus_sign_d1 = derived['venus_sign_d1']
        seventh_house_sign_d1 = derived['seventh_house_sign_d1']

        best = 0
        for seg in segs:
            if (seg['end'] < win_start) or (seg['start'] > win_end):
                continue
            md_rasi = seg['md']
            ad_rasi = seg['ad']
            score = 0
            if md_rasi == venus_sign_d1:
                score += 1
            if ad_rasi is not None:
                if ad_rasi == ((venus_sign_d1 + 6) % 12):
                    score += 1
                elif ad_rasi == ((md_rasi + 6) % 12):
                    score += 1
                elif ad_rasi == seventh_house_sign_d1:
                    score += 1
            best = max(best, min(score, 2))
            if best >= 2:
                break
        return best

    except Exception:
        return 0

# ---------- (Optional) Adaptors ----------
def to_chart_1_from_positions(planet_positions):
    slots = [""] * 12
    for pl, (sg, lon) in planet_positions:
        if pl == 'L':
            slots[sg] = ("L" if slots[sg] == "" else slots[sg] + "/L")
        else:
            token = str(pl)
            slots[sg] = token if slots[sg] == "" else (slots[sg] + "/" + token)
    return slots

def to_chart_1d_from_positions(planet_positions):
    return to_chart_1_from_positions(planet_positions)

def to_p_to_h_from_positions(planet_positions):
    out = {}
    for pl, (sg, lon) in planet_positions:
        if pl == 'L':
            out['L'] = sg
        else:
            out[pl] = sg
    return out

# ---------- Main (ad-hoc test harness) ----------
if __name__ == "__main__":
    utils.set_language('en')

    from pprint import pprint

    def run_case(tag, dob, tob, place_tuple):
        place = drik.Place(*place_tuple)
        jd = utils.julian_day_number(dob, tob)

        # Strict pick (1 item if strict passes)
        res_strict = predict_marriage_windows_from_jd_place(
            jd, place, start_year=None, end_year=None, marriage_age_range=(20,40),
            strict=True, top_k=3
        )
        print(f"\n[{tag}] Strict pick:")
        pprint(res_strict)

        # Top-3 exploratory (strict off)
        res_top3 = predict_marriage_windows_from_jd_place(
            jd, place, start_year=None, end_year=None, marriage_age_range=(20,40),
            strict=False, top_k=3
        )
        print(f"\n[{tag}] Top-3 exploratory:")
        pprint(res_top3[:3])

    # PVR Real-life Example-1
    """
    run_case(
        "PVR E1",
        (1973,7,26),
        (21,41,0),
        ('UNK', 16+13/60, 80+28/60, 5.5)
    )
    """
    #"""
    # PVR Real-life Example-5 (target Feb-1992)
    run_case(
        "PVR E5",
        (1968,5,21),
        (23,5,0),
        ('UNK', 18+40/60, 78+10/60, 5.5)
    )
    #"""
