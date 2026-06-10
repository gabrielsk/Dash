import os
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, html, dcc, Input, Output, callback

FILE  = os.path.join(os.path.dirname(__file__), "Modelo de Caixa v1.xlsx")
SHEET = "Fluxo de Caixa"

raw  = pd.read_excel(FILE, sheet_name=SHEET, header=None)
dre  = pd.read_excel(FILE, sheet_name="DRE", header=None)
lanc = pd.read_excel(FILE, sheet_name="Lançamentos", header=0)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_section(header_row):
    header = pd.to_datetime(raw.iloc[header_row, 1:], errors="coerce")
    mask   = header.notna()
    cols   = raw.columns[1:][mask.values]
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
})

# ── Daily realizado (header row 18) ──────────────────────────────────────────
d_dates, d_cols = get_section(18)
daily = pd.DataFrame({
    "Data":        d_dates,
    "Entradas":    vals(32, d_cols),
    "Saídas":      vals(76, d_cols),
    "Fluxo":       vals(77, d_cols),
    "Saldo Final": vals(78, d_cols),
})

# ── Forecast (header row 81) ──────────────────────────────────────────────────
f_dates, f_cols = get_section(81)
forecast = pd.DataFrame({
    "Data":        f_dates,
    "Entradas":    vals(95, f_cols),
    "Saídas":      vals(139, f_cols),
    "Fluxo":       vals(140, f_cols),
    "Saldo Final": vals(141, f_cols),
})

# ── DRE ───────────────────────────────────────────────────────────────────────
dre_header = pd.to_datetime(dre.iloc[4, 1:], errors="coerce")
dre_mask   = dre_header.notna()
dre_date_cols = dre.columns[1:][dre_mask.values]

# Last month with actual data
dre_receita = pd.to_numeric(dre.iloc[5, dre_date_cols], errors="coerce").fillna(0)
active_cols  = dre_date_cols[dre_receita.values != 0]
last_col     = active_cols[-1] if len(active_cols) else dre_date_cols[-1]

