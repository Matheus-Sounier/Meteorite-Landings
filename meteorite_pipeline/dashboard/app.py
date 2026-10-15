import logging
import os
from pathlib import Path

import dash
import dash_mantine_components as dmc
import plotly.express as px
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
from dotenv import load_dotenv

from meteorite_pipeline.analytics.meteorite_chat import answer_question
from meteorite_pipeline.dashboard.queries import load_dashboard_data
from meteorite_pipeline.db.chat_store import (
    add_message,
    create_conversation,
    get_messages,
    list_conversations,
)


load_dotenv()
LOGGER = logging.getLogger(__name__)
COLORS = {
    "ink": "#172a2b",
    "muted": "#667676",
    "teal": "#137c72",
    "coral": "#d16d55",
    "gold": "#b68124",
    "grid": "#e5eae7",
    "paper": "#ffffff",
    "canvas": "#f3f6f4",
}
FALL_COLORS = {"Fell": COLORS["teal"], "Found": COLORS["coral"]}


def _figure_layout(figure, height: int = 340):
    figure.update_layout(
        height=height,
        margin={"l": 12, "r": 12, "t": 12, "b": 12},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "DM Sans, sans-serif", "color": "#dce7ed", "size": 12},
        legend={"orientation": "h", "y": 1.08, "x": 0},
        xaxis={"showgrid": False, "zeroline": False, "linecolor": "rgba(183, 207, 222, 0.18)"},
        yaxis={"gridcolor": "rgba(183, 207, 222, 0.12)", "zeroline": False},
    )
    return figure


def _number(value: int | None) -> str:
    return f"{value or 0:,}"


def _empty_figure():
    figure = go.Figure()
    figure.add_annotation(
        text="No records for this filter",
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": COLORS["muted"], "size": 12},
    )
    return figure


def _metric_card(label: str, value: str, note: str, tone: str):
    return dmc.Paper(
        className=f"metric-card metric-card-{tone}",
        children=[
            dmc.Text(label, className="metric-label"),
            dmc.Text(value, className="metric-value"),
            dmc.Text(note, className="metric-note"),
        ],
    )


def _chart_panel(title: str, subtitle: str, figure, class_name: str = ""):
    return dmc.Paper(
        className=f"chart-panel {class_name}".strip(),
        children=[
            dmc.Group(
                [
                    dmc.Stack(
                        [
                            dmc.Text(title, className="panel-title"),
                            dmc.Text(subtitle, className="panel-subtitle"),
                        ],
                        gap=2,
                    ),
                ],
                justify="space-between",
                align="flex-start",
            ),
            dcc.Graph(
                figure=figure,
                config={"displayModeBar": False, "responsive": True},
                className="chart-graph",
                style={"height": f"{figure.layout.height or 340}px"},
            ),
        ],
    )


