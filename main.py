import os
import logging
import discord
from dotenv import load_dotenv

from bot.client import Bot

def main():
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if not token:
        raise SystemExit("DISCORD_TOKEN not set in environment (.env).")

    intents = discord.Intents.default()
    intents.members = True  # only if you really need members

    bot = Bot(intents=intents)
    bot.run(token)

if __name__ == "__main__":
    main()