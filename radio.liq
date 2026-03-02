#!/usr/bin/liquidsoap

# Enable telnet for bot to push URLs
settings.server.telnet.set(true)
settings.server.telnet.port.set(1234)

# Request queue — bot pushes URLs here
queue = request.queue(id="queue")

# Silence fallback when queue is empty
silence = blank(duration=0.0)

# Use queue, fall back to silence
radio = fallback(track_sensitive=false, [queue, silence])

# Stream to Icecast
output.icecast(
  %mp3(bitrate=128),
  host="127.0.0.1",
  port=8000,
  password="radio123",
  mount="/radio",
  name="telegramiradio",
  description="Telegram controlled radio",
  radio
)