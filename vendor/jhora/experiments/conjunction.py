from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Tuple, Optional

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import mplcursors

from jhora.panchanga import drik
from jhora import utils, const


# ------------------------ Helpers ------------------------
def _unwrap_deg(deg_series: np.ndarray) -> np.ndarray:
    """
    Unwrap a degree series (0..360) to a continuous series for robust
    intersection detection across the 360° boundary.
    """
    rad = np.deg2rad(deg_series)
    unwrapped_rad = np.unwrap(rad, discont=np.pi)
    return np.rad2deg(unwrapped_rad)
def _daterange(d0: date, d1: date) -> List[date]:
    if d1 < d0:
        raise ValueError("End date is before start date.")
    return [d0 + timedelta(days=i) for i in range((d1 - d0).days + 1)]

def _to_deg360(value) -> float:
    """
    Convert various return shapes to [0,360):
      - float/int (assumed degrees; auto-convert radians if <= ~6.5)
      - (rasi_index, degrees_in_rasi)
      - [rasi_index, degrees_in_rasi]
    """
    if value is None:
        return np.nan

    # Tuple/list like (rasi, deg_in_rasi)
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        try:
            rasi = float(value[0])
            deg_in_rasi = float(value[1])
            return (rasi * 30.0 + deg_in_rasi) % 360.0
        except Exception:
            return np.nan

    # Numeric: detect radians heuristically
    try:
        v = float(value)
    except Exception:
        return np.nan

    if 0.0 <= v <= 2 * np.pi + 0.5:
        v = np.degrees(v)
    return v % 360.0

def _planet_longitude_deg(jd, planet_id_or_key) -> float:
    """
    Get sidereal longitude in degrees (0..360) for a planet.
    Your environment: `sidereal_longitude` does NOT require `place`.
    If your build requires SWE index, we fall back to that.
    """
    # Try as-is (id/key)
    try:
        val = drik.sidereal_longitude(jd, planet_id_or_key)
        return _to_deg360(val)
    except Exception:
        pass
    # Fallback to Swiss index
    try:
        p_swe = drik.ephemeris_planet_index(planet_id_or_key)
        val = drik.sidereal_longitude(jd, p_swe)
        return _to_deg360(val)
    except Exception:
        return np.nan

def _circ_diff(a_deg: np.ndarray, b_deg: np.ndarray) -> np.ndarray:
    """Circular difference in [-180, +180] degrees."""
    return (a_deg - b_deg + 540.0) % 360.0 - 180.0

def _interp_circ(a0_deg: float, a1_deg: float, t: float) -> float:
    """Interpolate along the shortest arc between angles (degrees)."""
    delta = ((a1_deg - a0_deg + 540.0) % 360.0) - 180.0
    return (a0_deg + t * delta) % 360.0


# ------------------------ Main Polar Plot ------------------------

