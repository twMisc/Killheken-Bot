import json
from pathlib import Path
import random
import re
import time
import math
import discord
import subprocess
import datetime
from discord.ext import commands, tasks

token = Path('token').read_text()
guild = Path('guild').read_text()

with open('ids_admin.json') as f:
    admins = json.load(f)
with open('ids.json') as f:
    ID_list = json.load(f)
with open('emojis.json') as f:
    emojis = json.load(f)
with open('dinner_candidates.json') as f:
    dinner_candidates = json.load(f)
with open('skull_count.json') as f:
    skull_count = json.load(f)

ADMIN_LIST = set(admins)
MY_TOKEN = token
MY_GUILD_ID = discord.Object(guild)

#dinner_candidates = ['拉', '咖哩', '肯', '麥', '摩', '大的']
Response_list = ['誠', '大', '豪', '翔', '抹茶']
REPLY_RATE = 0.65
intents = discord.Intents().all()
intents.presences=True
intents.guilds=True
intents.members=True
client = commands.Bot(command_prefix='$', intents=intents)
client.owner_ids = ADMIN_LIST

def emoji(emoji: dict):
    return f"<:{emoji['name']}:{emoji['id']}>"

def t_func(t):
    if t<1*60:
        output = 0.7/(1+math.exp((t-60*1)/10)) + 0.3
    else:
        output = 0.7/(1+math.exp((t-60*1)/30)) + 0.3
    return output

def get_rate():
    global t_old, t_new
    t_new = time.time()
    t_span = min(60*60, t_new-t_old)
    REPLY_RATE = t_func(t_span)
    return REPLY_RATE

t=datetime.timezone(datetime.timedelta(hours=8))
@tasks.loop(time=datetime.time(hour=19,tzinfo=t))
async def send_daily_message():
    channel_id = 461180385972322306
    channel = client.get_channel(channel_id)        
    await channel.send("哲誠晚餐吃啥")

def save_dinner_candidates(candidates_list):
    with open('dinner_candidates.json', 'w') as file:
        json.dump(candidates_list, file)

@client.event
async def on_presence_update(before,after):
    if after.id==424569079278338059:
        channel=client.get_channel(1158685682076766208)

        if after.status==discord.Status.online:
            await channel.edit(name='折成在看holo')
        elif after.status == discord.Status.idle:
            await channel.edit(name='折成在床上滑手機')

@client.event
async def on_ready():
    print(
        f'\n\nSuccessfully logged into Discord as "{client.user}"\nAwaiting user input...'
    )
    global t_old, t_new
    t_old = -10**6
    send_daily_message.start()

    await client.change_presence(status=discord.Status.online,
                                 activity=discord.Activity(
                                     type=discord.ActivityType.playing,
                                     name="我是帥哥誠"))


@client.hybrid_command(name='whatdinner', description='問帥哥誠晚餐吃啥的開關')
async def whatdinner(ctx):
    if ctx.author.id == 424569079278338059:
        await ctx.send("無法使用")
    else:
        if not send_daily_message.is_running():
            send_daily_message.start()
            await ctx.send("已啟動每天詢問。")
        else:
            send_daily_message.cancel()
            await ctx.send("已停止每天詢問。")
    

@client.hybrid_command(name='dinner', description='問帥哥誠晚餐該吃啥')
async def dinner(ctx):
    food = random.choice(dinner_candidates)
    await ctx.send(food)

@client.hybrid_command(name='list', description='列出晚餐候選')
async def dinner_list(ctx):
    str_candidates=', '.join(dinner_candidates)
    await ctx.send(str_candidates)

@client.hybrid_command(name='add', description='增加晚餐選項')
async def add_dinner(ctx,food):
    if food in dinner_candidates:
        await ctx.send(f"{food}已在晚餐選項裡")
        return
    dinner_candidates.append(food)
    save_dinner_candidates(dinner_candidates)
    await ctx.send(f"已增加 {food}")

