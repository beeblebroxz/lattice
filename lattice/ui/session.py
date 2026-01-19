"""Session management for UI clients."""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from weakref import WeakSet
import uuid
import dag


@dataclass
class NodeSubscription:
    """Tracks a subscription to a dag node."""

    node_path: str
    computed_func: Any  # The computed function descriptor
    model: dag.Model
    format_spec: Optional[str] = None
    _watch_callback: Optional[Callable] = None

    def get_value(self) -> Any:
        """Get the current value of the subscribed node."""
        return self.computed_func()


class Session:
    """
    Represents a single client connection with its own subscriptions.

    Each session maintains:
    - A unique session ID
    - Set of subscribed node paths
    - Optional scenario for isolated overrides
    """

    def __init__(self, session_id: Optional[str] = None):
        """Create a new session."""
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self._subscriptions: dict[str, NodeSubscription] = {}
        self._scenario: Optional[dag.Scenario] = None
        self._pending_invalidations: set[str] = set()
        self._on_invalidation: Optional[Callable[[set[str]], None]] = None

    def subscribe(
        self,
        node_path: str,
        computed_func: Any,
        model: dag.Model,
        format_spec: Optional[str] = None,
    ) -> None:
        """
        Subscribe to a node for value updates.

        Args:
            node_path: Path like "option.Price" or "option.Strike"
            computed_func: The computed function descriptor
            model: The dag.Model instance
            format_spec: Optional format string for display
        """
        if node_path in self._subscriptions:
            return  # Already subscribed

        sub = NodeSubscription(
            node_path=node_path,
            computed_func=computed_func,
            model=model,
            format_spec=format_spec,
        )

        # Set up watch callback
        def on_invalidation():
            self._pending_invalidations.add(node_path)
            if self._on_invalidation:
                self._on_invalidation({node_path})

        # Keep a strong reference to the callback
        sub._watch_callback = on_invalidation
        computed_func.watch(on_invalidation)

        self._subscriptions[node_path] = sub

    def unsubscribe(self, node_path: str) -> None:
        """Unsubscribe from a node."""
        if node_path in self._subscriptions:
            del self._subscriptions[node_path]

    def get_value(self, node_path: str) -> tuple[Any, Optional[str]]:
        """
        Get the current value of a subscribed node.

        Returns:
            Tuple of (value, formatted_string)
        """
        if node_path not in self._subscriptions:
            raise KeyError(f"Not subscribed to {node_path}")

        sub = self._subscriptions[node_path]
        value = sub.get_value()
        formatted = self._format_value(value, sub.format_spec)
        return value, formatted

    def get_all_values(self) -> dict[str, tuple[Any, Optional[str]]]:
        """Get current values for all subscribed nodes."""
        result = {}
        for node_path in self._subscriptions:
            try:
                result[node_path] = self.get_value(node_path)
            except Exception as e:
                result[node_path] = (None, f"Error: {e}")
        return result

    def set_value(self, node_path: str, value: Any) -> None:
        """
        Set a node's value permanently (requires Input flag).

        Args:
            node_path: Path to the node
            value: New value to set
        """
        if node_path not in self._subscriptions:
            raise KeyError(f"Not subscribed to {node_path}")

        sub = self._subscriptions[node_path]
        sub.computed_func.set(value)

    def override_value(self, node_path: str, value: Any) -> None:
        """
        Override a node's value temporarily (requires Overridable flag).

        Args:
            node_path: Path to the node
            value: Value to override with
        """
        if node_path not in self._subscriptions:
            raise KeyError(f"Not subscribed to {node_path}")

        sub = self._subscriptions[node_path]
        sub.computed_func.override(value)

    def clear_override(self, node_path: str) -> None:
        """Clear an override on a node."""
        if node_path not in self._subscriptions:
            raise KeyError(f"Not subscribed to {node_path}")

        sub = self._subscriptions[node_path]
        sub.computed_func.clear_override()

    def flush_invalidations(self) -> set[str]:
        """
        Flush pending invalidations and return affected node paths.

        Returns:
            Set of node paths that were invalidated
        """
        invalidated = self._pending_invalidations.copy()
        self._pending_invalidations.clear()
        return invalidated

    @staticmethod
    def _format_value(value: Any, format_spec: Optional[str]) -> Optional[str]:
        """Format a value according to its format spec."""
        if format_spec is None or value is None:
            return None

        try:
            if format_spec == "%":
                return f"{value * 100:.2f}%"
            elif format_spec.startswith("$"):
                return f"${value:{format_spec[1:]}}"
            else:
                return f"{value:{format_spec}}"
        except (ValueError, TypeError):
            return str(value)

    @property
    def subscribed_paths(self) -> list[str]:
        """Get list of subscribed node paths."""
        return list(self._subscriptions.keys())


class SessionManager:
    """
    Manages multiple client sessions.

    Provides:
    - Session creation and cleanup
    - Lookup by session ID
    - Broadcasting to all sessions
    """

    def __init__(self):
        """Create a new session manager."""
        self._sessions: dict[str, Session] = {}

    def create_session(self, session_id: Optional[str] = None) -> Session:
        """
        Create a new session.

        Args:
            session_id: Optional custom session ID

        Returns:
            The created Session
        """
        session = Session(session_id)
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        """Remove a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]

    def get_all_sessions(self) -> list[Session]:
        """Get all active sessions."""
        return list(self._sessions.values())

    @property
    def session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self._sessions)
