"""
Message Queue System
====================
Production-ready message queue with Redis backend and event handling.
"""

import os
import json
import asyncio
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime
from enum import Enum
import structlog

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = structlog.get_logger(__name__)

# Try to import Redis
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not installed, using in-memory queue")


class EventType(str, Enum):
    """System event types."""
    # Invoice events
    INVOICE_UPLOADED = "invoice.uploaded"
    INVOICE_PROCESSED = "invoice.processed"
    INVOICE_APPROVED = "invoice.approved"
    INVOICE_REJECTED = "invoice.rejected"
    INVOICE_PAID = "invoice.paid"
    
    # Payment events
    PAYMENT_INITIATED = "payment.initiated"
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    
    # ERP events
    ERP_SYNC_STARTED = "erp.sync_started"
    ERP_SYNC_COMPLETED = "erp.sync_completed"
    ERP_SYNC_FAILED = "erp.sync_failed"
    
    # Approval events
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_ASSIGNED = "approval.assigned"
    APPROVAL_COMPLETED = "approval.completed"
    
    # System events
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"


class MessagePriority(int, Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class Message:
    """Message wrapper for queue."""
    
    def __init__(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: Optional[str] = None
    ):
        self.id = f"msg_{datetime.utcnow().timestamp()}"
        self.event_type = event_type
        self.data = data
        self.priority = priority
        self.correlation_id = correlation_id or self.id
        self.timestamp = datetime.utcnow()
        self.retry_count = 0
        self.max_retries = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type.value if isinstance(self.event_type, EventType) else self.event_type,
            "data": self.data,
            "priority": self.priority.value if isinstance(self.priority, MessagePriority) else self.priority,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        msg = cls(
            event_type=EventType(data["event_type"]),
            data=data["data"],
            priority=MessagePriority(data.get("priority", MessagePriority.NORMAL.value)),
            correlation_id=data.get("correlation_id")
        )
        msg.id = data["id"]
        msg.timestamp = datetime.fromisoformat(data["timestamp"])
        msg.retry_count = data.get("retry_count", 0)
        msg.max_retries = data.get("max_retries", 3)
        return msg


class RedisMessageQueue:
    """
    Redis-based message queue with pub/sub and stream support.
    
    Features:
    - Multiple channels for different event types
    - Message persistence with Redis Streams
    - Consumer groups for distributed processing
    - Dead letter queue for failed messages
    - Priority queue support
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.handlers: Dict[str, List[Callable]] = {}
        self.consumer_tasks: List[asyncio.Task] = []
        self.logger = logger.bind(component="RedisMessageQueue")
        self._running = False
    
    async def connect(self) -> bool:
        """Connect to Redis."""
        if not REDIS_AVAILABLE:
            self.logger.warning("Redis not available")
            return False
        
        try:
            # Parse password from URL if present
            from urllib.parse import urlparse
            parsed = urlparse(self.redis_url)
            
            # Build connection kwargs
            kwargs = {
                "encoding": "utf-8",
                "decode_responses": True
            }
            
            # Extract password from URL (format: redis://:password@host or redis://user:password@host)
            if parsed.password:
                kwargs["password"] = parsed.password
            
            self.redis_client = redis.from_url(
                self.redis_url,
                **kwargs
            )
            # Test the connection
            await self.redis_client.ping()
            self.logger.info("Connected to Redis successfully", host=parsed.hostname, port=parsed.port)
            return True
        except redis.AuthenticationError as e:
            self.logger.error("Redis authentication failed", error=str(e), url_format=self.redis_url)
            return False
        except redis.ConnectionError as e:
            self.logger.error("Redis connection failed", error=str(e))
            return False
        except Exception as e:
            self.logger.error("Failed to connect to Redis", error=str(e), error_type=type(e).__name__)
            return False
    
    async def disconnect(self):
        """Disconnect from Redis."""
        self._running = False
        
        # Cancel consumer tasks
        for task in self.consumer_tasks:
            task.cancel()
        
        if self.consumer_tasks:
            await asyncio.gather(*self.consumer_tasks, return_exceptions=True)
        
        if self.pubsub:
            await self.pubsub.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        self.logger.info("Disconnected from Redis")
    
    async def publish(self, message: Message) -> bool:
        """
        Publish message to Redis.
        
        Uses both pub/sub (for real-time) and streams (for persistence).
        """
        if not self.redis_client:
            self.logger.warning("Redis not connected")
            return False
        
        try:
            message_data = json.dumps(message.to_dict())
            channel = f"events:{message.event_type.value}"
            stream = f"stream:{message.event_type.value}"
            
            # Pub/Sub for real-time notifications
            await self.redis_client.publish(channel, message_data)
            
            # Stream for persistence and replay
            await self.redis_client.xadd(
                stream,
                {"data": message_data},
                maxlen=10000  # Keep last 10k messages
            )
            
            # Priority queue for task processing
            priority_queue = f"queue:{message.priority.value}"
            await self.redis_client.rpush(priority_queue, message_data)
            
            self.logger.debug(
                "Message published",
                event_type=message.event_type.value,
                message_id=message.id,
                priority=message.priority.value
            )
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to publish message", error=str(e))
            return False
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """Subscribe handler to event type."""
        event_key = event_type.value
        if event_key not in self.handlers:
            self.handlers[event_key] = []
        self.handlers[event_key].append(handler)
        self.logger.debug("Handler subscribed", event_type=event_key)
    
    async def start_consumers(self):
        """Start consumer tasks for all subscribed event types."""
        self._running = True
        
        for event_type in self.handlers.keys():
            task = asyncio.create_task(self._consume_channel(event_type))
            self.consumer_tasks.append(task)
        
        self.logger.info(
            "Consumers started",
            count=len(self.consumer_tasks),
            event_types=list(self.handlers.keys())
        )
    
    async def _consume_channel(self, event_type: str):
        """Consume messages from a specific channel."""
        if not self.redis_client:
            return
        
        channel = f"events:{event_type}"
        
        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(channel)
            
            self.logger.info("Consumer started", channel=channel)
            
            async for message in pubsub.listen():
                if not self._running:
                    break
                
                if message["type"] == "message":
                    await self._handle_message(event_type, message["data"])
            
        except Exception as e:
            self.logger.error("Consumer error", channel=channel, error=str(e))
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
    
    async def _handle_message(self, event_type: str, message_data: str):
        """Handle incoming message."""
        try:
            message_dict = json.loads(message_data)
            message = Message.from_dict(message_dict)
            
            handlers = self.handlers.get(event_type, [])
            
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                except Exception as e:
                    self.logger.error(
                        "Handler failed",
                        event_type=event_type,
                        handler=handler.__name__,
                        error=str(e)
                    )
                    await self._send_to_dlq(message, str(e))
        
        except Exception as e:
            self.logger.error("Failed to handle message", error=str(e))
    
    async def _send_to_dlq(self, message: Message, error: str):
        """Send failed message to dead letter queue."""
        if not self.redis_client:
            return
        
        try:
            dlq_data = {
                **message.to_dict(),
                "error": error,
                "failed_at": datetime.utcnow().isoformat()
            }
            
            await self.redis_client.rpush(
                "dlq:failed_messages",
                json.dumps(dlq_data)
            )
            
            self.logger.warning(
                "Message sent to DLQ",
                message_id=message.id,
                event_type=message.event_type.value
            )
        
        except Exception as e:
            self.logger.error("Failed to send to DLQ", error=str(e))
    
    async def get_stream_messages(
        self,
        event_type: EventType,
        count: int = 100,
        start_id: str = "0"
    ) -> List[Message]:
        """Get messages from stream (for replay/history)."""
        if not self.redis_client:
            return []
        
        try:
            stream = f"stream:{event_type.value}"
            messages = await self.redis_client.xrange(stream, min=start_id, count=count)
            
            result = []
            for msg_id, msg_data in messages:
                message_dict = json.loads(msg_data["data"])
                result.append(Message.from_dict(message_dict))
            
            return result
            
        except Exception as e:
            self.logger.error("Failed to get stream messages", error=str(e))
            return []


class InMemoryMessageQueue:
    """
    In-memory message queue fallback when Redis is not available.
    
    NOTE: Messages are not persisted and will be lost on restart.
    """
    
    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = {}
        self.messages: List[Message] = []
        self.logger = logger.bind(component="InMemoryMessageQueue")
        self._running = False
    
    async def connect(self) -> bool:
        """Mock connect."""
        self.logger.warning("Using in-memory message queue (messages not persisted)")
        return True
    
    async def disconnect(self):
        """Mock disconnect."""
        self._running = False
    
    async def publish(self, message: Message) -> bool:
        """Publish message to in-memory queue."""
        self.messages.append(message)
        
        # Immediately process
        await self._handle_message(message)
        
        self.logger.debug(
            "Message published (in-memory)",
            event_type=message.event_type.value,
            message_id=message.id
        )
        
        return True
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """Subscribe handler to event type."""
        event_key = event_type.value
        if event_key not in self.handlers:
            self.handlers[event_key] = []
        self.handlers[event_key].append(handler)
    
    async def start_consumers(self):
        """Mock start consumers."""
        self._running = True
        self.logger.info("In-memory consumers ready")
    
    async def _handle_message(self, message: Message):
        """Handle message."""
        handlers = self.handlers.get(message.event_type.value, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                self.logger.error(
                    "Handler failed",
                    event_type=message.event_type.value,
                    error=str(e)
                )
    
    async def get_stream_messages(
        self,
        event_type: EventType,
        count: int = 100,
        start_id: str = "0"
    ) -> List[Message]:
        """Get messages from in-memory log."""
        return [
            msg for msg in self.messages[-count:]
            if msg.event_type == event_type
        ]


# Global message queue instance
_message_queue: Optional[Any] = None


async def init_message_queue(redis_url: Optional[str] = None) -> Any:
    """Initialize global message queue."""
    global _message_queue
    
    redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    if REDIS_AVAILABLE:
        _message_queue = RedisMessageQueue(redis_url)
        connected = await _message_queue.connect()
        if not connected:
            logger.warning("Falling back to in-memory queue")
            _message_queue = InMemoryMessageQueue()
            await _message_queue.connect()
    else:
        _message_queue = InMemoryMessageQueue()
        await _message_queue.connect()
    
    return _message_queue


def get_message_queue() -> Any:
    """Get global message queue instance."""
    if _message_queue is None:
        raise RuntimeError("Message queue not initialized. Call init_message_queue() first.")
    return _message_queue
