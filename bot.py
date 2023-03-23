import json
from pathlib import Path
import random
import re
import discord
import subprocess
from discord.ext import commands

token = Path('token').read_text()
guild = Path('guild').read_text()

with open('ids_admin.json') as f:
    admins = json.load(f)
with open('ids.json') as f:
    ID_list = json.load(f)
with open('emojis.json') as f:
    emojis = json.load(f)

ADMIN_LIST = admins
MY_TOKEN = token
MY_GUILD_ID = discord.Object(guild)

dinner_candidtes = ['拉', '咖哩', '肯', '麥', '摩', '大的']
Response_list = ['誠', '大', '豪', '翔', '抹茶']
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
                       description='sync commands')
@commands.dm_only()
async def sync(ctx):
    if ctx.message.author.id in ADMIN_LIST:
        synced = await ctx.bot.tree.sync(guild=discord.Object(ctx.message.guild))
        _ = await ctx.bot.tree.sync(guild=MY_GUILD_ID)
        await ctx.send(f"Synced {len(synced)} commands to the current guild.")
        await ctx.send(f"Synced {len(_)} commands to Killheken's friends.")


@client.event
async def on_message(message):
    if message.content.startswith("誠"):
        if "晚餐" in message.content:
            await message.channel.send(random.choice(dinner_candidtes))
        elif "還是" in message.content:
            tmp = re.sub('^誠 ?','',message.content)
            options = tmp.split('還是')
            await message.channel.send(random.choice(options))
        else:
            text_flag = 1
            for number in range(len(ID_list)):
                if (message.author.id == ID_list[number]):
                    text_flag = 0
                    await message.channel.send(Response_list[number])
                    break
            if (text_flag):
                await message.channel.send("= =")
    if message.content.startswith(emoji(
            emojis[0])) and message.author != client.user:
        for number in range(len(ID_list)):
            if (message.author.id == ID_list[number]):
                await message.channel.send(emoji(emojis[number]))
                break
    await client.process_commands(message)


@client.hybrid_command(name='update',
                       description='update the bot')
@commands.dm_only()
async def update(ctx):
    if ctx.message.author.id in ADMIN_LIST:
        await ctx.send('Updating bot....')
        _ = subprocess.call(["bash", "/home/ubuntu/update_bot.sh"])


client.run(MY_TOKEN)
