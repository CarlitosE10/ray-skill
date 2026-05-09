#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "yfinance>=0.2.40",
#     "pandas>=2.0.0",
#     "pydantic>=2.0.0",
# ]
# ///
"""
Ray — Decision Agent (entrypoint)

Subcommands:
    decide       Full pipeline: BUY/HOLD/SELL with conviction and sizing
    dcf          DCF 3-scenarios only (Snowball JSON in)
    mos          MOS thresholds (fair value + Charlie JSON)
    sync         Sync gate only (Snowball + Charlie JSONs)
    conviction   Conviction score only
    sizing       Position sizing standalone

Output is JSON by default. Pass --format text for human-readable.

Examples:
    uv run ray.py decide --snowball aapl_snowball.json --charlie aapl_charlie.json
    uv run ray.py decide --snowball s.json --charlie c.json --portfolio p.json --risk-profile aggressive
    uv run ray.py dcf --snowball s.json --charlie c.json --format text
    uv run ray.py sync --snowball s.json --charlie c.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Make sibling modules importable
sys.path.insert(0, str(Path(__file__).parent))

from conviction import calc_conviction
from dcf import run_dcf
from inputs import load_charlie, load_portfolio, load_snowball
from margin_of_safety import calc_margin_of_safety
from pipeline import run_pipeline
from sync_gate import detect_conflicts


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def emit_json(obj: Any) -> None:
    if hasattr(obj, "model_dump"):
        data = obj.model_dump()
    elif isinstance(obj, list):
        data = [o.model_dump() if hasattr(o, "model_dump") else o for o in obj]
    else:
        data = obj
    print(json.dumps(data, indent=2, default=str))


def fmt_money(x):
    if x is None:
        return "—"
    if abs(x) >= 1e12:
        return f"${x / 1e12:.2f}T"
    if abs(x) >= 1e9:
        return f"${x / 1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:.2f}M"
    return f"${x:,.2f}"


def fmt_pct(x, digits=2):
    if x is None:
        return "—"
    return f"{x * 100:.{digits}f}%" if abs(x) < 5 else f"{x:.{digits}f}%"


def hr(width=70):
    return "─" * width


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND HANDLERS
# ─────────────────────────────────────────────────────────────────────────────


def cmd_decide(args):
    snowball = load_snowball(args.snowball)
    charlie = load_charlie(args.charlie)
    portfolio = load_portfolio(args.portfolio) if args.portfolio else None

    decision = run_pipeline(
        snowball=snowball,
        charlie=charlie,
        portfolio=portfolio,
        risk_profile=args.risk_profile,
    )

    if args.format == "json":
        emit_json(decision)
        return

    # Human-readable rendering
    badge = {
        "BUY": "🟢 BUY",
        "HOLD": "🟡 HOLD",
        "SELL": "🔴 SELL",
        "INSUFFICIENT_DATA": "⚪ INSUFFICIENT DATA",
    }.get(decision.decision, decision.decision)

    print(f"RAY — Decision: {decision.ticker}")
    print(hr())
    print(f"  Company: {decision.company_name or '—'}")
    print(f"  Sector:  {decision.sector or '—'}")
    print()
    print(f"  ► {badge}")
    print(f"  {decision.decision_reasoning}")
    print()

    if decision.current_price is not None:
        print(f"  Current price:    {fmt_money(decision.current_price)}")
    if decision.fair_value_per_share is not None:
        print(f"  Fair value:       {fmt_money(decision.fair_value_per_share)}")
    if decision.upside_pct is not None:
        sign = "+" if decision.upside_pct >= 0 else ""
        print(f"  Upside:           {sign}{decision.upside_pct:.1f}%")
    print()

    if decision.margin_of_safety:
        m = decision.margin_of_safety
        print("─ MARGIN OF SAFETY ─")
        print(f"  Applied MOS:      {m.applied_mos_pct * 100:.0f}%  (base {m.base_mos_pct * 100:.0f}% from MOAT '{m.moat_input}')")
        print(f"  Buy below:        {fmt_money(m.buy_below)}")
        print(f"  Sell above:       {fmt_money(m.sell_above)}")
        print(f"  {m.reasoning}")
        print()

    if decision.dcf and decision.dcf.scenarios:
        print("─ DCF SCENARIOS ─")
        print(f"  {'Scenario':<14} {'Growth p1':>10} {'Terminal':>9} {'WACC':>7} {'FV/sh':>10} {'Weight':>8}")
        for s in decision.dcf.scenarios:
            print(
                f"  {s.name:<14} "
                f"{s.growth_phase1_pct * 100:>9.1f}% "
                f"{s.terminal_growth_pct * 100:>8.1f}% "
                f"{s.wacc_pct * 100:>6.1f}% "
                f"{fmt_money(s.fair_value_per_share):>10} "
                f"{s.weight * 100:>7.0f}%"
            )
        print(f"  {'WEIGHTED':<14} {'':>10} {'':>9} {'':>7} {fmt_money(decision.dcf.weighted_fair_value_per_share):>10}")
        print()
        if decision.dcf.sensitivity_notes:
            for n in decision.dcf.sensitivity_notes:
                print(f"  • {n}")
            print()

    if decision.conviction:
        c = decision.conviction
        print("─ CONVICTION ─")
        print(f"  Level: {c.level.upper()} ({c.weighted_score:.0f}/100)")
        print(f"    quantitative confidence: {c.quantitative_confidence:>5.1f}/100  (× 40%)")
        print(f"    qualitative score:       {c.qualitative_score:>5.1f}/100  (× 30%)")
        print(f"    distance to threshold:   {c.distance_to_threshold:>5.1f}/100  (× 15%)")
        print(f"    coherence:               {c.coherence:>5.1f}/100  (× 15%)")
        print()

    if decision.sync_gate_conflicts:
        print("─ SYNC GATE — SNOWBALL ↔ CHARLIE CONFLICTS ─")
        for cf in decision.sync_gate_conflicts:
            tag = {"info": "ⓘ", "warning": "⚠", "critical": "✕"}.get(cf.severity, "•")
            print(f"  {tag} [{cf.pattern}]  −{cf.conviction_penalty_pp:.0f}pp")
            print(f"     {cf.description}")
        print()

    if decision.position_sizing:
        ps = decision.position_sizing
        print("─ POSITION SIZING ─")
        if ps.suggested_pct_of_portfolio is not None and ps.suggested_pct_of_portfolio > 0:
            print(f"  Suggested:  {ps.suggested_pct_of_portfolio:.2f}% of portfolio  (cap {ps.cap_pct:.1f}% on '{ps.risk_profile}' profile)")
            if ps.suggested_dollar_amount:
                print(f"              ≈ {fmt_money(ps.suggested_dollar_amount)}")
        else:
            print(f"  No new allocation suggested.")
        print(f"  {ps.rationale}")
        print()

    print(f"─ TIME HORIZON ─")
    print(f"  {decision.time_horizon}  — {decision.time_horizon_reasoning}")
    print()

    if decision.key_drivers:
        print("─ KEY DRIVERS ─")
        for d in decision.key_drivers:
            print(f"  • {d}")
        print()

    if decision.key_risks:
        print("─ KEY RISKS ─")
        for r in decision.key_risks:
            print(f"  • {r}")
        print()

    if decision.data_quality.warnings:
        print("─ DATA QUALITY ─")
        for w in decision.data_quality.warnings:
            print(f"  ⚠ {w}")
        if decision.data_quality.blocking_issues:
            for b in decision.data_quality.blocking_issues:
                print(f"  ✕ {b}")
        print()

    print(decision.disclaimer)


def cmd_dcf(args):
    snowball = load_snowball(args.snowball)
    charlie = load_charlie(args.charlie)
    dcf = run_dcf(snowball, charlie)
    if args.format == "json":
        emit_json(dcf)
        return
    print(f"DCF — {snowball.ticker}")
    print(hr())
    print(f"  FCF starting:  {fmt_money(dcf.fcf_starting_point)}")
    print(f"  Shares out:    {dcf.shares_outstanding:,.0f}" if dcf.shares_outstanding else "  Shares out:    —")
    print(f"  Net debt:      {fmt_money(dcf.net_debt)}")
    print()
    if dcf.scenarios:
        print(f"  {'Scenario':<14} {'Growth p1':>10} {'Terminal':>9} {'WACC':>7} {'FV/sh':>10} {'Weight':>8}")
        for s in dcf.scenarios:
            print(
                f"  {s.name:<14} "
                f"{s.growth_phase1_pct * 100:>9.1f}% "
                f"{s.terminal_growth_pct * 100:>8.1f}% "
                f"{s.wacc_pct * 100:>6.1f}% "
                f"{fmt_money(s.fair_value_per_share):>10} "
                f"{s.weight * 100:>7.0f}%"
            )
        print(f"  {'WEIGHTED':<14} {'':>10} {'':>9} {'':>7} {fmt_money(dcf.weighted_fair_value_per_share):>10}")
    print()
    for n in dcf.sensitivity_notes:
        print(f"  • {n}")


def cmd_mos(args):
    charlie = load_charlie(args.charlie)
    mos = calc_margin_of_safety(charlie, args.fair_value, risk_profile=args.risk_profile)
    if args.format == "json":
        emit_json(mos)
        return
    print(f"MARGIN OF SAFETY — {charlie.ticker}")
    print(hr(40))
    print(f"  MOAT input:        {mos.moat_input}")
    print(f"  Base MOS:          {mos.base_mos_pct * 100:.0f}%")
    print(f"  Applied MOS:       {mos.applied_mos_pct * 100:.0f}%  (after risk profile '{args.risk_profile}')")
    print(f"  Sell premium:      {mos.sell_premium_pct * 100:.0f}%")
    print(f"  Buy below:         {fmt_money(mos.buy_below)}")
    print(f"  Sell above:        {fmt_money(mos.sell_above)}")
    print(f"  {mos.reasoning}")


def cmd_sync(args):
    snowball = load_snowball(args.snowball)
    charlie = load_charlie(args.charlie)
    conflicts = detect_conflicts(snowball, charlie)
    if args.format == "json":
        emit_json(conflicts)
        return
    print(f"SYNC GATE — {snowball.ticker}")
    print(hr())
    if not conflicts:
        print("  No Snowball ↔ Charlie conflicts detected. ✓")
        return
    for cf in conflicts:
        tag = {"info": "ⓘ", "warning": "⚠", "critical": "✕"}.get(cf.severity, "•")
        print(f"  {tag} [{cf.pattern}]  −{cf.conviction_penalty_pp:.0f}pp")
        print(f"     {cf.description}")
        print()


def cmd_conviction(args):
    snowball = load_snowball(args.snowball)
    charlie = load_charlie(args.charlie)
    # Run pipeline to derive thresholds, then conviction
    decision = run_pipeline(snowball, charlie, risk_profile=args.risk_profile)
    if args.format == "json":
        emit_json(decision.conviction)
        return
    c = decision.conviction
    if c is None:
        print("Conviction unavailable — pipeline blocked.")
        return
    print(f"CONVICTION — {snowball.ticker}")
    print(hr(40))
    print(f"  Score: {c.weighted_score:.0f}/100  →  {c.level.upper()}")
    print(f"    quantitative confidence: {c.quantitative_confidence:>5.1f}/100  (× 40%)")
    print(f"    qualitative score:       {c.qualitative_score:>5.1f}/100  (× 30%)")
    print(f"    distance to threshold:   {c.distance_to_threshold:>5.1f}/100  (× 15%)")
    print(f"    coherence:               {c.coherence:>5.1f}/100  (× 15%)")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(prog="ray", description="Ray decision agent")
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=["json", "text"], default="json")
    common.add_argument(
        "--risk-profile",
        choices=["conservative", "moderate", "aggressive"],
        default="moderate",
    )

    p_dec = sub.add_parser("decide", parents=[common], help="Full pipeline (BUY/HOLD/SELL)")
    p_dec.add_argument("--snowball", required=True, help="Path to Snowball JSON")
    p_dec.add_argument("--charlie", required=True, help="Path to Charlie JSON")
    p_dec.add_argument("--portfolio", help="Optional path to portfolio JSON")
    p_dec.set_defaults(func=cmd_decide)

    p_dcf = sub.add_parser("dcf", parents=[common], help="DCF 3-scenarios only")
    p_dcf.add_argument("--snowball", required=True)
    p_dcf.add_argument("--charlie", required=True)
    p_dcf.set_defaults(func=cmd_dcf)

    p_mos = sub.add_parser("mos", parents=[common], help="Margin of Safety thresholds")
    p_mos.add_argument("--charlie", required=True)
    p_mos.add_argument("--fair-value", required=True, type=float)
    p_mos.set_defaults(func=cmd_mos)

    p_sync = sub.add_parser("sync", parents=[common], help="Sync-gate conflict detection")
    p_sync.add_argument("--snowball", required=True)
    p_sync.add_argument("--charlie", required=True)
    p_sync.set_defaults(func=cmd_sync)

    p_con = sub.add_parser("conviction", parents=[common], help="Conviction score breakdown")
    p_con.add_argument("--snowball", required=True)
    p_con.add_argument("--charlie", required=True)
    p_con.set_defaults(func=cmd_conviction)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
