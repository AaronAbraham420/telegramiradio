#!/usr/bin/liquidsoap

# ─────────────────────────────────────────
# telegramiradio — Liquidsoap script
# Bot pushes URLs via telnet on port 1234
# Audio is streamed to Icecast on port 8000
# ─────────────────────────────────────────

# Enable telnet server so the bot can push commands
settings.server.telnet.set(true)
settings.server.telnet.bind_addr.set("0.0.0.0")
settings.server.telnet.port.set(1234)

# Allow enough time for slow streams to buffer
settings.request.grace_time.set(10.)

# ── Request queue ────────────────────────
# The bot pushes audio URLs here via:
#   queue.push <url>
#   queue.skip
queue = request.queue(id="queue")

# ── Fallback — silence when queue is empty
silence = blank(duration=0.0)

# ── Main source — queue with silence fallback
radio = fallback(
  track_sensitive=false,
  [queue, silence]
)

# ── Log track changes ────────────────────
radio = on_track(
  fun(meta) ->
    log("Now playing: #{meta['artist']} - #{meta['title']}"),
  radio
)

# ── Output to Icecast ────────────────────
output.icecast(
  %mp3(bitrate=128, samplerate=44100, stereo=true),
  host="127.0.0.1",
  port=8000,
  password="radio123",
  mount="/radio",
  name="telegramiradio",
  description="Telegram controlled internet radio",
  genre="Mixed",
  url="http://localhost:8000/radio",
  public=false,
  fallible=true,
  radio
)
