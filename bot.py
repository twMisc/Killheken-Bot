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
from discord.ui import Button, View
import requests
from bardapi import BardCookies, SESSION_HEADERS

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
# with open('bard_cookie.json') as f:
#     cookie_dict = json.load(f)

# Bard with reusable session which contain mutiple cookie values
# session = requests.Session()
# session.cookies.set("__Secure-1PSID", cookie_dict['__Secure-1PSID'])
# session.cookies.set("__Secure-1PSIDTS", cookie_dict['__Secure-1PSIDTS'])
# session.headers = SESSION_HEADERS
# bard = BardCookies(cookie_dict=cookie_dict, session=session, conversation_id='c_2e5b34f1bae27158')

ADMIN_LIST = set(admins)
MY_TOKEN = token
MY_GUILD_ID = discord.Object(guild)

#dinner_candidates = ['拉', '咖哩', '肯', '麥', '摩', '大的']
Response_list = ['誠', '大', '豪', '翔', '抹茶']
REPLY_RATE = 0.65
HOLIDAY_MODE = False
DAILY_MESSAGE_ID = None
DAILY_CLAIMED_USERS = set()
COIN_FILE = 'coins.json'
HOLIDAY_FILE = 'holidays.json'
intents = discord.Intents().all()
intents.presences=True
intents.guilds=True
intents.members=True
client = commands.Bot(command_prefix='$', intents=intents)
client.owner_ids = ADMIN_LIST

