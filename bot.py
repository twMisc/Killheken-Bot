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

TOKEN = Path('token').read_text().strip()
GUILD = Path('guild').read_text().strip()

with open('ids_admin.json') as f:
    ADMIN_LIST = set(json.load(f))
with open('ids.json') as f:
    ID_LIST = json.load(f)
with open('emojis.json') as f:
    EMOJIS = json.load(f)
with open('dinner_candidates.json') as f:
    DINNER_CANDIDATES = json.load(f)
with open('skull_count.json') as f:
    SKULL_COUNT = json.load(f)

MY_TOKEN = TOKEN
MY_GUILD_ID = discord.Object(GUILD)

TAIPEI_TZ = datetime.timezone(datetime.timedelta(hours=8))
RESPONSE_LIST = ['誠', '大', '豪', '翔', '抹茶']
REPLY_RATE = 0.65
HOLIDAY_MODE = False
DAILY_MESSAGE_ID = None
DAILY_CLAIMED_USERS = set()
COIN_FILE = 'coins.json'
HOLIDAY_FILE = 'holidays.json'
DAILY_EVENT_TYPE = 'weekday'
HONGBAO_FILE = 'hongbao.json'
T_OLD = -10**6
T_NEW = time.time()

intents = discord.Intents().all()
intents.presences = True
intents.guilds = True
intents.members = True
client = commands.Bot(command_prefix='$', intents=intents)
client.owner_ids = ADMIN_LIST

def get_now():
    return datetime.datetime.now(TAIPEI_TZ)

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
            description=f"## {self.title}\n{'(可多選)' if self.multiple_choice else '(單選)'}",
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
            embed.add_field(name=option, value=value, inline=False)

        return embed

def emoji(emoji_dict: dict):
    return f"<:{emoji_dict['name']}:{emoji_dict['id']}>"

def t_func(t_val):
    if t_val < 1 * 60:
        return 0.7 / (1 + math.exp((t_val - 60 * 1) / 10)) + 0.3
    return 0.7 / (1 + math.exp((t_val - 60 * 1) / 30)) + 0.3

def get_rate():
    global T_OLD, T_NEW
    T_NEW = time.time()
    t_span = min(60 * 60, T_NEW - T_OLD)
    return t_func(t_span)
    
def get_today_holiday():
    try:
        with open(HOLIDAY_FILE, 'r', encoding='utf-8') as f:
            holidays = json.load(f)
        today_str = get_now().strftime('%Y-%m-%d')
        return holidays.get(today_str)
    except:
        return None
        
@tasks.loop(time=datetime.time(hour=18, tzinfo=TAIPEI_TZ))
async def send_daily_message():
    global HOLIDAY_MODE, DAILY_MESSAGE_ID, DAILY_CLAIMED_USERS, DAILY_EVENT_TYPE
    
    is_weekday = get_now().weekday() < 5
    channel = client.get_channel(461180385972322306)
    today_holiday = get_today_holiday()
    
    if HOLIDAY_MODE or today_holiday or not is_weekday:
        DAILY_EVENT_TYPE = 'holiday'
        holiday_name = today_holiday if today_holiday else ("連假" if HOLIDAY_MODE else "週末")
        
        msg = await channel.send(
            f"大家起來 Game ({holiday_name}) 🎉 假日限定抽獎！(前 5 名)\n"
            f"請點擊下方反應選擇你的命運：\n"
            f"🤑 **大賭** (20% 中 5 幣，80% 摃龜)\n"
            f"🎲 **小賭** (50% 中 2 幣，50% 摃龜)\n"
            f"🪙 **求穩** (保底領 1 幣)"
        )
        DAILY_MESSAGE_ID = msg.id
        DAILY_CLAIMED_USERS.clear()
        
        await msg.add_reaction("🤑")
        await msg.add_reaction("🎲")
        await msg.add_reaction("🪙")
        
    else:
        DAILY_EVENT_TYPE = 'weekday'
        msg = await channel.send("大家下班 <:camperlol:1401871423332421632> (前 3 名按反應領 1 枚折成幣!)")
        DAILY_MESSAGE_ID = msg.id
        DAILY_CLAIMED_USERS.clear()

def save_dinner_candidates(candidates_list):
    with open('dinner_candidates.json', 'w') as file:
        json.dump(candidates_list, file)

@client.event
async def on_presence_update(before, after):
    if after.id == 424569079278338059:
        channel = client.get_channel(1158685682076766208)
        if after.status == discord.Status.online:
            await channel.edit(name='折成在摸魚')
        elif after.status == discord.Status.idle:
            await channel.edit(name='折成在公司滑手機')
        elif after.status == discord.Status.offline:
            await channel.edit(name='折成在努力上班')

