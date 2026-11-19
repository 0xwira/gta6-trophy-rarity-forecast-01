"""gta6-trophy-rarity-forecast-01: forecast every GTA VI PS5 trophy's Exophase earn rate.

For each *.in case in the input directory this writes one <id>.out forecast to the output directory: for every trophy
of the case, five quantiles (levels 0.05, 0.25, 0.5, 0.75, 0.95) of its earn rate on Exophase at the case's target,
in percent of the players Exophase tracks. Python 3.13, standard library only, deterministic; reads
$MAKEFUN_INPUT_DIR (else /input) and writes $MAKEFUN_OUTPUT_DIR (else /output).

The baseline to beat is persistence: the median is each trophy's rate in the last read and the spread is the random
walk 0.5 * sqrt(horizon in days) on the logit scale. This program instead forecasts from the case's own history.

Every read is decomposed: a trophy's earners = rate_percent / 100 * players_tracked of that read. That leaves two
series per case, the tracked player pool over time, and each trophy's earners over time (skipping reads where its
rate is null).

  1. The player pool is projected to the target from a fit that decelerates in elapsed time: a straight line on
     log-log scales (a power law) through the reads where the count changed. The projection is guarded: it cannot
     fall below the last read, and its growth over the last read is capped at a sane factor.
  2. Each trophy's earners are fitted against the player count, in log-log space, over the case's reads. This
     captures dilution: a progression trophy's earners grow slower than the pool (slope < 1), so at the forecast
     pool its earn rate falls. Earners per player at the predicted pool give the median earn rate, clamped to the
     valid percent range the RULES use.
  3. The fits blend with persistence where they are worth trusting and fall back to it where they are not: a
     history too short, flat or degenerate for a fit (the practice cases: every read is the same unchanged page)
     keeps the persistence median; a noisier history moves the median only part of the way to the fit
     (shrinkage by the fit's standard error and by evidence of a change with the pool).
  4. The five levels and the logit scale are kept. The half-spread per level starts from the baseline's horizon term
     and is adjusted by the trophy's own residual scatter around its time fit, by how far it extrapolates (in units
     of the read span) and by the sampling noise in a computed earners count, then floored so no trophy is
     overconfident. Quantiles are mapped in order and forced non-decreasing and inside 0..100. When a history is
     perfectly flat the lower side is widened slightly more than the upper side: the RULES' Exophase refresh grows
     the tracked pool and pushes most rates down, so a flat page is likelier to fall than to rise.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# The grader's -P leaves the repository off sys.path: put it back first, so any module beside main.py imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The scored levels and the standard normal's quantile at each, in the row's order.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]

# The page prints 0.00 to 100.00; the score's logit clamps its argument to 0.01..99.99.
P_MIN = 0.01
P_MAX = 99.99
MAX_BYTES = 65536

# The baseline's random-walk spread in logit units per square-root day, the spine of the per-trophy spread.
SIGMA = 0.5
# Floor and ceiling on a trophy's per-level spread, in logit units per sqrt(day).
S_MIN = 0.10
S_MAX = 1.60
# Floor on the flat-history spread: a refresh breaks the page even on launch night.
S_FLAT_MIN = 0.30
# A perfectly flat history: widen the lower side (a refresh grows the pool and pushes rates down).
FLAT_LOWER = 1.30
FLAT_UPPER = 1.00
# Cap on the projected pool's growth over the last read, as a factor.
GROWTH_CAP = 5.0

# Axis for the pool's power law: days from noon the day before release (GTA VI is out at 2026-11-19T00:00:00Z).
RELEASE = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)


def is_flat(ys: list[float]) -> bool:
    """True when the values never move: no fit of growth can be trusted."""
    return all(abs(y - ys[0]) < 1e-9 for y in ys)


def trophy_fit(players: list[float], earners: list[float]):
    """Log-log fit of earners against the pool: (slope, intercept, resid_var, n), or None when it has no spread."""
    pts = [(p, e) for p, e in zip(players, earners) if p > 0 and e > 0]
    if len(pts) < 3 or is_flat([e for _, e in pts]):
        return None
    fit = linfit([math.log(p) for p, _ in pts], [math.log(e) for _, e in pts])
    if fit is None:
        return None
    a, b, _, resid_var, _ = fit
    return b, a, resid_var, len(pts)


def linfit(xs: list[float], ys: list[float]):
    """Ordinary least squares: intercept, slope, R-squared, residual variance, slope SE."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 1e-15:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    rss = sum(r * r for r in residuals)
    tss = sum((y - my) ** 2 for y in ys)
    r_squared = 1.0 - rss / tss if tss > 1e-15 else 0.0
    variance = rss / max(1, len(xs) - 2)
    slope_se = math.sqrt(variance / sxx) if variance > 0 else 0.0
    return intercept, slope, r_squared, variance, slope_se


def clamp_rate(value: float) -> float:
    """Keep predicted page rates in its scored, printable range."""
    return min(P_MAX, max(P_MIN, value))


def logit(pct: float) -> float:
    pct = clamp_rate(pct)
    return math.log(pct / (100.0 - pct))


def logistic(value: float) -> float:
    """Stable inverse logit, returning a percentage."""
    value = min(40.0, max(-40.0, value))
    return 100.0 / (1.0 + math.exp(-value))


def read_days(read: dict) -> float:
    stamp = datetime.fromisoformat(read["at"].replace("Z", "+00:00"))
    return max(1e-6, (stamp - RELEASE).total_seconds() / 86400.0)


