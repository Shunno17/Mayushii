import discord
from discord.ext import commands, tasks
import random
import os
import json
import aiohttp
from dotenv import load_dotenv
from difflib import get_close_matches

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="&", intents=intents, help_command=None)

DB_FILE = "quotes_db.json"
MAX_CACHE = 3000

quote_cache = []

session = None

# -----------------------
# LOAD / SAVE
# -----------------------

def load_db():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_db():
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(quote_cache, f, ensure_ascii=False)

# -----------------------
# API
# -----------------------

async def fetch_from_yurippe():
    try:
        async with session.get("https://yurippe.vercel.app/api/quotes") as res:
            if res.status != 200:
                return None
            data = await res.json()
            return random.choice(data)
    except:
        return None

async def fetch_from_animechan():
    try:
        async with session.get("https://api.animechan.io/v1/quotes/random") as res:
            if res.status != 200:
                return None
            return await res.json()
    except:
        return None

def normalize(q):
    return {
        "anime": q.get("anime") or q.get("source") or "Unknown",
        "character": q.get("character") or q.get("name") or "Unknown",
        "quote": q.get("quote") or q.get("content") or ""
    }

async def get_new_quote():
    q = await fetch_from_yurippe()
    if q:
        return normalize(q)

    q = await fetch_from_animechan()
    if q:
        return normalize(q)

    return None

# -----------------------
# CACHE
# -----------------------

def is_valid_quote(q):
    if not q:
        return False

    if not q["quote"] or len(q["quote"]) < 10:
        return False

    if q["character"].lower() in ["unknown", "", "watashi"]:
        return False

    return True

def add_to_cache(q):
    if not is_valid_quote(q):
        return

    if q not in quote_cache:
        quote_cache.append(q)

    if len(quote_cache) > MAX_CACHE:
        quote_cache.pop(0)

    save_db()

@tasks.loop(seconds=4)
async def build_cache():
    q = await get_new_quote()
    if q:
        add_to_cache(q)
        print(f"Cache size: {len(quote_cache)}")

# -----------------------
# EMBED
# -----------------------

def create_embed(q):
    embed = discord.Embed(
        description=f'“{q["quote"]}”',
        color=discord.Color.random()
    )

    embed.set_author(name=q["character"])
    embed.add_field(name="Anime", value=q["anime"], inline=False)
    embed.set_footer(text="✨ Mayushii Quotes")

    return embed

# -----------------------
# EVENTS
# -----------------------

@bot.event
async def on_ready():
    global session
    session = aiohttp.ClientSession()

    global quote_cache
    quote_cache = load_db()

    if not build_cache.is_running():
        build_cache.start()

    await bot.change_presence(activity=discord.Game(name="&help | Anime Quotes"))

    print(f"Loaded {len(quote_cache)} quotes")
    print(f"Logged in as {bot.user}")

# -----------------------
# COMMANDS
# -----------------------

@bot.command()
async def quote(ctx, *, arg=None):

    if not quote_cache:
        await ctx.send("⚠️ Database building... try again soon.")
        return

    # RANDOM
    if arg is None:
        await ctx.send(embed=create_embed(random.choice(quote_cache)))
        return

    arg = arg.lower().strip()

    # NORMAL SEARCH
    results = [
        q for q in quote_cache
        if arg in q["character"].lower()
        or arg in q["anime"].lower()
    ]

    # FUZZY SEARCH (ELITE FEATURE)
    if not results:
        all_names = list(set(
            [q["character"].lower() for q in quote_cache] +
            [q["anime"].lower() for q in quote_cache]
        ))

        matches = get_close_matches(arg, all_names, n=5, cutoff=0.6)

        for m in matches:
            for q in quote_cache:
                if m in q["character"].lower() or m in q["anime"].lower():
                    results.append(q)

    if results:
        await ctx.send(embed=create_embed(random.choice(results)))
        return

    # LIVE FETCH
    for _ in range(20):
        q = await get_new_quote()
        if not q:
            continue

        add_to_cache(q)

        if arg in q["character"].lower() or arg in q["anime"].lower():
            await ctx.send(embed=create_embed(q))
            return

    await ctx.send("❌ No matching quotes found.")

@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="📖 Mayushii Bot",
        description="Elite Anime Quote Bot 🎌",
        color=discord.Color.blue()
    )

    embed.add_field(name="&quote", value="Random quote", inline=False)
    embed.add_field(name="&quote <name>", value="Search by character/anime", inline=False)

    embed.set_footer(text="Fast • Smart • Persistent")

    await ctx.send(embed=embed)

@bot.command()
async def invite(ctx):
    await ctx.send("Invite me: https://your-invite-link-here")

# -----------------------
# CLEANUP
# -----------------------

@bot.event
async def on_close():
    await session.close()

# -----------------------
# RUN
# -----------------------

bot.run(os.getenv("TOKEN"))