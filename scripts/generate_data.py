#!/usr/bin/env python3
"""Generate realistic synthetic support-operations data for a static dashboard."""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median


@dataclass(frozen=True)
class RegionConfig:
    name: str
    base_created: int
    staffing: float
    monday_multiplier: float


@dataclass(frozen=True)
class ChannelConfig:
    name: str
    share: float
    base_response_hours: float
    base_csat: float
    breach_sensitivity: float


# Six Sigma I-MR control chart constants (subgroup size n=2)
_D2 = 1.128   # d2 constant — converts MR̄ to σ̂
_D4 = 3.267   # D4 constant — UCL factor for MR chart
_D3 = 0.0     # D3 constant — LCL factor for MR chart (= 0 for n=2)
_CSAT_LSL = 75.0   # Lower Specification Limit for CSAT (minimum acceptable daily average)
_CSAT_USL = 100.0  # Upper Specification Limit for CSAT

REGIONS = [
    RegionConfig("North America", 155, 0.98, 1.08),
    RegionConfig("EMEA", 128, 0.96, 1.10),
    RegionConfig("APAC", 116, 0.90, 1.18),
]

CHANNELS = [
    ChannelConfig("Email", 0.45, 7.4, 84.2, 1.20),
    ChannelConfig("Chat", 0.33, 1.3, 91.3, 0.72),
    ChannelConfig("Web", 0.22, 4.2, 87.4, 1.00),
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def round2(value: float) -> float:
    return round(value, 2)


def corr(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mx = mean(xs)
    my = mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denom_x = math.sqrt(sum(v * v for v in dx))
    denom_y = math.sqrt(sum(v * v for v in dy))
    if denom_x == 0 or denom_y == 0:
        return 0.0
    return sum(a * b for a, b in zip(dx, dy)) / (denom_x * denom_y)


def weighted_avg(items: list[tuple[float, float]]) -> float:
    total_weight = sum(weight for _, weight in items)
    if total_weight == 0:
        return 0.0
    return sum(value * weight for value, weight in items) / total_weight


def compute_csat_control_chart(daily: list[dict]) -> dict:
    """Compute a Six Sigma I-MR control chart for daily CSAT.

    Uses the standard constants for subgroup size n=2:
      sigma_hat  = MR_bar / d2  (d2 = 1.128)
      UCL        = x_bar + 3 * sigma_hat
      LCL        = x_bar - 3 * sigma_hat  (floored at 0)
      UCL_MR     = D4 * MR_bar            (D4 = 3.267)
      LCL_MR     = 0

    Western Electric rules checked:
      Rule 1 — one point beyond 3σ control limits
      Rule 2 — eight consecutive points on the same side of the centre line
      Rule 3 — six consecutive points steadily increasing or decreasing
    """
    csat_values = [day["csat"] for day in daily]
    dates = [day["date"] for day in daily]
    n = len(csat_values)

    center_line = mean(csat_values)

    # Moving range: MR_i = |x_i - x_{i-1}|, first point has no MR
    moving_ranges: list[float | None] = [None] + [
        abs(csat_values[i] - csat_values[i - 1]) for i in range(1, n)
    ]
    valid_mrs = [mr for mr in moving_ranges if mr is not None]
    mr_bar = mean(valid_mrs) if valid_mrs else 0.0

    sigma_hat = mr_bar / _D2 if _D2 else 0.0
    ucl = center_line + 3 * sigma_hat
    lcl = max(center_line - 3 * sigma_hat, 0.0)
    ucl_mr = _D4 * mr_bar
    lcl_mr = _D3 * mr_bar  # always 0 for n=2

    # Process capability
    if sigma_hat > 0:
        cpu = ((_CSAT_USL - center_line) / (3 * sigma_hat))
        cpl = ((center_line - _CSAT_LSL) / (3 * sigma_hat))
        cpk = min(cpu, cpl)
        sigma_level = (center_line - _CSAT_LSL) / sigma_hat
    else:
        cpk = 0.0
        sigma_level = 0.0

    # Western Electric rule violations
    rule1_dates = [
        dates[i]
        for i in range(n)
        if csat_values[i] > ucl or csat_values[i] < lcl
    ]

    rule2_dates = []
    for i in range(7, n):
        window = csat_values[i - 7 : i + 1]
        if all(v > center_line for v in window) or all(v < center_line for v in window):
            rule2_dates.append(dates[i])

    rule3_dates = []
    for i in range(5, n):
        window = csat_values[i - 5 : i + 1]
        if all(window[j] < window[j + 1] for j in range(5)) or all(
            window[j] > window[j + 1] for j in range(5)
        ):
            rule3_dates.append(dates[i])

    violations = []
    if rule1_dates:
        violations.append({
            "rule": "Rule 1: Beyond 3σ",
            "dates": rule1_dates,
            "description": (
                f"{len(rule1_dates)} point(s) outside the 3-sigma control limits — "
                "potential special-cause variation."
            ),
        })
    if rule2_dates:
        violations.append({
            "rule": "Rule 2: Run of 8",
            "dates": rule2_dates,
            "description": (
                f"{len(rule2_dates)} run(s) of 8 consecutive points on the same side "
                "of the centre line — possible process shift."
            ),
        })
    if rule3_dates:
        violations.append({
            "rule": "Rule 3: Trend of 6",
            "dates": rule3_dates,
            "description": (
                f"{len(rule3_dates)} trend(s) of 6 consecutive points steadily "
                "increasing or decreasing — sustained drift detected."
            ),
        })

    chart_daily = []
    for i, day in enumerate(daily):
        mr_val = moving_ranges[i]
        chart_daily.append({
            "date": day["date"],
            "csat": day["csat"],
            "moving_range": round2(mr_val) if mr_val is not None else None,
            "i_out_of_control": csat_values[i] > ucl or csat_values[i] < lcl,
            "mr_out_of_control": mr_val is not None and mr_val > ucl_mr,
        })

    return {
        "lsl": _CSAT_LSL,
        "usl": _CSAT_USL,
        "center_line": round2(center_line),
        "ucl": round2(ucl),
        "lcl": round2(lcl),
        "sigma_hat": round2(sigma_hat),
        "mr_bar": round2(mr_bar),
        "ucl_mr": round2(ucl_mr),
        "lcl_mr": round2(lcl_mr),
        "cpk": round2(cpk),
        "sigma_level": round2(sigma_level),
        "violations": violations,
        "daily": chart_daily,
    }


def generate(seed: int, days: int) -> dict:
    rng = random.Random(seed)
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    regional_backlog = {region.name: rng.randint(80, 150) for region in REGIONS}
    daily = []
    segment_rollup: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    region_rollup: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    if days > 40:
        incident_days = {rng.randrange(18, days - 18), rng.randrange(18, days - 18)}
    else:
        incident_days = {days // 3, max(days // 3 + 5, days // 2)}

    for offset in range(days):
        current_date = start_date + timedelta(days=offset)
        dow = current_date.weekday()  # Monday=0
        is_monday = dow == 0
        is_weekend = dow >= 5
        trend = 1.0 + (offset / max(days - 1, 1)) * 0.09
        monthly_wave = 1.0 + 0.05 * math.sin((2 * math.pi * offset) / 30.0)
        incident_multiplier = 1.18 if offset in incident_days else 1.0

        total_created = 0
        total_resolved = 0
        total_backlog_end = 0
        response_weighted = []
        csat_weighted = []
        breach_weighted = []
        region_day_rows = []

        for region in REGIONS:
            weekday_multiplier = 0.78 if is_weekend else region.monday_multiplier if is_monday else 1.0
            noise = rng.uniform(0.93, 1.08)
            created = int(region.base_created * trend * monthly_wave * incident_multiplier * weekday_multiplier * noise)

            staffing_drag = 0.80 if is_weekend else 1.0
            staffing_factor = region.staffing * staffing_drag
            resolution_noise = rng.uniform(0.95, 1.06)
            resolved_capacity = int(region.base_created * staffing_factor * resolution_noise)

            backlog_start = regional_backlog[region.name]
            resolved = min(backlog_start + created, resolved_capacity)
            backlog_end = backlog_start + created - resolved
            regional_backlog[region.name] = backlog_end

            backlog_pressure = backlog_end / max(created, 1)
            base_breach = 0.06 + 0.05 * backlog_pressure
            if is_weekend:
                base_breach += 0.015
            if is_monday:
                base_breach += 0.012
            breach_rate = clamp(base_breach + rng.uniform(-0.01, 0.01), 0.02, 0.40)

            region_ticket_count = 0
            region_response_weighted = []
            region_csat_weighted = []
            region_breach_weighted = []

            channel_breakdown = []
            remaining = created
            for idx, channel in enumerate(CHANNELS):
                if idx == len(CHANNELS) - 1:
                    ch_created = remaining
                else:
                    jitter = 1 + rng.uniform(-0.07, 0.07)
                    ch_created = int(round(created * channel.share * jitter))
                    ch_created = max(0, min(ch_created, remaining))
                    remaining -= ch_created

                response_hours = channel.base_response_hours
                response_hours *= 1 + 0.42 * backlog_pressure
                response_hours *= 1 + (0.12 if is_monday and channel.name == "Email" else 0)
                response_hours *= 1 + (0.06 if region.name == "APAC" else 0)
                response_hours += rng.uniform(-0.35, 0.35)
                response_hours = clamp(response_hours, 0.6, 18.0)

                ch_breach = breach_rate * channel.breach_sensitivity
                ch_breach = clamp(ch_breach + rng.uniform(-0.012, 0.012), 0.01, 0.55)

                csat = channel.base_csat
                csat -= 8.0 * ch_breach
                csat -= 0.45 * max(response_hours - 1.0, 0)
                csat -= 1.8 if region.name == "APAC" and is_monday else 0.0
                csat += rng.uniform(-1.4, 1.4)
                csat = clamp(csat, 68.0, 97.0)

                channel_breakdown.append({
                    "channel": channel.name,
                    "tickets": ch_created,
                    "first_response_hours": round2(response_hours),
                    "sla_breach_rate": round2(ch_breach * 100),
                    "csat": round2(csat),
                })

                key = (region.name, channel.name)
                segment_rollup[key]["tickets"] += ch_created
                segment_rollup[key]["response_hours_weighted"] += response_hours * ch_created
                segment_rollup[key]["csat_weighted"] += csat * ch_created
                segment_rollup[key]["breach_weighted"] += ch_breach * ch_created

                region_rollup[region.name]["tickets"] += ch_created
                region_rollup[region.name]["response_hours_weighted"] += response_hours * ch_created
                region_rollup[region.name]["csat_weighted"] += csat * ch_created
                region_rollup[region.name]["breach_weighted"] += ch_breach * ch_created
                region_rollup[region.name]["created"] += created
                region_rollup[region.name]["resolved"] += resolved
                region_rollup[region.name]["backlog_end_sum"] += backlog_end
                region_rollup[region.name]["days"] += 1

                region_ticket_count += ch_created
                region_response_weighted.append((response_hours, ch_created))
                region_csat_weighted.append((csat, ch_created))
                region_breach_weighted.append((ch_breach, ch_created))

            region_day_rows.append({
                "region": region.name,
                "created": created,
                "resolved": resolved,
                "backlog_end": backlog_end,
                "first_response_hours": round2(weighted_avg(region_response_weighted)),
                "sla_breach_rate": round2(weighted_avg(region_breach_weighted) * 100),
                "csat": round2(weighted_avg(region_csat_weighted)),
                "channels": channel_breakdown,
            })

            total_created += created
            total_resolved += resolved
            total_backlog_end += backlog_end
            response_weighted.append((weighted_avg(region_response_weighted), region_ticket_count))
            csat_weighted.append((weighted_avg(region_csat_weighted), region_ticket_count))
            breach_weighted.append((weighted_avg(region_breach_weighted), region_ticket_count))

        daily.append({
            "date": current_date.isoformat(),
            "weekday": current_date.strftime("%a"),
            "tickets_created": total_created,
            "tickets_resolved": total_resolved,
            "backlog_end": total_backlog_end,
            "first_response_hours": round2(weighted_avg(response_weighted)),
            "sla_breach_rate": round2(weighted_avg(breach_weighted) * 100),
            "csat": round2(weighted_avg(csat_weighted)),
            "regions": region_day_rows,
        })

    channel_stats = []
    for channel in CHANNELS:
        tickets = sum(segment_rollup[(region.name, channel.name)]["tickets"] for region in REGIONS)
        response_hours = sum(segment_rollup[(region.name, channel.name)]["response_hours_weighted"] for region in REGIONS) / max(tickets, 1)
        csat = sum(segment_rollup[(region.name, channel.name)]["csat_weighted"] for region in REGIONS) / max(tickets, 1)
        breach = sum(segment_rollup[(region.name, channel.name)]["breach_weighted"] for region in REGIONS) / max(tickets, 1)
        channel_stats.append({
            "channel": channel.name,
            "tickets": int(tickets),
            "ticket_share": round2(100 * tickets / max(sum(d["tickets_created"] for d in daily), 1)),
            "first_response_hours": round2(response_hours),
            "sla_breach_rate": round2(breach * 100),
            "csat": round2(csat),
        })

    region_stats = []
    for region in REGIONS:
        stats = region_rollup[region.name]
        tickets = stats["tickets"]
        days_count = max(int(stats["days"]), 1)
        region_stats.append({
            "region": region.name,
            "tickets": int(tickets),
            "avg_daily_created": round2(stats["created"] / days_count),
            "avg_daily_resolved": round2(stats["resolved"] / days_count),
            "avg_backlog_end": round2(stats["backlog_end_sum"] / days_count),
            "first_response_hours": round2(stats["response_hours_weighted"] / max(tickets, 1)),
            "sla_breach_rate": round2((stats["breach_weighted"] / max(tickets, 1)) * 100),
            "csat": round2(stats["csat_weighted"] / max(tickets, 1)),
        })

    total_tickets = sum(day["tickets_created"] for day in daily)
    total_resolved = sum(day["tickets_resolved"] for day in daily)
    current_backlog = daily[-1]["backlog_end"]
    first_response_hours = weighted_avg([(day["first_response_hours"], day["tickets_created"]) for day in daily])
    csat_overall = weighted_avg([(day["csat"], day["tickets_created"]) for day in daily])
    breach_overall = weighted_avg([(day["sla_breach_rate"], day["tickets_created"]) for day in daily])

    backlog_series = [day["backlog_end"] for day in daily[:-1]]
    next_day_breach_series = [day["sla_breach_rate"] for day in daily[1:]]
    backlog_to_next_breach_corr = corr(backlog_series, next_day_breach_series)

    monday_created = [day["tickets_created"] for day in daily if day["weekday"] == "Mon"]
    other_created = [day["tickets_created"] for day in daily if day["weekday"] != "Mon"]
    monday_spike_pct = ((mean(monday_created) / mean(other_created)) - 1) * 100

    email = next(item for item in channel_stats if item["channel"] == "Email")
    chat = next(item for item in channel_stats if item["channel"] == "Chat")
    email_chat_response_gap = email["first_response_hours"] - chat["first_response_hours"]
    email_chat_csat_gap = chat["csat"] - email["csat"]

    apac_region = next(item for item in region_stats if item["region"] == "APAC")
    other_regions = [item for item in region_stats if item["region"] != "APAC"]
    apac_backlog_gap = apac_region["avg_backlog_end"] - mean(item["avg_backlog_end"] for item in other_regions)

    last_30 = daily[-30:]
    prev_30 = daily[-60:-30] if len(daily) >= 60 else daily[:-30]
    created_change = 0.0
    if prev_30:
        created_change = ((sum(day["tickets_created"] for day in last_30) / sum(day["tickets_created"] for day in prev_30)) - 1) * 100

    alerts = []
    if daily[-1]["backlog_end"] > median([day["backlog_end"] for day in daily]) * 1.10:
        alerts.append({
            "severity": "high",
            "title": "Backlog elevated",
            "detail": f"Ending backlog is {daily[-1]['backlog_end']} tickets, above the historical median.",
        })
    if email_chat_response_gap > 4.5:
        alerts.append({
            "severity": "medium",
            "title": "Email channel is materially slower than chat",
            "detail": f"Average first response is {email_chat_response_gap:.1f} hours slower on email than chat.",
        })
    if backlog_to_next_breach_corr > 0.45:
        alerts.append({
            "severity": "medium",
            "title": "Backlog is a leading indicator for SLA risk",
            "detail": f"Correlation between backlog and next-day SLA breach is {backlog_to_next_breach_corr:.2f}.",
        })

    hypotheses = [
        {
            "id": "h1",
            "title": "Higher backlog predicts next-day SLA breaches",
            "status": "supported" if backlog_to_next_breach_corr >= 0.40 else "mixed",
            "evidence": f"Lag correlation between backlog and next-day breach rate is {backlog_to_next_breach_corr:.2f}.",
            "metric": "lag_correlation",
            "value": round2(backlog_to_next_breach_corr),
        },
        {
            "id": "h2",
            "title": "Email is slower and less loved than chat",
            "status": "supported" if email_chat_response_gap > 3.0 and email_chat_csat_gap > 3.0 else "mixed",
            "evidence": f"Email is {email_chat_response_gap:.1f} hours slower; chat CSAT is {email_chat_csat_gap:.1f} points higher.",
            "metric": "gap",
            "value": round2(email_chat_response_gap),
        },
        {
            "id": "h3",
            "title": "Weekends create a Monday spike",
            "status": "supported" if monday_spike_pct > 8.0 else "mixed",
            "evidence": f"Mondays show {monday_spike_pct:.1f}% more created tickets than the non-Monday average.",
            "metric": "monday_spike_pct",
            "value": round2(monday_spike_pct),
        },
        {
            "id": "h4",
            "title": "APAC carries the sharpest backlog burden",
            "status": "supported" if apac_backlog_gap > 10 else "mixed",
            "evidence": f"APAC average backlog exceeds the other regions by {apac_backlog_gap:.1f} tickets.",
            "metric": "backlog_gap",
            "value": round2(apac_backlog_gap),
        },
    ]

    csat_control_chart = compute_csat_control_chart(daily)

    return {
        "metadata": {
            "title": "Support Operations Health",
            "domain": "B2B SaaS customer support",
            "generated_on": end_date.isoformat(),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": days,
            "seed": seed,
            "notes": [
                "Synthetic dataset designed to feel realistic rather than represent a real company.",
                "Fresh seed on every GitHub Pages deploy creates small but plausible movement.",
            ],
        },
        "kpis": {
            "tickets_created": int(total_tickets),
            "tickets_resolved": int(total_resolved),
            "open_backlog": int(current_backlog),
            "first_response_hours": round2(first_response_hours),
            "sla_breach_rate": round2(breach_overall),
            "csat": round2(csat_overall),
            "created_change_last_30d_pct": round2(created_change),
        },
        "daily": daily,
        "channel_stats": channel_stats,
        "region_stats": region_stats,
        "alerts": alerts,
        "hypotheses": hypotheses,
        "narrative": [
            "The operation is mostly healthy, but backlog remains the best leading indicator of service failure.",
            "Chat performs best on both speed and satisfaction, while email is the main drag on service quality.",
            "The operating model looks slightly under-staffed around weekends, especially in APAC.",
        ],
        "csat_control_chart": csat_control_chart,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible output")
    parser.add_argument("--days", type=int, default=180, help="Number of days to generate")
    parser.add_argument("--output", type=Path, default=Path("site/data/dashboard.json"), help="Output JSON file")
    args = parser.parse_args()

    payload = generate(seed=args.seed, days=args.days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.output} with seed={args.seed} days={args.days}")


if __name__ == "__main__":
    main()
