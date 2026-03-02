#!/usr/bin/liquidsoap

# ─────────────────────────────────────────
# telegramiradio — Liquidsoap 2.x script
# ─────────────────────────────────────────

# Telnet server — bot pushes commands here
settings.server.telnet.set(true)
settings.server.telnet.bind_addr.set("127.0.0.1")
settings.server.telnet.port.set(1234)

# Request queue — bot pushes URLs via:
#   queue.push <url>
#   queue.skip
queue = request.queue(id="queue")

# Silence fallback when queue is empty
silence = blank()

# Main radio source
radio = fallback(track_sensitive=false, [queue, silence])

# Stream to Icecast
output.icecast(
  %opus,
  host="127.0.0.1",
  port=8000,
  password="radio123",
  mount="/radio",
  name="telegramiradio",
  description="Telegram controlled internet radio",
  genre="Mixed",
  public=false,
  fallible=true,
  radio
)
