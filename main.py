import json
import requests
import asyncio
from datetime import datetime

import discord
from discord.ext import commands
from addict import Dict as dotdict

REQUEST_URL = "https://splatoon.oatmealdome.me/api/v1/three/versus/phases?count=12"
MODES = ["Bankara", "BankaraOpen", "X"]
REVERSE_MODE_MAP = {'x': "X", 'open': 'BankaraOpen', 'series': 'Bankara'}
LETTERS = 'abcdefghijkl'

async def get_rot_data(retry=3, sleep=2):
    success = False
    res = requests.get(REQUEST_URL)
    for _ in range(retry):
        try:
            res = requests.get(REQUEST_URL)
            if res.status_code == 200:
                success = True
        except Exception as e:
            print("ERROR >>", e)
        if success:
            break
        else:
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
        out = "No zones rotations found for the next 24H."
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
                out_data.append(f"{LETTERS[len(out_data)]}) <t:{unix_time}:t> - {sz.mode} - {sz.stages[0]} / {sz.stages[1]}")
        if out_data:
            out = "Zones rotations in the next 24 hours:\n"+'\n'.join(out_data)
        await ctx.send(out)
        return
    except Exception as e:
        await ctx.send("command failed")
        print("command failed:", e)
        return

bot.run(cfg.token)
