"""Tests for lattice UI framework."""

import pytest
import json
import dag
from lattice.instruments import VanillaOption
from lattice.ui.protocol import (
    MessageType,
    SubscribeMessage,
    SetMessage,
    OverrideMessage,
    ConnectedMessage,
    ValueMessage,
    ErrorMessage,
    parse_message,
)
from lattice.ui.bindings import bind, InputBinding, OutputBinding, TwoWayBinding, BindingType
from lattice.ui.session import Session, SessionManager
from lattice.ui.app import DagApp, Layout, LayoutSection


class TestProtocol:
    """Tests for protocol message types."""

    def test_subscribe_message_serialization(self):
        msg = SubscribeMessage(node_paths=["option.Price", "option.Delta"])
        json_str = msg.to_json()
        data = json.loads(json_str)
        assert data["type"] == "subscribe"
        assert data["node_paths"] == ["option.Price", "option.Delta"]

    def test_subscribe_message_deserialization(self):
        json_str = '{"type": "subscribe", "node_paths": ["option.Price"]}'
        msg = parse_message(json_str)
        assert isinstance(msg, SubscribeMessage)
        assert msg.node_paths == ["option.Price"]

    def test_set_message_serialization(self):
        msg = SetMessage(node_path="option.Strike", value=110.0)
        json_str = msg.to_json()
        data = json.loads(json_str)
        assert data["type"] == "set"
        assert data["node_path"] == "option.Strike"
        assert data["value"] == 110.0

    def test_set_message_deserialization(self):
        json_str = '{"type": "set", "node_path": "option.Strike", "value": 110.0}'
        msg = parse_message(json_str)
        assert isinstance(msg, SetMessage)
        assert msg.node_path == "option.Strike"
        assert msg.value == 110.0

    def test_override_message(self):
        msg = OverrideMessage(node_path="option.Spot", value=105.0)
        json_str = msg.to_json()
        restored = parse_message(json_str)
        assert isinstance(restored, OverrideMessage)
        assert restored.node_path == "option.Spot"
        assert restored.value == 105.0

    def test_connected_message(self):
        msg = ConnectedMessage(session_id="abc123")
        json_str = msg.to_json()
        data = json.loads(json_str)
        assert data["type"] == "connected"
        assert data["session_id"] == "abc123"

    def test_value_message_with_formatted(self):
        msg = ValueMessage(node_path="option.Price", value=10.5, formatted="$10.50")
        json_str = msg.to_json()
        data = json.loads(json_str)
        assert data["value"] == 10.5
        assert data["formatted"] == "$10.50"

    def test_error_message(self):
        msg = ErrorMessage(error="Node not found", node_path="option.Foo")
        json_str = msg.to_json()
        data = json.loads(json_str)
        assert data["type"] == "error"
        assert data["error"] == "Node not found"
        assert data["node_path"] == "option.Foo"


class TestBindings:
    """Tests for binding functions."""

    def setup_method(self):
        dag.reset()
        self.option = VanillaOption()

    def test_bind_input_node(self):
        binding = bind(self.option.Strike)
        assert isinstance(binding, InputBinding)
        assert binding.binding_type == BindingType.INPUT

    def test_bind_output_node(self):
        binding = bind(self.option.Price)
        assert isinstance(binding, OutputBinding)
        assert binding.binding_type == BindingType.OUTPUT

    def test_bind_with_label(self):
        binding = bind(self.option.Strike, label="Strike Price")
        assert binding.display_label == "Strike Price"

    def test_bind_default_label(self):
        binding = bind(self.option.TimeToExpiry)
        # Should convert PascalCase to Title Case
        assert binding.display_label == "Time To Expiry"

    def test_bind_with_format(self):
        binding = bind(self.option.Price, format="$,.4f")
        assert binding.format == "$,.4f"

    def test_bind_with_widget_type(self):
        binding = bind(
            self.option.Volatility,
            widget_type="slider",
            min_value=0.01,
            max_value=1.0,
            step=0.01,
        )
        assert binding.widget_type == "slider"
        assert binding.min_value == 0.01
        assert binding.max_value == 1.0
        assert binding.step == 0.01

    def test_bind_force_editable(self):
        # Price is normally output-only, but we can force editable
        binding = bind(self.option.Price, editable=True)
        assert binding.binding_type == BindingType.INPUT

    def test_bind_force_readonly(self):
        # Strike is normally input, but we can force read-only
        binding = bind(self.option.Strike, editable=False)
        assert binding.binding_type == BindingType.OUTPUT

    def test_binding_to_dict(self):
        binding = bind(
            self.option.Strike,
            label="Strike",
            format="$,.2f",
            widget_type="input",
        )
        d = binding.to_dict()
        assert d["label"] == "Strike"
        assert d["format"] == "$,.2f"
        assert d["widget_type"] == "input"
        assert d["binding_type"] == "input"


