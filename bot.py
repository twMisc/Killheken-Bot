import json
from pathlib import Path
import random
import discord
from discord.ext import commands

token = Path('token').read_text()
guild = Path('guild').read_text()
boss_id = Path('boss_id').read_text()
albert_id = Path('albert_id').read_text()
zenox_id = Path('zenox_id').read_text()
with open('emojis.json') as f:
    emojis = json.load(f)

MY_TOKEN = token
MY_GUILD_ID = discord.Object(guild)
BOSS_ID = int(boss_id)
ALBERT_ID = int(albert_id)
ZENOX_ID = int(zenox_id)

dinner_candidtes = ['拉', '咖哩', '肯', '麥', '摩', '大的']
ID_list = [BOSS_ID, ALBERT_ID, ZENOX_ID]
Response_list = ['大', '豪', '翔']
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
            text_flag = 1
            for number in range(len(ID_list)):
                if (message.author.id == ID_list[number]):
                    text_flag = 0
                    await message.channel.send(Response_list[number])
            if (text_flag):
                await message.channel.send("= =")
    if message.content.startswith(emoji(
            emojis[0])) and message.author != client.user:
        for number in range(len(ID_list)):
            if (message.author.id == ID_list[number]):
                await message.channel.send(emoji(emojis[number + 1]))
    await client.process_commands(message)


client.run(MY_TOKEN)
