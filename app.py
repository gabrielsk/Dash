import os
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, html, dcc, Input, Output, callback

FILE = os.path.join(os.path.dirname(__file__), "Modelo de Caixa.xlsx")
SHEET = "Fluxo de Caixa"

raw = pd.read_excel(FILE, sheet_name=SHEET, header=None)


def get_section(header_row):
    header = pd.to_datetime(raw.iloc[header_row, 1:], errors="coerce")
    mask = header.notna()
    cols = raw.columns[1:][mask.values]
    return pd.to_datetime(header[mask].values), cols


def vals(row, cols):
    return pd.to_numeric(raw.iloc[row, cols], errors="coerce").fillna(0).values.astype(float)


# ── Monthly (header row 4) ────────────────────────────────────────────────────
m_dates, m_cols = get_section(4)
monthly = pd.DataFrame({
    "Data":            m_dates,
    "Entradas":        vals(6, m_cols),
    "Saídas":          vals(7, m_cols),
    "Fluxo":           vals(8, m_cols),
    "Saldo Acumulado": vals(9, m_cols),
    "Banco do Brasil": vals(12, m_cols),
    "Itaú":            vals(13, m_cols),
    "Caixa":           vals(14, m_cols),
})

# ── Daily realizado (header row 18) ──────────────────────────────────────────
d_dates, d_cols = get_section(18)
daily = pd.DataFrame({
    "Data":       d_dates,
    "Entradas":   vals(32, d_cols),
    "Saídas":     vals(76, d_cols),
    "Fluxo":      vals(77, d_cols),
    "Saldo Final": vals(78, d_cols),
})

# ── Forecast (header row 81) ─────────────────────────────────1─────────────────
f_dates, f_cols = get_section(81)
forecast = pd.DataFrame({
    "Data":       f_dates,
    "Entradas":   vals(95, f_cols),
    "Saídas":     vals(139, f_cols),
    "Fluxo":      vals(140, f_cols),
    "Saldo Final": vals(141, f_cols),
})

# Category totals from forecast (realizado ainda sem lançamentos)
rec_cats   = raw.iloc[84:95, 0].tolist()
rec_totals = pd.Series({c: vals(84 + i, f_cols).sum() for i, c in enumerate(rec_cats)})
rec_totals = rec_totals[rec_totals > 0].sort_values()

desp_cats   = raw.iloc[97:139, 0].tolist()
desp_totals = pd.Series({c: vals(97 + i, f_cols).sum() for i, c in enumerate(desp_cats)})
desp_totals = desp_totals[desp_totals > 0].sort_values()

# ── KPIs ──────────────────────────────────────────────────────────────────────
saldo_atual    = float(monthly.loc[monthly["Saldo Acumulado"] != 0, "Saldo Acumulado"].iloc[-1])
total_entradas = float(monthly["Entradas"].sum())
total_saidas   = float(monthly["Saídas"].sum())
fluxo_periodo  = total_entradas + total_saidas

# ── Theme ─────────────────────────────────────────────────────────────────────
C = dict(
    bg="#0f172a", card="#1e293b", border="#334155",
    green="#22c55e", red="#ef4444", blue="#3b82f6",
    yellow="#f59e0b", purple="#a855f7",
    text="#f1f5f9", muted="#94a3b8",
)

CARD = {
    "background":   C["card"],
    "border":       f"1px solid {C['border']}",
    "borderRadius": "12px",
    "padding":      "20px",
}


def plot_base(title=""):
    return dict(
        title=dict(text=title, font=dict(color=C["text"], size=13), x=0.01),
        paper_bgcolor=C["card"], plot_bgcolor=C["card"],
        font=dict(color=C["text"], size=11),
        margin=dict(l=50, r=20, t=42, b=40),
        xaxis=dict(gridcolor=C["border"], linecolor=C["border"]),
        yaxis=dict(gridcolor=C["border"], linecolor=C["border"]),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        hovermode="x unified",
    )


# ── Static figures ────────────────────────────────────────────────────────────
mlabels = monthly["Data"].dt.strftime("%b/%y")

