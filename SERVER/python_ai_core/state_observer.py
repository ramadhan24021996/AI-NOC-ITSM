import json
import logging
from datetime import datetime, timezone
from typing import Protocol, List, Optional
from state_machine import IncidentStateMachine, IncidentState

logger = logging.getLogger("STATE_OBSERVER")

class StateTransitionObserver(Protocol):
    async def on_transition(self, nc, conn, event: dict):
        """Called when a state transition occurs."""
        pass

class TelemetryObserver:
    """Publishes state transitions to NATS for external systems (Dashboard, etc.)"""
    async def on_transition(self, nc, conn, event: dict):
        if not nc:
            return
        try:
            site_id = event.get("site_id", "global")
            await nc.publish(f"incident.state_transition.{site_id}", json.dumps(event).encode())
            
            # Legacy UI update topic
            update_event = {
                "incident_id": event["incident_id"],
                "site_id": site_id,
                "status": event["to_state"],
                "timestamp": event["timestamp"]
            }
            await nc.publish(f"incident.site.{site_id}.update", json.dumps(update_event).encode())
        except Exception as e:
            logger.error(f"[TELEMETRY OBSERVER] Failed to publish telemetry: {e}")

class AuditObserver:
    """Records the transition into CQRS event store"""
    async def on_transition(self, nc, conn, event: dict):
        if not conn:
            return
        try:
            from core.event_store import get_event_store
            event_store = get_event_store(conn)
            
            incident_id = str(event["incident_id"])
            event_type = f"STATE_TRANSITION_{event['to_state']}"
            payload = {
                "from_state": event["from_state"],
                "to_state": event["to_state"],
                "actor": event["actor"],
                "context": event.get("context", {}),
                "state_version": event.get("state_version", 1)
            }
            event_store.append_event(incident_id, event_type, payload, event["actor"])
        except Exception as e:
            logger.error(f"[AUDIT OBSERVER] Failed to append event: {e}")

class IncidentEventBus:
    """
    Central Nervous System for Incident State Changes.
    Ensures that State Machine is pure, and Observers are decoupled.
    """
    def __init__(self):
        self.observers: List[StateTransitionObserver] = []
        self.state_machine = IncidentStateMachine()
        
    def register_observer(self, observer: StateTransitionObserver):
        self.observers.append(observer)
        
    async def apply_transition(
        self, 
        nc, 
        conn, 
        incident_id: int, 
        from_state: str, 
        to_state: str, 
        site_id: str = "global", 
        actor: str = "system", 
        context: dict = None
    ) -> bool:
        """The SINGLE GATEWAY for state transitions and fleet_incidents updates."""
        
        result = self.state_machine.transition(from_state, to_state)
        
        if not result.success:
            logger.error(f"[EVENT BUS] Transition Rejected: {from_state} -> {to_state} for {incident_id}: {result.reason}")
            return False
            
        if result.reason == "NO_OP":
            return True
            
        # 1. Database Transaction (Atomic update of fleet_incidents & incident_states)
        new_version = 1
        if conn and incident_id is not None:
            try:
                with conn.cursor() as cur:
                    # Update fleet_incidents and increment state_version
                    cur.execute("""
                        UPDATE fleet_incidents 
                        SET status = %s, 
                            state_version = COALESCE(state_version, 0) + 1
                        WHERE incident_id = %s
                        RETURNING state_version
                    """, (to_state, incident_id))
                    
                    row = cur.fetchone()
                    if row:
                        new_version = row[0]
                    
                    # Log transition
                    cur.execute("""
                        INSERT INTO incident_states
                            (incident_id, from_state, to_state, result, reason,
                             actor, site_id, context, flag, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT DO NOTHING
                    """, (
                        incident_id, from_state, to_state, "APPLIED", result.reason,
                        actor, site_id,
                        json.dumps(context or {}),
                        "APPLIED"
                    ))
                conn.commit()
            except Exception as e:
                logger.error(f"[EVENT BUS] Database Error for {incident_id}: {e}")
                try:
                    conn.rollback()
                except:
                    pass
                return False
                
        # 2. Build Rich Event Payload
        event_payload = {
            "incident_id": incident_id,
            "site_id": site_id,
            "from_state": from_state,
            "to_state": to_state,
            "actor": actor,
            "reason": result.reason,
            "state_version": new_version,
            "timestamp": result.timestamp,
            "context": context or {}
        }
        
        # 3. Notify all Observers asynchronously
        for obs in self.observers:
            try:
                await obs.on_transition(nc, conn, event_payload)
            except Exception as e:
                logger.error(f"[EVENT BUS] Observer {obs.__class__.__name__} failed: {e}")
                
        return True

# Singleton instance
incident_event_bus = IncidentEventBus()
incident_event_bus.register_observer(TelemetryObserver())
incident_event_bus.register_observer(AuditObserver())