class TestSession:
    """Tests for session management."""

    def setup_method(self):
        dag.reset()
        self.option = VanillaOption()
        self.option._name = "option"

    def test_session_creation(self):
        session = Session()
        assert session.session_id is not None
        assert len(session.session_id) == 8

    def test_session_custom_id(self):
        session = Session(session_id="custom123")
        assert session.session_id == "custom123"

    def test_subscribe_and_get_value(self):
        session = Session()
        session.subscribe("option.Price", self.option.Price, self.option)
        value, formatted = session.get_value("option.Price")
        assert value > 0  # Price should be positive
        assert formatted is None  # No format specified

    def test_subscribe_with_format(self):
        session = Session()
        session.subscribe("option.Price", self.option.Price, self.option, format_spec="$,.4f")
        value, formatted = session.get_value("option.Price")
        assert formatted is not None
        assert formatted.startswith("$")

    def test_set_value(self):
        session = Session()
        session.subscribe("option.Strike", self.option.Strike, self.option)

        original_value, _ = session.get_value("option.Strike")
        session.set_value("option.Strike", 110.0)
        new_value, _ = session.get_value("option.Strike")

        assert new_value == 110.0
        assert new_value != original_value

    def test_unsubscribe(self):
        session = Session()
        session.subscribe("option.Price", self.option.Price, self.option)
        assert "option.Price" in session.subscribed_paths

        session.unsubscribe("option.Price")
        assert "option.Price" not in session.subscribed_paths

    def test_get_all_values(self):
        session = Session()
        session.subscribe("option.Strike", self.option.Strike, self.option)
        session.subscribe("option.Price", self.option.Price, self.option)

        values = session.get_all_values()
        assert "option.Strike" in values
        assert "option.Price" in values

    def test_subscribed_paths(self):
        session = Session()
        session.subscribe("option.Strike", self.option.Strike, self.option)
        session.subscribe("option.Spot", self.option.Spot, self.option)

        paths = session.subscribed_paths
        assert "option.Strike" in paths
        assert "option.Spot" in paths


class TestSessionManager:
    """Tests for session manager."""

    def test_create_session(self):
        manager = SessionManager()
        session = manager.create_session()
        assert session is not None
        assert manager.session_count == 1

    def test_get_session(self):
        manager = SessionManager()
        session = manager.create_session()
        retrieved = manager.get_session(session.session_id)
        assert retrieved is session

    def test_remove_session(self):
        manager = SessionManager()
        session = manager.create_session()
        manager.remove_session(session.session_id)
        assert manager.session_count == 0
        assert manager.get_session(session.session_id) is None

    def test_multiple_sessions(self):
        manager = SessionManager()
        s1 = manager.create_session()
        s2 = manager.create_session()
        s3 = manager.create_session()

        assert manager.session_count == 3
        assert len(manager.get_all_sessions()) == 3


class TestDagApp:
    """Tests for DagApp."""

    def setup_method(self):
        dag.reset()
        self.option = VanillaOption()

    def test_app_creation(self):
        app = DagApp("Test App")
        assert app.title == "Test App"

    def test_register_model(self):
        app = DagApp()
        app.register(self.option, name="myoption")
        assert "myoption" in app._models
        assert app._models["myoption"] is self.option

    def test_register_model_default_name(self):
        app = DagApp()
        app.register(self.option)
        assert "VanillaOption" in app._models

    def test_add_section(self):
        app = DagApp()
        app.register(self.option, name="option")

        app.add_section(
            "Inputs",
            inputs=[
                bind(self.option.Strike, label="Strike"),
                bind(self.option.Spot, label="Spot"),
            ],
        )

        assert len(app.layout.sections) == 1
        assert app.layout.sections[0].name == "Inputs"
        assert len(app.layout.sections[0].inputs) == 2

    def test_layout_to_dict(self):
        app = DagApp("My App")
        app.register(self.option, name="option")

        app.add_section(
            "Results",
            outputs=[bind(self.option.Price, label="Price")],
        )

        layout_dict = app.layout.to_dict()
        assert layout_dict["title"] == "My App"
        assert len(layout_dict["sections"]) == 1
        assert layout_dict["sections"][0]["name"] == "Results"

    def test_set_layout_from_dict(self):
        app = DagApp()
        app.register(self.option, name="option")

        app.layout = {
            "title": "Custom Title",
            "sections": [
                {
                    "name": "Section 1",
                    "inputs": [bind(self.option.Strike)],
                    "outputs": [],
                }
            ],
        }

        assert app.layout.title == "Custom Title"
        assert len(app.layout.sections) == 1

    def test_url_property(self):
        app = DagApp()
        app._port = 9000
        assert app.url == "http://localhost:9000"


class TestFormatting:
    """Tests for value formatting."""

    def test_percentage_format(self):
        session = Session()
        formatted = session._format_value(0.25, "%")
        assert formatted == "25.00%"

    def test_currency_format(self):
        session = Session()
        formatted = session._format_value(1234.5678, "$,.2f")
        assert "$" in formatted
        assert "1,234.57" in formatted

    def test_decimal_format(self):
        session = Session()
        formatted = session._format_value(3.14159, ".2f")
        assert formatted == "3.14"

    def test_none_format(self):
        session = Session()
        formatted = session._format_value(100, None)
        assert formatted is None

    def test_none_value(self):
        session = Session()
        formatted = session._format_value(None, "$,.2f")
        assert formatted is None
