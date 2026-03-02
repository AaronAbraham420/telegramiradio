# telegramiradio
An Online Radio Controlled via telegram groups for queing songs and more

---

> 🎙️ Control a live internet radio stream directly from your Telegram group — queue songs, fetch lyrics, and get cross-platform links, all via bot commands.

---

## Features

- 🎵 **Song queuing** — search and queue audio from multiple sources
- 🔍 **Multi-API search** — aggregates results from 7 audio/music APIs simultaneously
- 🎤 **Lyrics** — fetches synced and plain lyrics via LRCLIB
- 🔗 **Cross-platform links** — resolves Spotify/Apple/YouTube URLs to all platforms via Song.link
- 📡 **Live streaming** — integrates with Icecast2 + Liquidsoap for real radio broadcasting
- 👮 **Admin controls** — skip, clear queue, restrict commands to specific groups
- ⚡ **Async** — all API calls run concurrently for fast responses

---

## Audio Sources

| # | API | Used For |
|---|-----|----------|
| 1 | [MusicBrainz](https://musicbrainz.org) | Open music metadata (artist, title, recording ID) |
| 2 | [Spotify API](https://developer.spotify.com) | Track info + 30-second audio previews |
| 3 | [LRCLIB](https://lrclib.net) | Plain and time-synced lyrics |
| 4 | [Song.link](https://song.link) | Cross-platform streaming URL resolver |
| 5 | [hifi-api](https://hifi-api.vercel.app) | High-quality audio stream sources |
| 6 | [dabmusic.xyz](https://dabmusic.xyz) | Audio file search |
| 7 | [yoinkify.lol](https://yoinkify.lol) | Audio extraction service |

**Playback priority:** `yoinkify → dabmusic → hifi-api → Spotify preview → MusicBrainz (metadata only)`

---

## Bot Commands

| Command | Description | Access |
|---------|-------------|--------|
| `/start` | Show help and all commands | Everyone |
| `/play <song name>` | Search and queue a song | Everyone |
| `/queue` | Show the current queue | Everyone |
| `/np` | Show what's currently playing | Everyone |
| `/lyrics <artist - title>` | Fetch lyrics from LRCLIB | Everyone |
| `/links <url>` | Get cross-platform links via Song.link | Everyone |
| `/sources` | List all audio APIs used | Everyone |
| `/skip` | Skip the current song | Admins only |
| `/clear` | Clear the entire queue | Admins only |

---

## Project Structure

```
telegramiradio/
├── radio_bot.py       # Main bot — commands, API clients, queue logic
├── requirements.txt   # Python dependencies
├── Procfile           # Railway/Heroku process definition
└── README.md
```

---

## Setup & Deployment

### Prerequisites

- Python 3.10+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- Spotify Developer credentials (optional, for preview URLs)

### Local Development

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/telegramiradio.git
cd telegramiradio

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
export BOT_TOKEN="your_token_here"
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export ALLOWED_GROUP_ID="-100123456789"   # optional
export ADMIN_IDS="123456,789012"          # optional

# 4. Run the bot
python radio_bot.py
```

### Deploy to Railway (Recommended — Free)

1. Fork or push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Select this repo
4. Go to **Variables** tab and add:

| Variable | Value |
|---|---|
| `BOT_TOKEN` | From @BotFather |
| `SPOTIFY_CLIENT_ID` | From Spotify Dashboard |
| `SPOTIFY_CLIENT_SECRET` | From Spotify Dashboard |
| `ALLOWED_GROUP_ID` | Your group's chat ID (optional) |
| `ADMIN_IDS` | Comma-separated Telegram user IDs (optional) |

5. Railway auto-deploys on every `git push` to `main`

> ⚠️ Make sure `Procfile` uses `worker:` not `web:` — bots use long polling, not HTTP.

---

## Radio Streaming (Optional)

To use this bot as a real radio station (not just a queue manager), pair it with:

- **[Icecast2](https://icecast.org/)** — stream server
- **[Liquidsoap](https://www.liquidsoap.info/)** — audio queue engine

```bash
sudo apt install icecast2 liquidsoap ffmpeg -y
```

The bot communicates with Liquidsoap via telnet to push audio URLs into the live stream.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ Yes | Telegram bot token |
| `SPOTIFY_CLIENT_ID` | ⚠️ Optional | Enables Spotify search & previews |
| `SPOTIFY_CLIENT_SECRET` | ⚠️ Optional | Enables Spotify search & previews |
| `ALLOWED_GROUP_ID` | ⚠️ Optional | Restrict bot to one specific group |
| `ADMIN_IDS` | ⚠️ Optional | Comma-separated IDs for admin commands |

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first.

---

## License

[MIT](LICENSE)