def plot_sidereal_polar_spiral(
    start_date: Tuple[int, int, int],
    end_date: Tuple[int, int, int],
    place,                                   # needed for Ascendant (not needed for planets in your build)
    planets: Optional[Iterable] = None,      # default: all values from drik.planet_list
    include_asc: bool = True,
    mark_conjunctions: bool = False,
    near_miss_tol_deg: Optional[float] = None,  # e.g., 0.25 to mark near-conjunctions
    r1: float = 1.0,
    dr_per_day: float = 1/const.sidereal_year,            # outward radial increment per day
    figsize: Tuple[int, int] = (8, 8),
    dpi: int = 96,
):
    """
    Polar spiral plot (R–θ) of Ascendant and planets.
      - θ: sidereal longitude (unwrapped), in radians on the polar axes
      - R: r1 + day_index * dr_per_day

    Conjunctions (same θ modulo 360 on the same day) are optionally marked.
    """
    # Dates & radius series
    y0, m0, d0 = start_date
    y1, m1, d1 = end_date
    dates = _daterange(date(y0, m0, d0), date(y1, m1, d1))
    N = len(dates)
    if N < 2:
        raise ValueError("Need at least two dates to draw a spiral.")

    # Radius for each day (shared by all bodies)
    r = r1 + np.arange(N, dtype=float) * dr_per_day

    # Planet list (prefer ids/values)
    if planets is None:
        planet_ids = list(drik.planet_list.values())
    else:
        planet_ids = list(planets)

    # Storage
    theta_deg_series: Dict[str, List[float]] = {}
    if include_asc:
        theta_deg_series["Ascendant"] = []

    # Compute longitudes for each day
    noon = (12, 0, 0)
    for d in dates:
        dob = (d.year, d.month, d.day)
        jd = utils.julian_day_number(dob, noon)

        if include_asc:
            asc = drik.ascendant(jd, place)  # expected (rasi, deg_in_rasi)
            asc_deg = _to_deg360(asc)
            theta_deg_series["Ascendant"].append(asc_deg)

        for p in planet_ids:
            name = utils.PLANET_NAMES[p]
            if name not in theta_deg_series:
                theta_deg_series[name] = []
            # Your note: place NOT required for sidereal_longitude
            lon_deg = _planet_longitude_deg(jd, p)
            theta_deg_series[name].append(lon_deg)

    # Convert to numpy; unwrap for smooth spirals; convert to radians
    series_unwrapped_rad: Dict[str, np.ndarray] = {}
    for name, vals in theta_deg_series.items():
        arr_deg = np.array(vals, dtype=float)
        arr_unw_deg = _unwrap_deg(arr_deg)
        series_unwrapped_rad[name] = np.deg2rad(arr_unw_deg)

    # --- Plot (polar) ---
    try:
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi, subplot_kw={"projection": "polar"}, layout="constrained")
    except TypeError:
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi, subplot_kw={"projection": "polar"}, constrained_layout=True)

    # Aesthetics for polar
    # 0° at the right (Aries) and increasing CCW (astronomical convention)
    ax.set_theta_zero_location("E")  # 'E' puts 0° to the right
    ax.set_theta_direction(1)        # counter-clockwise positive

    # Plot each series as a spiral: theta(t) vs r(t)
    for name, theta_rad in series_unwrapped_rad.items():
        ax.plot(theta_rad, r, linewidth=1.6, label=name)

    # --- Conjunction markers (same θ modulo 360 on same day) ---
    if mark_conjunctions:
        # Build θ modulo 360 arrays for sign-change detection
        series_mod_deg = {k: np.array(v) % 360.0 for k, v in theta_deg_series.items()}
        keys = list(series_mod_deg.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                n1, n2 = keys[i], keys[j]
                th1 = series_mod_deg[n1].astype(float)
                th2 = series_mod_deg[n2].astype(float)
                valid = ~np.isnan(th1) & ~np.isnan(th2)
                if np.count_nonzero(valid) < 2:
                    continue

                # Use only valid spans
                idx = np.flatnonzero(valid)
                th1 = th1[valid]
                th2 = th2[valid]

                d = _circ_diff(th1, th2)
                prod = d[:-1] * d[1:]
                crossing_idx = np.where(prod < 0)[0]          # strict sign change
                zero_idx = np.where(d[:-1] == 0)[0]           # exact equality (rare)
                all_idx = np.unique(np.concatenate([crossing_idx, zero_idx]))

                # Interpolate and mark
                for k in all_idx:
                    denom = abs(d[k]) + abs(d[k + 1])
                    t = 0.5 if denom == 0 else abs(d[k]) / denom
                    # Global day index fraction (to get radius)
                    # Map back to original indices:
                    i0_global = idx[k]
                    # Interpolated radius for time between day k and k+1
                    r_k = r1 + (i0_global + t) * dr_per_day

                    # For angle, interpolate along shortest arc of series n1
                    th_k_deg = _interp_circ(series_mod_deg[n1][i0_global],
                                            series_mod_deg[n1][i0_global + 1], t)
                    ax.scatter(np.deg2rad(th_k_deg), r_k, s=26, c="red", zorder=6)

                # Optional: near-miss marker if requested and no crossings found
                if near_miss_tol_deg and len(all_idx) == 0:
                    idx_min_local = int(np.nanargmin(np.abs(d)))
                    if abs(d[idx_min_local]) <= near_miss_tol_deg:
                        i_global = idx[idx_min_local]
                        ax.scatter(np.deg2rad(th1[idx_min_local]), r[i_global], s=26, c="orange", zorder=6)

    # Grid & labels
    ax.set_title("Sidereal Longitudes — Polar Spiral (R–θ)\nR = r1 + day_index / "+str(const.sidereal_year)+".", va="bottom")
    ax.set_rlabel_position(135)  # move radial labels away from clutter

    # 30° gridlines (zodiac signs)
    tick_degs = np.arange(0, 360, 30)
    ax.set_thetagrids(angles=tick_degs, labels=[f"{int(t)}°" for t in tick_degs])

    # Radial bounds
    r_min = r1
    r_max = r1 + (N - 1) * dr_per_day
    ax.set_rlim(r_min, r_max)

    # Legend outside (toggle to taste)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0., title="Bodies")
    fig.subplots_adjust(right=0.82)

    return fig, ax


def _find_pairwise_intersections(
    x: np.ndarray,
    series: Dict[str, np.ndarray],
) -> List[Tuple[float, float, str, str]]:
    """
    Find intersections for every pair of named series using linear interpolation
    on unwrapped values. Returns a list of (x_float_date, y_mod_360, name1, name2).
    """
    names = list(series.keys())
    intersections = []

    # Precompute unwrapped arrays
    unwrapped = {name: _unwrap_deg(np.asarray(series[name], dtype=float)) for name in names}

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            name_i, name_j = names[i], names[j]
            y1 = unwrapped[name_i]
            y2 = unwrapped[name_j]
            diff = y1 - y2

            # Identify sign changes (crossings) between successive samples
            prod = diff[:-1] * diff[1:]
            crossing_idx = np.where(prod < 0)[0]

            # Also handle exact zero (rare), treat as crossings
            exact_zero_idx = np.where(diff[:-1] == 0)[0]
            all_idx = np.unique(np.concatenate([crossing_idx, exact_zero_idx]))

            for k in all_idx:
                # Linear interpolation fraction between k and k+1
                denom = (abs(diff[k]) + abs(diff[k + 1]))
                if denom == 0:
                    t_frac = 0.5  # identical values, arbitrary midpoint
                else:
                    t_frac = abs(diff[k]) / denom

                # Interpolate x and y (on unwrapped values), then mod 360 for plotting
                xk = x[k] + t_frac * (x[k + 1] - x[k])
                yk = y1[k] + t_frac * (y1[k + 1] - y1[k])
                yk_mod = yk % 360.0
                intersections.append((xk, yk_mod, name_i, name_j))

    return intersections


def plot_sidereal_longitudes(
    start_date:tuple,
    end_date:tuple,
    place,
    planets: Optional[Iterable] = None,
    skip_ascendant = True,
    mark_intersections: bool = False,
    figsize: Tuple[int, int] = (10, 6),
    dpi: int = 96,
):
    """
    Plot sidereal longitudes (0..360°) of Ascendant and planets for each day at local 12:00,
    over the given date range. Optionally marks intersections between any pair of curves.

    Parameters
    ----------
    year_from, month_from, day_from : int
        Start date (inclusive).
    year_to, month_to, day_to : int
        End date (inclusive).
    place : Any
        Place object as required by jhora.panchanga.drik functions.
    planets : iterable of planet keys, optional
        Iterable of planet keys accepted by drik.sidereal_longitude. Defaults to all keys in drik.planet_list.
    mark_intersections : bool, default True
        Whether to detect and mark pairwise intersections with red filled circles.
    figsize : tuple, default (14, 7)
        Figure size.
    dpi : int, default 120
        Figure resolution.

    Returns
    -------
    fig, ax : matplotlib Figure and Axes
    """
    # Build date list
    year_from, month_from, day_from = start_date
    year_to, month_to, day_to = end_date
    start = date(year_from, month_from, day_from)
    end = date(year_to, month_to, day_to)
    dates = _daterange(start, end)

    # Sample at local 12:00
    noon = (12, 0, 0)

    # Determine planets list
    if planets is None:
        # Use all dictionary keys (e.g., const._SUN, etc.)
        planets = list(drik.planet_list.values())
    else:
        planets = list(planets)
    # Storage
    x_dates_dt = []
    asc_vals = []
    planet_series: Dict[str, List[float]] = {utils.PLANET_NAMES[p]: [] for p in planets}

    # Compute longitudes for each day
    for d in dates:
        dob = (d.year, d.month, d.day)
        jd = utils.julian_day_number(dob, noon)

        # Store x as datetime (matplotlib will handle conversion)
        x_dates_dt.append(datetime(d.year, d.month, d.day, 12, 0, 0))
        if skip_ascendant:
            # Ascendant
            asc = drik.ascendant(jd, place)
            asc_long = asc[0]*30+asc[1]
            asc_vals.append(asc_long)
        # Each planet
        for p in planets:
            p_swe = drik.ephemeris_planet_index(p)
            try:
                jd_utc = jd - place.timezone/24.0
                lon = drik.sidereal_longitude(jd_utc, p_swe) % 360.0
            except Exception:
                # If a particular body is unsupported for that date/time, record NaN
                lon = np.nan
            planet_series[utils.PLANET_NAMES[p]].append(lon)

    # Convert to numpy arrays
    x = mdates.date2num(x_dates_dt)  # matplotlib float dates
    series = {} if skip_ascendant else {"Ascendant": np.array(asc_vals, dtype=float)}
    for name, vals in planet_series.items():
        series[name] = np.array(vals, dtype=float)

    # Plot
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    # Colormap cycling
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key().get('color', None)

    # Plot each series
    for idx, (name, y) in enumerate(series.items()):
        # To keep plot within 0..360, we use modulo values (wrap will show as jumps)
        ax.plot(x_dates_dt, y, label=name, linewidth=1.8)

    # Intersections
    if mark_intersections:
        # Remove any series with all-NaN (unlikely for Ascendant)
        filtered_series = {k: v for k, v in series.items() if not np.all(np.isnan(v))}
        # For robust intersection detection, ignore NaN spans
        # Build masks where both series have valid data on consecutive samples
        intersections_all = []
        keys = list(filtered_series.keys())
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                k1, k2 = keys[i], keys[j]
                y1 = filtered_series[k1]
                y2 = filtered_series[k2]
                valid = ~np.isnan(y1) & ~np.isnan(y2)
                # If fewer than 2 valid points, skip
                if np.count_nonzero(valid) < 2:
                    continue

                # Compress to valid samples
                xv = x[valid]
                y1v = y1[valid]
                y2v = y2[valid]

                # Find intersections on the valid segments
                # Build a temporary dict to use the helper on this pair only
                tmp_series = {k1: y1v, k2: y2v}
                inter = _find_pairwise_intersections(xv, tmp_series)
                intersections_all.extend(inter)

        if intersections_all:
            xs, ys, n1s, n2s = zip(*intersections_all)
            ax.scatter(mdates.num2date(np.array(xs)), ys, s=30, color="red", zorder=5, label="Intersections")
        else:
            # No crossings found; nothing to scatter
            pass

    # Formatting
    ax.set_title("Sidereal Longitudes at Local 12:00 (Ascendant & Planets)")
    ax.set_ylabel("Sidereal Longitude (°)")
    ax.set_ylim(0, 360)
    ax.set_xlim(x_dates_dt[0], x_dates_dt[-1])

    # Degree gridlines
    ax.yaxis.set_major_locator(plt.MultipleLocator(30))
    ax.yaxis.set_minor_locator(plt.MultipleLocator(10))
    ax.grid(which="major", axis="y", linestyle="--", alpha=0.35)
    ax.grid(which="minor", axis="y", linestyle=":", alpha=0.15)

    # Date formatter
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=12))
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(mdates.AutoDateLocator()))

    ax.legend(ncol=2, fontsize=9)
    fig.tight_layout()
    return fig, ax
