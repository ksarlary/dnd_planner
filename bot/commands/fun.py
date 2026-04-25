import random

import discord
from discord import app_commands

from bot.storage.profiles import get_profile


EXCUSES = [
    "The {label} is stuck in a time loop again.",
    "The {label} has been polymorphed into a chair.",
    "The {label} is attending a very important side quest (snack-related).",
    "The {label} forgot what day it is. Again.",
    "The {label} is busy arguing with an NPC.",
    "The {label} got distracted by loot. It happens.",
    "The {label} is emotionally unavailable. Also physically.",
    "The {label} failed a saving throw against the sofa.",
    "The {label} is trapped under an urgent pile of blankets.",
    "The {label} has joined a secret meeting of suspiciously punctual NPCs.",
    "The {label} is negotiating peace with their laundry.",
    "The {label} opened one tiny side quest and has not been seen since.",
    "The {label} is recovering from a critical hit to motivation.",
    "The {label} was last seen chasing a plot hook in the wrong direction.",
]

SPELLS = [
    "Summon Mild Confusion",
    "Fireball (but it's just warm)",
    "Greater Procrastination",
    "Invisibility (only when not needed)",
    "Summon Snacks",
    "Teleport (but slightly off target)",
    "Detect Bad Decisions",
    "Mage Hand, But It Points Accusingly",
    "Conjure Unread Notifications",
    "Speak With Furniture",
    "Blessing of Suspicious Confidence",
    "Instant Regret",
    "Counterspell, But Too Late",
    "Summon Dramatic Fog Machine",
    "Enlarge Ego",
]

CURSES = [
    "You will step on a d4.",
    "Your dice will betray you at the worst moment.",
    "You will forget your character sheet.",
    "Your snacks will mysteriously disappear.",
    "Every door you open will be a pull door.",
    "Your initiative rolls will have performance anxiety.",
    "Your coffee will become room temperature exactly when needed.",
    "Every NPC name will sound important, except the important one.",
    "Your next natural 20 will be on a perception check for soup.",
    "Your pencil will vanish between turns.",
    "Your inventory will be perfectly organized and still useless.",
    "Your battle plan will work, but only after everyone ignores it.",
]


def setup_fun_commands(bot) -> None:
    @bot.tree.command(name="excuse", description="Generate a totally valid excuse")
    async def excuse(interaction: discord.Interaction):
        label = _get_excuse_label(interaction.user.id)
        excuse_text = random.choice(EXCUSES).format(label=label)
        await interaction.response.send_message(f"📜 {excuse_text}")

    @bot.tree.command(name="fight", description="Start a totally fair fight")
    @app_commands.describe(opponent="Who do you fight?")
    async def fight(interaction: discord.Interaction, opponent: discord.Member):
        winner = random.choice([interaction.user, opponent])
        loser = opponent if winner == interaction.user else interaction.user

        await interaction.response.send_message(
            f"⚔️ {interaction.user.mention} vs {opponent.mention}\n"
            f"🏆 Winner: **{winner.display_name}**\n"
            f"💀 {loser.display_name} has been defeated (emotionally)."
        )

    @bot.tree.command(name="spell", description="Cast a random spell")
    async def spell(interaction: discord.Interaction):
        await interaction.response.send_message(
            f"✨ You cast **{random.choice(SPELLS)}**!"
        )

    @bot.tree.command(name="curse", description="Curse someone")
    @app_commands.describe(target="Who to curse?")
    async def curse(interaction: discord.Interaction, target: discord.Member):
        await interaction.response.send_message(
            f"🔮 {target.mention}, {random.choice(CURSES)}"
        )


def _get_excuse_label(user_id: int) -> str:
    profile = get_profile(user_id)
    if profile is None:
        return "unimportant NPC"

    return random.choice([profile["race"], profile["class"]]).lower()
