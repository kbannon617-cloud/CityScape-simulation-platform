"""
Event type codes written to SimulationEvent.EventType.

The set of event types is deliberately not a database table yet (see
migration 0019). Constants live here so emitters and readers share one
spelling.
"""

# A need could not be fully met from the resources mapped to it (ADR-0009
# Decision 2). Payload: NeedTypeCode, Needed, Consumed, Shortfall as exact
# Decimal strings.
NEEDS_SHORTFALL = "NeedsShortfall"
