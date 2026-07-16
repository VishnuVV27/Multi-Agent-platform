from confluent_kafka import Producer, Consumer
from confluent_kafka.admin import AdminClient, NewTopic
from typing import Optional, Callable
import json
import uuid

from src.config import settings

producer: Optional[Producer] = None
admin_client: Optional[AdminClient] = None


async def init_kafka():
    """Initialize Kafka producer and admin client."""
    global producer, admin_client
    try:
        # Initialize producer
        producer = Producer({
            'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS,
            'client.id': f'producer-{uuid.uuid4().hex[:8]}',
        })

        # Initialize admin client
        admin_client = AdminClient({
            'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS,
        })

        # Create topics if they don't exist
        await create_topics()

        print("✅ Kafka initialized")
    except Exception as e:
        print(f"❌ Kafka initialization failed: {e}")
        raise


async def create_topics():
    """Create Kafka topics if they don't exist."""
    if admin_client is None:
        raise RuntimeError("Kafka not initialized")

    topics_to_create = [
        NewTopic(topic, num_partitions=1, replication_factor=1)
        for topic in settings.KAFKA_TOPICS.values()
    ]

    # Create topics (ignore if they already exist)
    try:
        fs = admin_client.create_topics(topics_to_create, validate_only=False)
        for topic, f in fs.items():
            try:
                f.result()
                print(f"  ✓ Topic '{topic}' created or already exists")
            except Exception as e:
                if "already exists" in str(e):
                    pass  # Topic exists, this is fine
                else:
                    print(f"  ⚠ Topic '{topic}' creation issue: {e}")
    except Exception as e:
        print(f"⚠ Could not create topics: {e}")


def get_producer() -> Producer:
    """Get Kafka producer instance."""
    if producer is None:
        raise RuntimeError("Kafka not initialized. Call init_kafka() first.")
    return producer


def delivery_report(err, msg):
    """Kafka delivery report callback."""
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")


async def publish_event(topic: str, event_data: dict, event_id: str = None):
    """Publish an event to Kafka."""
    if event_id is None:
        event_id = str(uuid.uuid4())

    p = get_producer()

    # Add event metadata
    event_data['event_id'] = event_id
    event_data['timestamp'] = None  # Will be added by Kafka

    try:
        p.produce(
            topic,
            value=json.dumps(event_data),
            key=event_id,
            callback=delivery_report
        )
        p.flush()
        return event_id
    except Exception as e:
        print(f"Error publishing event: {e}")
        raise


async def create_consumer(group_id: str):
    """Create a Kafka consumer."""
    consumer = Consumer({
        'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS,
        'group.id': group_id,
        'auto.offset.reset': 'earliest',
    })
    return consumer


async def consume_events(consumer: Consumer, topics: list, callback: Callable):
    """Consume events from Kafka."""
    consumer.subscribe(topics)

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue

            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue

            try:
                event_data = json.loads(msg.value())
                await callback(event_data)
            except Exception as e:
                print(f"Error processing message: {e}")

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
