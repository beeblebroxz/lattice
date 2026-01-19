"""WebSocket server for dag UI communication."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Optional, Callable
import weakref

import dag

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    web = None

from .protocol import (
    Message,
    MessageType,
    SubscribeMessage,
    UnsubscribeMessage,
    SetMessage,
    OverrideMessage,
    ClearOverrideMessage,
    ConnectedMessage,
    ValueMessage,
    InvalidatedMessage,
    ErrorMessage,
    SchemaMessage,
    parse_message,
)
from .session import Session, SessionManager


class LatticeUIServer:
    """
    WebSocket server for reactive dag UI.

    Handles:
    - HTTP serving of static frontend files
    - WebSocket connections for real-time updates
    - dag.watch() integration for change notifications
    - Session management for multiple clients
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8080,
        static_dir: Optional[Path] = None,
    ):
        """
        Create a new UI server.

        Args:
            host: Host to bind to
            port: Port to bind to
            static_dir: Directory containing frontend static files
        """
        if not HAS_AIOHTTP:
            raise ImportError(
                "aiohttp is required for the UI server. "
                "Install with: pip install aiohttp"
            )

        self.host = host
        self.port = port
        self.static_dir = static_dir or (Path(__file__).parent / "static")

        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None

        self._session_manager = SessionManager()
        self._registered_models: dict[str, dag.Model] = {}
        self._websockets: dict[str, web.WebSocketResponse] = {}

        # Callback for dag.flush() integration
        self._flush_pending = False

    def register(self, model: dag.Model, name: Optional[str] = None) -> None:
        """
        Register a dag model with the server.

        Args:
            model: The dag.Model instance
            name: Optional name for the model (defaults to class name)
        """
        model_name = name or type(model).__name__
        # Store the name on the model for node_path generation
        model._name = model_name
        self._registered_models[model_name] = model

    def _resolve_node_path(self, node_path: str) -> tuple[dag.Model, Any, str]:
        """
        Resolve a node path to (model, computed_func, attr_name).

        Args:
            node_path: Path like "option.Price" or "VanillaOption.Strike"

        Returns:
            Tuple of (model instance, computed function, attribute name)
        """
        parts = node_path.split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid node path: {node_path}")

        model_name, attr_name = parts

        # Try to find model by registered name
        model = self._registered_models.get(model_name)
        if model is None:
            # Try by class name
            for name, m in self._registered_models.items():
                if type(m).__name__ == model_name:
                    model = m
                    break

        if model is None:
            raise KeyError(f"Model not found: {model_name}")

        computed_func = getattr(model, attr_name, None)
        if computed_func is None:
            raise AttributeError(f"Model {model_name} has no attribute {attr_name}")

        return model, computed_func, attr_name

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connection."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # Create session for this connection
        session = self._session_manager.create_session()
        self._websockets[session.session_id] = ws

        # Set up invalidation callback
        async def on_invalidation(node_paths: set[str]):
            if not ws.closed:
                for path in node_paths:
                    try:
                        value, formatted = session.get_value(path)
                        msg = ValueMessage(node_path=path, value=value, formatted=formatted)
                        await ws.send_str(msg.to_json())
                    except Exception as e:
                        err_msg = ErrorMessage(error=str(e), node_path=path)
                        await ws.send_str(err_msg.to_json())

        # Store reference to prevent garbage collection
        session._on_invalidation = lambda paths: asyncio.create_task(on_invalidation(paths))

        # Send connected message
        connected = ConnectedMessage(session_id=session.session_id)
        await ws.send_str(connected.to_json())

        # Send schema for registered models
        schema = self._build_schema()
        schema_msg = SchemaMessage(models=schema)
        await ws.send_str(schema_msg.to_json())

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    await self._handle_message(session, ws, msg.data)
                elif msg.type == web.WSMsgType.ERROR:
                    print(f"WebSocket error: {ws.exception()}")
        finally:
            # Cleanup
            self._session_manager.remove_session(session.session_id)
            if session.session_id in self._websockets:
                del self._websockets[session.session_id]

        return ws

    async def _handle_message(
        self,
        session: Session,
        ws: web.WebSocketResponse,
        data: str,
    ) -> None:
        """Handle an incoming WebSocket message."""
        try:
            msg = parse_message(data)

            if isinstance(msg, SubscribeMessage):
                await self._handle_subscribe(session, ws, msg)
            elif isinstance(msg, UnsubscribeMessage):
                await self._handle_unsubscribe(session, msg)
            elif isinstance(msg, SetMessage):
                await self._handle_set(session, ws, msg)
            elif isinstance(msg, OverrideMessage):
                await self._handle_override(session, ws, msg)
            elif isinstance(msg, ClearOverrideMessage):
                await self._handle_clear_override(session, ws, msg)
            else:
                err = ErrorMessage(error=f"Unknown message type: {msg.type}")
                await ws.send_str(err.to_json())

        except Exception as e:
            err = ErrorMessage(error=str(e))
            await ws.send_str(err.to_json())

    async def _handle_subscribe(
        self,
        session: Session,
        ws: web.WebSocketResponse,
        msg: SubscribeMessage,
    ) -> None:
        """Handle subscribe message."""
        for node_path in msg.node_paths:
            try:
                model, computed_func, attr_name = self._resolve_node_path(node_path)
                session.subscribe(node_path, computed_func, model)

                # Send current value
                value, formatted = session.get_value(node_path)
                value_msg = ValueMessage(node_path=node_path, value=value, formatted=formatted)
                await ws.send_str(value_msg.to_json())

            except Exception as e:
                err = ErrorMessage(error=str(e), node_path=node_path)
                await ws.send_str(err.to_json())

    async def _handle_unsubscribe(self, session: Session, msg: UnsubscribeMessage) -> None:
        """Handle unsubscribe message."""
        for node_path in msg.node_paths:
            session.unsubscribe(node_path)

    async def _handle_set(
        self,
        session: Session,
        ws: web.WebSocketResponse,
        msg: SetMessage,
    ) -> None:
        """Handle set value message."""
        try:
            model, computed_func, attr_name = self._resolve_node_path(msg.node_path)
            computed_func.set(msg.value)

            # Flush dag to trigger watch callbacks
            dag.flush()

            # Send updated values to all sessions subscribed to this path
            await self._broadcast_updates()

        except Exception as e:
            err = ErrorMessage(error=str(e), node_path=msg.node_path)
            await ws.send_str(err.to_json())

    async def _handle_override(
        self,
        session: Session,
        ws: web.WebSocketResponse,
        msg: OverrideMessage,
    ) -> None:
        """Handle override value message."""
        try:
            model, computed_func, attr_name = self._resolve_node_path(msg.node_path)
            computed_func.override(msg.value)

            # Flush dag to trigger watch callbacks
            dag.flush()

            # Send updated values
            await self._broadcast_updates()

        except Exception as e:
            err = ErrorMessage(error=str(e), node_path=msg.node_path)
            await ws.send_str(err.to_json())

    async def _handle_clear_override(
        self,
        session: Session,
        ws: web.WebSocketResponse,
        msg: ClearOverrideMessage,
    ) -> None:
        """Handle clear override message."""
        try:
            model, computed_func, attr_name = self._resolve_node_path(msg.node_path)
            computed_func.clear_override()

            dag.flush()
            await self._broadcast_updates()

        except Exception as e:
            err = ErrorMessage(error=str(e), node_path=msg.node_path)
            await ws.send_str(err.to_json())

    async def _broadcast_updates(self) -> None:
        """Broadcast value updates to all connected sessions."""
        for session in self._session_manager.get_all_sessions():
            ws = self._websockets.get(session.session_id)
            if ws is None or ws.closed:
                continue

            # Get all current values for subscribed nodes
            values = session.get_all_values()
            for node_path, (value, formatted) in values.items():
                msg = ValueMessage(node_path=node_path, value=value, formatted=formatted)
                try:
                    await ws.send_str(msg.to_json())
                except Exception:
                    pass  # Connection may have closed

    def _build_schema(self) -> dict[str, dict]:
        """Build schema for all registered models."""
        schema = {}
        for name, model in self._registered_models.items():
            model_schema = {"inputs": [], "outputs": [], "computed": []}

            # Introspect the model class for computed functions
            for attr_name in dir(type(model)):
                if attr_name.startswith("_"):
                    continue

                attr = getattr(type(model), attr_name, None)
                if attr is None:
                    continue

                # Check if it's a computed function descriptor
                # ComputedFunctionDescriptor has 'flags' attribute (not '_flags')
                if hasattr(attr, "flags") and hasattr(attr, "func"):
                    flags = attr.flags
                    node_info = {
                        "name": attr_name,
                        "path": f"{name}.{attr_name}",
                        "has_input": bool(flags & dag.Input),
                        "has_overridable": bool(flags & dag.Overridable),
                    }

                    if flags & dag.Input:
                        model_schema["inputs"].append(node_info)
                    else:
                        model_schema["outputs"].append(node_info)
                    model_schema["computed"].append(node_info)

            schema[name] = model_schema

        return schema

    async def _handle_index(self, request: web.Request) -> web.Response:
        """Serve index.html."""
        index_path = self.static_dir / "index.html"
        if index_path.exists():
            return web.FileResponse(index_path)
        else:
            # Return a simple placeholder if no frontend is built
            return web.Response(
                text=self._default_html(),
                content_type="text/html",
            )

    def _default_html(self) -> str:
        """Generate default HTML when no frontend is built."""
        return """<!DOCTYPE html>
<html>
<head>
    <title>Lattice UI</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            padding: 0; margin: 0;
            background: #f5f5f5;
            color: #333;
        }
        .container { max-width: 900px; margin: 0 auto; padding: 20px; }
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 20px; margin-bottom: 20px;
        }
        header h1 { margin: 0; font-weight: 500; }
        .status {
            display: inline-block; padding: 4px 12px; border-radius: 12px;
            font-size: 12px; margin-left: 15px;
        }
        .status.connected { background: rgba(255,255,255,0.2); }
        .status.disconnected { background: rgba(255,0,0,0.3); }
        .card {
            background: white; border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px; overflow: hidden;
        }
        .card-header {
            background: #f8f9fa; padding: 12px 20px;
            border-bottom: 1px solid #eee; font-weight: 600;
        }
        .card-body { padding: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .field { margin-bottom: 15px; }
        .field label {
            display: block; font-size: 12px; color: #666;
            margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;
        }
        .field .value {
            font-size: 24px; font-weight: 600; color: #333;
        }
        .field input {
            width: 100%; padding: 10px 12px; border: 1px solid #ddd;
            border-radius: 6px; font-size: 16px;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        .field input:focus {
            outline: none; border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102,126,234,0.1);
        }
        .outputs-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px;
        }
        .output-item {
            text-align: center; padding: 15px;
            background: #f8f9fa; border-radius: 8px;
        }
        .output-item .label { font-size: 11px; color: #888; margin-bottom: 5px; text-transform: uppercase; }
        .output-item .value { font-size: 20px; font-weight: 600; color: #333; }
        .price-highlight {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .price-highlight .label { color: rgba(255,255,255,0.8); }
        .price-highlight .value { color: white; font-size: 28px; }
    </style>
</head>
<body>
    <header>
        <h1>Lattice <span class="status disconnected" id="status">Connecting...</span></h1>
    </header>
    <div class="container">
        <div id="models"></div>
    </div>
    <script>
        const ws = new WebSocket(`ws://${location.host}/ws`);
        const values = {};
        const rawValues = {};
        let schema = {};

        ws.onopen = () => {
            document.getElementById('status').textContent = 'Connected';
            document.getElementById('status').className = 'status connected';
        };

        ws.onclose = () => {
            document.getElementById('status').textContent = 'Disconnected';
            document.getElementById('status').className = 'status disconnected';
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.type === 'schema') {
                schema = msg.models;
                renderModels();
            } else if (msg.type === 'value') {
                values[msg.node_path] = msg.formatted !== null ? msg.formatted : formatValue(msg.value);
                rawValues[msg.node_path] = msg.value;
                updateValue(msg.node_path);
            } else if (msg.type === 'connected') {
                console.log('Session:', msg.session_id);
            } else if (msg.type === 'error') {
                console.error('Error:', msg.error, msg.node_path);
            }
        };

        function formatValue(v) {
            if (v === null || v === undefined) return '-';
            if (typeof v === 'number') return v.toFixed(4);
            if (typeof v === 'boolean') return v ? 'Yes' : 'No';
            return String(v);
        }

        function pascalToTitle(s) {
            return s.replace(/([A-Z])/g, ' $1').trim();
        }

        function renderModels() {
            const container = document.getElementById('models');
            container.innerHTML = '';

            for (const [name, model] of Object.entries(schema)) {
                // Subscribe to all nodes
                const nodePaths = model.computed.map(n => n.path);
                if (nodePaths.length > 0) {
                    ws.send(JSON.stringify({ type: 'subscribe', node_paths: nodePaths }));
                }

                // Inputs card
                if (model.inputs.length > 0) {
                    const inputsCard = document.createElement('div');
                    inputsCard.className = 'card';
                    inputsCard.innerHTML = '<div class="card-header">Inputs</div><div class="card-body"><div class="grid" id="inputs-grid"></div></div>';
                    const grid = inputsCard.querySelector('.grid');

                    model.inputs.forEach(node => {
                        const field = document.createElement('div');
                        field.className = 'field';
                        field.innerHTML = `
                            <label>${pascalToTitle(node.name)}</label>
                            <input type="number" step="any" id="input-${node.path}"
                                   onchange="setValue('${node.path}', this.value)"
                                   placeholder="Enter value...">
                        `;
                        grid.appendChild(field);
                    });
                    container.appendChild(inputsCard);
                }

                // Outputs card
                const outputs = model.computed.filter(n => !n.has_input);
                if (outputs.length > 0) {
                    const outputsCard = document.createElement('div');
                    outputsCard.className = 'card';
                    outputsCard.innerHTML = '<div class="card-header">Results</div><div class="card-body"><div class="outputs-grid" id="outputs-grid"></div></div>';
                    const grid = outputsCard.querySelector('.outputs-grid');

                    outputs.forEach((node, i) => {
                        const item = document.createElement('div');
                        const isPrice = node.name.toLowerCase().includes('price');
                        item.className = 'output-item' + (isPrice ? ' price-highlight' : '');
                        item.innerHTML = `
                            <div class="label">${pascalToTitle(node.name)}</div>
                            <div class="value" id="val-${node.path}">-</div>
                        `;
                        grid.appendChild(item);
                    });
                    container.appendChild(outputsCard);
                }
            }
        }

        function updateValue(path) {
            // Update output display
            const outputEl = document.getElementById('val-' + path);
            if (outputEl) outputEl.textContent = values[path];

            // Update input field placeholder with current value
            const inputEl = document.getElementById('input-' + path);
            if (inputEl && rawValues[path] !== undefined) {
                inputEl.placeholder = rawValues[path];
            }
        }

        function setValue(path, value) {
            const parsed = parseFloat(value);
            if (!isNaN(parsed)) {
                ws.send(JSON.stringify({ type: 'set', node_path: path, value: parsed }));
            }
        }
    </script>
</body>
</html>"""

    def _setup_routes(self) -> None:
        """Set up HTTP routes."""
        self._app.router.add_get("/", self._handle_index)
        self._app.router.add_get("/ws", self._handle_websocket)

        # Serve static files if directory exists
        if self.static_dir.exists():
            self._app.router.add_static("/assets/", self.static_dir / "assets")

    async def start(self) -> None:
        """Start the server."""
        self._app = web.Application()
        self._setup_routes()

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        print(f"Lattice UI server running at http://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the server."""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()

    def run(self) -> None:
        """Run the server (blocking)."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.start())
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            loop.run_until_complete(self.stop())
            loop.close()
