from pathlib import Path
import random
import discord
from discord.ext import commands
import re

token = Path('token').read_text()
MY_TOKEN = token

dinner_candidtes = ['拉', '咖哩', '肯', '麥', '摩', '大的']

intents = discord.Intents().all()
client = commands.Bot(command_prefix='$', intents=intents)


@client.event
async def on_ready():
    print(
        f'\n\nSuccessfully logged into Discord as "{client.user}"\nAwaiting user input...'
    )
    await client.change_presence(status=discord.Status.online,
                                 activity=discord.Activity(
                                     type=discord.ActivityType.playing,
                                     name="all by myself..."))


@client.hybrid_command()
async def dinner(ctx):
    food = random.choice(dinner_candidtes)
    await ctx.send(food)


@client.event
async def on_message(message):
    if message.content.startswith("誠"):
        if "晚餐" in message.content:
            await message.channel.send(random.choice(dinner_candidtes))
        else:
            await message.channel.send("= =")


client.run(MY_TOKEN)
