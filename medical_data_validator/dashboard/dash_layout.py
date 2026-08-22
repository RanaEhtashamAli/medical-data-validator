"""Dash app shell: persistent sidebar navigation + the active page's content."""

import dash
import dash_bootstrap_components as dbc
from dash import html


def setup_dash_layout(dash_app):
    sidebar = dbc.Nav(
        [
            dbc.NavLink(page['name'], href=page['relative_path'], active='exact')
            for page in dash.page_registry.values()
        ],
        vertical=True,
        pills=True,
        className="bg-light p-3",
    )
    dash_app.layout = dbc.Container([
        dbc.Row([
            dbc.Col(sidebar, width=2),
            dbc.Col(dash.page_container, width=10),
        ])
    ], fluid=True)
