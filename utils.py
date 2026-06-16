import json
import asyncio
import datetime
import random
import functools

# ========== 常數與檔案路徑 ==========
TAIPEI_TZ = datetime.timezone(datetime.timedelta(hours=8))
COIN_FILE = 'coins.json'
HOLIDAY_FILE = 'holidays.json'
HONGBAO_FILE = 'hongbao.json'
CHECKIN_FILE = 'checkin.json'
STEAL_FILE = 'steal.json'
GAMBLE_STATS_FILE = 'gamble_stats.json'
FIXED_DEPOSIT_FILE = 'fixed_deposit.json'
LOTTO_FILE = 'lotto.json'
INVENTORY_FILE = 'inventory.json'
BUFFS_FILE = 'active_buffs.json'

# ========== 經濟系統參數 ==========
FIXED_DEPOSIT_INTEREST = 0.05
FIXED_DEPOSIT_RATIO_LIMIT = 0.3

ECONOMY_SCALE_BASE = 100
TIER_THRESHOLDS = (0.20, 0.80, 2.00)
TIER_MULTIPLIERS = (3.0, 1.5, 1.0, 0.8)
TIER_LABELS = ('赤貧加成', '勞工加成', '標準', '富豪減成')

LOTTO_MAX_NUM = 100         
LOTTO_PRICE = 5            
LOTTO_TO_POT = 5          
LOTTO_MAX_TICKETS = 3

# ========== 共用非同步鎖 ==========
data_lock = asyncio.Lock()

def with_lock(func):
    """確保檔案 I/O 不會發生資源競用的 Decorator"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        async with data_lock:
            return await func(*args, **kwargs)
    return wrapper

# ========== 共用輔助函式 ==========
def get_now():
    return datetime.datetime.now(TAIPEI_TZ)

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

def get_median_wealth() -> float:
    try:
        with open(COIN_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return float(ECONOMY_SCALE_BASE)

    all_balances = list(data.values())
    if len(all_balances) < 3:
        return float(ECONOMY_SCALE_BASE)

    non_zero = [b for b in all_balances if b > 0]
    if len(non_zero) < len(all_balances) / 2:
        if len(non_zero) < 3:
            return float(ECONOMY_SCALE_BASE)
        balances = sorted(non_zero)
    else:
        balances = sorted(all_balances)

    n = len(balances)
    mid = n // 2
    median = (balances[mid - 1] + balances[mid]) / 2.0 if n % 2 == 0 else float(balances[mid])
    return max(median, float(ECONOMY_SCALE_BASE))

def get_wealth_tier(user_balance: int, median: float) -> int:
    ratio = user_balance / median if median > 0 else 1.0
    if ratio < TIER_THRESHOLDS[0]:
        return 0
    elif ratio < TIER_THRESHOLDS[1]:
        return 1
    elif ratio <= TIER_THRESHOLDS[2]:
        return 2
    return 3

def calc_dynamic_reward(base_amount: int, user_balance: int) -> int:
    median = get_median_wealth()
    economy_scale = max(1.0, median / ECONOMY_SCALE_BASE)
    tier = get_wealth_tier(user_balance, median)
    rng = random.uniform(0.8, 1.2)
    return max(1, round(base_amount * economy_scale * TIER_MULTIPLIERS[tier] * rng))

def get_lotto_data():
    try:
        with open(LOTTO_FILE, 'r') as f:
            data = json.load(f)
            if "pot" not in data: data["pot"] = 0
            if "tickets" not in data: data["tickets"] = {}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"pot": 0, "tickets": {}}

def save_lotto_data(data):
    with open(LOTTO_FILE, 'w') as f:
        json.dump(data, f)

def update_gamble_stats(user_id, amount, is_win):
    try:
        with open(GAMBLE_STATS_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
        
    uid_str = str(user_id)
    if uid_str not in data:
        data[uid_str] = {"games_played": 0, "games_won": 0, "net_profit": 0}
        
    data[uid_str]["games_played"] += 1
    if is_win:
        data[uid_str]["games_won"] += 1
    data[uid_str]["net_profit"] += amount
    
    with open(GAMBLE_STATS_FILE, 'w') as f:
        json.dump(data, f)

def get_inventory(user_id):
    try:
        with open(INVENTORY_FILE, 'r') as f:
            data = json.load(f)
            user_inv = data.get(str(user_id), {})
            if not isinstance(user_inv, dict):
                user_inv = {}
            user_inv.setdefault("passives", {})
            user_inv.setdefault("consumables", {})
            return user_inv
    except (FileNotFoundError, json.JSONDecodeError):
        return {"passives": {}, "consumables": {}}

def save_inventory(user_id, user_inv):
    try:
        with open(INVENTORY_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data[str(user_id)] = user_inv
    with open(INVENTORY_FILE, 'w') as f:
        json.dump(data, f)

def get_buffs(user_id):
    try:
        with open(BUFFS_FILE, 'r') as f:
            data = json.load(f)
            return data.get(str(user_id), {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_buffs(user_id, user_buffs):
    try:
        with open(BUFFS_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data[str(user_id)] = user_buffs
    with open(BUFFS_FILE, 'w') as f:
        json.dump(data, f)
