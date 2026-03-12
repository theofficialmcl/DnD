from __future__ import annotations

from dataclasses import dataclass, asdict
from collections import Counter
from typing import Dict, List, Tuple
import math

import matplotlib.pyplot as plt
import pandas as pd
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
    div[data-baseweb="select"] > div {
        background-color: #18202a;
        color: #e8eef2;
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
    name: str
    num_dice: int
    die_size: int
    save_stat: str
    half_on_save: bool


SAVE_STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

# eye-friendly colors for dark background
SPELL_COLORS = [
    "#8ecae6",  # soft blue
    "#90be6d",  # soft green
    "#f9c74f",  # muted gold
    "#cdb4db",  # soft lavender
    "#f4a261",  # muted orange
    "#84a59d",  # sage
    "#e5989b",  # dusty rose
    "#bde0fe",  # pale blue
]


# ----------------------------
# Math helpers
# ----------------------------
def dice_distribution(num_dice: int, die_size: int) -> Dict[int, float]:
    dist = Counter({0: 1.0})
    for _ in range(num_dice):
        new_dist = Counter()
        for subtotal, prob in dist.items():
            for face in range(1, die_size + 1):
                new_dist[subtotal + face] += prob / die_size
        dist = new_dist
    return dict(sorted(dist.items()))


def save_success_probability(save_dc: int, save_bonus: int) -> float:
    successes = 0
    for roll in range(1, 21):
        if roll + save_bonus >= save_dc:
            successes += 1
    return successes / 20.0


def spell_outcome_distribution(spell: Spell, save_bonus: int, save_dc: int) -> Dict[int, float]:
    base_dist = dice_distribution(spell.num_dice, spell.die_size)
    p_save = save_success_probability(save_dc, save_bonus)
    p_fail = 1.0 - p_save

    final_dist = Counter()
    for dmg, prob in base_dist.items():
        final_dist[dmg] += prob * p_fail
        saved_dmg = dmg // 2 if spell.half_on_save else 0
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


def expected_spell_damage(spell: Spell, save_bonus: int, save_dc: int) -> float:
    return expected_value(spell_outcome_distribution(spell, save_bonus, save_dc))


# ----------------------------
# Session state
# ----------------------------
if "spells" not in st.session_state:
    st.session_state.spells = [
        Spell("Fireball", 8, 6, "DEX", True),
        Spell("Blight", 8, 8, "CON", False),
    ]


# ----------------------------
# Sidebar controls
# ----------------------------
st.title("D&D Spell Damage Analyzer")
st.caption("Compare full spell damage distributions with saving throws, live DC changes, and multiple spells.")

with st.sidebar:
    st.header("Target Saving Throws")

    st.write("You can type values directly or use the +/- controls.")

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
    save_dc = st.slider("Spell Save DC", min_value=5, max_value=30, value=15, step=1)

    st.divider()
    st.header("Add a Spell")

    new_name = st.text_input("Spell Name", value="New Spell")
    new_x = st.number_input("Number of Dice (X)", min_value=1, max_value=40, value=6, step=1)
    new_y = st.number_input("Die Size (Y)", min_value=2, max_value=20, value=6, step=1)
    new_stat = st.selectbox("Save Stat", SAVE_STATS, index=1)
    new_half = st.checkbox("Half Damage on Save", value=True)

    if st.button("Add Spell", use_container_width=True):
        st.session_state.spells.append(
            Spell(
                name=new_name.strip() or "Unnamed Spell",
                num_dice=int(new_x),
                die_size=int(new_y),
                save_stat=new_stat,
                half_on_save=new_half,
            )
        )
        st.rerun()

    if st.button("Clear All Spells", use_container_width=True):
        st.session_state.spells = []
        st.rerun()


# ----------------------------
# Current spell table
# ----------------------------
st.subheader("Current Spells")

if not st.session_state.spells:
    st.info("No spells added yet.")
    st.stop()

rows = []
for i, spell in enumerate(st.session_state.spells):
    save_bonus = int(target_saves[spell.save_stat])
    dist = spell_outcome_distribution(spell, save_bonus, save_dc)
    mean = expected_value(dist)
    sd = std_dev(dist, mean)
    peak_x, peak_p = distribution_peak(dist)
    p_save = save_success_probability(save_dc, save_bonus)

    rows.append(
        {
            "Index": i,
            "Name": spell.name,
            "Damage": f"{spell.num_dice}d{spell.die_size}",
            "Save": spell.save_stat,
            "Half on Save": spell.half_on_save,
            "Target Save Bonus": save_bonus,
            "Save Chance": f"{p_save:.1%}",
            "Mean": round(mean, 3),
            "Std Dev": round(sd, 3),
            "Peak Damage": peak_x,
            "Peak Probability": f"{peak_p:.1%}",
        }
    )

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)


