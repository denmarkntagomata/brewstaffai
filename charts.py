"""
charts.py - Plotly charts. Green = Okay, amber = Congested, red = Overloaded.
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ui import AMBER, BORDER, LEVEL_COLOR, LIME, MUTED, RED, TEXT, GREEN, BLUE

FONT = dict(family="Source Sans Pro, Arial, sans-serif", color=TEXT, size=14)


def _layout(fig, height=320, **kw):
    kw.setdefault("margin", dict(l=10, r=10, t=40, b=10))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=FONT, height=height, **kw)
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    return fig


def wait_gauge(wait, title):
    color = LEVEL_COLOR["Okay"] if wait <= 7 else AMBER if wait <= 15 else RED
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=round(wait, 1), number={"suffix": " min", "font": {"size": 40, "color": color}},
        title={"text": title, "font": {"size": 15, "color": MUTED}},
        gauge={"axis": {"range": [0, 30], "tickcolor": MUTED, "tickvals": [0, 7, 15, 30]},
               "bar": {"color": color, "thickness": 0.28}, "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
               "steps": [{"range": [0, 7], "color": "rgba(63,185,80,.18)"},
                         {"range": [7, 15], "color": "rgba(240,167,58,.18)"},
                         {"range": [15, 30], "color": "rgba(229,83,75,.18)"}]}))
    return _layout(fig, height=250, margin=dict(l=30, r=30, t=50, b=20))


def options_bar(opts, best):
    df = pd.DataFrame(opts)
    df["name"] = df.apply(lambda r: f"{r.cashiers}C + {r.baristas}B", axis=1)
    df["is_best"] = (df.cashiers == best["cashiers"]) & (df.baristas == best["baristas"])
    colors = [LEVEL_COLOR[l] for l in df.level]
    fig = go.Figure(go.Bar(
        x=df.name, y=df.wait, marker_color=colors,
        marker_line_color=[LIME if b else "rgba(0,0,0,0)" for b in df.is_best], marker_line_width=4,
        text=[f"{w:.1f} min" + (" ★ best" if b else "") for w, b in zip(df.wait, df.is_best)],
        textposition="outside", cliponaxis=False, hovertemplate="%{x}<br>Expected wait: %{y:.1f} min<extra></extra>"))
    for y, name in ((7, "Okay limit"), (15, "Overloaded limit")):
        fig.add_hline(y=y, line_dash="dot", line_color=MUTED, annotation_text=name,
                      annotation_font_color=MUTED, annotation_position="top right")
    fig.update_yaxes(title="Average wait (minutes)", rangemode="tozero")
    fig.update_xaxes(title="Crew option (C = cashier, B = barista)")
    return _layout(fig, height=360, title=dict(text="Every crew option the AI checked", font=dict(size=16)),
                   showlegend=False)


def confidence_bar(probs):
    order = ["Okay", "Congested", "Overloaded"]
    fig = go.Figure()
    for lvl in order:
        p = probs.get(lvl, 0)
        fig.add_trace(go.Bar(y=[""], x=[p * 100], orientation="h", name=lvl, marker_color=LEVEL_COLOR[lvl],
                             text=f"{lvl} {p:.0%}" if p >= 0.12 else "", textposition="inside",
                             hovertemplate=f"{lvl}: {p:.0%}<extra></extra>"))
    fig.update_layout(barmode="stack", showlegend=False)
    fig.update_xaxes(range=[0, 100], visible=False)
    fig.update_yaxes(visible=False)
    return _layout(fig, height=70, margin=dict(l=0, r=0, t=0, b=0))


def day_chart(rows):
    df = pd.DataFrame(rows)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=df.slot, y=df.cashiers, name="Cashiers", marker_color=AMBER), secondary_y=False)
    fig.add_trace(go.Bar(x=df.slot, y=df.baristas, name="Baristas", marker_color=GREEN), secondary_y=False)
    fig.add_trace(go.Scatter(x=df.slot, y=df.customers, name="Expected customers", mode="lines+markers",
                             line=dict(color=LIME, width=3), marker=dict(size=8)), secondary_y=True)
    fig.update_layout(barmode="stack", legend=dict(orientation="h", y=1.15, x=0))
    fig.update_yaxes(title_text="Staff on the counter", secondary_y=False, dtick=1)
    fig.update_yaxes(title_text="Customers per hour", secondary_y=True, showgrid=False, tickformat=".0f", rangemode="tozero")
    fig.update_yaxes(rangemode="tozero", secondary_y=False)
    return _layout(fig, height=380)


def day_strip(rows):
    """Colored timeline: one block per hour, colored by the AI's predicted level."""
    fig = go.Figure(go.Bar(
        x=[r["slot"][:5] for r in rows], y=[1] * len(rows), marker_color=[LEVEL_COLOR[r["level"]] for r in rows],
        text=[f"<b>{r['wait']}m</b>" for r in rows], textposition="inside", insidetextanchor="middle",
        textfont=dict(color="white", size=14),
        hovertemplate="%{x}<br>%{text} expected wait<extra></extra>"))
    fig.update_yaxes(visible=False)
    fig.update_layout(bargap=0.08, showlegend=False)
    return _layout(fig, height=110, margin=dict(l=0, r=0, t=6, b=0))


def donut(labels, values, colors, center=""):
    texts = [str(v) if v else "" for v in values]
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.62, marker=dict(colors=colors),
                           text=texts, textinfo="text", sort=False))
    fig.update_layout(annotations=[dict(text=center, showarrow=False, font=dict(size=20, color=TEXT))],
                      legend=dict(orientation="h", y=-0.1))
    return _layout(fig, height=300)