# Entradas vs Saídas por mês
fig_bar = go.Figure([
    go.Bar(x=mlabels, y=monthly["Entradas"], name="Entradas", marker_color=C["green"]),
    go.Bar(x=mlabels, y=monthly["Saídas"],   name="Saídas",   marker_color=C["red"]),
])
fig_bar.update_layout(**plot_base("Entradas vs Saídas por Mês"), barmode="group")

# Saldo acumulado mensal
fig_saldo_m = go.Figure(go.Scatter(
    x=mlabels, y=monthly["Saldo Acumulado"], mode="lines+markers",
    line=dict(color=C["blue"], width=2), marker=dict(size=6),
    fill="tozeroy", fillcolor="rgba(59,130,246,0.08)", name="Saldo",
))
fig_saldo_m.update_layout(**plot_base("Saldo Acumulado Mensal"))

# Receitas previstas por categoria
fig_rec = go.Figure(go.Bar(
    x=rec_totals.values, y=rec_totals.index, orientation="h",
    marker_color=C["green"],
    text=[f"R$ {v:,.2f}" for v in rec_totals.values],
    textposition="outside",
))
fig_rec.update_layout(**plot_base("Previsão — Receitas por Categoria"))
fig_rec.update_layout(margin=dict(l=210, r=100, t=42, b=40))
fig_rec.update_yaxes(gridcolor="rgba(0,0,0,0)")

# Despesas previstas por categoria
fig_desp = go.Figure(go.Bar(
    x=desp_totals.values, y=desp_totals.index, orientation="h",
    marker_color=C["red"],
    text=[f"R$ {v:,.2f}" for v in desp_totals.values],
    textposition="outside",
))
fig_desp.update_layout(**plot_base("Previsão — Despesas por Categoria"))
fig_desp.update_layout(margin=dict(l=210, r=100, t=42, b=40))
fig_desp.update_yaxes(gridcolor="rgba(0,0,0,0)")

# Movimentação por banco
fig_bank = go.Figure([
    go.Bar(x=mlabels, y=monthly["Banco do Brasil"], name="Banco do Brasil", marker_color=C["blue"]),
    go.Bar(x=mlabels, y=monthly["Itaú"],            name="Itaú",            marker_color=C["yellow"]),
    go.Bar(x=mlabels, y=monthly["Caixa"],           name="Caixa",           marker_color=C["purple"]),
])
fig_bank.update_layout(**plot_base("Movimentação por Banco (Mensal)"), barmode="group")

# ── App ───────────────────────────────────────────────────────────────────────
app = Dash(__name__)
server = app.server
app.title = "Fluxo de Caixa"


def kpi_card(title, value, color):
    return html.Div([
        html.P(title, style={"color": C["muted"], "fontSize": "0.78rem", "margin": "0 0 6px"}),
        html.H3(f"R$ {value:,.2f}", style={
            "color": color, "margin": 0, "fontSize": "1.25rem", "fontWeight": "600",
        }),
    ], style={**CARD, "flex": "1", "minWidth": "170px"})


