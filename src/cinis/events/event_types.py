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

# A ConstructionProject reached its AdjustedDurationMonths and the ordered
# buildings were added to the city's Building count (ADR-0011, Step 4.5c).
# Not required by ADR-0011 itself; added for consistency with
# NEEDS_SHORTFALL and Document 7's explainability requirement. Payload:
# ConstructionProjectID, BuildingTypeCode, BuildingsOrdered.
CONSTRUCTION_COMPLETED = "ConstructionCompleted"