def sentiment_donut(df):
    order = ["Positive", "Neutral", "Negative"]
    counts = [int((df.sentiment == s).sum()) for s in order]
    return donut(["Positive", "Neutral", "Negative"], counts, [LEVEL_COLOR["Okay"], BLUE, RED],
                 f"{len(df)}<br>reports")


def category_bar(df):
    c = df.category.value_counts().sort_values()
    fig = go.Figure(go.Bar(x=c.values, y=c.index, orientation="h", marker_color=GREEN, text=c.values,
                           textposition="outside", cliponaxis=False))
    fig.update_xaxes(visible=False, range=[0, max(c.values) * 1.3])
    return _layout(fig, height=300, title=dict(text="What the reports are about", font=dict(size=16)))


def trend(df):
    d = df.copy()
    d["day"] = pd.to_datetime(d.created_at).dt.date
    t = d.groupby(["day", "sentiment"]).size().unstack(fill_value=0)
    fig = go.Figure()
    for s, col in (("Positive", LEVEL_COLOR["Okay"]), ("Neutral", BLUE), ("Negative", RED)):
        if s in t:
            fig.add_trace(go.Bar(x=[pd.Timestamp(x).strftime("%b %d") for x in t.index], y=t[s], name=s,
                                 marker_color=col))
    fig.update_layout(barmode="stack", legend=dict(orientation="h", y=-0.15), bargap=0.4)
    fig.update_xaxes(type="category")
    fig.update_yaxes(dtick=1)
    return _layout(fig, height=300, title=dict(text="Reports per day", font=dict(size=16)))


def confusion(cm, title="Right vs. wrong answers on 800 test hours", x_prefix="AI said", y_prefix="Really"):
    labels = cm["labels"]
    fig = go.Figure(go.Heatmap(z=cm["matrix"], x=[f"{x_prefix} {l}" for l in labels],
                               y=[f"{y_prefix} {l}" for l in labels],
                               colorscale=[[0, "#16201B"], [1, GREEN]], showscale=False,
                               text=cm["matrix"], texttemplate="%{text}", textfont=dict(size=18)))
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, height=320, title=dict(text=title, font=dict(size=16)))


def agreement_by_day(days):
    """days: list of dicts with day (label), agree, differ."""
    df = pd.DataFrame(days)
    total = df.agree + df.differ
    pct = (df.agree / total * 100).round(0)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=df.day, y=df.agree, name="Agreed", marker_color=LEVEL_COLOR["Okay"]), secondary_y=False)
    fig.add_trace(go.Bar(x=df.day, y=df.differ, name="Different", marker_color=AMBER), secondary_y=False)
    fig.add_trace(go.Scatter(x=df.day, y=pct, name="Agreement %", mode="lines+markers+text",
                             text=[f"{p:.0f}%" for p in pct], textposition="top center",
                             line=dict(color=LIME, width=3), marker=dict(size=9)), secondary_y=True)
    fig.update_layout(barmode="stack", legend=dict(orientation="h", y=1.15, x=0), bargap=0.35)
    fig.update_xaxes(type="category")
    fig.update_yaxes(title_text="Reports", dtick=1, rangemode="tozero", secondary_y=False)
    fig.update_yaxes(title_text="Agreement", range=[0, 115], tickvals=[0, 25, 50, 75, 100], ticksuffix="%",
                     showgrid=False, secondary_y=True)
    return _layout(fig, height=380)


def score_gauge(value, target, title):
    color = LEVEL_COLOR["Okay"] if value >= target else AMBER
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value * 100, number={"suffix": "%", "font": {"size": 40, "color": color}},
        title={"text": title, "font": {"size": 15, "color": MUTED}},
        gauge={"axis": {"range": [0, 100], "tickcolor": MUTED}, "bar": {"color": color, "thickness": 0.3},
               "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
               "threshold": {"line": {"color": LIME, "width": 4}, "value": target * 100}}))
    return _layout(fig, height=250, margin=dict(l=40, r=40, t=50, b=20))


FRIENDLY = {"barista_load": "Barista workload", "cashier_load": "Cashier workload", "arr_rate": "Customers per minute",
            "num_barista": "Number of baristas", "num_cashier": "Number of cashiers", "p_simple": "Share of simple drinks",
            "complex_prep": "Complex drink time", "simple_prep": "Simple drink time", "cashier_mean": "Time per order"}


def importance(fi):
    s = pd.Series({FRIENDLY.get(k, k): v for k, v in fi.items()}).sort_values().tail(6)
    fig = go.Figure(go.Bar(x=s.values * 100, y=s.index, orientation="h", marker_color=LIME,
                           text=[f"{v * 100:.0f}%" for v in s.values], textposition="outside", cliponaxis=False))
    fig.update_xaxes(visible=False, range=[0, max(s.values) * 100 * 1.25])
    return _layout(fig, height=320, title=dict(text="What the AI looks at most", font=dict(size=16)))


def accuracy_gauge(acc, baseline):
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta", value=acc * 100, number={"suffix": "%", "font": {"size": 44, "color": LIME}},
        delta={"reference": baseline * 100, "suffix": " pts vs guessing", "font": {"size": 14}},
        title={"text": "Test accuracy (target 85%)", "font": {"size": 15, "color": MUTED}},
        gauge={"axis": {"range": [0, 100], "tickcolor": MUTED}, "bar": {"color": LIME, "thickness": 0.3},
               "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
               "threshold": {"line": {"color": AMBER, "width": 4}, "value": 85}}))
    return _layout(fig, height=270, margin=dict(l=45, r=45, t=50, b=20))
