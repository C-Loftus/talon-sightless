from typing import Optional
from talon import Module, actions, Context, settings, cron, ui, registry, scope, clip, app  
import os,  subprocess
from ..lib import scheduling
from ..lib.utils import remove_special, SpeakerType
import enum


if os.name == 'nt':
    import win32com.client

mod = Module()
ctx = Context()

# We want to get the settings from the talon file but then update 
    # them locally here so we can change them globally via expose talon actions
def initialize_settings():
    ctx.settings["user.echo_dictation"]: bool = settings.get("user.echo_dictation")
    ctx.settings["user.echo_context"]: bool = settings.get("user.echo_context")

# initialize the settings only after the user settings have been loaded
app.register('ready', initialize_settings)


current_speaker: tuple[SpeakerType, Optional[subprocess.Popen]]

@mod.action_class
class Actions:
    def set_current_speaker(type: SpeakerType, process: Optional[subprocess.Popen]):
        """Sets the current speaker"""
        global current_speaker 
        current_speaker = (type, process)

    def cancel_current_speaker():
        """Cancels the current speaker"""
        global current_speaker
        if current_speaker:
            match SPEAKER_TYPE := current_speaker[0], \
                  SPEAKER_PROCESS := current_speaker[1]:
                
                case SpeakerType.LIBRARY_CONTROLLER, _:
                    # should be handled in the library / dll itself
                    pass
                case SpeakerType.SCHEDULED, _:
                    scheduling.Scheduler.cancel()
                case SpeakerType.NON_BLOCKING, _:
                    SPEAKER_PROCESS.kill()


    def braille(text: str):
        """Output braille with the screenreader"""

    def echo_dictation_enabled() -> bool:
        """Returns true if echo dictation is enabled"""
        return ctx.settings["user.echo_dictation"]
    
    def echo_context_enabled() -> bool:
        """Returns true if echo context is enabled"""
        return ctx.settings["user.echo_context"]

    def toggle_echo():
        """Toggles echo dictation on and off"""

        if actions.user.echo_dictation_enabled():
            actions.user.robot_tts("echo disabled")
            ctx.settings["user.echo_dictation"] = False
        else:
            actions.user.robot_tts("echo enabled")
            ctx.settings["user.echo_dictation"] = True

    def toggle_echo_context():
        """Toggles echo context on and off"""

        if actions.user.echo_context_enabled():
            actions.user.robot_tts("echo context disabled")
            ctx.settings["user.echo_context"] = False
        else:
            actions.user.robot_tts("echo context enabled")
            ctx.settings["user.echo_context"] = True

    def toggle_echo_all():
        """Toggles echo dictation and echo context on and off"""

        dictation, context = actions.user.echo_dictation_enabled(), actions.user.echo_context_enabled()

        if any([dictation, context]):
            actions.user.robot_tts("echo disabled")
            ctx.settings["user.echo_dictation"] = False
            ctx.settings["user.echo_context"] = False
        else:
            actions.user.robot_tts("echo enabled")
            ctx.settings["user.echo_dictation"] = True
            ctx.settings["user.echo_context"] = True


    def robot_tts(text: str):
        '''text to speech with robot voice'''

    def espeak(text: str):
        '''text to speech with espeak'''


ctxWindows = Context()
ctxWindows.matches = r"""
os: windows
"""

@ctxWindows.action_class('user')
class UserActions:
    def robot_tts(text: str):
        """text to speech with windows voice"""
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.rate = settings.get("user.tts_speed", 1.0)
        
        # send it to a central scheduler thread so it can be cancelled and so
        # it doesn't block the main thread or clog the log with warnings
        scheduling.Scheduler.send(speaker.Speak, text)
        actions.user.set_current_speaker(SpeakerType.SCHEDULED, speaker)
        


ctxLinux = Context()
ctxLinux.matches = r"""
os: linux
"""



@ctxLinux.action_class('user')
class UserActions:
    def espeak(text: str):
        """Text to speech with a robotic/narrator voice"""
        rate = settings.get("user.tts_speed", 0)
        # convert -5 to 5 to -100 to 100 
        rate = rate * 20
        text = remove_special(text)

        proc = subprocess.Popen(["spd-say", text, "--rate", str(rate)])
        actions.user.set_current_speaker(SpeakerType.NON_BLOCKING, proc)


    def robot_tts(text: str):
        """Text to speech with a robotic/narrator voice"""
        # change the directory to the directory of this file
        # so we can run the command from the correct directory
        model_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "additional_voices", "models")
        piper = os.path.expanduser("~/.local/bin/piper")

        os.chdir(model_dir)

        modes = ['en_US-amy-low.onnx', 'en_US-lessac-medium.onnx']

        high = 22050
        low = 16000

        #  we need this more verbose representation here so we don't use the 
        # shell and have risks of shell expansion
        command1 = ["echo", f"{text}"]

        command2 = [piper, "--model", modes[0], "--length_scale", "0.5", "--output_raw"]

        command3 = ["aplay", "-r", str(low), "-c", "1", "-f", "S16_LE", "-t", "raw"]

        echo = subprocess.Popen(command1, stdout=subprocess.PIPE)
        piper = subprocess.Popen(command2, stdin=echo.stdout, stdout=subprocess.PIPE)
        echo.stdout.close()
        aplay = subprocess.Popen(command3, stdin=piper.stdout)
        piper.stdout.close()
        actions.user.set_current_speaker(SpeakerType.NON_BLOCKING, aplay)


ctxMac = Context()
ctxMac.matches = r"""
os: mac
"""

@ctxMac.action_class('user')
class UserActions:
    def robot_tts(text: str):
        """Text to speech with a robotic/narrator voice"""
        # We can't really schedule this since it is a system command, so we
        # have to spawn a new process each time unfortunately
        proc = subprocess.Popen(["say", text])
        actions.user.set_current_speaker(SpeakerType.NON_BLOCKING, proc)

    
