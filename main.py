import json
import requests
import asyncio
import os
from datetime import datetime

import discord
from discord.ext import commands, tasks
from addict import Dict as dotdict

REQUEST_URL = "https://splatoon.oatmealdome.me/api/v1/three/versus/phases?count=12"
MODES = ["Bankara", "BankaraOpen", "X"]
REVERSE_MODE_MAP = {'x': "X", 'open': 'BankaraOpen', 'series': 'Bankara'}
LETTERS = 'abcdefghijkl'

SUB_FILE = "subscribers.json"

def load_subscribers():
    if not os.path.exists(SUB_FILE):
        return []
    with open(SUB_FILE, "r") as f:
        return json.load(f).get("users", [])


def save_subscribers(users):
    with open(SUB_FILE, "w") as f:
        json.dump({"users": users}, f, indent=2)

async def get_rot_data(retry=3, sleep=2):
    success = False
    res = None

    for _ in range(retry):
        try:
            res = requests.get(REQUEST_URL)
            if res.status_code == 200:
                success = True
                break
        except Exception as e:
            print("ERROR >>", e)

        await asyncio.sleep(sleep)

    data = json.loads(res._content.decode()) if success else {}
    rotations = data.get('normal') or []
    return [dotdict(r) for r in rotations]


### main:

with open('.config.json', 'r') as fh:
    cfg = dotdict(json.load(fh))

with open('splatoon_data.json', 'r') as fh:
    spl_id_map = dotdict(json.load(fh))
    for i in spl_id_map.stages:
        spl_id_map.stages[i] = spl_id_map.stages[i].split(' ')[0]

# IMPORTANT: Enable 'Message Content Intent' in Discord Developer Portal
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=".", intents=intents)


async def build_zones_message(modes):
    rotations = await get_rot_data()
    out_data = []

    for r in rotations:
        sz = None
        for m in modes:
            if r[m].rule == "Area":
                sz = dotdict(
                    mode=spl_id_map.modes[m],
                    stages=[spl_id_map.stages[str(i)] for i in r[m].stages]
                )
                break

        if sz is not None:
            unix_time = int(datetime.fromisoformat(r.startTime).timestamp())
            out_data.append(
                f"{LETTERS[len(out_data)]}) <t:{unix_time}:t> - {sz.mode} - {sz.stages[0]} / {sz.stages[1]}"
            )

    if out_data:
        return "Zones rotations in the next 24 hours:\n" + "\n".join(out_data)

    return "No zones rotations found for the next 24H."

@bot.event
async def on_ready():
    print(f'{bot.user} connected')
    # Set the bot's status and activity
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.watching, 
            name=".zones (x, series, open)"
        )
    )

    if not daily_zones_task.is_running():
        daily_zones_task.start()

@bot.command()
async def zones(ctx, *modes):
    if not modes:
        modes = MODES
    else:
        true_modes = []
        for m in modes:
            if not m.lower() in REVERSE_MODE_MAP:
                await ctx.send(f"{m} is not a valid mode -- valid modes are {list(REVERSE_MODE_MAP.keys())}.")
                return
            true_modes.append(REVERSE_MODE_MAP[m.lower()])
        modes = true_modes
    try:
        msg = await build_zones_message(modes)
        await ctx.send(msg)
    except Exception as e:
        await ctx.send("command failed")
        print("command failed:", e)


@bot.command()
async def zones_sub(ctx):
    users = load_subscribers()
    uid = ctx.author.id

    if uid in users:
        await ctx.send("youre already subscribed to daily zones DMs.")
        return

    users.append(uid)
    save_subscribers(users)

    await ctx.send("ok youre in")


@bot.command()
async def zones_unsub(ctx):
    users = load_subscribers()
    uid = ctx.author.id

    if uid not in users:
        await ctx.send("youre not in")
        return

    users.remove(uid)
    save_subscribers(users)

    await ctx.send("ok youre out")


@tasks.loop(minutes=1)
async def daily_zones_task():
    now = datetime.now()

    if now.hour == 0 and now.minute == 0:
        users = load_subscribers()
        if not users:
            return

        print("rise and shine for the 3k")

        try:
            msg = await build_zones_message(MODES)
        except Exception as e:
            print("something happened: ", e)
            return

        for user_id in users:
            try:
                user = await bot.fetch_user(user_id)
                await user.send(msg)
            except Exception as e:
                print(f"failed to DM {user_id}:", e)

bot.run(cfg.token)