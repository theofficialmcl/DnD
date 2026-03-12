from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from typing import Dict, List, Tuple
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ----------------------------
# Page config + dark styling
# ----------------------------
st.set_page_config(page_title="D&D Spell Damage Analyzer", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background-color: #0b0f14;
        color: #e8eef2;
    }
    section[data-testid="stSidebar"] {
        background-color: #11161d;
    }
    .stMarkdown, .stText, label, p, h1, h2, h3, h4, h5, h6, div {
        color: #e8eef2;
    }
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div {
        background-color: #18202a !important;
        color: #e8eef2 !important;
    }
    input, textarea {
        color: #e8eef2 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------
# Data model
# ----------------------------
@dataclass
class Spell:
    id: int
    name: str
    num_dice: int
    die_size: int
    save_stat: str
    half_on_save: bool
    enabled: bool = True
    color: str = "#8ecae6"
    dc_mode: str = "Global"   # "Global" or "Custom"
    custom_dc: int = 15


SAVE_STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
DEFAULT_COLORS = [
    "#8ecae6",
    "#90be6d",
    "#f9c74f",
    "#cdb4db",
    "#f4a261",
    "#84a59d",
    "#e5989b",
    "#bde0fe",
]


# ----------------------------
# Cached math helpers
# ----------------------------
@st.cache_data
def dice_distribution(num_dice: int, die_size: int) -> Dict[int, float]:
    dist = Counter({0: 1.0})
    for _ in range(num_dice):
        new_dist = Counter()
        for subtotal, prob in dist.items():
            for face in range(1, die_size + 1):
                new_dist[subtotal + face] += prob / die_size
        dist = new_dist
    return dict(sorted(dist.items()))


@st.cache_data
def single_d20_distribution(mode: str = "normal") -> Dict[int, float]:
    if mode == "normal":
        return {r: 1 / 20 for r in range(1, 21)}

    counts = Counter()
    total = 20 * 20

    for a in range(1, 21):
        for b in range(1, 21):
            if mode == "advantage":
                counts[max(a, b)] += 1
            elif mode == "disadvantage":
                counts[min(a, b)] += 1
            else:
                raise ValueError("mode must be normal, advantage, or disadvantage")

    return {r: counts[r] / total for r in range(1, 21)}


@st.cache_data
def save_success_probability(save_dc: int, save_bonus: int, mode: str = "normal") -> float:
    d20_dist = single_d20_distribution(mode)
    return sum(
        prob for roll, prob in d20_dist.items()
        if roll + save_bonus >= save_dc
    )


@st.cache_data
def spell_outcome_distribution(
    num_dice: int,
    die_size: int,
    half_on_save: bool,
    save_bonus: int,
    save_dc: int,
    mode: str = "normal",
) -> Dict[int, float]:
    base_dist = dice_distribution(num_dice, die_size)
    p_save = save_success_probability(save_dc, save_bonus, mode=mode)
    p_fail = 1.0 - p_save

    final_dist = Counter()
    for dmg, prob in base_dist.items():
        final_dist[dmg] += prob * p_fail
        saved_dmg = dmg // 2 if half_on_save else 0
        final_dist[saved_dmg] += prob * p_save

    return dict(sorted(final_dist.items()))


def expected_value(distribution: Dict[int, float]) -> float:
    return sum(x * p for x, p in distribution.items())


def variance(distribution: Dict[int, float], mean: float) -> float:
    return sum(((x - mean) ** 2) * p for x, p in distribution.items())


def std_dev(distribution: Dict[int, float], mean: float) -> float:
    return math.sqrt(variance(distribution, mean))


def distribution_peak(distribution: Dict[int, float]) -> Tuple[int, float]:
    peak_x = max(distribution, key=distribution.get)
    return peak_x, distribution[peak_x]


def expected_spell_damage(
    num_dice: int,
    die_size: int,
    half_on_save: bool,
    save_bonus: int,
    save_dc: int,
    mode: str = "normal",
) -> float:
    dist = spell_outcome_distribution(
        num_dice=num_dice,
        die_size=die_size,
        half_on_save=half_on_save,
        save_bonus=save_bonus,
        save_dc=save_dc,
        mode=mode,
    )
    return expected_value(dist)


def get_spell_dc(spell: Spell, global_dc: int) -> int:
    return spell.custom_dc if spell.dc_mode == "Custom" else global_dc


# ----------------------------
# Session state
# ----------------------------
if "next_spell_id" not in st.session_state:
    st.session_state.next_spell_id = 3

if "spells" not in st.session_state:
    st.session_state.spells = [
        Spell(1, "Fireball", 8, 6, "DEX", True, True, DEFAULT_COLORS[0], "Global", 15),
        Spell(2, "Blight", 8, 8, "CON", False, True, DEFAULT_COLORS[1], "Global", 15),
    ]


# ----------------------------
# Header
# ----------------------------
st.title("D&D Spell Damage Analyzer")
st.caption("Interactive spell distribution and save comparison with hover data, multiple spells, and advantage/disadvantage support.")


# ----------------------------
# Sidebar controls
# ----------------------------
with st.sidebar:
    st.header("Target Saving Throws")
    st.write("Type values directly or use the +/- controls.")

    target_saves = {
        "STR": st.number_input("STR Save Bonus", min_value=-10, max_value=30, value=0, step=1),
        "DEX": st.number_input("DEX Save Bonus", min_value=-10, max_value=30, value=2, step=1),
        "CON": st.number_input("CON Save Bonus", min_value=-10, max_value=30, value=3, step=1),
        "INT": st.number_input("INT Save Bonus", min_value=-10, max_value=30, value=1, step=1),
        "WIS": st.number_input("WIS Save Bonus", min_value=-10, max_value=30, value=1, step=1),
        "CHA": st.number_input("CHA Save Bonus", min_value=-10, max_value=30, value=0, step=1),
    }

    st.divider()
    st.header("Global Save DC")
    global_dc = st.slider(
        "Global Spell Save DC",
        min_value=5,
        max_value=30,
        value=15,
        step=1,
        key="global_dc_slider",
    )

    st.divider()
    st.header("Add a Spell")

    new_name = st.text_input("Spell Name", value="New Spell")
    new_x = st.number_input("Number of Dice (X)", min_value=1, max_value=40, value=6, step=1)
    new_y = st.number_input("Die Size (Y)", min_value=2, max_value=20, value=6, step=1)
    new_stat = st.selectbox("Save Stat", SAVE_STATS, index=1)
    new_half = st.checkbox("Half Damage on Save", value=True)
    new_color = st.color_picker("Spell Color", value=DEFAULT_COLORS[len(st.session_state.spells) % len(DEFAULT_COLORS)])
    new_dc_mode = st.selectbox("DC Mode", ["Global", "Custom"])
    new_custom_dc = 15
    if new_dc_mode == "Custom":
        new_custom_dc = st.slider("Custom DC", min_value=5, max_value=30, value=15, step=1)

    if st.button("Add Spell", use_container_width=True):
        st.session_state.spells.append(
            Spell(
                id=st.session_state.next_spell_id,
                name=new_name.strip() or "Unnamed Spell",
                num_dice=int(new_x),
                die_size=int(new_y),
                save_stat=new_stat,
                half_on_save=new_half,
                enabled=True,
                color=new_color,
                dc_mode=new_dc_mode,
                custom_dc=int(new_custom_dc),
            )
        )
        st.session_state.next_spell_id += 1
        st.rerun()

    if st.button("Clear All Spells", use_container_width=True):
        st.session_state.spells = []
        st.rerun()


# ----------------------------
# Spell editor
# ----------------------------
st.subheader("Spell Controls")

if not st.session_state.spells:
    st.info("No spells added yet.")
    st.stop()

edited_spells: List[Spell] = []

for i, spell in enumerate(st.session_state.spells):
    with st.expander(f"{spell.name} — {spell.num_dice}d{spell.die_size}", expanded=(i < 2)):
        c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])

        with c1:
            enabled = st.checkbox("Show spell", value=spell.enabled, key=f"enabled_{spell.id}")
            name = st.text_input("Name", value=spell.name, key=f"name_{spell.id}")
        with c2:
            num_dice = st.number_input("Dice (X)", min_value=1, max_value=40, value=spell.num_dice, step=1, key=f"x_{spell.id}")
            die_size = st.number_input("Die Size (Y)", min_value=2, max_value=20, value=spell.die_size, step=1, key=f"y_{spell.id}")
        with c3:
            save_stat = st.selectbox("Save Stat", SAVE_STATS, index=SAVE_STATS.index(spell.save_stat), key=f"stat_{spell.id}")
            half_on_save = st.checkbox("Half on Save", value=spell.half_on_save, key=f"half_{spell.id}")
        with c4:
            color = st.color_picker("Color", value=spell.color, key=f"color_{spell.id}")
            dc_mode = st.selectbox("DC Mode", ["Global", "Custom"], index=0 if spell.dc_mode == "Global" else 1, key=f"dcmode_{spell.id}")
            custom_dc = spell.custom_dc
            if dc_mode == "Custom":
                custom_dc = st.slider("Custom DC", min_value=5, max_value=30, value=spell.custom_dc, step=1, key=f"customdc_{spell.id}")

        remove = st.button("Remove Spell", key=f"remove_{spell.id}")

        if not remove:
            edited_spells.append(
                Spell(
                    id=spell.id,
                    name=name.strip() or "Unnamed Spell",
                    num_dice=int(num_dice),
                    die_size=int(die_size),
                    save_stat=save_stat,
                    half_on_save=half_on_save,
                    enabled=enabled,
                    color=color,
                    dc_mode=dc_mode,
                    custom_dc=int(custom_dc),
                )
            )