@client.event
async def on_ready():
    print(f'\n\nSuccessfully logged into Discord as "{client.user}"\nAwaiting user input...')
    if not send_daily_message.is_running():
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
    await ctx.send(random.choice(DINNER_CANDIDATES))

@client.hybrid_command(name='list', description='列出晚餐候選')
async def dinner_list(ctx):
    await ctx.send(', '.join(DINNER_CANDIDATES))

@client.hybrid_command(name='add', description='增加晚餐選項')
async def add_dinner(ctx, food: str):
    food = food.strip()
    if food in DINNER_CANDIDATES:
        await ctx.send(f"{food}已在晚餐選項裡")
        return
    DINNER_CANDIDATES.append(food)
    save_dinner_candidates(DINNER_CANDIDATES)
    await ctx.send(f"已增加 {food}")

@client.hybrid_command(name='delete', description='刪除晚餐選項')
async def delete_dinner(ctx, food: str):
    food = food.strip()
    if food not in DINNER_CANDIDATES:
        await ctx.send(f"{food}不在晚餐選項裡")
        return
    DINNER_CANDIDATES.remove(food)
    save_dinner_candidates(DINNER_CANDIDATES)
    await ctx.send(f"已刪除 {food}")

@client.hybrid_command(name='remain', description='問老大何時日本')
async def remain(ctx):
    remain_days = (datetime.datetime(2025, 9, 6, tzinfo=TAIPEI_TZ) - get_now()).days
    if remain_days > 0:
        await ctx.send(f"離老大日本還有{remain_days}天")
    else:
        await ctx.send("老大已經在日本爽了 <:Kreygasm:527748250900496384>")

@client.hybrid_command(name='sync', description='sync commands')
@commands.is_owner()
@commands.dm_only()
async def sync(ctx):
    synced = await ctx.bot.tree.sync()
    await ctx.send(f"Synced {len(synced)} commands globally.")

@client.hybrid_command(name='update', description='update the bot')
@commands.is_owner()
@commands.dm_only()
async def update(ctx):
    await ctx.send('Updating bot....')
    _ = subprocess.call(["bash", "/home/ubuntu/update_bot.sh"])

@client.hybrid_command(name='shell', description='run a shell command')
@commands.is_owner()
@commands.dm_only()
async def shell(ctx, command):
    command = command.split()
    result = subprocess.run(command, capture_output=True, text=True).stdout.strip("\n")
    await ctx.send(result)

@client.hybrid_command(name='rate', description='輸出帥哥誠的回應率')
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
    await ctx.send(embed=view.create_embed(), view=view)

@tasks.loop(time=datetime.time(hour=10, tzinfo=TAIPEI_TZ))
async def send_morning_message():
    if get_now().weekday() < 5:
        channel = client.get_channel(461180385972322306)
        remain_days = (datetime.datetime(2025, 1, 20, tzinfo=TAIPEI_TZ) - get_now()).days
        
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
        
        await channel.send(f"{random.choice(greetings)} 離哲誠出獄還有{remain_days}天")
    
@client.hybrid_command(name='toggle_morning_message', description='開關每天早上10點的問候訊息')
async def toggle_morning_message(ctx):
    if not send_morning_message.is_running():
        send_morning_message.start()
        await ctx.send("已啟動每天早上10點的問候訊息。")
    else:
        send_morning_message.cancel()
        await ctx.send("已停止每天早上10點的問候訊息。")

@client.event
async def on_command_error(ctx, exception):
    if isinstance(exception, commands.CommandOnCooldown):
        minutes, seconds = divmod(int(exception.retry_after), 60)
        time_str = f"{minutes} 分 {seconds} 秒" if minutes > 0 else f"{seconds} 秒"
        await ctx.send(f"⏳ 賭場休息中！請等待 **{time_str}** 後再試。", ephemeral=True)
    elif isinstance(exception, commands.MissingRequiredArgument):
        await ctx.send("❌ 缺少參數！請確認指令格式。", ephemeral=True)
    elif isinstance(exception, commands.BadArgument):
        await ctx.send("❌ 參數格式錯誤！", ephemeral=True)
    elif isinstance(exception, commands.NotOwner):
        await ctx.send("This is an admin only command.")
    elif isinstance(exception, commands.PrivateMessageOnly):
        await ctx.send("DM me this command to use it.")
    else:
        print(f"Error: {exception}")

@client.hybrid_command(name='free', description='查看哲誠米蟲的天數')
async def free(ctx):
    elapsed = get_now() - datetime.datetime(2025, 8, 1, tzinfo=TAIPEI_TZ)
    await ctx.send(f"今天是哲誠當米蟲的第 {elapsed.days} 天。")

