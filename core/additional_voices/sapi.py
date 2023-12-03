from __future__ import absolute_import
from collections import OrderedDict
import pywintypes
import os

if os.name == "nt":
    import win32com.client

SVSFDefault = 0
SVSFlagsAsync = 1
SVSFPurgeBeforeSpeak = 2
SVSFIsFilename = 4
SVSFIsXML = 8
SVSFIsNotXML = 16
SVSFPersistXML = 32


class SAPI5():
    """Supports the microsoft speech API version 5."""

    has_volume = True
    has_rate = True
    has_pitch = True
    min_pitch = -10
    max_pitch = 10
    min_rate = -10
    max_rate = 10
    min_volume = 0
    max_volume = 100
    name = "sapi5"
    priority = 101
    system_output = True

    def __init__(self):
        try:
            # self.object = load_com("SAPI.SPVoice")

            self.object = win32com.client.Dispatch("SAPI.SpVoice")

            self._voices = self._available_voices()
        except (pywintypes.com_error, TypeError):
            raise Exception
        self._pitch = 0

    def _available_voices(self):
        _voices = OrderedDict()
        for v in self.object.GetVoices():
            _voices[v.GetDescription()] = v
        return _voices

    def list_voices(self):
        return list(self._voices.keys())

    def get_voice(self):
        return self.object.Voice.GetDescription()

    def set_voice(self, value):
        self.object.Voice = self._voices[value]
        # For some reason SAPI5 does not reset audio after changing the voice
        # By setting the audio device after changing voices seems to fix this
        # This was noted from information at:
        # http://lists.nvaccess.org/pipermail/nvda-dev/2011-November/022464.html
        self.object.AudioOutput = self.object.AudioOutput

    def get_pitch(self):
        return self._pitch

    def set_pitch(self, value):
        self._pitch = value

    def get_rate(self):
        return self.object.Rate

    def set_rate(self, value):
        self.object.Rate = value

    def get_volume(self):
        return self.object.Volume

    def set_volume(self, value):
        self.object.Volume = value

    def speak(self, text, interrupt=False):
        if interrupt:
            self.silence()
        # We need to do the pitch in XML here
        textOutput = '<pitch absmiddle="%d">%s</pitch>' % (
            round(self._pitch),
            text.replace("<", "&lt;"),
        )
        self.object.Speak(textOutput, SVSFlagsAsync | SVSFIsXML)

    def silence(self):
        self.object.Speak("", SVSFlagsAsync | SVSFPurgeBeforeSpeak)

    def is_active(self):
        if self.object:
            return True
        return False



import ctypes
import time

def send_text_to_narrator(text):
    # Load the user32.dll library
    user32 = ctypes.windll.user32

    # SPI_SETSCREENREADER constant value
    SPI_SETSCREENREADER = 0x0047

    # Set the screen reader text
    user32.SystemParametersInfoW(SPI_SETSCREENREADER, 0, text, 2)

# time.sleep(5)
# # Example usage
# text_to_read = "Hello, this is a test message for the Narrator."
# send_text_to_narrator(text_to_read)