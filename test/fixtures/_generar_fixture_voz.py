"""Genera test/fixtures/abre_la_calculadora.wav (16 kHz mono PCM16) a partir
de edge-tts. Reproducible: se vuelve a correr si hace falta regenerar."""
import asyncio
import io
import pathlib

import av
import edge_tts

FRASE = "Abre la calculadora"
VOZ = "es-MX-JorgeNeural"
OUT = pathlib.Path(__file__).parent / "abre_la_calculadora.wav"


async def _sintetiza() -> bytes:
    mp3 = io.BytesIO()
    com = edge_tts.Communicate(FRASE, VOZ)
    async for chunk in com.stream():
        if chunk["type"] == "audio":
            mp3.write(chunk["data"])
    return mp3.getvalue()


def _mp3_a_wav(mp3_bytes: bytes) -> None:
    inp = av.open(io.BytesIO(mp3_bytes), "r")
    resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=16000)
    out = av.open(str(OUT), "w", format="wav")
    ostream = out.add_stream("pcm_s16le", rate=16000, layout="mono")
    for frame in inp.decode(audio=0):
        frame.pts = None
        for rframe in resampler.resample(frame):
            for packet in ostream.encode(rframe):
                out.mux(packet)
    for packet in ostream.encode(None):
        out.mux(packet)
    out.close()
    inp.close()


mp3 = asyncio.run(_sintetiza())
_mp3_a_wav(mp3)
print("escrito:", OUT, OUT.stat().st_size, "bytes")

# verificacion rapida de duracion/forma
cont = av.open(str(OUT))
print("rate:", cont.streams.audio[0].rate,
      "dur_s:", float(cont.duration) / av.time_base)
cont.close()