class PollView(View):
    def __init__(self, title, options, multiple_choice=False):
        super().__init__(timeout=None)
        self.title = title
        self.votes = {option: 0 for option in options}
        self.user_votes = {}
        self.total_votes = 0
        self.multiple_choice = multiple_choice

        for option in options:
            button = Button(label=option, style=discord.ButtonStyle.primary)
            button.callback = self.create_vote_callback(option)
            self.add_item(button)

        update_button = Button(label="更新", style=discord.ButtonStyle.secondary)
        update_button.callback = self.update_poll
        self.add_item(update_button)

        end_button = Button(label="結束投票", style=discord.ButtonStyle.danger)
        end_button.callback = self.end_poll
        self.add_item(end_button)

    def create_vote_callback(self, option):
        async def callback(interaction: discord.Interaction):
            user_id = interaction.user.id
            
            if self.multiple_choice:
                if user_id not in self.user_votes:
                    self.user_votes[user_id] = set()
                
                if option in self.user_votes[user_id]:
                    self.user_votes[user_id].remove(option)
                    self.votes[option] -= 1
                    self.total_votes -= 1
                    await interaction.response.send_message(f"已取消選擇: {option}", ephemeral=True)
                else:
                    self.user_votes[user_id].add(option)
                    self.votes[option] += 1
                    self.total_votes += 1
                    await interaction.response.send_message(f"已選擇: {option}", ephemeral=True)
            else:
                if user_id in self.user_votes:
                    if self.user_votes[user_id] == option:
                        self.votes[option] -= 1
                        del self.user_votes[user_id]
                        self.total_votes -= 1
                        await interaction.response.send_message("已取消投票", ephemeral=True)
                    else:
                        previous_option = self.user_votes[user_id]
                        self.votes[previous_option] -= 1
                        self.votes[option] += 1
                        self.user_votes[user_id] = option
                        await interaction.response.send_message(f"已更改投票為: {option}", ephemeral=True)
                else:
                    self.votes[option] += 1
                    self.user_votes[user_id] = option
                    self.total_votes += 1
                    await interaction.response.send_message(f"已投票: {option}", ephemeral=True)

            await interaction.message.edit(embed=self.create_embed())
        return callback

    async def update_poll(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.create_embed())

    async def end_poll(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    def create_embed(self):
        embed = discord.Embed(
            title="📊 投票",
            description=f"## {self.title}\n{'(可多選)' if self.multiple_choice else '(單選)'}",  # 使用 Markdown 標題語法
            color=discord.Color.blue()
        )

        total_voters = len(self.user_votes)
        embed.add_field(
            name=f"總投票數: {self.total_votes}",
            value=f"參與人數: {total_voters}",
            inline=False
        )

        for option, count in self.votes.items():
            percentage = (count / self.total_votes * 100) if self.total_votes > 0 else 0
            bar_length = 20
            filled = int((percentage / 100) * bar_length)
            
            bar = '─' * filled + ' ' * (bar_length - filled)
            
            value = f"{count}票 ({percentage:.1f}%)\n```{bar}```"
            
            embed.add_field(
                name=option,
                value=value,
                inline=False
            )

        return embed

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
    
def get_today_holiday():
    try:
        with open(HOLIDAY_FILE, 'r', encoding='utf-8') as f:
            holidays = json.load(f)
        today_str = datetime.datetime.now(t).strftime('%Y-%m-%d')
        return holidays.get(today_str)
    except:
        return None
        
t=datetime.timezone(datetime.timedelta(hours=8))
@tasks.loop(time=datetime.time(hour=18,tzinfo=t))
async def send_daily_message():
    global HOLIDAY_MODE, DAILY_MESSAGE_ID, DAILY_CLAIMED_USERS
    is_weekday = datetime.datetime.today().astimezone(t).weekday() < 5
    channel_id = 461180385972322306
    channel = client.get_channel(channel_id)   

    today_holiday = get_today_holiday()
    
    if HOLIDAY_MODE:
        await channel.send("大家起來 Game")
    elif today_holiday:
        await channel.send(f"大家起來 Game")
    elif is_weekday:
        msg = await channel.send("大家下班 <:camperlol:1401871423332421632> (前3名按反應領折成幣!)")
        DAILY_MESSAGE_ID = msg.id
        DAILY_CLAIMED_USERS.clear()
    else:
        await channel.send("大家晚餐吃啥")

def save_dinner_candidates(candidates_list):
    with open('dinner_candidates.json', 'w') as file:
        json.dump(candidates_list, file)

@client.event
async def on_presence_update(before,after):
    if after.id==424569079278338059:
        channel=client.get_channel(1158685682076766208)

        if after.status==discord.Status.online:
            await channel.edit(name='折成在摸魚')
        elif after.status == discord.Status.idle:
            await channel.edit(name='折成在公司滑手機')
        elif after.status==discord.Status.offline:
            await channel.edit(name='折成在努力上班')

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

@client.hybrid_command(name='remain', description='問老大何時日本')
async def remain(ctx):
    remain_days=(datetime.datetime(2025,9,6)-datetime.datetime.now()).days
    if remain_days>0:
        await ctx.send(f"離老大日本還有{remain_days}天")
    else:
        await ctx.send("老大已經在日本爽了 <:Kreygasm:527748250900496384>")

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

@client.hybrid_command(name='poll', description='建立一個投票')
async def poll(ctx, title: str, options: str, multiple_choice: bool = False):
    option_list = [opt.strip() for opt in options.split(',')]
    
    if len(option_list) < 2:
        await ctx.send("請提供至少兩個選項。")
        return
    
    if len(option_list) != len(set(option_list)):
        await ctx.send("選項不能重複。")
        return
        
    view = PollView(title, option_list, multiple_choice)
    embed = view.create_embed()
    await ctx.send(embed=embed, view=view)

@tasks.loop(time=datetime.time(hour=10, tzinfo=t))
async def send_morning_message():
    is_weekday = datetime.datetime.today().astimezone(t).weekday() < 5
    
    if is_weekday:
        channel_id = 461180385972322306
        channel = client.get_channel(channel_id)
        
        remain_days = (datetime.datetime(2025, 1, 20) - datetime.datetime.now()).days
        
        greetings = [
            "早安，大家！哲誠祝你們有個美好的一天！",
            "早上好！哲誠今天也要加油哦！",
            "早安！哲誠祝你今天心情愉快！",
            "新的一天，新的開始！哲誠說早安！",
            "早安！哲誠今天也要充滿活力地面對挑戰！",
            "哲誠提醒：早安，記得吃早餐哦！",
            "哲誠在這裡，祝你有個愉快的早晨！",
            "哲誠說：新的一天，新的希望，早安！",
            "哲誠：早安，希望今天的你充滿能量！",
            "哲誠祝福：早安，願你今天一切順利！",
            "大家工作加油!"
        ]
        
        greeting_message = random.choice(greetings)
        
        await channel.send(f"{greeting_message} 離哲誠出獄還有{remain_days}天")
    
@client.hybrid_command(name='toggle_morning_message', description='開關每天早上10點的問候訊息')
async def toggle_morning_message(ctx):
    if not send_morning_message.is_running():
        send_morning_message.start()
        await ctx.send("已啟動每天早上10點的問候訊息。")
    else:
        send_morning_message.cancel()
        await ctx.send("已停止每天早上10點的問候訊息。")

# @client.command(name='chat', description='Chat with the bot. (Bard API)')
# async def chat(ctx, *, input_text):
#     response = bard.get_answer(input_text)['content']
#     await ctx.send(response)
    
# @client.tree.command(name='chat', description='Chat with the bot. (Bard API)')
# async def chat2(ctx, input_text: str):
#     await ctx.response.defer()
#     response = bard.get_answer(input_text)['content']
#     await ctx.followup.send(response)

@client.event
async def on_command_error(ctx, exception):
    if isinstance(exception, commands.CommandOnCooldown):
        # 將總秒數換算成分鐘與秒數
        minutes, seconds = divmod(int(exception.retry_after), 60)
        time_str = f"{minutes} 分 {seconds} 秒" if minutes > 0 else f"{seconds} 秒"
        
        # ephemeral=True 代表這則訊息只有觸發指令的人看得到，不會洗頻
        await ctx.send(f"⏳ 賭場休息中！請等待 **{time_str}** 後再試。", ephemeral=True)
        
    elif isinstance(exception, commands.NotOwner):
        await ctx.send("This is an admin only command.")
    elif isinstance(exception, commands.PrivateMessageOnly):
        await ctx.send("DM me this command to use it.")
    else:
        print(f"Error: {exception}")

@client.hybrid_command(name='free', description='查看哲誠米蟲的天數')
async def free(ctx):
    free_date = datetime.datetime(2025, 8, 1).astimezone(t)
    today = datetime.datetime.now().astimezone(t)
    elapsed = today - free_date
    await ctx.send(f"今天是哲誠當米蟲的第 {elapsed.days} 天。")

@client.hybrid_command(name='nextholiday', description='查看下一個連假')
async def nextholiday(ctx):
    try:
        with open(HOLIDAY_FILE, 'r', encoding='utf-8') as f:
            holidays = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        await ctx.send("找不到假日名單。")
        return

    today = datetime.datetime.now(t).date()
    today_str = today.strftime('%Y-%m-%d')
    
    response_lines = []
    
    today_holiday_name = holidays.get(today_str)
    
    if today_holiday_name:
        response_lines.append(f"🎉 我們現在正在放 **{today_holiday_name}**！好好享受！\n")
        
    next_holiday_date_str = None
    next_holiday_name = None
    
    for date_str, name in holidays.items():
        if date_str > today_str:
            if today_holiday_name and name == today_holiday_name:
                continue
                
            next_holiday_date_str = date_str
            next_holiday_name = name
            break
            
    if next_holiday_date_str:
        next_date = datetime.datetime.strptime(next_holiday_date_str, '%Y-%m-%d').date()
        days_left = (next_date - today).days
        
        response_lines.append(f"📅 下一個連假是 **{next_holiday_name}** ({next_holiday_date_str})")
        response_lines.append(f"⏳ 距離現在還有 **{days_left}** 天")
    else:
        if not today_holiday_name:
            response_lines.append("今年看起來已經沒有連假了...")
            
    await ctx.send("\n".join(response_lines))
    
@client.hybrid_command(name='toggle_holiday', description='手動強制開關假日模式')
async def toggle_holiday(ctx):
    global HOLIDAY_MODE
    HOLIDAY_MODE = not HOLIDAY_MODE
    status = "開啟" if HOLIDAY_MODE else "關閉"
    await ctx.send(f"手動假日模式已{status}。")

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

def update_user_coins(user_id, amount=1):
    try:
        with open(COIN_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    
    uid_str = str(user_id)
    new_balance = data.get(uid_str, 0) + amount
    data[uid_str] = new_balance
    
    with open(COIN_FILE, 'w') as f:
        json.dump(data, f)
        
    return new_balance

@client.event
async def on_raw_reaction_add(payload):
    global DAILY_MESSAGE_ID, DAILY_CLAIMED_USERS

    if DAILY_MESSAGE_ID is None or payload.message_id != DAILY_MESSAGE_ID:
        return

    if payload.user_id == client.user.id:
        return

    if payload.user_id in DAILY_CLAIMED_USERS:
        return

    if len(DAILY_CLAIMED_USERS) >= 3:
        return

    DAILY_CLAIMED_USERS.add(payload.user_id)
    new_balance = update_user_coins(payload.user_id)
    spots_left = 3 - len(DAILY_CLAIMED_USERS)
    
    channel = client.get_channel(payload.channel_id)
    await channel.send(f"💰 <@{payload.user_id}> 下班打卡成功！獲得 1 折成幣 (目前: {new_balance})。剩餘名額: {spots_left}")

@client.hybrid_command(name='wallet', description='查看你的折成幣數量')
async def wallet(ctx):
    try:
        with open(COIN_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    
    balance = data.get(str(ctx.author.id), 0)
    await ctx.send(f"<@{ctx.author.id}> 你目前擁有 {balance} 枚折成幣 💰")
    
# --- 經濟與娛樂系統 ---

HONGBAO_FILE = 'hongbao.json'

@client.hybrid_command(name='gamble', description='賭博：輸入金額，骰出 >50 翻倍，否則歸零')
@commands.cooldown(1, 3600, commands.BucketType.user)  # 👈 1 代表次數，3600 代表秒數 (1小時)
async def gamble(ctx, amount: int):
    if amount <= 0:
        await ctx.send("❌ 賭注必須大於 0")
        return
        
    try:
        with open(COIN_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
        
    current_balance = data.get(str(ctx.author.id), 0)
    
    if amount > current_balance:
        await ctx.send(f"❌ 你的錢不夠！你只有 {current_balance} 枚折成幣。")
        return
        
    roll = random.randint(1, 100)
    if roll > 50:
        new_balance = update_user_coins(ctx.author.id, amount)
        await ctx.send(f"🎲 你骰出了 **{roll}**！贏了！獲得 {amount} 枚折成幣 (目前: {new_balance}) 🎉")
    else:
        new_balance = update_user_coins(ctx.author.id, -amount)
        await ctx.send(f"🎲 你骰出了 **{roll}**... 輸光光 💸 (目前: {new_balance})")
        
@client.hybrid_command(name='rich', description='查看折成幣富豪榜 (前 5 名)')
async def rich(ctx):
    try:
        with open(COIN_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        await ctx.send("目前還沒有人有錢...")
        return
    
    sorted_users = sorted(data.items(), key=lambda item: item[1], reverse=True)
    top_5 = sorted_users[:5]
    
    if not top_5:
        await ctx.send("目前還沒有人有錢...")
        return
    
    embed = discord.Embed(title="🏆 折成幣富豪榜", color=discord.Color.gold())
    
    for rank, (uid, coins) in enumerate(top_5, 1):
        user = client.get_user(int(uid))
        name = user.display_name if user else f"User {uid}"
        embed.add_field(name=f"第 {rank} 名", value=f"**{name}**: {coins} 幣", inline=False)
        
    await ctx.send(embed=embed)

@client.hybrid_command(name='hongbao', description='🧧 春節限定：每天領取一次折成幣紅包！')
async def hongbao(ctx):
    today_holiday = get_today_holiday()
    if today_holiday != "春節連假":
        await ctx.send("❌ 現在不是春節連假期間，沒有紅包可以領喔！")
        return

    user_id = ctx.author.id
    today_str = datetime.datetime.now(t).strftime('%Y-%m-%d')

    try:
        with open(HONGBAO_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"date": "", "claimed_users": []}

    if data.get("date") != today_str:
        data = {"date": today_str, "claimed_users": []}

    if user_id in data["claimed_users"]:
        await ctx.send("🧧 你今天已經領過紅包囉！明天再來吧！")
        return

    amount = random.choices(
        population=[1, 2, 3, 5, 8, 18], 
        weights=[30, 30, 20, 10, 8, 2], 
        k=1
    )[0]

    data["claimed_users"].append(user_id)
    with open(HONGBAO_FILE, 'w') as f:
        json.dump(data, f)

    new_balance = update_user_coins(user_id, amount)
    await ctx.send(f"🧨 **新年快樂！** <@{user_id}> 打開了紅包，獲得了 **{amount}** 枚折成幣！ (目前總計: {new_balance} 幣) 🧧")
    
client.run(MY_TOKEN)