app.layout = html.Div([

    # Header
    html.Div([
        html.H1("Fluxo de Caixa", style={
            "color": C["text"], "margin": 0, "fontSize": "1.5rem", "fontWeight": "700",
        }),
        html.P("Dashboard financeiro · 2026", style={
            "color": C["muted"], "margin": "4px 0 0", "fontSize": "0.82rem",
        }),
    ], style={"marginBottom": "28px"}),

    # KPIs
    html.Div([
        kpi_card("Saldo Acumulado",   saldo_atual,           C["blue"]),
        kpi_card("Total de Entradas", total_entradas,         C["green"]),
        kpi_card("Total de Saídas",   abs(total_saidas),      C["red"]),
        kpi_card("Fluxo do Período",  abs(fluxo_periodo),
                 C["green"] if fluxo_periodo >= 0 else C["red"]),
    ], style={"display": "flex", "gap": "14px", "marginBottom": "24px", "flexWrap": "wrap"}),

    # Mensal: Entradas/Saídas + Saldo
    html.Div([
        html.Div([dcc.Graph(figure=fig_bar,     config={"displayModeBar": False})],
                 style={**CARD, "flex": "1"}),
        html.Div([dcc.Graph(figure=fig_saldo_m, config={"displayModeBar": False})],
                 style={**CARD, "flex": "1"}),
    ], style={"display": "flex", "gap": "16px", "marginBottom": "24px"}),

    # Fluxo diário: Realizado vs Forecast
    html.Div([
        html.Div([
            html.Span("Saldo Diário: Realizado vs Forecast", style={
                "color": C["text"], "fontSize": "0.9rem", "fontWeight": "600",
            }),
            dcc.DatePickerRange(
                id="date-range",
                min_date_allowed=str(daily["Data"].min().date()),
                max_date_allowed=str(daily["Data"].max().date()),
                start_date=str(daily["Data"].min().date()),
                end_date=str(daily["Data"].max().date()),
                display_format="DD/MM/YYYY",
            ),
        ], style={
            "display": "flex", "justifyContent": "space-between",
            "alignItems": "center", "marginBottom": "12px",
        }),
        dcc.Graph(id="daily-graph", config={"displayModeBar": False}),
    ], style={**CARD, "marginBottom": "24px"}),

    # Fluxo diário por dia (barras)
    html.Div([
        html.Span("Fluxo do Dia (Realizado vs Forecast)", style={
            "color": C["text"], "fontSize": "0.9rem", "fontWeight": "600",
        }),
        dcc.Graph(id="daily-bar-graph", config={"displayModeBar": False}),
    ], style={**CARD, "marginBottom": "24px"}),

    # Categorias: Receitas + Despesas
    html.Div([
        html.Div([dcc.Graph(figure=fig_rec,  config={"displayModeBar": False}, style={"height": "520px"})],
                 style={**CARD, "flex": "1"}),
        html.Div([dcc.Graph(figure=fig_desp, config={"displayModeBar": False}, style={"height": "520px"})],
                 style={**CARD, "flex": "1"}),
    ], style={"display": "flex", "gap": "16px", "marginBottom": "24px"}),

    # Bancos
    html.Div([dcc.Graph(figure=fig_bank, config={"displayModeBar": False})], style=CARD),

], style={
    "background":  C["bg"],
    "minHeight":   "100vh",
    "padding":     "32px 36px",
    "fontFamily":  '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    "boxSizing":   "border-box",
})


@callback(
    Output("daily-graph", "figure"),
    Output("daily-bar-graph", "figure"),
    Input("date-range", "start_date"),
    Input("date-range", "end_date"),
)
def update_daily(start, end):
    start = start or str(daily["Data"].min().date())
    end   = end   or str(daily["Data"].max().date())

    d = daily[(daily["Data"] >= start) & (daily["Data"] <= end)]
    f = forecast[(forecast["Data"] >= start) & (forecast["Data"] <= end)]

    # Saldo line chart
    fig_line = go.Figure([
        go.Scatter(
            x=d["Data"], y=d["Saldo Final"], mode="lines",
            name="Realizado", line=dict(color=C["blue"], width=2),
        ),
        go.Scatter(
            x=f["Data"], y=f["Saldo Final"], mode="lines",
            name="Forecast", line=dict(color=C["yellow"], width=2, dash="dash"),
        ),
    ])
    fig_line.update_layout(**plot_base("Saldo Final do Dia"))

    # Fluxo bar chart
    fig_fluxo = go.Figure([
        go.Bar(
            x=d["Data"], y=d["Fluxo"],
            name="Realizado", marker_color=C["blue"], opacity=0.85,
        ),
        go.Bar(
            x=f["Data"], y=f["Fluxo"],
            name="Forecast", marker_color=C["yellow"], opacity=0.65,
        ),
    ])
    fig_fluxo.update_layout(**plot_base(""), barmode="overlay")
    # Color bars by positive/negative
    fig_fluxo.update_traces(
        selector=dict(name="Realizado"),
        marker_color=[C["green"] if v >= 0 else C["red"] for v in d["Fluxo"]],
    )

    return fig_line, fig_fluxo


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host="0.0.0.0", port=port)