def _globe_panel():
    return dmc.Paper(
        className="chart-panel globe-panel",
        children=[
            dmc.Stack(
                [
                    dmc.Text("Meteorite locations", className="panel-title"),
                    dmc.Text(
                        "Select a cell or point to inspect the records on Earth.",
                        className="panel-subtitle",
                    ),
                ],
                gap=2,
            ),
            dmc.Group(
                [
                    dmc.Group(
                        [html.Span(className="legend-dot legend-found"), dmc.Text("Found")],
                        gap=6,
                    ),
                    dmc.Group(
                        [html.Span(className="legend-dot legend-fell"), dmc.Text("Fell")],
                        gap=6,
                    ),
                ],
                gap="md",
                className="globe-legend",
            ),
            html.Div(
                className="globe-frame",
                children=[
                    html.Div(
                        id="meteorite-globe",
                        className="globe-canvas",
                        role="img",
                        **{"aria-label": "Interactive 3D globe showing meteorite coordinates"},
                    ),
                    html.Div(
                        "No valid coordinates in this view",
                        id="globe-empty-state",
                        className="globe-empty-state",
                        style={"display": "none"},
                    ),
                    html.Div(
                        className="globe-detail-controls",
                        id="globe-detail-controls",
                        style={"display": "none"},
                        children=[
                            html.Span(id="globe-detail-summary", role="status"),
                            html.Button(
                                "Close detail",
                                id="globe-detail-close",
                                type="button",
                                className="globe-detail-close",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _chat_welcome():
    return html.Div(
        [
            dmc.Text("ASSISTENTE DE METEORITOS", className="chat-eyebrow"),
            dmc.Title("O que você quer descobrir?", order=2, className="chat-welcome-title"),
            dmc.Text(
                "Pergunte sobre os registros, os indicadores de qualidade ou meteoritos em geral.",
                className="chat-welcome-copy",
            ),
        ],
        className="chat-welcome",
    )


def _render_chat_messages(messages: list[dict]):
    if not messages:
        return _chat_welcome()
    return [
        html.Article(
            [
                dmc.Text("YOU" if message["role"] == "user" else "METEORITE ASSISTANT", className="message-author"),
                dcc.Markdown(
                    message["content"],
                    className="message-content",
                    link_target="_blank",
                ),
            ],
            className=f"chat-message chat-message-{message['role']}",
        )
        for message in messages
    ]


def _chat_screen():
    return html.Main(
        id="chat-screen",
        className="chat-layout",
        style={"display": "none"},
        children=[
            html.Aside(
                className="chat-sidebar",
                children=[
                    dcc.Link("← Dashboard", href="/dashboard", className="chat-back-link"),
                    dmc.Button(
                        "Nova conversa",
                        id="new-chat",
                        variant="light",
                        color="dark",
                        fullWidth=True,
                        className="new-chat-button",
                    ),
                    dmc.Text("Conversas recentes", className="history-heading"),
                    html.Div(id="chat-history-list", className="chat-history-list"),
                    html.Div(id="chat-history-notice", className="chat-history-notice"),
                ],
            ),
            html.Section(
                className="chat-workspace",
                children=[
                    dcc.Loading(
                        type="dot",
                        color=COLORS["teal"],
                        children=html.Div(
                            id="chat-thread",
                            className="chat-thread",
                            children=_chat_welcome(),
                        ),
                    ),
                    html.Div(id="chat-error", className="chat-error"),
                    html.Div(
                        className="chat-composer-wrap",
                        children=[
                            html.Div(
                                className="chat-composer",
                                children=[
                                    dcc.Textarea(
                                        id="chat-input",
                                        placeholder="Pergunte sobre os meteoritos...",
                                        maxLength=4000,
                                        className="chat-input",
                                        autoFocus=False,
                                    ),
                                    dmc.Button(
                                        "Enviar",
                                        id="send-message",
                                        n_clicks=0,
                                        color="teal",
                                        className="send-message-button",
                                    ),
                                ],
                            ),
                            dmc.Text(
                                "Respostas sobre os dados usam o PostgreSQL local. Fontes externas são citadas.",
                                className="chat-disclaimer",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _chat_store_is_configured() -> bool:
    return bool(os.environ.get("CHAT_DB_USER") and os.environ.get("CHAT_DB_PASSWORD"))


def _make_figures(data: dict):
    years = data["by_year"]
    if years:
        year_figure = px.area(
            years,
            x="year",
            y="records",
            markers=True,
            labels={"year": "Year", "records": "Records"},
        )
        year_figure.update_traces(
            line={"color": COLORS["teal"], "width": 2},
            fillcolor="rgba(19, 124, 114, 0.12)",
            marker={"size": 4, "color": COLORS["teal"]},
        )
    else:
        year_figure = _empty_figure()
    year_figure = _figure_layout(year_figure)

    classes = data["by_class"]
    if classes:
        class_figure = px.bar(
            classes[::-1],
            x="records",
            y="recclass",
            orientation="h",
            labels={"records": "Records", "recclass": "Class"},
            color_discrete_sequence=[COLORS["coral"]],
        )
    else:
        class_figure = _empty_figure()
    class_figure = _figure_layout(class_figure)
    class_figure.update_layout(xaxis={"showgrid": True, "gridcolor": COLORS["grid"]})

    summary = data["summary"]
    fell_records = summary["fell_records"]
    found_records = summary["found_records"]
    if fell_records or found_records:
        fall_figure = px.pie(
            names=["Fell", "Found"],
            values=[fell_records, found_records],
            hole=0.72,
            color=["Fell", "Found"],
            color_discrete_map=FALL_COLORS,
            labels={"label": "Fall type", "value": "Records"},
        )
        fall_figure.update_traces(textinfo="none", marker={"line": {"color": "white", "width": 3}})
    else:
        fall_figure = _empty_figure()
    fall_figure = _figure_layout(fall_figure, height=310)

    return year_figure, class_figure, fall_figure


def create_app() -> dash.Dash:
    assets_folder = Path(__file__).resolve().parent / "assets"
    app = dash.Dash(
        __name__,
        assets_folder=str(assets_folder),
        external_stylesheets=dmc.styles.ALL,
        external_scripts=[
            "https://cdn.jsdelivr.net/npm/gsap@3.13.0/dist/gsap.min.js",
            "https://cdn.jsdelivr.net/npm/gsap@3.13.0/dist/ScrollTrigger.min.js",
            "https://cdn.jsdelivr.net/npm/globe.gl@2.46.2",
        ],
        title="Meteorite Field Notes",
        update_title="Querying PostgreSQL...",
        suppress_callback_exceptions=True,
    )

    app.layout = dmc.MantineProvider(
        theme={"primaryColor": "teal", "fontFamily": "DM Sans, sans-serif"},
        children=html.Div(
            className="dashboard-shell",
            children=[
                dcc.Location(id="app-location", refresh=False),
                dcc.Store(id="globe-points", data=[]),
                html.Div(id="globe-render-state", style={"display": "none"}),
                dcc.Store(id="active-conversation-id", storage_type="session"),
                dcc.Store(id="chat-history-revision", data=0),
                html.Div(
                    id="solar-system-scene",
                    className="solar-system-stage",
                    **{"aria-hidden": "true"},
                ),
                html.Header(
                    className="topbar",
                    children=[
                        html.Div(
                            html.Div(id="scroll-progress-fill", className="scroll-progress-fill"),
                            id="scroll-progress-track",
                            className="scroll-progress-track",
                            role="progressbar",
                            **{
                                "aria-label": "Reading progress",
                                "aria-valuemin": "0",
                                "aria-valuemax": "100",
                                "aria-valuenow": "0",
                            },
                        ),
                        dmc.Group(
                            [
                                dcc.Link("Dashboard", href="/dashboard", className="top-nav-link"),
                                dcc.Link("Meteorite chat", href="/chat", className="top-nav-link"),
                            ],
                            gap="md",
                            className="top-navigation",
                        ),
                        dmc.Group(
                            [
                                html.Div("ML", className="brand-mark"),
                                dmc.Stack(
                                    [
                                        dmc.Text("FIELD NOTES", className="brand-name"),
                                        dmc.Text("METEORITE LANDINGS", className="brand-caption"),
                                    ],
                                    gap=1,
                                ),
                            ],
                            gap="sm",
                        ),
                        dmc.Group(
                            [
                                html.Span(className="status-dot"),
                                dmc.Text("POSTGRESQL · READ ONLY", className="connection-label"),
                            ],
                            gap="xs",
                            className="connection-status",
                        ),
                    ],
                ),
                html.Main(
                    id="dashboard-screen",
                    className="dashboard-screen",
                    children=[
                        html.Section(
                            className="space-hero",
                            children=[
                                html.Div(className="hero-starfield", **{"aria-hidden": "true"}),
                                html.Div(
                                    className="hero-content",
                                    children=[
                                        dmc.Text("EARTH IMPACT ARCHIVE / 01", className="eyebrow hero-eyebrow"),
                                        dmc.Title("Meteorite landings", order=1, className="page-title hero-title"),
                                        dmc.Text(
                                            "A record of what reaches us, written across time and the surface of our planet.",
                                            className="page-description hero-description",
                                        ),
                                        html.A(
                                            ["EXPLORE THE DATA", html.Span("↓", **{"aria-hidden": "true"})],
                                            href="#meteorite-data",
                                            className="scroll-cue",
                                        ),
                                    ],
                                ),
                                html.Div(
                                    className="hero-coordinate",
                                    children=[
                                        html.Span("GLOBAL METEORITE RECORD"),
                                        html.Span("OBSERVED FALLS + RECOVERED FINDS"),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(
                            id="meteorite-data",
                            className="dashboard-flow",
                            children=[
                        dmc.Group(
                            [
                                dmc.Stack(
                                    [
                                        dmc.Text(
                                            "OBSERVATION CONTROLS",
                                            className="eyebrow",
                                        ),
                                        dmc.Text(
                                            "Refine the records before exploring the archive.",
                                            className="filter-intro",
                                        ),
                                    ],
                                    gap=3,
                                ),
                            ],
                            justify="space-between",
                            align="center",
                            className="filter-heading",
                        ),
                        dmc.Paper(
                            className="filter-strip",
                            children=[
                                dmc.Group(
                                    [
                                        dmc.Stack(
                                            [
                                                dmc.Text("FALL TYPE", className="filter-label"),
                                                dmc.SegmentedControl(
                                                    id="fall-filter",
                                                    value="all",
                                                    data=[
                                                        {"label": "All", "value": "all"},
                                                        {"label": "Fell", "value": "Fell"},
                                                        {"label": "Found", "value": "Found"},
                                                    ],
                                                    size="sm",
                                                    color="teal",
                                                ),
                                            ],
                                            gap=6,
                                        ),
                                        dmc.Switch(
                                            id="include-flagged",
                                            label="Include quality-flagged records",
                                            checked=False,
                                            color="teal",
                                            className="quality-switch",
                                        ),
                                        dmc.Button(
                                            "Refresh data",
                                            id="refresh-dashboard",
                                            n_clicks=0,
                                            variant="light",
                                            color="dark",
                                            className="refresh-button",
                                        ),
                                    ],
                                    justify="space-between",
                                    align="flex-end",
                                    className="filter-controls",
                                )
                            ],
                        ),
                        dcc.Loading(
                            type="dot",
                            color=COLORS["teal"],
                            children=html.Div(
                                id="dashboard-content",
                                className="dashboard-content",
                                children=dmc.Alert(
                                    "Loading analytics from PostgreSQL...",
                                    color="teal",
                                    variant="light",
                                ),
                            ),
                        ),
                        dmc.Text(
                            "Coordinates flagged as missing, (0, 0), or outside valid ranges are omitted from the map.",
                            className="footnote",
                        ),
                            ],
                        ),
                    ],
                ),
                _chat_screen(),
            ],
        ),
    )

    @app.callback(
        Output("dashboard-content", "children"),
        Output("globe-points", "data"),
        Input("fall-filter", "value"),
        Input("include-flagged", "checked"),
        Input("refresh-dashboard", "n_clicks"),
    )
    def refresh_dashboard(fall_type: str, include_flagged: bool, _clicks: int):
        try:
            data = load_dashboard_data(fall_type or "all", bool(include_flagged))
        except Exception:
            LOGGER.exception("Dashboard query failed")
            return (
                dmc.Alert(
                    title="Database unavailable",
                    children="Could not load analytics. Check the PostgreSQL service and DASH_DB_* credentials.",
                    color="red",
                    variant="light",
                ),
                [],
            )

        summary = data["summary"]
        total = int(summary["total_records"] or 0)
        fell = int(summary["fell_records"] or 0)
        found = int(summary["found_records"] or 0)
        flagged = int(summary["flagged_records"] or 0)
        flag_rate = (flagged / total * 100) if total else 0
        year_figure, class_figure, fall_figure = _make_figures(data)

        return (
            html.Div(
                className="story-content",
                children=[
                    html.Section(
                        className="story-section story-overview story-reveal",
                        id="timeline-section",
                        children=[
                            html.Div(
                                className="story-heading",
                                children=[
                                    dmc.Text("01 / THE ARCHIVE", className="eyebrow"),
                                    dmc.Title("A long record of impact", order=2, className="section-title"),
                                    dmc.Text(
                                        "Each point in the record marks a fall observed or a fragment recovered.",
                                        className="section-description",
                                    ),
                                ],
                            ),
                            dmc.SimpleGrid(
                                [
                                    _metric_card("RECORDS IN VIEW", f"{total:,}", "Filtered database rows", "teal"),
                                    _metric_card("OBSERVED FALLS", f"{fell:,}", "Recorded as Fell", "coral"),
                                    _metric_card("FOUND", f"{found:,}", "Recovered after landing", "gold"),
                                    _metric_card("QUALITY FLAGS", f"{flagged:,}", f"{flag_rate:.1f}% of current view", "ink"),
                                ],
                                cols={"base": 2, "md": 4},
                                spacing="md",
                                className="metric-grid",
                            ),
                            dmc.Grid(
                                [
                                    dmc.GridCol(
                                        span={"base": 12, "lg": 7},
                                        children=_chart_panel(
                                            "Records through time",
                                            "Year of recorded fall or find",
                                            year_figure,
                                        ),
                                    ),
                                    dmc.GridCol(
                                        span={"base": 12, "lg": 5},
                                        children=_chart_panel(
                                            "Fall classification",
                                            "Observed falls versus recovered finds",
                                            fall_figure,
                                        ),
                                    ),
                                ],
                                gutter="md",
                                className="chart-grid",
                            ),
                        ],
                    ),
                    html.Section(
                        className="story-section story-classes story-reveal",
                        id="classification-section",
                        children=[
                            html.Div(
                                className="story-heading story-heading-inline",
                                children=[
                                    dmc.Text("02 / MATERIAL EVIDENCE", className="eyebrow"),
                                    dmc.Title("What reached the ground", order=2, className="section-title"),
                                    dmc.Text(
                                        "Recorded meteorite classes reveal the variety of material in the archive.",
                                        className="section-description",
                                    ),
                                ],
                            ),
                            dmc.Grid(
                                [
                                    dmc.GridCol(
                                        span=12,
                                        children=_chart_panel(
                                            "Most common classes",
                                            "Top 12 recorded meteorite classes",
                                            class_figure,
                                        ),
                                    ),
                                ],
                                gutter="md",
                                className="chart-grid",
                            ),
                        ],
                    ),
                    html.Section(
                        className="earth-finale story-reveal",
                        id="earth-section",
                        children=[
                            html.Div(
                                className="story-heading earth-heading",
                                children=[
                                    dmc.Text("03 / THE SURFACE", className="eyebrow"),
                                    dmc.Title("Every record has a place", order=2, className="section-title"),
                                    dmc.Text(
                                        "The same Earth from the orbital view now reveals every mapped fall and find.",
                                        className="section-description",
                                    ),
                                ],
                            ),
                            _globe_panel(),
                            html.Div(
                                className="earth-caption",
                                children=[
                                    html.Span("THE METEORITE LANDINGS ARCHIVE"),
                                    html.Span("Coordinates are shown as recorded"),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            data["map_points"],
        )

    app.clientside_callback(
        """function(points, pathname) {
            if (pathname === '/chat') {
                if (window.pauseMeteoriteStory) window.pauseMeteoriteStory();
                const container = document.getElementById('meteorite-globe');
                if (container && container.globeInstance) container.globeInstance.pauseAnimation();
                return '';
            }
            window.setTimeout(function() {
                window.meteoriteMapRecords = points || [];
                if (window.renderMeteoriteGlobe) window.renderMeteoriteGlobe(window.meteoriteMapRecords);
                const globeContainer = document.getElementById('meteorite-globe');
                if (globeContainer && globeContainer.globeInstance) globeContainer.globeInstance.resumeAnimation();
                if (window.initializeMeteoriteStory) window.initializeMeteoriteStory();
                if (window.resumeMeteoriteStory) window.resumeMeteoriteStory();
            }, 100);
            return '';
        }""",
        Output("globe-render-state", "children"),
        Input("globe-points", "data"),
        Input("app-location", "pathname"),
    )

    @app.callback(
        Output("dashboard-screen", "style"),
        Output("chat-screen", "style"),
        Input("app-location", "pathname"),
    )
    def switch_screen(pathname: str | None):
        if pathname == "/chat":
            return {"display": "none"}, {"display": "flex"}
        return {}, {"display": "none"}

    @app.callback(
        Output("chat-history-list", "children"),
        Output("chat-history-notice", "children"),
        Input("app-location", "pathname"),
        Input("chat-history-revision", "data"),
    )
    def refresh_chat_history(pathname: str | None, _revision: int):
        if pathname != "/chat":
            raise PreventUpdate
        if not _chat_store_is_configured():
            return [], (
                "Configure CHAT_DB_USER e CHAT_DB_PASSWORD no .env e execute "
                "python -m meteorite_pipeline.db.provision_chat_store."
            )
        try:
            conversations = list_conversations()
        except Exception:
            LOGGER.exception("Could not load chat history")
            return [], (
                "Configure CHAT_DB_USER e CHAT_DB_PASSWORD no .env e execute "
                "python -m meteorite_pipeline.db.provision_chat_store."
            )
        if not conversations:
            return [], "Your conversations will appear here."
        return (
            [
                html.Button(
                    conversation["title"],
                    id={"type": "history-conversation", "conversation_id": conversation["id"]},
                    n_clicks=0,
                    className="history-conversation-button",
                    title=conversation["title"],
                )
                for conversation in conversations
            ],
            "",
        )

    @app.callback(
        Output("active-conversation-id", "data"),
        Output("chat-thread", "children"),
        Output("chat-input", "value"),
        Output("chat-history-revision", "data"),
        Output("chat-error", "children"),
        Input("new-chat", "n_clicks"),
        Input({"type": "history-conversation", "conversation_id": ALL}, "n_clicks"),
        Input("send-message", "n_clicks"),
        Input("chat-input", "n_submit"),
        State("chat-input", "value"),
        State("active-conversation-id", "data"),
        State("chat-history-revision", "data"),
        prevent_initial_call=True,
    )
    def handle_chat_action(
        _new_clicks: int,
        _history_clicks: list[int],
        _send_clicks: int,
        _submit_count: int,
        question: str | None,
        active_conversation: str | None,
        history_revision: int | None,
    ):
        triggered = ctx.triggered_id
        revision = int(history_revision or 0)
        if triggered == "new-chat":
            return None, _chat_welcome(), "", revision, ""
        if isinstance(triggered, dict) and triggered.get("type") == "history-conversation":
            conversation_id = triggered["conversation_id"]
            try:
                return (
                    conversation_id,
                    _render_chat_messages(get_messages(conversation_id)),
                    "",
                    revision,
                    "",
                )
            except Exception:
                LOGGER.exception("Could not load selected conversation")
                return active_conversation, no_update, no_update, revision, "Could not load this conversation."

        if triggered not in {"send-message", "chat-input"}:
            raise PreventUpdate
        prompt = (question or "").strip()
        if not prompt:
            raise PreventUpdate
        if not _chat_store_is_configured():
            return (
                active_conversation,
                no_update,
                no_update,
                revision,
                "Configure CHAT_DB_USER e CHAT_DB_PASSWORD no .env e execute o provisionador.",
            )

        try:
            conversation_id = active_conversation or create_conversation()
            previous_messages = get_messages(conversation_id)
            add_message(conversation_id, "user", prompt)
        except Exception:
            LOGGER.exception("Could not persist chat message")
            return (
                active_conversation,
                no_update,
                no_update,
                revision,
                "Histórico indisponível. Configure o role do chat e execute o provisionador.",
            )

        try:
            answer = answer_question(prompt, previous_messages)
            error_message = ""
        except Exception:
            LOGGER.exception("Meteorite assistant request failed")
            answer = "Não consegui concluir a resposta. Verifique a conexão OpenRouter e tente novamente."
            error_message = "O assistente não conseguiu responder a esta mensagem."

        try:
            add_message(conversation_id, "assistant", answer)
            messages = get_messages(conversation_id)
        except Exception:
            LOGGER.exception("Could not persist assistant response")
            messages = previous_messages + [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": answer},
            ]
            error_message = "A resposta apareceu, mas não foi salva no histórico da conversa."

        return (
            conversation_id,
            _render_chat_messages(messages),
            "",
            revision + 1,
            error_message,
        )

    return app


app = create_app()


def main() -> None:
    host = os.environ["DASH_HOST"]
    port = int(os.environ["DASH_PORT"])
    debug_setting = os.environ["DASH_DEBUG"].strip().lower()
    if debug_setting not in {"true", "false"}:
        raise ValueError("DASH_DEBUG must be either 'true' or 'false'.")
    app.run(host=host, port=port, debug=debug_setting == "true")


if __name__ == "__main__":
    main()
