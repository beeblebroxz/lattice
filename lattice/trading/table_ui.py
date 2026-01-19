"""Shared table UI server for TradeBlotter and PositionTable."""

import asyncio
import webbrowser
from typing import Callable, List, Dict, Any, Optional
from aiohttp import web


def create_table_app(
    title: str,
    columns: List[Dict[str, str]],
    get_rows: Callable[[], List[Dict[str, Any]]],
    get_stats: Optional[Callable[[], Dict[str, Any]]] = None,
) -> web.Application:
    """
    Create an aiohttp app for displaying a table.

    Args:
        title: Page title
        columns: List of column definitions [{"key": "col_name", "label": "Display Name"}, ...]
        get_rows: Function that returns list of row dicts
        get_stats: Optional function that returns stats dict for header display

    Returns:
        Configured aiohttp Application
    """

    async def handle_index(request):
        return web.Response(text=_generate_html(title, columns, get_stats is not None), content_type="text/html")

    async def handle_data(request):
        return web.json_response(get_rows())

    async def handle_stats(request):
        if get_stats:
            return web.json_response(get_stats())
        return web.json_response({})

    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/data", handle_data)
    app.router.add_get("/api/stats", handle_stats)

    return app


def _generate_html(title: str, columns: List[Dict[str, str]], has_stats: bool) -> str:
    """Generate the HTML page for the table UI."""

    # Build column headers
    headers_html = "\n".join(f'<th>{col["label"]}</th>' for col in columns)

    # Build row template (JavaScript will populate)
    cell_template = " + ".join(f'`<td>${{formatCell(row["{col["key"]}"], "{col.get("format", "")}")}}</td>`' for col in columns)

    stats_html = """
        <div class="stats" id="stats"></div>
    """ if has_stats else ""

    stats_js = """
            // Fetch stats
            const stats = await fetch('/api/stats').then(r => r.json());
            const statsEl = document.getElementById('stats');
            if (statsEl && Object.keys(stats).length > 0) {
                statsEl.innerHTML = Object.entries(stats).map(([key, value]) => `
                    <div class="stat-card">
                        <div class="value">${typeof value === 'number' ? value.toLocaleString() : value}</div>
                        <div class="label">${key.replace(/_/g, ' ')}</div>
                    </div>
                `).join('');
            }
    """ if has_stats else ""

    return f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
        }}
        header {{
            background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
            padding: 20px 30px;
            border-bottom: 1px solid #333;
        }}
        header h1 {{ font-weight: 500; color: #fff; }}
        header h1 span {{ color: #4ecca3; }}
        .container {{ padding: 20px 30px; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }}
        .stat-card {{
            background: #16213e;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-card .value {{ font-size: 24px; font-weight: 600; color: #4ecca3; }}
        .stat-card .label {{ font-size: 12px; color: #888; margin-top: 5px; text-transform: uppercase; }}
        .card {{
            background: #16213e;
            border-radius: 8px;
            overflow: hidden;
        }}
        .card-header {{
            padding: 15px 20px;
            background: #0f3460;
            font-weight: 600;
        }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px 15px; text-align: left; }}
        th {{ background: rgba(0,0,0,0.2); font-size: 11px; text-transform: uppercase; color: #888; }}
        tr:not(:last-child) td {{ border-bottom: 1px solid #333; }}
        .positive {{ color: #4ecca3; }}
        .negative {{ color: #ff6b6b; }}
        .buy {{ color: #4ecca3; }}
        .sell {{ color: #ff6b6b; }}
        .empty {{ padding: 30px; text-align: center; color: #666; }}
        .refresh-indicator {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #16213e;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            color: #888;
        }}
    </style>
</head>
<body>
    <header>
        <h1><span>Lattice</span> {title}</h1>
    </header>
    <div class="container">
        {stats_html}
        <div class="card">
            <div class="card-header">Data</div>
            <div class="card-body">
                <table>
                    <thead><tr>{headers_html}</tr></thead>
                    <tbody id="table-body"></tbody>
                </table>
            </div>
        </div>
    </div>
    <div class="refresh-indicator">Auto-refresh: 1s</div>
    <script>
        function formatCell(value, format) {{
            if (value === null || value === undefined) return '-';
            if (format === 'currency') return '$' + value.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
            if (format === 'number') return value.toLocaleString();
            if (format === 'side') return `<span class="${{value.toLowerCase()}}">${{value}}</span>`;
            if (format === 'quantity') {{
                const cls = value >= 0 ? 'positive' : 'negative';
                return `<span class="${{cls}}">${{value}}</span>`;
            }}
            if (format === 'pnl') {{
                if (typeof value !== 'number') return value;
                const cls = value >= 0 ? 'positive' : 'negative';
                const sign = value >= 0 ? '+' : '';
                return `<span class="${{cls}}">${{sign}}${{value.toFixed(2)}}</span>`;
            }}
            return value;
        }}

        async function refresh() {{
            {stats_js}

            // Fetch data
            const rows = await fetch('/api/data').then(r => r.json());
            const tbody = document.getElementById('table-body');
            if (rows.length === 0) {{
                tbody.innerHTML = '<tr><td colspan="{len(columns)}" class="empty">No data</td></tr>';
            }} else {{
                tbody.innerHTML = rows.map(row => `<tr>${{{cell_template}}}</tr>`).join('');
            }}
        }}

        refresh();
        setInterval(refresh, 1000);
    </script>
</body>
</html>
"""


def run_table_ui(
    title: str,
    columns: List[Dict[str, str]],
    get_rows: Callable[[], List[Dict[str, Any]]],
    get_stats: Optional[Callable[[], Dict[str, Any]]] = None,
    port: int = 8080,
    open_browser: bool = True,
) -> None:
    """
    Run the table UI server.

    Args:
        title: Page title
        columns: Column definitions
        get_rows: Function to get row data
        get_stats: Optional function to get stats
        port: Server port (default 8080)
        open_browser: Whether to open browser automatically
    """
    app = create_table_app(title, columns, get_rows, get_stats)

    if open_browser:
        # Open browser after short delay to let server start
        async def open_browser_task():
            await asyncio.sleep(0.5)
            webbrowser.open(f"http://localhost:{port}")

        async def on_startup(app):
            asyncio.create_task(open_browser_task())

        app.on_startup.append(on_startup)

    print(f"{title} running at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    web.run_app(app, host="localhost", port=port, print=None)
