import discord
from discord.ext import commands
import random
import json
import os
import utils

# ---------- 卡池結構定義 ----------
S_CARDS = {
    "SSR": ["ssr_gamble_refund", "ssr_steal_buff", "ssr_wealth_bypass"],
    "SR": ["sr_steal_shield", "sr_tax_audit", "sr_robin_hood", "sr_gamble_insurance", "sr_lotto_boost"],
    "R": ["r_coin_bag", "r_gamble_ban", "r_purify_debuff", "r_emoji_curse", "r_fake_steal"]
}

P_CARDS = {
    "SSR": ["p_101", "p_102"],
    "SR": ["p_201", "p_202"],
    "R": ["p_301", "p_302", "p_303"]
}

# 基礎 S 卡顯示名稱
ITEM_NAMES = {
    "ssr_gamble_refund": "🌟 賭博止損 (被動)",
    "ssr_steal_buff": "🌟 神偷體質 (被動)",
    "ssr_wealth_bypass": "🌟 階級豁免 (被動)",
    "sr_steal_shield": "🛡️ 次數型護盾",
    "sr_tax_audit": "🔥 強制查水表",
    "sr_robin_hood": "🏹 劫富濟貧",
    "sr_gamble_insurance": "📑 賭場保險",
    "sr_lotto_boost": "🎫 破例下注",
    "r_coin_bag": "💰 現金包",
    "r_gamble_ban": "🚫 禁賭令",
    "r_purify_debuff": "✨ 撤銷公文",
    "r_emoji_curse": "👀 主管的凝視",
    "r_fake_steal": "👻 幻覺驚嚇"
}

# 嘗試從本機載入機密的 P 卡名稱，若無檔案則使用預設顯示
try:
    with open('p_cards.json', 'r', encoding='utf-8') as f:
        p_card_names = json.load(f)
        ITEM_NAMES.update(p_card_names)
except FileNotFoundError:
    print("Warning: p_cards.json not found. P-cards will show default names.")


class GachaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def roll_gacha(self, is_vip, guarantee_sr=False):
        """執行一次抽卡邏輯，回傳抽中的物品 ID 與是否為 P 卡"""
        roll = random.random()
        if is_vip:
            ssr_rate, sr_rate = 0.07, 0.20 # 尊爵池機率
        else:
            ssr_rate, sr_rate = 0.05, 0.17 # 一般池機率
            
        if guarantee_sr:
            if roll < ssr_rate: rarity = "SSR"
            else: rarity = "SR"
        else:
            if roll < ssr_rate: rarity = "SSR"
            elif roll < ssr_rate + sr_rate: rarity = "SR"
            else: rarity = "R"

        # 學マス比例：P卡 40%, S卡 60%
        is_p_card = random.random() < 0.40
        pool = P_CARDS if is_p_card else S_CARDS
        
        item = random.choice(pool[rarity])
        return item, rarity, is_p_card

    @commands.hybrid_command(name='gacha', description='進行抽卡！(支援 1 或 10 連抽)')
    @utils.with_lock
    async def gacha(self, ctx, times: int = 1):
        if times not in [1, 10]:
            await ctx.send("❌ 只能選擇單抽 (1) 或是十連抽 (10)！", ephemeral=True)
            return

        user_id = ctx.author.id
        current_balance = utils.update_user_coins(user_id, 0)
        median = utils.get_median_wealth()
        tier = utils.get_wealth_tier(current_balance, median)

        if tier == 0:   price_per_pull = 1000
        elif tier == 1: price_per_pull = 5000
        elif tier == 2: price_per_pull = 10000
        else:           price_per_pull = 50000

        total_cost = price_per_pull * times
        if current_balance < total_cost:
            await ctx.send(f"❌ 餘額不足！你需要 {total_cost} 幣才能抽卡。你的階級是 {utils.TIER_LABELS[tier]} (單抽價格: {price_per_pull})", ephemeral=True)
            return

        utils.update_user_coins(user_id, -total_cost)
        is_vip = (tier == 3)
        inventory = utils.get_inventory(user_id)
        
        results = []
        files_to_send = [] # 準備用來裝迷因圖的清單
        
        for i in range(times):
            guarantee = (times == 10 and i == 9 and not any("SR" in r[1] or "SSR" in r[1] for r in results))
            item, rarity, is_p_card = self.roll_gacha(is_vip, guarantee_sr=guarantee)
            results.append((item, rarity, is_p_card))

            if is_p_card:
                inventory["passives"][item] = 1 # 成就只要獲得就紀錄為 1
                
                # 如果是 SSR 或 SR 的 P 卡，準備附加圖片
                if rarity in ["SSR", "SR"]:
                    image_path = f"images/{item}.webp" # 根據代號抓圖檔，例如 images/p_101.webp
                    if os.path.exists(image_path):
                        files_to_send.append(discord.File(image_path, filename=f"{item}.webp"))
            else:
                if rarity == "SSR":
                    current_level = inventory["passives"].get(item, 0)
                    if current_level < 5:
                        inventory["passives"][item] = current_level + 1
                    else:
                        utils.update_user_coins(user_id, 50000)
                else:
                    inventory["consumables"][item] = inventory["consumables"].get(item, 0) + 1

        utils.save_inventory(user_id, inventory)

        # 組合輸出訊息
        embed = discord.Embed(title="🎰 折成轉蛋機 結算", description=f"消費: **{total_cost}** 幣\n卡池: **{'尊爵黑金池' if is_vip else '一般標準池'}**", color=discord.Color.gold() if is_vip else discord.Color.blue())
        
        result_text = ""
        for item, rarity, is_p_card in results:
            prefix = "[P卡]" if is_p_card else "[S卡]"
            # 若字典抓不到名稱，代表 P 卡名稱檔案缺失或這張圖沒被解鎖
            name = ITEM_NAMES.get(item, "🔒 [??? 未知成就 ???]")
            
            if rarity == "SSR": result_text += f"✨ **{rarity}** {prefix} {name} ✨\n"
            elif rarity == "SR": result_text += f"⭐ **{rarity}** {prefix} {name}\n"
            else: result_text += f"⚪ **{rarity}** {prefix} {name}\n"
            
        embed.add_field(name="抽卡結果", value=result_text, inline=False)
        
        # 結算發送：同時丟出 Embed 與剛剛打包好的所有迷因圖
        if files_to_send:
            await ctx.send(embed=embed, files=files_to_send)
        else:
            await ctx.send(embed=embed)

    @commands.hybrid_command(name='inventory', description='查看你的收集品與道具背包')
    async def inventory(self, ctx):
        inventory = utils.get_inventory(ctx.author.id)
        embed = discord.Embed(title=f"🎒 <@{ctx.author.id}> 的背包", color=discord.Color.green())
        
        # 分離出 S 卡被動與 P 卡成就
        passive_s_text = ""
        achievement_p_text = ""
        
        for item, level in inventory["passives"].items():
            # inventory["passives"] contains both S-card passives (ssr_*) and P-card achievements (p_*); split them below.
            if item in P_CARDS["SSR"] or item in P_CARDS["SR"] or item in P_CARDS["R"]:
                achievement_p_text += f"🏆 **{ITEM_NAMES.get(item, '🔒 [未知]')}**\n"
            else:
                passive_s_text += f"**{ITEM_NAMES.get(item, item)}** (Lv.{level}/5)\n"
                
        if not passive_s_text: passive_s_text = "空空如也..."
        if not achievement_p_text: achievement_p_text = "空空如也..."
        
        embed.add_field(name="🌟 永久被動 (S卡)", value=passive_s_text, inline=False)
        embed.add_field(name="🏆 成就徽章 (P卡)", value=achievement_p_text, inline=False)
        
        consumable_text = ""
        for item, count in inventory["consumables"].items():
            if count > 0:
                consumable_text += f"**{ITEM_NAMES.get(item, item)}** x {count}\n"
        if not consumable_text: consumable_text = "空空如也..."
        embed.add_field(name="📦 消耗道具 (SR/R)", value=consumable_text, inline=False)
        
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name='use', description='使用背包裡的消耗型 S 卡道具')
    @utils.with_lock
    async def use_item(self, ctx, item_code: str, target: discord.Member = None):
        user_id = ctx.author.id
        inventory = utils.get_inventory(user_id)
        
        if inventory["consumables"].get(item_code, 0) <= 0:
            await ctx.send(f"❌ 你沒有這個道具：`{item_code}`！(請使用 /inventory 查看正確代號)", ephemeral=True)
            return

        today_str = utils.get_now().strftime('%Y-%m-%d')
        buffs = utils.get_buffs(user_id)

        # ---------------- R卡: 經濟與惡搞 ----------------
        if item_code == "r_coin_bag":
            reward = random.randint(5000, 10000)
            utils.update_user_coins(user_id, reward)
            await ctx.send(f"💰 你打開了 `現金包`，獲得了 **{reward}** 枚折成幣！")

        elif item_code == "r_gamble_ban":
            if not target: return await ctx.send("❌ 此道具需指定 @對象！", ephemeral=True)
            target_buffs = utils.get_buffs(target.id)
            target_buffs["gamble_ban_until"] = utils.get_now().timestamp() + 3600
            utils.save_buffs(target.id, target_buffs)
            await ctx.send(f"🚫 你對 {target.mention} 發布了 `禁賭令`！他接下來 1 小時內被禁止進入賭場。")

        elif item_code == "r_purify_debuff":
            buffs["gamble_ban_until"] = 0
            buffs["emoji_curse_stacks"] = 0
            utils.save_buffs(user_id, buffs)
            await ctx.send("✨ 你使用了 `撤銷公文`，清除了身上所有的負面狀態！")

        elif item_code == "r_emoji_curse":
            if not target: return await ctx.send("❌ 此道具需指定 @對象！", ephemeral=True)
            target_buffs = utils.get_buffs(target.id)
            target_buffs["emoji_curse_stacks"] = 3
            utils.save_buffs(target.id, target_buffs)
            await ctx.send(f"👀 你對 {target.mention} 發動了 `主管的凝視`！他接下來的 3 句話都會被密切關注...")

        elif item_code == "r_fake_steal":
            if not target: return await ctx.send("❌ 此道具需指定 @對象！", ephemeral=True)
            target_balance = utils.update_user_coins(target.id, 0)
            fake_amount = int(target_balance * 0.5)
            await ctx.send(f"🥷 <@{user_id}> 趁著 {target.mention} 不注意，偷偷摸走了 **{fake_amount}** 枚折成幣！(目前總計: 99999999 幣)")

        # ---------------- SR卡: 戰術道具 ----------------
        elif item_code == "sr_steal_shield":
            current_stacks = buffs.get("steal_shield_stacks", 0)
            buffs["steal_shield_stacks"] = min(current_stacks + 1, 3)
            utils.save_buffs(user_id, buffs)
            await ctx.send(f"🛡️ 你裝備了 `次數型護盾`！目前護盾層數: {buffs['steal_shield_stacks']}/3")

        elif item_code == "sr_tax_audit":
            if not target:
                return await ctx.send("❌ 此道具需指定 @對象！", ephemeral=True)

            audit_key = f"tax_audit_date_{target.id}"
            if buffs.get(audit_key) == today_str:
                return await ctx.send("❌ 你今天已經對這個人發動過查水表了！明天的公文還沒批下來。", ephemeral=True)
            
            target_balance = utils.update_user_coins(target.id, 0)
            damage = int(target_balance * 0.02)
            if damage > 0:
                utils.update_user_coins(target.id, -damage)

            buffs[audit_key] = today_str
            utils.save_buffs(user_id, buffs)
            await ctx.send(f"🔥 國稅局出動！{target.mention} 遭到了 `強制查水表`，**{damage}** 枚折成幣瞬間被依法銷毀！")

        elif item_code == "sr_robin_hood":
            # 找出首富
            with open(utils.COIN_FILE, 'r') as f:
                all_coins = json.load(f)
            richest_id = max(all_coins, key=all_coins.get)
            richest_balance = all_coins[richest_id]
            
            if random.random() < 0.30:
                amount = max(1, int(richest_balance * 0.01))
                utils.update_user_coins(int(richest_id), -amount)
                utils.update_user_coins(user_id, amount)
                await ctx.send(f"🏹 義賊現身！你成功對首富 <@{richest_id}> 發動了 `劫富濟貧`，強行奪走 **{amount}** 幣！")
            else:
                await ctx.send(f"💨 劫富濟貧失敗！首富 <@{richest_id}> 的保鑣把你趕了出去。")

        elif item_code == "sr_gamble_insurance":
            buffs["gamble_insurance"] = 1
            utils.save_buffs(user_id, buffs)
            await ctx.send("📑 你簽署了 `賭場保險`！下一次輸錢時，最高可獲賠 1,000,000 幣。")

        elif item_code == "sr_lotto_boost":
            buffs["lotto_boost_date"] = today_str
            utils.save_buffs(user_id, buffs)
            await ctx.send("🎫 你啟動了 `破例下注`！今天你的大樂透購買上限已解除 (可額外購買 3 張)。")

        else:
            await ctx.send("❌ 此道具暫時無法使用或代號錯誤。", ephemeral=True)
            return

        # 扣除道具
        inventory["consumables"][item_code] -= 1
        utils.save_inventory(user_id, inventory)

async def setup(bot):
    await bot.add_cog(GachaCog(bot))