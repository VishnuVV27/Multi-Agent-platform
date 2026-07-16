"""
Kafka Event Consumer: Listens to agent events for observability and logging.

Consumes events published by agents and stores them for:
- Audit logging
- Observability/monitoring
- Analytics
- Debugging
"""

import asyncio
import json
from datetime import datetime
from typing import Callable, Dict, Any, Optional

from src.infrastructure.kafka_client import create_consumer
from src.config import settings


class EventConsumer:
    """Consume and process Kafka events."""

    def __init__(self):
        """Initialize consumer."""
        self.consumer = None
        self.handlers: Dict[str, Callable] = {}
        self.event_buffer = []

    def register_handler(self, event_type: str, handler: Callable):
        """Register a handler for a specific event type."""
        self.handlers[event_type] = handler

    async def start(self, topics: list[str]):
        """Start consuming events."""
        self.consumer = await create_consumer(
            group_id="observability-consumer"
        )

        try:
            self.consumer.subscribe(topics)
            await self._consume_loop()
        finally:
            self.consumer.close()

    async def _consume_loop(self):
        """Main consume loop."""
        while True:
            try:
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    print(f"Consumer error: {msg.error()}")
                    continue

                # Parse event
                try:
                    event_data = json.loads(msg.value())
                    event_type = event_data.get("event_type")

                    # Store in buffer
                    self.event_buffer.append({
                        "event_type": event_type,
                        "data": event_data,
                        "received_at": datetime.utcnow().isoformat(),
                    })

                    # Call handler if registered
                    if event_type in self.handlers:
                        await self.handlers[event_type](event_data)

                    # Keep buffer to last 1000 events
                    if len(self.event_buffer) > 1000:
                        self.event_buffer = self.event_buffer[-1000:]

                except Exception as e:
                    print(f"Error processing event: {e}")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Consumer loop error: {e}")
                await asyncio.sleep(1)

    def get_events(self, event_type: Optional[str] = None) -> list:
        """Get buffered events, optionally filtered by type."""
        if event_type:
            return [e for e in self.event_buffer if e["event_type"] == event_type]
        return self.event_buffer.copy()

    async def handle_agent_started(self, event: Dict[str, Any]):
        """Handle agent.started event."""
        print(f"[{event.get('timestamp')}] Agent started: {event.get('agent_id')}")

    async def handle_agent_completed(self, event: Dict[str, Any]):
        """Handle agent.completed event."""
        print(f"[{event.get('timestamp')}] Agent completed: {event.get('agent_id')}")

    async def handle_agent_failed(self, event: Dict[str, Any]):
        """Handle agent.failed event."""
        print(f"[{event.get('timestamp')}] Agent failed: {event.get('agent_id')}")


# Global consumer instance
_event_consumer = None


def get_event_consumer() -> EventConsumer:
    """Get the global event consumer."""
    global _event_consumer
    if _event_consumer is None:
        _event_consumer = EventConsumer()
    return _event_consumer