def forecast_players(history: list[dict], target: str) -> tuple[float, float, bool]:
    """Project the tracked pool with a decelerating power law and bound extrapolation."""
    last = history[-1]
    last_count = float(last["players_tracked"])
    target_stamp = datetime.fromisoformat(target.replace("Z", "+00:00"))
    target_day = max(1e-6, (target_stamp - RELEASE).total_seconds() / 86400.0)
    changed = []
    previous = None
    for read in history:
        count = float(read["players_tracked"])
        if previous is None or count != previous:
            changed.append((read_days(read), count))
        previous = count
    if len(changed) < 2:
        return last_count, 1.0, False
    fit = linfit([math.log(t) for t, _ in changed], [math.log(n) for _, n in changed])
    if fit is None:
        return last_count, 1.0, False
    intercept, slope, _, _, _ = fit
    # Nonpositive growth is not extrapolated as a declining player pool.
    slope = min(1.25, max(0.0, slope))
    predicted = math.exp(intercept + slope * math.log(target_day))
    predicted = max(last_count, min(last_count * GROWTH_CAP, predicted))
    return predicted, predicted / max(1.0, last_count), True


def baseline_rate(last_rate: float | None) -> float:
    return clamp_rate(0.0 if last_rate is None else float(last_rate))


def quantiles(median: float, lower_spread: float, upper_spread: float) -> list[float]:
    """Map normal logit quantiles to a monotone bounded percentage sequence."""
    center = logit(clamp_rate(median))
    out = []
    for z in Z:
        spread = lower_spread if z < 0 else upper_spread
        out.append(round(logistic(center + z * spread), 4))
    for i in range(1, len(out)):
        out[i] = max(out[i - 1], min(100.0, out[i]))
    return [min(100.0, max(0.0, q)) for q in out]


def forecast_case(case: dict, name: str) -> dict:
    """Forecast one case from its own history, with persistence as a conservative anchor."""
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    history = case["history"]
    if not history:
        raise ValueError(f"{name} has no history")
    last = history[-1]
    horizon_days = max(0.0, float(case["horizon_minutes"]) / 1440.0)
    base_spread = SIGMA * math.sqrt(horizon_days)
    forecast_pool, pool_growth, pool_fit_ok = forecast_players(history, case["target"])
    player_series = [float(read["players_tracked"]) for read in history]
    perfectly_flat = all(
        read["players_tracked"] == history[0]["players_tracked"]
        and read["rates"] == history[0]["rates"]
        for read in history
    )
    rows = []
    for index, trophy in enumerate(case["trophies"]):
        last_value = last["rates"][index]
        persist = baseline_rate(last_value)
        earners = []
        pools = []
        for read in history:
            rate = read["rates"][index]
            if rate is None:
                continue
            rate_value = float(rate)
            if rate_value <= 0:
                continue
            pools.append(float(read["players_tracked"]))
            earners.append(rate_value / 100.0 * float(read["players_tracked"]))

        fit = trophy_fit(pools, earners)
        median = persist
        residual_sd = 0.0
        credibility = 0.0
        if fit is not None:
            slope, intercept, residual_var, count = fit
            fitted_earners = math.exp(intercept + slope * math.log(forecast_pool))
            fitted_rate = clamp_rate(100.0 * fitted_earners / forecast_pool)
            raw_fit = linfit([math.log(p) for p in pools], [math.log(e) for e in earners])
            slope_se = raw_fit[4] if raw_fit else 1.0
            residual_sd = math.sqrt(max(0.0, residual_var))
            evidence = min(1.0, max(0.0, (count - 3) / 7.0))
            # Require both enough distinct observations and a reasonably stable slope before
            # allowing a small rate movement to pull the median away from the last page.
            precision = 1.0 / (1.0 + 2.5 * slope_se + 1.25 * residual_sd)
            # Trust only a well-supported relationship that materially differs from persistence.
            dilution_signal = min(1.0, abs(math.log(fitted_rate / persist)) / 0.20)
            credibility = evidence * precision * min(1.0, 0.30 + dilution_signal)
            median = clamp_rate(math.exp(
                (1.0 - credibility) * math.log(persist)
                + credibility * math.log(fitted_rate)
            ))

        # Use the baseline horizon spread as a floor, then widen for model scatter and extrapolation.
        spread = math.sqrt(base_spread ** 2 + (0.65 * residual_sd) ** 2)
        extrapolation = max(0.0, math.log(max(1.0, pool_growth)))
        if pool_fit_ok:
            spread += 0.20 * extrapolation
        spread = min(S_MAX * math.sqrt(max(horizon_days, 0.04)), max(S_MIN * math.sqrt(max(horizon_days, 0.04)), spread))
        if fit is None:
            spread = max(spread, S_FLAT_MIN * math.sqrt(max(horizon_days, 0.04)))
        elif credibility < 0.5:
            # Weak fits should carry their unexplained residual scatter even when shrinkage
            # keeps the median close to persistence.
            spread = max(spread, S_FLAT_MIN * math.sqrt(max(horizon_days, 0.04)) * (1.0 - credibility))
        lower = spread * (FLAT_LOWER if perfectly_flat else 1.0)
        upper = spread * (FLAT_UPPER if perfectly_flat else 1.0)
        rows.append({"id": trophy["id"], "q": quantiles(median, lower, upper)})
    return {"trophies": rows}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        output = json.dumps(forecast, separators=(",", ":"), allow_nan=False) + "\n"
        if len(output.encode("utf-8")) > MAX_BYTES:
            raise ValueError(f"{path.name} output exceeds {MAX_BYTES} bytes")
        (OUTPUT_DIR / f"{path.stem}.out").write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
