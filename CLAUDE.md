# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Killheken-Bot is a Discord bot built for a friend group. It started as a bot imitating a friend ("Killheken" / "帥哥誠") and evolved into a general-purpose group bot ("twMisc's bot"). The bot and all user-facing text are in **Traditional Chinese (zh-TW)**.

## Running the Bot

```bash
python bot.py
```

The bot requires these files in the working directory (all gitignored):
- `token` — Discord bot token (plain text)
- `guild` — Discord guild ID (plain text)
- `ids_admin.json` — list of admin user IDs
- `ids.json` — list of tracked user IDs (order matters, maps to RESPONSE_LIST)
- `emojis.json` — list of emoji dicts with `name` and `id` keys
- `dinner_candidates.json` — list of dinner option strings
- `skull_count.json` — dict of emoji-string → count
- `coins.json` — dict of user-ID-string → coin balance (created at runtime)
- `hongbao.json` — daily red envelope claim tracking (created at runtime)
- `fixed_deposit.json` — weekly fixed deposit tracking (created at runtime)

`holidays.json` is the only JSON data file tracked in git. It maps `YYYY-MM-DD` → holiday name strings for Taiwanese holidays.

## Architecture

Single-file bot (`bot.py`, ~730 lines) using **discord.py** with the `commands.Bot` hybrid command framework. No external packages beyond `discord.py`. Deployed on a remote Ubuntu server (`/home/ubuntu/update_bot.sh`).

**Key patterns:**
- All times use `TAIPEI_TZ` (UTC+8). Use `get_now()` for current time.
- Commands use `@client.hybrid_command` (slash + prefix `$`) or `@client.tree.command` (slash-only, used for `darkbid` which must be ephemeral).
- Admin-only commands are gated with `@commands.is_owner()` and `@commands.dm_only()`.
- Coin economy persisted via `coins.json` — read/write through `update_user_coins(user_id, amount)`.
- Scheduled tasks use `@tasks.loop(time=...)` — daily message at 18:00 Taipei, optional morning message at 10:00.
- Reply rate decays over time via `t_func`/`get_rate` (sigmoid-based cooldown).

**Core features:**
- Coin economy: daily check-in rewards, gambling, wallet, leaderboard, seasonal hongbao, and weekly fixed deposit (5% interest)
- Dark bid system (`/darkbid`): secret bidding to become "boss" who steals daily rewards
- Dinner randomizer with persistent candidate list
- Polling system (`PollView` with discord.py `View`/`Button`)
- Presence tracking: renames a channel based on a specific user's online status
- Message response: replies when messages start with "誠" or a specific custom emoji

## gstack

This project uses [gstack](https://github.com/garrytan/gstack) skills. For all web browsing, always use the `/browse` skill — never use `mcp__claude-in-chrome__*` tools.

**Available skills:**
`/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/design-shotgun`, `/design-html`, `/review`, `/ship`, `/land-and-deploy`, `/canary`, `/benchmark`, `/browse`, `/connect-chrome`, `/qa`, `/qa-only`, `/design-review`, `/setup-browser-cookies`, `/setup-deploy`, `/retro`, `/investigate`, `/document-release`, `/codex`, `/cso`, `/autoplan`, `/plan-devex-review`, `/devex-review`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`, `/learn`

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