@client.hybrid_command(name='delete', description='刪除晚餐選項')
async def delete_dinner(ctx,food):
    if food not in dinner_candidates:
        await ctx.send(f"{food}不在晚餐選項裡")
        return
    dinner_candidates.remove(food)
    save_dinner_candidates(dinner_candidates)
    await ctx.send(f"已刪除 {food}")

@client.hybrid_command(name='remain', description='問帥哥誠還有幾天本尊退伍')
async def remain(ctx):
    remain_days=(datetime.datetime(2023,7,7)-datetime.datetime.now()).days
    if remain_days>0:
        await ctx.send(f"離哲誠退伍還有{remain_days}天")
    else:
        await ctx.send("哲誠已經退伍在家爽了 <:Kreygasm:527748250900496384>")

@client.hybrid_command(name='sync',
                       description='sync commands')
@commands.is_owner()
@commands.dm_only()
async def sync(ctx):
    synced = await ctx.bot.tree.sync()
    await ctx.send(f"Synced {len(synced)} commands globally.")


@client.hybrid_command(name='update',
                       description='update the bot')
@commands.is_owner()
@commands.dm_only()
async def update(ctx):
    await ctx.send('Updating bot....')
    _ = subprocess.call(["bash", "/home/ubuntu/update_bot.sh"])


@client.hybrid_command(name='shell',
                       description='run a shell command')
@commands.is_owner()
@commands.dm_only()
async def shell(ctx, command):
    command = command.split()
    result = subprocess.run(command, capture_output=True, text=True).stdout.strip("\n")
    await ctx.send(result)


@client.hybrid_command(name='rate',
                       description='輸出帥哥誠的回應率')
async def rate(ctx):
    await ctx.send(f'`帥哥誠現在的回應率是: {get_rate():.3f}`')


@client.event
async def on_command_error(ctx, exception):
    if isinstance(exception, commands.NotOwner):
        await ctx.send("This is an admin only command.")
    elif isinstance(exception, commands.PrivateMessageOnly):
        await ctx.send("DM me this command to use it.")


@client.event
async def on_message(message):
    global REPLY_RATE, t_old, t_new, skull_count, emojis
    
    if message.author.id==424569079278338059:
        for ej,count in skull_count.items():
            if ej in message.content  :
                count=count+1
                skull_count[ej]=count
                with open('skull_count.json','w') as f:
                    json.dump(skull_count,f)
                await message.channel.send(f"哲誠已經{ej}了{count}次")

    if message.content.startswith("誠"):
        REPLY_RATE = get_rate()
        t_old = t_new

        if "在幹啥" in message.content:
            await message.channel.send("<a:owofonje:1151089087760052234>")
        elif "晚餐" in message.content:
            await message.channel.send(random.choice(dinner_candidates))
        elif "還是" in message.content:
            tmp = re.sub('^誠 ?','',re.sub('你+','我',message.content))
            options = tmp.split('還是')
            await message.channel.send(random.choice(options))
        elif random.random() < REPLY_RATE:
            for number,id in enumerate(ID_list):
                if (message.author.id == id) and len(re.sub('\s','',message.content))==1:
                    await message.channel.send(Response_list[number])
                    break
            else:
                if random.random()>0.1:
                    await message.channel.send("<a:MarineDance:984255206139248670>")
                else:
                    await message.channel.send("<:sad:913344603497828413>")                    
    if message.content.startswith(emoji(emojis[0])) and message.author != client.user: 
        REPLY_RATE = get_rate()
        
        if random.random() < REPLY_RATE:
            for number,id in enumerate(ID_list):
                if (message.author.id == id):
                    await message.channel.send(emoji(emojis[number]))
                    break
            else:
                if random.random()>0.1:
                    await message.channel.send("<a:MarineDance:984255206139248670>")
                else:
                    await message.channel.send("<:sad:913344603497828413>")
    await client.process_commands(message)

client.run(MY_TOKEN)