@client.hybrid_command(name='nextholiday', description='查看下一個連假')
async def nextholiday(ctx):
    try:
        with open(HOLIDAY_FILE, 'r', encoding='utf-8') as f:
            holidays = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        await ctx.send("找不到假日名單。")
        return

    today = get_now().date()
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
    global REPLY_RATE, T_OLD, T_NEW, SKULL_COUNT, EMOJIS
    
    if message.author.id == 424569079278338059:
        for ej, count in SKULL_COUNT.items():
            if ej in message.content:
                count = count + 1
                SKULL_COUNT[ej] = count
                with open('skull_count.json', 'w') as f:
                    json.dump(SKULL_COUNT, f)
                await message.channel.send(f"哲誠已經{ej}了{count}次")

    if message.content.startswith("誠"):
        REPLY_RATE = get_rate()
        T_OLD = T_NEW

        if "在幹啥" in message.content:
            await message.channel.send("<a:owofonje:1151089087760052234>")
        elif "晚餐" in message.content:
            await message.channel.send(random.choice(DINNER_CANDIDATES))
        elif "還是" in message.content:
            tmp = re.sub('^誠 ?', '', re.sub('你+', '我', message.content))
            options = tmp.split('還是')
            await message.channel.send(random.choice(options))
        elif random.random() < REPLY_RATE:
            for number, user_id in enumerate(ID_LIST):
                if (message.author.id == user_id) and len(re.sub(r'\s', '', message.content)) == 1:
                    await message.channel.send(RESPONSE_LIST[number])
                    break
            else:
                if random.random() > 0.1:
                    await message.channel.send("<a:MarineDance:984255206139248670>")
                else:
                    await message.channel.send("<:sad:913344603497828413>")
                    
    if message.content.startswith(emoji(EMOJIS[0])) and message.author != client.user: 
        REPLY_RATE = get_rate()
        
        if random.random() < REPLY_RATE:
            for number, user_id in enumerate(ID_LIST):
                if (message.author.id == user_id):
                    await message.channel.send(emoji(EMOJIS[number]))
                    break
            else:
                if random.random() > 0.1:
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
    global DAILY_MESSAGE_ID, DAILY_CLAIMED_USERS, DAILY_EVENT_TYPE

    if DAILY_MESSAGE_ID is None or payload.message_id != DAILY_MESSAGE_ID:
        return
    if payload.user_id == client.user.id:
        return
    if payload.user_id in DAILY_CLAIMED_USERS:
        return

    max_users = 3 if DAILY_EVENT_TYPE == 'weekday' else 5
    if len(DAILY_CLAIMED_USERS) >= max_users:
        return

    channel = client.get_channel(payload.channel_id)
    emoji_clicked = str(payload.emoji)

    if DAILY_EVENT_TYPE == 'holiday':
        if emoji_clicked == "🤑":
            amount = 5 if random.random() < 0.2 else 0
            choice_text = "大賭"
        elif emoji_clicked == "🎲":
            amount = 2 if random.random() < 0.5 else 0
            choice_text = "小賭"
        elif emoji_clicked == "🪙":
            amount = 1
            choice_text = "求穩"
        else:
            return
            
        DAILY_CLAIMED_USERS.add(payload.user_id)
        spots_left = max_users - len(DAILY_CLAIMED_USERS)
        
        if amount > 0:
            new_balance = update_user_coins(payload.user_id, amount)
            await channel.send(f"🎰 <@{payload.user_id}> 選擇了【{choice_text}】... 恭喜中獎！獲得 **{amount}** 枚折成幣！ (目前: {new_balance})。剩餘名額: {spots_left}")
        else:
            new_balance = update_user_coins(payload.user_id, 0)
            await channel.send(f"💨 <@{payload.user_id}> 選擇了【{choice_text}】... 沒中！一毛都沒拿到 幫QQ (目前: {new_balance})。剩餘名額: {spots_left}")

    else:
        DAILY_CLAIMED_USERS.add(payload.user_id)
        new_balance = update_user_coins(payload.user_id, 1)
        spots_left = max_users - len(DAILY_CLAIMED_USERS)
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

@client.hybrid_command(name='gamble', description='賭博：輸入金額，骰出 >50 翻倍，否則歸零')
@commands.cooldown(1, 3600, commands.BucketType.user)
async def gamble(ctx, amount: int):
    if amount <= 0:
        await ctx.send("❌ 賭注必須大於 0")
        ctx.command.reset_cooldown(ctx)
        return
        
    try:
        with open(COIN_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
        
    current_balance = data.get(str(ctx.author.id), 0)
    
    if amount > current_balance:
        await ctx.send(f"❌ 你的錢不夠！你只有 {current_balance} 枚折成幣。")
        ctx.command.reset_cooldown(ctx)
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
    today_str = get_now().strftime('%Y-%m-%d')

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
