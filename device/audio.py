"""Text-to-speech playback, page by page (the "Listen" feature).

Synthesizes the current page with the piper CLI, plays it, and pre-synthesizes the
next page while the current one plays. All subprocess-based and best-effort — there
is no audio hardware in dev, so failures are surfaced via the on_update callback.

Audio goes to the default sink (a connected Bluetooth speaker once you pair one in
Settings). Playback tries pw-play (PipeWire) -> paplay -> aplay.
"""
import os
import subprocess
import tempfile
import threading

import config

_PLAYERS = (["pw-play"], ["paplay"], ["aplay"])


def _player_cmd():
    for cmd in _PLAYERS:
        from shutil import which
        if which(cmd[0]):
            return cmd
    raise RuntimeError("no audio player (install pipewire or alsa-utils)")


def synth_to_wav(text, path):
    """Run piper: text on stdin -> WAV at `path`. Raises on failure."""
    p = subprocess.run([config.PIPER_BIN, "--model", config.PIPER_MODEL,
                        "--output_file", path],
                       input=text.encode("utf-8"), capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "replace")[:200] or "piper failed")


class Player:
    """Streams synthesized pages. on_update(idx, state) is called to drive the UI."""

    def __init__(self, pages, on_update):
        self.pages = pages
        self.on_update = on_update
        self.idx = 0
        self._seek = None          # set by skip(); loop jumps here instead of +1
        self._stop = False
        self._proc = None
        self._dir = None
        self._thread = None

    def start(self, at=0):
        self.idx = at
        self._dir = tempfile.mkdtemp(prefix="piwi-tts-")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _wav(self, i):
        return os.path.join(self._dir, f"{i}.wav")

    def _run(self):
        try:
            play = _player_cmd()
        except Exception as e:
            self.on_update(self.idx, f"audio error: {e}")
            return
        while not self._stop and 0 <= self.idx < len(self.pages):
            wav = self._wav(self.idx)
            if not os.path.exists(wav):
                self.on_update(self.idx, "Converting")
                try:
                    synth_to_wav(self.pages[self.idx], wav)
                except Exception as e:
                    self.on_update(self.idx, f"TTS error: {e}")
                    print(f"TTS error: {e}")
                    return
            if self._stop:
                break
            # pre-synthesize the next page while this one plays
            nxt = self.idx + 1
            if nxt < len(self.pages) and not os.path.exists(self._wav(nxt)):
                threading.Thread(target=self._prefetch, args=(nxt,), daemon=True).start()
            self.on_update(self.idx, "Playing")
            self._proc = subprocess.Popen(play + [wav])
            self._proc.wait()
            if self._stop:
                break
            if self._seek is not None:
                self.idx, self._seek = self._seek, None    # skip: don't auto-advance
            else:
                self.idx += 1
        if not self._stop:
            self.on_update(min(self.idx, len(self.pages) - 1), "Done")

    def _prefetch(self, i):
        try:
            synth_to_wav(self.pages[i], self._wav(i))
        except Exception:
            pass                   # will retry synchronously when we reach it

    def skip(self, delta):
        target = max(0, min(len(self.pages) - 1, self.idx + delta))
        self._seek = target
        self._kill()               # stop current page; loop resumes at target

    def stop(self):
        self._stop = True
        self._kill()

    def _kill(self):
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass


# ---- self-check ------------------------------------------------------------
def _selftest():
    # skip clamps to valid page range without touching audio
    p = Player(["a", "b", "c"], lambda i, s: None)
    p.idx = 1
    p.skip(5)
    assert p._seek == 2
    p.idx = 1
    p.skip(-9)
    assert p._seek == 0
    print("audio selftest OK")


if __name__ == "__main__":
    _selftest()
