from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from typing import Dict, List
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st


# ----------------------------
# Data models
# ----------------------------
@dataclass
class Spell:
    name: str
    num_dice: int
    die_size: int
    save_dc: int
    save_stat: str
    half_on_save: bool


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


def spell_outcome_distribution(spell: Spell, save_bonus: int) -> Dict[int, float]:
    base_dist = dice_distribution(spell.num_dice, spell.die_size)
    p_save = save_success_probability(spell.save_dc, save_bonus)
    p_fail = 1.0 - p_save

    final_dist = Counter()
    for dmg, prob in base_dist.items():
        final_dist[dmg] += prob * p_fail
        saved_dmg = dmg // 2 if spell.half_on_save else 0
        final_dist[saved_dmg] += prob * p_save

    return dict(sorted(final_dist.items()))


def expected_value(distribution: Dict[int, float]) -> float:
    return sum(dmg * prob for dmg, prob in distribution.items())


def expected_spell_damage(spell: Spell, save_bonus: int) -> float:
    return expected_value(spell_outcome_distribution(spell, save_bonus))


# ----------------------------
# Streamlit app
# ----------------------------
st.set_page_config(page_title="Spell Damage Grapher", layout="wide")
st.title("Spell Damage Grapher")

SAVE_STATS = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

if "spells" not in st.session_state:
    st.session_state.spells = [
        Spell("Fireball", 8, 6, 15, "DEX", True),
        Spell("Blight", 8, 8, 16, "CON", False),
        Spell("Dissonant Whispers", 3, 6, 15, "WIS", False),
    ]

with st.sidebar:
    st.header("Target Saving Throws")
    target_saves = {
        "STR": st.number_input("STR", value=0, step=1),
        "DEX": st.number_input("DEX", value=2, step=1),
        "CON": st.number_input("CON", value=3, step=1),
        "INT": st.number_input("INT", value=1, step=1),
        "WIS": st.number_input("WIS", value=1, step=1),
        "CHA": st.number_input("CHA", value=0, step=1),
    }

    st.divider()
    st.header("Add Spell")

    name = st.text_input("Spell Name", value="New Spell")
    x = st.number_input("Number of Dice (X)", min_value=1, value=6, step=1)
    y = st.number_input("Die Size (Y)", min_value=2, value=6, step=1)
    dc = st.number_input("Save DC", min_value=1, value=15, step=1)
    save_stat = st.selectbox("Save Stat", SAVE_STATS, index=1)
    half_on_save = st.checkbox("Half Damage on Save", value=True)

    if st.button("Add Spell"):
        st.session_state.spells.append(
            Spell(
                name=name.strip() or "Unnamed Spell",
                num_dice=int(x),
                die_size=int(y),
                save_dc=int(dc),
                save_stat=save_stat,
                half_on_save=half_on_save,
            )
        )
        st.rerun()

st.subheader("Current Spells")

if not st.session_state.spells:
    st.info("No spells added yet.")
else:
    rows = []
    for i, spell in enumerate(st.session_state.spells):
        save_bonus = target_saves[spell.save_stat]
        p_save = save_success_probability(spell.save_dc, save_bonus)
        expected = expected_spell_damage(spell, save_bonus)
        rows.append({
            "Index": i,
            "Name": spell.name,
            "Damage": f"{spell.num_dice}d{spell.die_size}",
            "DC": spell.save_dc,
            "Save": spell.save_stat,
            "Half on Save": spell.half_on_save,
            "Target Bonus": save_bonus,
            "Save Chance": f"{p_save:.1%}",
            "Expected Damage": round(expected, 3),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    # Comparison chart
    st.subheader("Expected Damage Comparison")
    fig1, ax1 = plt.subplots(figsize=(10, 5))
    ax1.bar(df["Name"], df["Expected Damage"])
    ax1.set_ylabel("Expected Damage")
    ax1.set_xlabel("Spell")
    ax1.set_title("Expected Damage vs Current Target")
    plt.xticks(rotation=20)
    plt.tight_layout()
    st.pyplot(fig1)

    # Detailed spell distribution
    st.subheader("Detailed Distribution")
    spell_names = [s.name for s in st.session_state.spells]
    selected_name = st.selectbox("Choose a spell", spell_names)
    selected_spell = next(s for s in st.session_state.spells if s.name == selected_name)

    selected_save_bonus = target_saves[selected_spell.save_stat]
    dist = spell_outcome_distribution(selected_spell, selected_save_bonus)

    fig2, ax2 = plt.subplots(figsize=(10, 5))
    ax2.bar(list(dist.keys()), list(dist.values()))
    ax2.set_xlabel("Final Damage Dealt")
    ax2.set_ylabel("Probability")
    ax2.set_title(
        f"{selected_spell.name}: DC {selected_spell.save_dc} "
        f"{selected_spell.save_stat} save vs bonus {selected_save_bonus}"
    )
    plt.tight_layout()
    st.pyplot(fig2)

    # Remove spell
    st.subheader("Remove Spell")
    remove_name = st.selectbox("Select a spell to remove", spell_names, key="remove_spell")
    if st.button("Remove Selected Spell"):
        st.session_state.spells = [s for s in st.session_state.spells if s.name != remove_name]
        st.rerun()
