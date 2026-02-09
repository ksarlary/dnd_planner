import logging
import discord
from discord import app_commands

log = logging.getLogger("discord-bot")

def setup_error_handler(bot) -> None:
    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        async def _safe_respond(content: str, ephemeral: bool = False):
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(content, ephemeral=ephemeral)
                else:
                    await interaction.response.send_message(content, ephemeral=ephemeral)
            except Exception:
                pass

        if isinstance(error, app_commands.CommandOnCooldown):
            return await _safe_respond(f"⏳ Slow down! Try again in {error.retry_after:.1f}s.", ephemeral=True)

        if isinstance(error, app_commands.CheckFailure):
            return await _safe_respond("🚫 You don't have permission to use this command here.", ephemeral=True)

        log.exception("Unhandled app command error (%s)", getattr(interaction, "command", None))
        await _safe_respond("⚠️ Something went wrong. It’s been logged.", ephemeral=True)