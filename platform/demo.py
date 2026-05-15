"""Standalone demo entrypoint for local pipeline traces.

Author: Sarala Biswal
"""

from __future__ import annotations

import argparse
import asyncio
import time
from platform.core.config import settings
from platform.layer6_sdk import BlueprintRunner, blueprint_for_scenario
from platform.observability.logging import configure_logging
from platform.observability.tracing import configure_tracing, force_flush_traces


async def _run(customer_id: str, scenario: str) -> None:
    """Run one full six-layer pipeline demo with mock infrastructure."""
    runner = BlueprintRunner()
    blueprint = blueprint_for_scenario(scenario)
    started = time.perf_counter()
    result = await runner.run(
        blueprint=blueprint,
        customer_id=customer_id,
        trigger="demo",
        caller_id="demo_cli",
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    print("Banking Agentic AI Platform -- Demo")
    print(f"customer_id: {customer_id}")
    print(f"scenario: {blueprint.scenario}")
    print(f"trace_id: {result.trace_id}")
    print("")
    print("Layer timeline:")
    for event in runner.event_bus.events_for(result.trace_id):
        if event.event_type != "layer_completed":
            continue
        layer = event.payload["layer"]
        latency_ms = event.payload["latency_ms"]
        print(f"  {layer}: {latency_ms}ms")
    print("")
    print("Action summary:")
    print(f"  action_executed: {result.action_executed}")
    print(f"  action_id: {result.action_id}")
    print(f"  status: {result.status}")
    print(f"  channel: {result.channel.value if result.channel is not None else 'NONE'}")
    print(f"  outcome_tracking_id: {result.outcome_tracking_id}")
    print(f"  customer_message: {result.customer_message}")
    print(f"  pending_actions: {len(result.pending_actions)}")
    print(f"total_ms: {elapsed_ms}")
    force_flush_traces()


def main() -> None:
    """Run the demo via ``python -m platform.demo``."""
    configure_logging(settings)
    configure_tracing(settings)
    parser = argparse.ArgumentParser(description="Run the local banking AI platform demo.")
    parser.add_argument("--customer", default="C002")
    parser.add_argument("--scenario", default="payment_risk_intervention")
    args = parser.parse_args()
    asyncio.run(_run(customer_id=args.customer, scenario=args.scenario))


if __name__ == "__main__":
    main()