_MESES_PT = {1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",5:"Maio",6:"Junho",
             7:"Julho",8:"Agosto",9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro"}
_ref_dt   = pd.to_datetime(dre.iloc[4, last_col])
ref_month = f"{_MESES_PT[_ref_dt.month]}/{_ref_dt.year}"


def dv(row):
    return float(pd.to_numeric(dre.iloc[row, last_col], errors="coerce") or 0)


receita_bruta = dv(5)
cmv           = dv(8)
lucro_bruto   = dv(9)
desp_op       = dv(10)
ebitda        = dv(11)
desp_fin      = dv(13)
lucro_liq     = dv(17)

margem_bruta = (lucro_bruto / receita_bruta * 100) if receita_bruta else 0
margem_liq   = (lucro_liq   / receita_bruta * 100) if receita_bruta else 0

# ── Category breakdown from Lançamentos ──────────────────────────────────────
rec_cats  = (
    lanc[lanc["Tipo"] == "Entrada"]
    .groupby("Categoria")["Valor"].sum()
    .pipe(lambda s: s[s > 0].sort_values())
)

desp_cats = (
    lanc[lanc["Tipo"] == "Saída"]
    .groupby("Categoria")["Valor"].sum().abs()
    .pipe(lambda s: s[s > 0].sort_values())
)

grupo_desp = (
    lanc[lanc["Tipo"] == "Saída"]
    .groupby("Grupo DRE")["Valor"].sum().abs()
    .pipe(lambda s: s[s > 0].sort_values(ascending=False))
)

# ── KPIs ──────────────────────────────────────────────────────────────────────
saldo_atual    = float(monthly.loc[monthly["Saldo Acumulado"] != 0, "Saldo Acumulado"].iloc[-1])
total_entradas = receita_bruta
total_saidas   = float(lanc[lanc["Tipo"] == "Saída"]["Valor"].sum())

# ── Theme ─────────────────────────────────────────────────────────────────────
C = dict(
    bg="#0f172a", card="#1e293b", border="#334155",
    green="#22c55e", red="#ef4444", blue="#3b82f6",
    yellow="#f59e0b", purple="#a855f7", teal="#14b8a6",
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

# Entradas vs Saídas mensais
fig_bar = go.Figure([
    go.Bar(x=mlabels, y=monthly["Entradas"], name="Entradas", marker_color=C["green"]),
    go.Bar(x=mlabels, y=monthly["Saídas"],   name="Saídas",   marker_color=C["red"]),
])
fig_saldo_m.update_layout(**plot_base("Saldo Acumulado Mensal"))

# DRE Waterfall
fig_dre = go.Figure(go.Waterfall(
    orientation="v",
    measure=["absolute", "relative", "total", "relative", "total", "relative", "total"],
    x=["Receita Bruta", "(-) CMV", "Lucro Bruto", "(-) Desp. Op.", "EBITDA", "(-) Desp. Fin.", "Lucro Líquido"],
    y=[receita_bruta, cmv, lucro_bruto, desp_op, ebitda, desp_fin, lucro_liq],
    text=[f"R$ {abs(v):,.0f}" for v in [receita_bruta, cmv, lucro_bruto, desp_op, ebitda, desp_fin, lucro_liq]],
    textposition="outside",
    connector=dict(line=dict(color=C["border"], width=1, dash="dot")),
    increasing=dict(marker=dict(color=C["green"])),
    decreasing=dict(marker=dict(color=C["red"])),
    totals=dict(marker=dict(color=C["blue"])),
))
fig_dre.update_layout(**plot_base(f"DRE — Demonstração do Resultado  ({ref_month})"))
fig_dre.update_layout(margin=dict(l=50, r=70, t=42, b=40), showlegend=False)

# Pie — estrutura de custos
PIE_COLORS = [C["red"], C["yellow"], C["purple"], C["teal"], C["blue"]]
fig_pie = go.Figure(go.Pie(
    labels=grupo_desp.index.tolist(),
    values=grupo_desp.values.tolist(),
    hole=0.52,
    marker=dict(colors=PIE_COLORS[:len(grupo_desp)], line=dict(color=C["bg"], width=2)),
    textinfo="label+percent",
    textfont=dict(color=C["text"], size=11),
    hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<extra></extra>",
))
fig_pie.update_layout(
    title=dict(text="Estrutura de Custos (Realizado)", font=dict(color=C["text"], size=13), x=0.01),
    paper_bgcolor=C["card"], plot_bgcolor=C["card"],
    font=dict(color=C["text"]),
    margin=dict(l=20, r=20, t=42, b=20),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
    showlegend=True,
)

# Receitas por categoria
fig_rec = go.Figure(go.Bar(
    x=rec_cats.values, y=rec_cats.index, orientation="h",
    marker_color=C["green"],
    text=[f"R$ {v:,.2f}" for v in rec_cats.values],
    textposition="outside",
))
fig_rec.update_layout(**plot_base("Receitas por Categoria (Realizado)"))
fig_rec.update_layout(margin=dict(l=210, r=140, t=42, b=40))
fig_rec.update_yaxes(gridcolor="rgba(0,0,0,0)")

# Despesas por categoria
fig_desp = go.Figure(go.Bar(
    x=desp_cats.values, y=desp_cats.index, orientation="h",
    marker_color=C["red"],
    text=[f"R$ {v:,.2f}" for v in desp_cats.values],
    textposition="outside",
))
fig_desp.update_layout(**plot_base("Despesas por Categoria (Realizado)"))
fig_desp.update_layout(margin=dict(l=240, r=140, t=42, b=40))
fig_desp.update_yaxes(gridcolor="rgba(0,0,0,0)")

# Movimentação por banco — construído a partir dos Lançamentos reais
@callback(
    Output("daily-graph",     "figure"),
    Output("daily-bar-graph", "figure"),
    Input("date-range", "start_date"),
    Input("date-range", "end_date"),
)
def update_daily(start, end):
    start = start or _d_start
    end   = end   or _d_end

    d = daily[(daily["Data"] >= start) & (daily["Data"] <= end)]
    f = forecast[(forecast["Data"] >= start) & (forecast["Data"] <= end)]

    fig_line = go.Figure([
        go.Scatter(
            x=d["Data"], y=d["Saldo Final"], mode="lines+markers",
            name="Realizado", line=dict(color=C["blue"], width=2),
            marker=dict(size=5),
        ),
        go.Scatter(
            x=f["Data"], y=f["Saldo Final"], mode="lines",
            name="Forecast", line=dict(color=C["yellow"], width=2, dash="dash"),
        ),
    ])
    fig_line.update_layout(**plot_base("Saldo Final do Dia"))

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
    fig_fluxo.update_layout(**plot_base("Fluxo do Dia"), barmode="overlay")
    fig_fluxo.update_traces(
        selector=dict(name="Realizado"),
        marker_color=[C["green"] if v >= 0 else C["red"] for v in d["Fluxo"]],
    )

    return fig_line, fig_fluxo
fig_bar.update_layout(**plot_base("Entradas vs Saídas por Mês"), barmode="group")

# Saldo acumulado mensal
fig_saldo_m = go.Figure(go.Scatter(
    x=mlabels, y=monthly["Saldo Acumulado"], mode="lines+markers",
    line=dict(color=C["blue"], width=2), marker=dict(size=6),
    fill="tozeroy", fillcolor="rgba(59,130,246,0.08)", name="Saldo",
))
_bank_df = (
    lanc.groupby([pd.to_datetime(lanc["Mês"]).dt.to_period("M"), "Banco", "Tipo"])["Valor"]
    .sum()
    .reset_index()
)
_bank_df["Label"] = _bank_df["Mês"].dt.to_timestamp().dt.strftime("%b/%y")

_bank_df["Valor"] = _bank_df["Valor"].abs()

BANK_COLORS = {"Cresol": C["blue"], "Stone": C["teal"]}
fig_bank = go.Figure()
for banco in sorted(_bank_df["Banco"].unique()):
    color = BANK_COLORS.get(banco, C["purple"])
    for tipo, opacity in [("Entrada", 0.90), ("Saída", 0.50)]:
        sub = _bank_df[(_bank_df["Banco"] == banco) & (_bank_df["Tipo"] == tipo)]
        fig_bank.add_trace(go.Bar(
            x=sub["Label"], y=sub["Valor"],
            name=f"{banco} — {tipo}s",
            marker_color=color, opacity=opacity,
        ))


fig_bank.update_layout(**plot_base("Movimentação por Banco (Mensal)"), barmode="group")
# ── App ───────────────────────────────────────────────────────────────────────
app   = Dash(__name__)
server = app.server

app.title = "Dashboard Financeiro"


DIVIDER = {"borderTop": f"1px solid {C['border']}", "margin": "8px 0 20px"}


def kpi_card(title, value, color, subtitle=None, is_percent=False):
    fmt = f"{value:.1f}%" if is_percent else f"R$ {value:,.2f}"
    return html.Div([
        html.P(title, style={"color": C["muted"], "fontSize": "0.75rem",
                             "margin": "0 0 4px", "fontWeight": "500"}),
        html.H3(fmt, style={"color": color, "margin": 0,
                            "fontSize": "1.3rem", "fontWeight": "700"}),
        html.P(subtitle or " ", style={"color": C["muted"],
               "fontSize": "0.70rem", "margin": "4px 0 0"}),
    ], style={**CARD, "flex": "1", "minWidth": "160px"})


def section_label(text):
    return html.P(text, style={
        "color": C["muted"], "fontSize": "0.70rem", "fontWeight": "600",
        "letterSpacing": "0.09em", "textTransform": "uppercase",
        "margin": "0 0 12px",
    })
# default date range for daily chart
_d_start = str(daily["Data"].min().date())

_d_end   = str(daily["Data"].max().date())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host="0.0.0.0", port=port)


app.layout = html.Div([

    # ── Header ───────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.H1("Dashboard Financeiro", style={
                "color": C["text"], "margin": 0,
                "fontSize": "1.6rem", "fontWeight": "700",
            }),
            html.P(f"Fluxo de Caixa · {ref_month}", style={
                "color": C["muted"], "margin": "4px 0 0", "fontSize": "0.82rem",
            }),
        ]),
        html.Span("● Dados Atualizados", style={
            "color": C["green"], "fontSize": "0.75rem",
            "background": "rgba(34,197,94,0.10)",
            "padding": "5px 14px", "borderRadius": "20px",
            "border": f"1px solid {C['green']}33",
        }),
    ], style={
        "display": "flex", "justifyContent": "space-between",
        "alignItems": "center", "marginBottom": "28px",
    }),

    # ── KPIs ─────────────────────────────────────────────────────────────────
    section_label("Resultado do Período"),
    html.Div([
        kpi_card("Receita Bruta",   receita_bruta, C["green"]),
        kpi_card("Lucro Bruto",     lucro_bruto,   C["blue"],
                 f"Margem {margem_bruta:.1f}%"),
        kpi_card("EBITDA",          ebitda,        C["yellow"]),
        kpi_card("Lucro Líquido",   lucro_liq,     C["green"],
                 f"Margem {margem_liq:.1f}%"),
        kpi_card("Saldo em Caixa",  saldo_atual,   C["blue"]),
    ], style={"display": "flex", "gap": "14px", "marginBottom": "28px", "flexWrap": "wrap"}),

    html.Hr(style=DIVIDER),

    # ── DRE + Estrutura de Custos ─────────────────────────────────────────────
    section_label("Demonstração do Resultado (DRE)"),
    html.Div([
        html.Div([dcc.Graph(figure=fig_dre, config={"displayModeBar": False})],
                 style={**CARD, "flex": "3"}),
        html.Div([dcc.Graph(figure=fig_pie, config={"displayModeBar": False})],
                 style={**CARD, "flex": "2"}),
    ], style={"display": "flex", "gap": "16px", "marginBottom": "24px"}),

    html.Hr(style=DIVIDER),

    # ── Visão Mensal ──────────────────────────────────────────────────────────
    section_label("Visão Mensal"),
    html.Div([
        html.Div([dcc.Graph(figure=fig_bar,     config={"displayModeBar": False})],
                 style={**CARD, "flex": "1"}),
        html.Div([dcc.Graph(figure=fig_saldo_m, config={"displayModeBar": False})],
                 style={**CARD, "flex": "1"}),
    ], style={"display": "flex", "gap": "16px", "marginBottom": "24px"}),

    html.Hr(style=DIVIDER),

    # ── Fluxo Diário ──────────────────────────────────────────────────────────
    section_label("Fluxo de Caixa Diário"),
    html.Div([
        html.Div([
            html.Span("Saldo Diário: Realizado vs Forecast", style={
                "color": C["text"], "fontSize": "0.9rem", "fontWeight": "600",
            }),
            dcc.DatePickerRange(
                id="date-range",
                min_date_allowed=_d_start,
                max_date_allowed=_d_end,
                start_date=_d_start,
                end_date=_d_end,
                display_format="DD/MM/YYYY",
            ),
        ], style={
            "display": "flex", "justifyContent": "space-between",
            "alignItems": "center", "marginBottom": "12px",
        }),
        dcc.Graph(id="daily-graph", config={"displayModeBar": False}),
    ], style={**CARD, "marginBottom": "24px"}),

    html.Div([
        html.Span("Fluxo do Dia (Realizado vs Forecast)", style={
            "color": C["text"], "fontSize": "0.9rem", "fontWeight": "600",
        }),
        dcc.Graph(id="daily-bar-graph", config={"displayModeBar": False}),
    ], style={**CARD, "marginBottom": "24px"}),

    html.Hr(style=DIVIDER),

    # ── Análise por Categoria ─────────────────────────────────────────────────
    section_label("Análise por Categoria (Realizado)"),
    html.Div([
        html.Div(
            [dcc.Graph(figure=fig_rec,  config={"displayModeBar": False},
                       style={"height": "320px"})],
            style={**CARD, "flex": "1"},
        ),
        html.Div(
            [dcc.Graph(figure=fig_desp, config={"displayModeBar": False},
                       style={"height": "320px"})],
            style={**CARD, "flex": "1"},
        ),
    ], style={"display": "flex", "gap": "16px", "marginBottom": "24px"}),
    html.Hr(style=DIVIDER),

    # ── Bancos ────────────────────────────────────────────────────────────────
    section_label("Movimentação por Banco"),
    html.Div([dcc.Graph(figure=fig_bank, config={"displayModeBar": False})],
             style=CARD),

], style={
    "background":  C["bg"],
    "minHeight":   "100vh",
    "padding":     "32px 36px",
    "fontFamily":  '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    "boxSizing":   "border-box",
})
