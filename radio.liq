#!/usr/bin/liquidsoap

settings.server.telnet.set(true)
settings.server.telnet.bind_addr.set("127.0.0.1")  # native, no need for 0.0.0.0
settings.server.telnet.port.set(1234)

settings.request.grace_time.set(10.)

queue = request.queue(id="queue")
silence = blank(duration=0.0)

radio = fallback(
  track_sensitive=false,
  [queue, silence]
)

radio = on_track(
  fun(meta) ->
    log("Now playing: #{meta['artist']} - #{meta['title']}"),
  radio
)

output.icecast(
  %mp3(bitrate=128, samplerate=44100, stereo=true),
  host="127.0.0.1",    # Icecast exposed by Podman on localhost:8000
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