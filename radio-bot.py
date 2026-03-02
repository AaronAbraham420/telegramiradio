"""
Telegram Radio Bot — Base Script
Searches audio via: MusicBrainz, Spotify Lyrics API, LRCLIB,
Song.link, hifi-api, dabmusic.xyz, yoinkify.lol
"""

import logging
import asyncio
import aiohttp
from urllib.parse import quote_plus
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# ─────────────────────────────────────────
# CONFIG — fill these in
# ─────────────────────────────────────────
import os


BOT_TOKEN             = os.environ["BOT_TOKEN"]
SPOTIFY_CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
ALLOWED_GROUP_ID      = int(os.environ["ALLOWED_GROUP_ID"]) if os.environ.get("ALLOWED_GROUP_ID") else None
ADMIN_IDS             = list(map(int, os.environ.get("ADMIN_IDS", "").split(","))) if os.environ.get("ADMIN_IDS") else []
# ─────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger("RadioBot")

# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════

async def get(session: aiohttp.ClientSession, url: str, **kwargs) -> dict | list | None:
    """Safe GET — returns parsed JSON or None on failure."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8), **kwargs) as r:
            if r.status == 200:
                return await r.json(content_type=None)
    except Exception as e:
        log.warning(f"GET {url} failed: {e}")
    return None

def is_allowed(update: Update) -> bool:
    """Block commands outside the allowed group (if configured)."""
    if ALLOWED_GROUP_ID is None:
        return True
    return update.effective_chat.id == ALLOWED_GROUP_ID

def is_admin(update: Update) -> bool:
    return update.effective_user.id in ADMIN_IDS


# ══════════════════════════════════════════════════════════
# API CLIENTS
# ══════════════════════════════════════════════════════════

# ── 1. MusicBrainz ──────────────────────────────────────
async def search_musicbrainz(query: str) -> list[dict]:
    """Returns list of {title, artist, mb_id, duration_ms}."""
    url = (
        f"https://musicbrainz.org/ws/2/recording"
        f"?query={quote_plus(query)}&limit=5&fmt=json"
    )
    headers = {"User-Agent": "RadioBot/1.0 (your@email.com)"}
    async with aiohttp.ClientSession() as s:
        data = await get(s, url, headers=headers)
    results = []
    if data and "recordings" in data:
        for r in data["recordings"]:
            artist = r.get("artist-credit", [{}])[0].get("name", "Unknown")
            results.append({
                "title":    r.get("title", ""),
                "artist":   artist,
                "mb_id":    r.get("id", ""),
                "duration": r.get("length", 0),
                "source":   "MusicBrainz"
            })
    return results


# ── 2. Spotify (OAuth2 Client Credentials) ──────────────
_spotify_token: str | None = None

async def _get_spotify_token() -> str | None:
    global _spotify_token
    if _spotify_token:
        return _spotify_token
    async with aiohttp.ClientSession() as s:
        try:
            async with s.post(
                "https://accounts.spotify.com/api/token",
                data={"grant_type": "client_credentials"},
                auth=aiohttp.BasicAuth(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
                timeout=aiohttp.ClientTimeout(total=8)
            ) as r:
                if r.status == 200:
                    d = await r.json()
                    _spotify_token = d.get("access_token")
        except Exception as e:
            log.warning(f"Spotify token error: {e}")
    return _spotify_token

async def search_spotify(query: str) -> list[dict]:
    """Search Spotify for tracks — returns metadata + 30s preview_url."""
    token = await _get_spotify_token()
    if not token:
        return []
    url = f"https://api.spotify.com/v1/search?q={quote_plus(query)}&type=track&limit=5"
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as s:
        data = await get(s, url, headers=headers)
    results = []
    if data and "tracks" in data:
        for t in data["tracks"]["items"]:
            results.append({
                "title":       t["name"],
                "artist":      ", ".join(a["name"] for a in t["artists"]),
                "album":       t["album"]["name"],
                "preview_url": t.get("preview_url"),   # 30s MP3, may be None
                "spotify_url": t["external_urls"].get("spotify"),
                "source":      "Spotify"
            })
    return results


# ── 3. LRCLIB (Synced Lyrics) ────────────────────────────
async def get_lyrics_lrclib(title: str, artist: str = "") -> dict | None:
    """Returns {plain_lyrics, synced_lyrics} or None."""
    url = f"https://lrclib.net/api/search?q={quote_plus(f'{artist} {title}')}"
    async with aiohttp.ClientSession() as s:
        data = await get(s, url)
    if data and len(data) > 0:
        best = data[0]
        return {
            "plain":  best.get("plainLyrics", ""),
            "synced": best.get("syncedLyrics", ""),
            "title":  best.get("trackName", title),
            "artist": best.get("artistName", artist),
        }
    return None


# ── 4. Song.link (Odesli) ────────────────────────────────
async def get_songlink(url_or_query: str) -> dict | None:
    """
    Pass a Spotify/Apple Music/YouTube URL to get cross-platform links.
    Returns dict with streaming platform URLs.
    """
    api_url = f"https://api.song.link/v1-alpha.1/links?url={quote_plus(url_or_query)}"
    async with aiohttp.ClientSession() as s:
        data = await get(s, api_url)
    if not data:
        return None
    links = {}
    platforms = data.get("linksByPlatform", {})
    for platform, info in platforms.items():
        links[platform] = info.get("url")
    return {
        "title":         data.get("entitiesByUniqueId", {}).values().__iter__().__next__().get("title") if data.get("entitiesByUniqueId") else "",
        "page_url":      data.get("pageUrl"),
        "platform_links": links
    }


# ── 5. hifi-api (streaming quality metadata) ────────────
async def search_hifi(query: str) -> list[dict]:
    """
    Queries hifi-api for high-quality audio sources.
    Endpoint: https://hifi-api.vercel.app  (unofficial, may change)
    """
    url = f"https://hifi-api.vercel.app/search?q={quote_plus(query)}"
    async with aiohttp.ClientSession() as s:
        data = await get(s, url)
    results = []
    if isinstance(data, list):
        for item in data[:5]:
            results.append({
                "title":    item.get("title", ""),
                "artist":   item.get("artist", ""),
                "audio_url": item.get("url") or item.get("audio_url"),
                "quality":  item.get("quality", ""),
                "source":   "hifi-api"
            })
    elif isinstance(data, dict):
        results.append({
            "title":    data.get("title", ""),
            "artist":   data.get("artist", ""),
            "audio_url": data.get("url") or data.get("audio_url"),
            "quality":  data.get("quality", ""),
            "source":   "hifi-api"
        })
    return results


# ── 6. dabmusic.xyz ──────────────────────────────────────
async def search_dabmusic(query: str) -> list[dict]:
    """
    Queries dabmusic.xyz for audio.
    Adjust endpoint path if their API changes.
    """
    url = f"https://dabmusic.xyz/api/search?q={quote_plus(query)}"
    async with aiohttp.ClientSession() as s:
        data = await get(s, url)
    results = []
    if isinstance(data, list):
        for item in data[:5]:
            results.append({
                "title":     item.get("title", ""),
                "artist":    item.get("artist", ""),
                "audio_url": item.get("url") or item.get("stream"),
                "cover":     item.get("cover") or item.get("thumbnail"),
                "source":    "dabmusic"
            })
    return results


# ── 7. yoinkify.lol ──────────────────────────────────────
async def search_yoinkify(query: str) -> list[dict]:
    """
    Queries yoinkify.lol for audio extraction.
    Adjust endpoint path if their API changes.
    """
    url = f"https://yoinkify.lol/api/search?q={quote_plus(query)}"
    async with aiohttp.ClientSession() as s:
        data = await get(s, url)
    results = []
    if isinstance(data, dict) and "results" in data:
        items = data["results"]
    elif isinstance(data, list):
        items = data
    else:
        items = []
    for item in items[:5]:
        results.append({
            "title":     item.get("title", ""),
            "artist":    item.get("uploader") or item.get("artist", ""),
            "audio_url": item.get("url") or item.get("audio"),
            "duration":  item.get("duration"),
            "source":    "yoinkify"
        })
    return results


# ══════════════════════════════════════════════════════════
# AGGREGATED SEARCH — tries all APIs in order
# ══════════════════════════════════════════════════════════

async def full_search(query: str) -> dict:
    """
    Runs all API searches concurrently and returns aggregated results.
    Returns: {mb, spotify, hifi, dab, yoinkify}
    """
    mb_task      = asyncio.create_task(search_musicbrainz(query))
    sp_task      = asyncio.create_task(search_spotify(query))
    hifi_task    = asyncio.create_task(search_hifi(query))
    dab_task     = asyncio.create_task(search_dabmusic(query))
    yoink_task   = asyncio.create_task(search_yoinkify(query))

    mb, sp, hifi, dab, yoink = await asyncio.gather(
        mb_task, sp_task, hifi_task, dab_task, yoink_task,
        return_exceptions=True
    )

    def safe(r):
        return r if isinstance(r, list) else []

    return {
        "musicbrainz": safe(mb),
        "spotify":     safe(sp),
        "hifi":        safe(hifi),
        "dabmusic":    safe(dab),
        "yoinkify":    safe(yoink),
    }


# ══════════════════════════════════════════════════════════
# QUEUE STATE
# ══════════════════════════════════════════════════════════

class RadioQueue:
    def __init__(self):
        self.items: list[dict] = []
        self.current: dict | None = None
        self.history: list[dict] = []

    def add(self, item: dict):
        self.items.append(item)

    def next(self) -> dict | None:
        if self.current:
            self.history.append(self.current)
        self.current = self.items.pop(0) if self.items else None
        return self.current

    def skip(self): return self.next()

    def clear(self): self.items.clear()

    def list_str(self) -> str:
        if not self.items:
            return "Queue is empty."
        lines = [f"{i+1}. {t.get('title','?')} — {t.get('artist','?')} [{t.get('source','?')}]"
                 for i, t in enumerate(self.items)]
        return "\n".join(lines)

queue = RadioQueue()


# ══════════════════════════════════════════════════════════
# BOT COMMAND HANDLERS
# ══════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 *Radio Bot Online!*\n\n"
        "Commands:\n"
        "/play `<song name>` — Search & queue a song\n"
        "/queue — Show current queue\n"
        "/skip — Skip current song _(admin)_\n"
        "/np — Now playing\n"
        "/lyrics `<song>` — Get lyrics from LRCLIB\n"
        "/links `<Spotify/Apple URL>` — Cross-platform links via Song.link\n"
        "/clear — Clear queue _(admin)_\n"
        "/sources — Info on all audio sources\n",
        parse_mode="Markdown"
    )


async def cmd_play(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return

    if not ctx.args:
        await update.message.reply_text("Usage: /play <song name or artist - title>")
        return

    query = " ".join(ctx.args)
    msg   = await update.message.reply_text(f"🔍 Searching: *{query}*...", parse_mode="Markdown")

    results = await full_search(query)

    # Priority: yoinkify → dabmusic → hifi → spotify preview → musicbrainz metadata
    audio_result = None
    for source_key in ("yoinkify", "dabmusic", "hifi"):
        items = results.get(source_key, [])
        if items and items[0].get("audio_url"):
            audio_result = items[0]
            break

    # Fallback: Spotify 30s preview
    if not audio_result:
        sp = results.get("spotify", [])
        if sp and sp[0].get("preview_url"):
            audio_result = {
                "title":     sp[0]["title"],
                "artist":    sp[0]["artist"],
                "audio_url": sp[0]["preview_url"],
                "source":    "Spotify Preview (30s)"
            }

    # Fallback: MusicBrainz metadata only
    if not audio_result:
        mb = results.get("musicbrainz", [])
        if mb:
            audio_result = {
                "title":     mb[0]["title"],
                "artist":    mb[0]["artist"],
                "audio_url": None,
                "source":    "MusicBrainz (metadata only)"
            }

    if not audio_result:
        await msg.edit_text(f"❌ No results found for *{query}*", parse_mode="Markdown")
        return

    queue.add(audio_result)
    title  = audio_result.get("title", query)
    artist = audio_result.get("artist", "Unknown")
    source = audio_result.get("source", "?")
    url    = audio_result.get("audio_url")

    text = (
        f"✅ Added to queue:\n"
        f"🎵 *{title}* — {artist}\n"
        f"📡 Source: `{source}`"
    )
    if url:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("▶ Play Now", callback_data=f"playnow:{len(queue.items)-1}"),
            InlineKeyboardButton("🎤 Lyrics", callback_data=f"lyrics:{title}|{artist}")
        ]])
        await msg.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await msg.edit_text(
            text + "\n⚠️ No direct audio URL found — metadata only.",
            parse_mode="Markdown"
        )


async def cmd_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    text = f"📋 *Queue ({len(queue.items)} songs):*\n\n{queue.list_str()}"
    if queue.current:
        np = queue.current
        text = f"▶ *Now playing:* {np.get('title','?')} — {np.get('artist','?')}\n\n" + text
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_np(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if not queue.current:
        await update.message.reply_text("Nothing is playing right now.")
        return
    np = queue.current
    await update.message.reply_text(
        f"▶ *Now Playing*\n🎵 {np.get('title','?')} — {np.get('artist','?')}\n"
        f"📡 Source: `{np.get('source','?')}`",
        parse_mode="Markdown"
    )


async def cmd_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if not is_admin(update):
        await update.message.reply_text("⛔ Only admins can skip songs.")
        return
    nxt = queue.skip()
    if nxt:
        await update.message.reply_text(
            f"⏭ Skipped! Now playing: *{nxt.get('title','?')}*", parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⏭ Skipped! Queue is now empty.")


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if not is_admin(update):
        await update.message.reply_text("⛔ Only admins can clear the queue.")
        return
    queue.clear()
    await update.message.reply_text("🗑 Queue cleared.")


async def cmd_lyrics(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /lyrics <song name>")
        return

    query  = " ".join(ctx.args)
    parts  = query.split(" - ", 1)
    artist = parts[0] if len(parts) > 1 else ""
    title  = parts[1] if len(parts) > 1 else query

    msg = await update.message.reply_text(f"🎤 Fetching lyrics for *{query}*...", parse_mode="Markdown")
    result = await get_lyrics_lrclib(title, artist)

    if not result or not result.get("plain"):
        await msg.edit_text("❌ Lyrics not found on LRCLIB.")
        return

    lyrics = result["plain"]
    header = f"🎤 *{result['title']}* — {result['artist']}\n\n"

    # Telegram message limit is 4096 chars
    full = header + lyrics
    if len(full) > 4000:
        full = full[:4000] + "\n...(truncated)"

    await msg.edit_text(full, parse_mode="Markdown")


async def cmd_links(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /links <Spotify/Apple Music/YouTube URL>")
        return

    url = ctx.args[0]
    msg = await update.message.reply_text("🔗 Fetching cross-platform links...", parse_mode="Markdown")
    result = await get_songlink(url)

    if not result:
        await msg.edit_text("❌ Could not resolve links. Make sure you passed a valid music URL.")
        return

    lines = [f"🔗 *Cross-Platform Links*", f"Page: {result.get('page_url', '')}", ""]
    icons = {
        "spotify": "🎵", "appleMusic": "🍎", "youtube": "▶️", "youtubeMusic": "🎶",
        "tidal": "💎", "deezer": "📻", "amazonMusic": "📦", "soundcloud": "☁️",
    }
    for platform, link in (result.get("platform_links") or {}).items():
        icon = icons.get(platform, "🎧")
        lines.append(f"{icon} [{platform}]({link})")

    await msg.edit_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)


async def cmd_sources(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📡 *Audio Sources Used by This Bot*\n\n"
        "1️⃣ *MusicBrainz* — Open music metadata database\n"
        "2️⃣ *Spotify API* — Track metadata + 30s previews\n"
        "3️⃣ *LRCLIB* — Synced & plain lyrics\n"
        "4️⃣ *Song.link* — Cross-platform music links\n"
        "5️⃣ *hifi-api* — High quality audio stream sources\n"
        "6️⃣ *dabmusic.xyz* — Audio file search\n"
        "7️⃣ *yoinkify.lol* — Audio extraction service\n",
        parse_mode="Markdown"
    )


# ── Inline button callbacks ───────────────────────────────
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("lyrics:"):
        _, rest = data.split(":", 1)
        parts = rest.split("|", 1)
        title  = parts[0]
        artist = parts[1] if len(parts) > 1 else ""
        result = await get_lyrics_lrclib(title, artist)
        if result and result.get("plain"):
            txt = f"🎤 *{title}*\n\n" + result["plain"][:4000]
        else:
            txt = f"❌ No lyrics found for *{title}*"
        await query.message.reply_text(txt, parse_mode="Markdown")

    elif data.startswith("playnow:"):
        await query.message.reply_text("▶ Play-now integration requires your Icecast/Liquidsoap setup.")


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_start))
    app.add_handler(CommandHandler("play",    cmd_play))
    app.add_handler(CommandHandler("queue",   cmd_queue))
    app.add_handler(CommandHandler("np",      cmd_np))
    app.add_handler(CommandHandler("skip",    cmd_skip))
    app.add_handler(CommandHandler("clear",   cmd_clear))
    app.add_handler(CommandHandler("lyrics",  cmd_lyrics))
    app.add_handler(CommandHandler("links",   cmd_links))
    app.add_handler(CommandHandler("sources", cmd_sources))
    app.add_handler(CallbackQueryHandler(button_handler))

    log.info("Bot started. Listening...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()