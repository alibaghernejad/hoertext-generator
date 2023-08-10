from functools import reduce
import calendar
import time
import logging
import io
from urllib.request import urlopen
import asyncio
import re
import urllib.parse
import aiohttp
import librosa
import pydub
import soundfile as sf
import numpy as np
import payloads as ps


async def main():
    # Load the text template, used to generate hoertext.
    # Ignore whitespace and empty lines.
    file = open("sample4.md", encoding="utf-8", mode="r")
    lines = [line for line in file.readlines() if line and line.strip()]
    file.close()

    # A list of requests to process
    locale_de_de = "de-DE"
    # locale_fa_ir = "fa-IR"
    pattern_section = r"\#\["

    def request(line, r):
        return [
            (
                str(ps.payload_de_DE()["url"]),
                str(ps.payload_de_DE()["payload"]).format(
                    urllib.parse.quote_plus(line)
                ),
                ps.payload_de_DE()["headers"],
            )
            if re.search(locale_de_de, r[0])
            else (
                str(ps.payload_fa_IR()["url"]),
                str(ps.payload_fa_IR()["payload"]).format(
                    urllib.parse.quote_plus(line)
                ),
                ps.payload_fa_IR()["headers"],
            )
        ]

    formatted_requests = reduce(
        lambda r, l: (
            l,
            r[1] if re.search(pattern_section, l) else r[1] + request(l, r),
        ),
        lines[1:],
        (lines[0], []),
    )

    # Select reduced list of payload.
    formatted_requests = formatted_requests[1]

    # A function to make an async GET request and return the response content
    async def fetch(session, url, payload, headers):
        time.sleep(1)
        async with session.post(url, data=payload, headers=headers) as response:
            res = await response.text()
            time.sleep(1)
            return res

    results: list[any]
    # Create a session object
    async with aiohttp.ClientSession() as session:
        # Create a semaphore with 10 permits
        # semaphore = asyncio.Semaphore(10)
        # Create a list of tasks with the semaphore
        tasks = [
            asyncio.create_task(fetch(session, request[0], request[1], request[2]))
            for request in formatted_requests
        ]
        # Wait for the tasks to complete and get their results
        results = await asyncio.gather(*tasks)
        logging.getLogger().info("All of the scheduled tasks have done.")

    # Fill template placeholders.
    audio_path_key = """'cpCurrAudioPathVoices':'"""
    audio_paths = [
        (r[r.find(audio_path_key) + audio_path_key.count :])[
            : r[r.find(audio_path_key) + audio_path_key.count :].find("'")
        ]
        for r in results
    ]

    intro_name = "intro.mp3"
    # outro_name = "intro.mp3"

    # The silence chunk between each element.
    logging.getLogger().info("Generating silence chunk...")
    silence = np.pad([], (0, 3 * 22050))

    body_bytes = [sf.read(io.BytesIO(urlopen(p).read())) for p in audio_paths if p]
    body_bytes = reduce(
        lambda r, v: r + [(silence, 22050), v], body_bytes[1:], body_bytes[:1]
    )
    logging.getLogger().info("Generating silence chunk. Done.")

    # Consider first audio file sample rate a default sample rate.
    _, body_sample_rate = body_bytes[0]

    logging.getLogger().info("Loading Intro...")
    intro_bytes, _ = sf.read(intro_name)

    logging.getLogger().info("Writing body chunk...")
    # Save body chunk as a an audio array as wav.
    sf.write("body.wav", np.concatenate(list(zip(*body_bytes))[0]), body_sample_rate)

    # Convert wav to mp3 using pydub
    sound = pydub.AudioSegment.from_wav("body.wav")
    sound.export("body.mp3", format="mp3")

    # Load intro and outro audio files.
    intro_bytes, _ = librosa.load("intro.mp3", sr=body_sample_rate)

    body_bytes, body_sample_rate = librosa.load("body.mp3", sr=body_sample_rate)
    combined0 = np.concatenate((intro_bytes, body_bytes), axis=0)
    unix_timestamp = calendar.timegm(time.gmtime())
    file_name = "combined{}".format(unix_timestamp)
    sf.write(f"{file_name}.wav", combined0, body_sample_rate)

    sf.write(f"{file_name}.mp3", combined0, body_sample_rate)

    # resample the intro to match the sample rate of the main
    # intro = resampy.resample(intro, sr1, sr2)

    # combined = np.concatenate((intro, main), axis=0)

    # sf.write('combined.wav', combined, sr2)


# Call the main function
if __name__ == "__main__":
    asyncio.run(main())
