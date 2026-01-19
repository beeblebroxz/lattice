"""Main application class for Lattice UI."""

import asyncio
import threading
import webbrowser
from pathlib import Path
from typing import Any, Optional, Union
from dataclasses import dataclass, field

import dag

from .server import LatticeUIServer, HAS_AIOHTTP
from .bindings import Binding, bind


@dataclass
class LayoutSection:
    """A section of the UI layout."""

    name: str
    inputs: list[Binding] = field(default_factory=list)
    outputs: list[Binding] = field(default_factory=list)


@dataclass
class Layout:
    """UI layout configuration."""

    title: str = "Lattice App"
    sections: list[LayoutSection] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert layout to dictionary for serialization."""
        return {
            "title": self.title,
            "sections": [
                {
                    "name": s.name,
                    "inputs": [b.to_dict() for b in s.inputs],
                    "outputs": [b.to_dict() for b in s.outputs],
                }
                for s in self.sections
            ],
        }


class DagApp:
    """
    Main application class for building reactive UIs with dag models.

    Example:
        from lattice import VanillaOption
        from lattice.ui import DagApp, bind

        option = VanillaOption()
        app = DagApp("Option Pricer")
        app.register(option, name="option")

        # Optional: customize layout
        app.add_section("Inputs", inputs=[
            bind(option.Strike, label="Strike"),
            bind(option.Spot, label="Spot"),
        ])
        app.add_section("Results", outputs=[
            bind(option.Price, label="Price"),
            bind(option.Delta, label="Delta"),
        ])

        app.run(port=8080)  # Or app.show() in Jupyter
    """

    def __init__(self, title: str = "Lattice App"):
        """
        Create a new DagApp.

        Args:
            title: Title displayed in the UI
        """
        self.title = title
        self._models: dict[str, dag.Model] = {}
        self._layout = Layout(title=title)
        self._server: Optional[LatticeUIServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._port: int = 8080

    def register(self, model: dag.Model, name: Optional[str] = None) -> None:
        """
        Register a dag model with the app.

        Args:
            model: The dag.Model instance
            name: Optional name for the model (defaults to class name)
        """
        model_name = name or type(model).__name__
        model._name = model_name
        self._models[model_name] = model

    def add_section(
        self,
        name: str,
        inputs: Optional[list[Binding]] = None,
        outputs: Optional[list[Binding]] = None,
    ) -> None:
        """
        Add a section to the layout.

        Args:
            name: Section name
            inputs: List of input bindings
            outputs: List of output bindings
        """
        section = LayoutSection(
            name=name,
            inputs=inputs or [],
            outputs=outputs or [],
        )
        self._layout.sections.append(section)

    @property
    def layout(self) -> Layout:
        """Get the current layout."""
        return self._layout

    @layout.setter
    def layout(self, value: Union[Layout, dict]) -> None:
        """Set the layout from a Layout object or dict."""
        if isinstance(value, dict):
            self._layout = self._layout_from_dict(value)
        else:
            self._layout = value

    def _layout_from_dict(self, d: dict) -> Layout:
        """Create a Layout from a dictionary."""
        layout = Layout(title=d.get("title", self.title))

        for section_dict in d.get("sections", []):
            section = LayoutSection(name=section_dict.get("name", ""))

            # Process inputs
            for input_spec in section_dict.get("inputs", []):
                if isinstance(input_spec, Binding):
                    section.inputs.append(input_spec)
                # Could also support dict specs here

            # Process outputs
            for output_spec in section_dict.get("outputs", []):
                if isinstance(output_spec, Binding):
                    section.outputs.append(output_spec)

            layout.sections.append(section)

        return layout

    def _create_server(self, host: str = "localhost", port: int = 8080) -> LatticeUIServer:
        """Create and configure the server."""
        server = LatticeUIServer(host=host, port=port)

        # Register all models
        for name, model in self._models.items():
            server.register(model, name)

        return server

    def run(self, host: str = "localhost", port: int = 8080, open_browser: bool = True) -> None:
        """
        Run the app as a standalone server (blocking).

        Args:
            host: Host to bind to
            port: Port to bind to
            open_browser: Whether to open browser automatically
        """
        if not HAS_AIOHTTP:
            raise ImportError(
                "aiohttp is required for the UI server. "
                "Install with: pip install aiohttp"
            )

        self._port = port
        self._server = self._create_server(host, port)

        if open_browser:
            # Open browser after a short delay
            def open_delayed():
                import time
                time.sleep(0.5)
                webbrowser.open(f"http://{host}:{port}")

            threading.Thread(target=open_delayed, daemon=True).start()

        self._server.run()

    async def start_async(self, host: str = "localhost", port: int = 8080) -> None:
        """Start the server asynchronously (non-blocking)."""
        if not HAS_AIOHTTP:
            raise ImportError("aiohttp is required for the UI server.")

        self._port = port
        self._server = self._create_server(host, port)
        await self._server.start()

    async def stop_async(self) -> None:
        """Stop the server asynchronously."""
        if self._server:
            await self._server.stop()

    def start_background(self, host: str = "localhost", port: int = 8080) -> None:
        """
        Start the server in a background thread.

        Useful for Jupyter notebooks when you want to continue interacting
        with the kernel while the server runs.
        """
        if not HAS_AIOHTTP:
            raise ImportError("aiohttp is required for the UI server.")

        self._port = port

        def run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._server = self._create_server(host, port)
            loop.run_until_complete(self._server.start())
            loop.run_forever()

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()

    def stop_background(self) -> None:
        """Stop the background server."""
        if self._server:
            # Schedule stop in the server's event loop
            asyncio.run(self._server.stop())

    def show(self, port: int = 8080) -> Any:
        """
        Display the app in a Jupyter notebook.

        Args:
            port: Port for the local server

        Returns:
            IPython display object (IFrame)
        """
        # Start server in background if not running
        if self._server is None:
            self.start_background(port=port)

        # Try to use IPython display
        try:
            from IPython.display import IFrame, display
            iframe = IFrame(f"http://localhost:{port}", width="100%", height=500)
            display(iframe)
            return iframe
        except ImportError:
            print(f"Lattice UI running at http://localhost:{port}")
            webbrowser.open(f"http://localhost:{port}")
            return None

    @property
    def url(self) -> str:
        """Get the URL of the running server."""
        return f"http://localhost:{self._port}"


def show(model: dag.Model, port: int = 8080) -> Any:
    """
    Quick display function for showing a dag model in the browser/notebook.

    This creates a temporary DagApp and displays the model with auto-generated
    layout based on the model's computed functions.

    Args:
        model: The dag.Model to display
        port: Port for the local server

    Returns:
        IFrame in Jupyter, None otherwise

    Example:
        from lattice import VanillaOption
        from lattice.ui import show

        option = VanillaOption()
        show(option)  # Opens browser or IFrame
    """
    app = DagApp(title=type(model).__name__)
    app.register(model)
    return app.show(port=port)