# ----------------------------
# Remove spell UI
# ----------------------------
with st.expander("Remove a spell"):
    spell_names = [s.name for s in st.session_state.spells]
    remove_name = st.selectbox("Select spell to remove", spell_names)
    if st.button("Remove Selected Spell"):
        removed = False
        new_spells = []
        for s in st.session_state.spells:
            if s.name == remove_name and not removed:
                removed = True
                continue
            new_spells.append(s)
        st.session_state.spells = new_spells
        st.rerun()


# ----------------------------
# Multi-spell distribution graph
# ----------------------------
st.subheader("Spell Damage Distributions")

fig, ax = plt.subplots(figsize=(13, 7))
fig.patch.set_facecolor("#0b0f14")
ax.set_facecolor("#0b0f14")

max_x = 0

for i, spell in enumerate(st.session_state.spells):
    color = SPELL_COLORS[i % len(SPELL_COLORS)]
    save_bonus = int(target_saves[spell.save_stat])
    dist = spell_outcome_distribution(spell, save_bonus, save_dc)
    mean = expected_value(dist)
    sd = std_dev(dist, mean)
    peak_x, peak_p = distribution_peak(dist)

    x_vals = list(dist.keys())
    y_vals = list(dist.values())
    max_x = max(max_x, max(x_vals))

    ax.plot(
        x_vals,
        y_vals,
        linewidth=2.5,
        color=color,
        label=f"{spell.name} ({spell.num_dice}d{spell.die_size}, {spell.save_stat})",
    )

    # Peak marker
    ax.scatter([peak_x], [peak_p], color=color, s=60, zorder=5)
    ax.annotate(
        f"Peak {peak_x}",
        xy=(peak_x, peak_p),
        xytext=(6, 8),
        textcoords="offset points",
        color=color,
        fontsize=9,
    )

    # Mean line
    ax.axvline(mean, color=color, linestyle="--", alpha=0.85, linewidth=1.8)

    # Std dev lines
    ax.axvline(mean - sd, color=color, linestyle=":", alpha=0.7, linewidth=1.3)
    ax.axvline(mean + sd, color=color, linestyle=":", alpha=0.7, linewidth=1.3)

    # text summary in upper-right area
    summary_y = 0.97 - i * 0.09
    ax.text(
        0.985,
        summary_y,
        (
            f"{spell.name}: "
            f"μ={mean:.2f}, "
            f"σ={sd:.2f}, "
            f"peak={peak_x}"
        ),
        transform=ax.transAxes,
        ha="right",
        va="top",
        color=color,
        fontsize=10,
        bbox=dict(facecolor="#11161d", edgecolor=color, alpha=0.55, boxstyle="round,pad=0.25"),
    )

ax.set_title(f"Final Damage Distributions at Save DC {save_dc}", color="#e8eef2", fontsize=15)
ax.set_xlabel("Final Damage Dealt", color="#e8eef2")
ax.set_ylabel("Probability", color="#e8eef2")
ax.tick_params(colors="#d7e3ea")
for spine in ax.spines.values():
    spine.set_color("#5c6773")
ax.grid(True, color="#2a3441", alpha=0.45)
ax.legend(facecolor="#11161d", edgecolor="#5c6773", labelcolor="#e8eef2")

st.pyplot(fig, use_container_width=True)


# ----------------------------
# Expected damage by DC graph
# ----------------------------
st.subheader("Expected Damage vs Save DC")

dc_min, dc_max = st.slider(
    "DC range for comparison",
    min_value=5,
    max_value=30,
    value=(8, 22),
    step=1,
)

fig2, ax2 = plt.subplots(figsize=(13, 6))
fig2.patch.set_facecolor("#0b0f14")
ax2.set_facecolor("#0b0f14")

dc_values = list(range(dc_min, dc_max + 1))

for i, spell in enumerate(st.session_state.spells):
    color = SPELL_COLORS[i % len(SPELL_COLORS)]
    save_bonus = int(target_saves[spell.save_stat])
    y_vals = [expected_spell_damage(spell, save_bonus, dc) for dc in dc_values]

    ax2.plot(
        dc_values,
        y_vals,
        linewidth=2.5,
        color=color,
        label=f"{spell.name} ({spell.save_stat})",
    )

ax2.axvline(save_dc, color="#ffffff", linestyle="--", alpha=0.35, linewidth=1.5)
ax2.set_title("Expected Damage Across Different Save DCs", color="#e8eef2", fontsize=15)
ax2.set_xlabel("Save DC", color="#e8eef2")
ax2.set_ylabel("Expected Damage", color="#e8eef2")
ax2.tick_params(colors="#d7e3ea")
for spine in ax2.spines.values():
    spine.set_color("#5c6773")
ax2.grid(True, color="#2a3441", alpha=0.45)
ax2.legend(facecolor="#11161d", edgecolor="#5c6773", labelcolor="#e8eef2")

st.pyplot(fig2, use_container_width=True)
