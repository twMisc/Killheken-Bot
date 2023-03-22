import json
from pathlib import Path
import random
import discord
from discord.ext import commands

token = Path('token').read_text()
guild = Path('guild').read_text()
user_id = Path('user_id').read_text()
user_id_2 = Path('user_id_2').read_text()
with open('emojis.json') as f:
    emojis = json.load(f)

MY_TOKEN = token
MY_GUILD_ID = discord.Object(guild)
MY_ID = int(user_id)
MY_ID_2 = int(user_id_2)

dinner_candidtes = ['拉', '咖哩', '肯', '麥', '摩', '大的']

intents = discord.Intents().all()
client = commands.Bot(command_prefix='$', intents=intents)


def emoji(emoji: dict):
    return f"<:{emoji['name']}:{emoji['id']}>"


@client.event
async def on_ready():
    print(
        f'\n\nSuccessfully logged into Discord as "{client.user}"\nAwaiting user input...'
    )
    await client.change_presence(status=discord.Status.online,
                                 activity=discord.Activity(
                                     type=discord.ActivityType.playing,
                                     name="我是帥哥誠"))


@client.hybrid_command(name='dinner', description='問帥哥誠晚餐該吃啥')
async def dinner(ctx):
    food = random.choice(dinner_candidtes)
    await ctx.send(food)


@client.hybrid_command(name='sync',
                       description='sync commands',
                       guild=MY_GUILD_ID)
async def sync(ctx):
    synced = await ctx.bot.tree.sync()
    await ctx.send(f"Synced {len(synced)} commands to the current guild.")


@client.event
async def on_message(message):
    if message.content.startswith("誠"):
        if "晚餐" in message.content:
            await message.channel.send(random.choice(dinner_candidtes))
        elif "還是" in message.content:
            tmp = message.content.find("還是")
            options = [message.content[1:tmp], message.content[tmp + 2:]]
            await message.channel.send(random.choice(options))
        else:
            if (message.author.id == MY_ID):
                await message.channel.send('大')
            else:
                await message.channel.send("= =")
    if message.content.startswith(emoji(
            emojis[0])) and message.author != client.user:
        await message.channel.send(emoji(emojis[0]))
    await client.process_commands(message)


client.run(MY_TOKEN)