st.session_state.spells = edited_spells
visible_spells = [s for s in st.session_state.spells if s.enabled]

if not visible_spells:
    st.warning("All spells are hidden. Enable at least one spell to display graphs.")
    st.stop()


# ----------------------------
# Summary table
# ----------------------------
with st.expander("Current Spell Summary", expanded=False):
    rows = []
    for spell in visible_spells:
        dc = get_spell_dc(spell, global_dc)
        save_bonus = int(target_saves[spell.save_stat])

        dist = spell_outcome_distribution(
            num_dice=spell.num_dice,
            die_size=spell.die_size,
            half_on_save=spell.half_on_save,
            save_bonus=save_bonus,
            save_dc=dc,
            mode="normal",
        )
        mean = expected_value(dist)
        sd = std_dev(dist, mean)
        peak_x, peak_p = distribution_peak(dist)
        p_save = save_success_probability(dc, save_bonus, mode="normal")

        rows.append(
            {
                "Name": spell.name,
                "Damage": f"{spell.num_dice}d{spell.die_size}",
                "Save": spell.save_stat,
                "DC Used": dc,
                "Half on Save": spell.half_on_save,
                "Target Save Bonus": save_bonus,
                "Save Chance": f"{p_save:.1%}",
                "Mean": round(mean, 3),
                "Std Dev": round(sd, 3),
                "Peak Damage": peak_x,
                "Peak Probability": f"{peak_p:.1%}",
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True)


# ----------------------------
# Main distribution graph
# ----------------------------
st.subheader("Spell Damage Distribution")

show_markers = st.checkbox("Show data point markers", value=True)
line_width = st.slider("Line width", min_value=1, max_value=6, value=3, step=1)

chart_placeholder = st.empty()

fig = go.Figure()

for spell in visible_spells:
    dc = get_spell_dc(spell, global_dc)
    save_bonus = int(target_saves[spell.save_stat])

    dist = spell_outcome_distribution(
        num_dice=spell.num_dice,
        die_size=spell.die_size,
        half_on_save=spell.half_on_save,
        save_bonus=save_bonus,
        save_dc=dc,
        mode="normal",
    )

    mean = expected_value(dist)
    sd = std_dev(dist, mean)
    peak_x, peak_p = distribution_peak(dist)

    x_vals = list(dist.keys())
    y_vals = list(dist.values())

    hover_text = [
        (
            f"<b>{spell.name}</b><br>"
            f"Damage: {x}<br>"
            f"Probability: {y:.3%}<br>"
            f"Mean: {mean:.2f}<br>"
            f"Std Dev: {sd:.2f}<br>"
            f"Peak Damage: {peak_x}<br>"
            f"Peak Probability: {peak_p:.3%}<br>"
            f"DC: {dc}<br>"
            f"Save Stat: {spell.save_stat}<br>"
            f"Target Save Bonus: {save_bonus}"
        )
        for x, y in zip(x_vals, y_vals)
    ]

    fig.add_trace(
        go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="lines+markers" if show_markers else "lines",
            name=spell.name,
            line=dict(color=spell.color, width=line_width, shape="linear"),
            marker=dict(
                color=spell.color,
                size=7 if show_markers else 0,
                line=dict(color="rgba(255,255,255,0.12)", width=0.8),
            ),
            hoverinfo="text",
            hovertext=hover_text,
        )
    )

    # Invisible hover targets for mean / std dev / peak
    fig.add_trace(
        go.Scatter(
            x=[peak_x],
            y=[peak_p],
            mode="markers",
            marker=dict(size=16, color=spell.color, opacity=0.001),
            showlegend=False,
            hovertemplate=(
                f"<b>{spell.name} Peak</b><br>"
                f"Peak Damage: {peak_x}<br>"
                f"Peak Probability: {peak_p:.3%}<br>"
                f"Mean: {mean:.2f}<br>"
                f"Std Dev: {sd:.2f}<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[mean],
            y=[max(y_vals) * 0.95],
            mode="markers",
            marker=dict(size=16, color=spell.color, opacity=0.001),
            showlegend=False,
            hovertemplate=(
                f"<b>{spell.name} Mean</b><br>"
                f"Mean: {mean:.2f}<br>"
                f"Std Dev: {sd:.2f}<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[mean - sd, mean + sd],
            y=[max(y_vals) * 0.88, max(y_vals) * 0.88],
            mode="markers",
            marker=dict(size=16, color=spell.color, opacity=0.001),
            showlegend=False,
            hovertemplate=(
                f"<b>{spell.name} Std Dev Marker</b><br>"
                f"Value: %{{x:.2f}}<br>"
                f"Mean: {mean:.2f}<br>"
                f"Std Dev: {sd:.2f}<extra></extra>"
            ),
        )
    )

with chart_placeholder:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0b0f14",
        plot_bgcolor="#0b0f14",
        font=dict(color="#e8eef2"),
        title=f"Final Damage Distribution (Global DC = {global_dc})",
        xaxis_title="Final Damage Dealt",
        yaxis_title="Probability",
        hovermode="closest",
        legend=dict(
            bgcolor="rgba(17,22,29,0.70)",
            bordercolor="rgba(255,255,255,0.15)",
            borderwidth=1,
        ),
        margin=dict(l=30, r=30, t=50, b=30),
    )

    fig.update_xaxes(gridcolor="rgba(120,140,160,0.18)")
    fig.update_yaxes(gridcolor="rgba(120,140,160,0.18)", tickformat=".0%")

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ----------------------------
# Save comparison graph
# ----------------------------
st.subheader("Expected Damage vs Save Bonus")
st.caption("Normal vs advantage vs disadvantage on the save.")

save_bonus_range = st.slider(
    "Save Bonus Range",
    min_value=-5,
    max_value=20,
    value=(-2, 12),
    step=1,
)

selected_spell_name = st.selectbox(
    "Spell for save comparison",
    [spell.name for spell in visible_spells],
)

selected_spell = next(spell for spell in visible_spells if spell.name == selected_spell_name)
selected_dc = get_spell_dc(selected_spell, global_dc)

bonus_values = list(range(save_bonus_range[0], save_bonus_range[1] + 1))
normal_vals = [
    expected_spell_damage(
        num_dice=selected_spell.num_dice,
        die_size=selected_spell.die_size,
        half_on_save=selected_spell.half_on_save,
        save_bonus=bonus,
        save_dc=selected_dc,
        mode="normal",
    )
    for bonus in bonus_values
]
adv_vals = [
    expected_spell_damage(
        num_dice=selected_spell.num_dice,
        die_size=selected_spell.die_size,
        half_on_save=selected_spell.half_on_save,
        save_bonus=bonus,
        save_dc=selected_dc,
        mode="advantage",
    )
    for bonus in bonus_values
]
dis_vals = [
    expected_spell_damage(
        num_dice=selected_spell.num_dice,
        die_size=selected_spell.die_size,
        half_on_save=selected_spell.half_on_save,
        save_bonus=bonus,
        save_dc=selected_dc,
        mode="disadvantage",
    )
    for bonus in bonus_values
]

fig2 = go.Figure()

series = [
    ("Normal", normal_vals, "#8ecae6"),
    ("Advantage", adv_vals, "#90be6d"),
    ("Disadvantage", dis_vals, "#f4a261"),
]

for label, y_vals, color in series:
    hover_text = [
        (
            f"<b>{selected_spell.name}</b><br>"
            f"Mode: {label}<br>"
            f"Save Bonus: {bonus}<br>"
            f"Expected Damage: {y:.2f}<br>"
            f"DC: {selected_dc}<br>"
            f"Save Stat: {selected_spell.save_stat}"
        )
        for bonus, y in zip(bonus_values, y_vals)
    ]

    fig2.add_trace(
        go.Scatter(
            x=bonus_values,
            y=y_vals,
            mode="lines+markers",
            name=label,
            line=dict(color=color, width=3, shape="linear"),
            marker=dict(
                color=color,
                size=7,
                line=dict(color="rgba(255,255,255,0.12)", width=0.8),
            ),
            hoverinfo="text",
            hovertext=hover_text,
        )
    )

fig2.update_layout(
    template="plotly_dark",
    paper_bgcolor="#0b0f14",
    plot_bgcolor="#0b0f14",
    font=dict(color="#e8eef2"),
    title=f"{selected_spell.name}: Expected Damage by Save Bonus",
    xaxis_title="Target Save Bonus",
    yaxis_title="Expected Damage",
    hovermode="closest",
    legend=dict(
        bgcolor="rgba(17,22,29,0.70)",
        bordercolor="rgba(255,255,255,0.15)",
        borderwidth=1,
    ),
    margin=dict(l=30, r=30, t=50, b=30),
)

fig2.update_xaxes(gridcolor="rgba(120,140,160,0.18)")
fig2.update_yaxes(gridcolor="rgba(120,140,160,0.18)")

st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