if __name__ == "__main__":
    utils.set_language('en')
    drik.set_planet_list(set_rahu_ketu_as_true_nodes=True)
    _ayanamsa = "TRUE_PUSHYA"
    planets_to_plot = [const.JUPITER_ID, const.SATURN_ID, const.RAHU_ID]
    drik.set_ayanamsa_mode(_ayanamsa)
    start_date = (1996,12,7); end_date = (2000,12,31)
    place = drik.Place('Chennai,India',13.03862,80.261818,5.5)
    #fig,ax = plot_sidereal_longitudes(start_date, end_date,place,planets=planets_to_plot,
    #                                  mark_intersections=True)
    fig,ax = plot_sidereal_polar_spiral(start_date, end_date, place, planets_to_plot)
# Attach to all line artists on the axes
    cursor = mplcursors.cursor(ax.lines, hover=True)
    
    @cursor.connect("add")
    def on_add(sel):
        # sel.target is (x, y) in data coords; x is a Matplotlib date float
        x, y = sel.target
        dt = mdates.num2date(x)
        # Optional: get line label (series name)
        label = sel.artist.get_label()
        sel.annotation.set(
            text=f"{label}\n{dt:%Y-%m-%d %H:%M}\n{y:.2f}°",
            fontsize=9,
            ha="left",
        )
        # Optional style tweaks
        sel.annotation.get_bbox_patch().set(fc="w", alpha=0.85)
    plt.show()

    