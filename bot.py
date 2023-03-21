import random
import discord
from discord.ext import commands

MY_TOKEN = 'BOT_TOKEN'

intents = discord.Intents().all()
bot = commands.Bot(command_prefix='$', intents=intents)


@bot.event
async def on_ready():
    print(
        f'\n\nSuccessfully logged into Discord as "{bot.user}"\nAwaiting user input...'
    )
    await bot.change_presence(status=discord.Status.online,
                              activity=discord.Activity(
                                  type=discord.ActivityType.playing,
                                  name="all by myself..."))


@bot.hybrid_command()
async def dinner(ctx):
    food_string = ['拉', '咖哩', '肯', '麥', '摩', '大的']
    food = random.choice(food_string)
    await ctx.send(food)


bot.run(MY_TOKEN)
