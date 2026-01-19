"""WebSocket protocol message types for dag UI communication."""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from enum import Enum
import json


class MessageType(Enum):
    """Message types for client-server communication."""

    # Client -> Server
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SET = "set"
    OVERRIDE = "override"
    CLEAR_OVERRIDE = "clear_override"

    # Server -> Client
    CONNECTED = "connected"
    VALUE = "value"
    INVALIDATED = "invalidated"
    ERROR = "error"
    SCHEMA = "schema"


@dataclass
class Message:
    """Base message class."""

    type: MessageType

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        data = asdict(self)
        data["type"] = self.type.value
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "Message":
        """Deserialize message from JSON string."""
        data = json.loads(json_str)
        msg_type = MessageType(data.pop("type"))

        # Route to appropriate message class
        message_classes = {
            MessageType.SUBSCRIBE: SubscribeMessage,
            MessageType.UNSUBSCRIBE: UnsubscribeMessage,
            MessageType.SET: SetMessage,
            MessageType.OVERRIDE: OverrideMessage,
            MessageType.CLEAR_OVERRIDE: ClearOverrideMessage,
            MessageType.CONNECTED: ConnectedMessage,
            MessageType.VALUE: ValueMessage,
            MessageType.INVALIDATED: InvalidatedMessage,
            MessageType.ERROR: ErrorMessage,
            MessageType.SCHEMA: SchemaMessage,
        }

        msg_cls = message_classes.get(msg_type)
        if msg_cls is None:
            raise ValueError(f"Unknown message type: {msg_type}")

        return msg_cls(**data)


# Client -> Server messages

@dataclass
class SubscribeMessage(Message):
    """Subscribe to node value updates."""

    type: MessageType = field(default=MessageType.SUBSCRIBE, init=False)
    node_paths: list[str] = field(default_factory=list)


@dataclass
class UnsubscribeMessage(Message):
    """Unsubscribe from node value updates."""

    type: MessageType = field(default=MessageType.UNSUBSCRIBE, init=False)
    node_paths: list[str] = field(default_factory=list)


@dataclass
class SetMessage(Message):
    """Permanently set a node's value (requires Input flag)."""

    type: MessageType = field(default=MessageType.SET, init=False)
    node_path: str = ""
    value: Any = None


@dataclass
class OverrideMessage(Message):
    """Temporarily override a node's value (requires Overridable flag)."""

    type: MessageType = field(default=MessageType.OVERRIDE, init=False)
    node_path: str = ""
    value: Any = None


@dataclass
class ClearOverrideMessage(Message):
    """Clear an override, reverting to computed/set value."""

    type: MessageType = field(default=MessageType.CLEAR_OVERRIDE, init=False)
    node_path: str = ""


# Server -> Client messages

@dataclass
class ConnectedMessage(Message):
    """Sent when client connects successfully."""

    type: MessageType = field(default=MessageType.CONNECTED, init=False)
    session_id: str = ""
    server_version: str = "0.1.0"


@dataclass
class ValueMessage(Message):
    """Send current value of a node."""

    type: MessageType = field(default=MessageType.VALUE, init=False)
    node_path: str = ""
    value: Any = None
    formatted: Optional[str] = None  # Pre-formatted display string


@dataclass
class InvalidatedMessage(Message):
    """Notify that nodes have been invalidated and need re-evaluation."""

    type: MessageType = field(default=MessageType.INVALIDATED, init=False)
    node_paths: list[str] = field(default_factory=list)


@dataclass
class ErrorMessage(Message):
    """Send error information to client."""

    type: MessageType = field(default=MessageType.ERROR, init=False)
    error: str = ""
    node_path: Optional[str] = None  # Optional: which node caused the error


@dataclass
class SchemaMessage(Message):
    """Send model schema to client for auto-layout generation."""

    type: MessageType = field(default=MessageType.SCHEMA, init=False)
    models: dict[str, dict] = field(default_factory=dict)
    # Structure: {"model_name": {"inputs": [...], "outputs": [...], "computed": [...]}}


def parse_message(json_str: str) -> Message:
    """Parse a JSON string into a Message object."""
    return Message.from_json(json_str)


def create_value_message(node_path: str, value: Any, format_spec: Optional[str] = None) -> ValueMessage:
    """Create a value message with optional formatting."""
    formatted = None
    if format_spec and value is not None:
        try:
            if format_spec == "%":
                formatted = f"{value * 100:.2f}%"
            elif format_spec.startswith("$"):
                formatted = f"${value:{format_spec[1:]}}"
            else:
                formatted = f"{value:{format_spec}}"
        except (ValueError, TypeError):
            formatted = str(value)

    return ValueMessage(node_path=node_path, value=value, formatted=formatted)
