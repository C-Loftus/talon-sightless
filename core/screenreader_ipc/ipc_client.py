from talon import Module, Context, actions, settings
import os
import ipaddress
import json
import socket
import threading
from typing import Tuple, assert_never
from .ipc_schema import (
    IPC_COMMAND,
    IPCServerResponse,
    IPCClientResponse,
    ServerSpec,
    ServerStatusResult,
    RETURNED_VAL,
)


mod = Module()
lock = threading.Lock()


def check_ipc_result(
    response: Tuple[IPCClientResponse, IPCServerResponse, list[any]],
) -> Tuple[list[IPC_COMMAND], list[RETURNED_VAL]]:
    """
    Sanitize the response from the screenreader server
    and return just the commands and a return value
    if present
    """

    match response:
        case (
            (
                IPCClientResponse.NO_RESPONSE
                | IPCClientResponse.TIMED_OUT
                | IPCClientResponse.GENERAL_ERROR,
                _,
            ) as error
        ):
            raise RuntimeError(
                f"Clientside {error} communicating with screenreader extension"
            )
        case (IPCClientResponse.SUCCESS, _):
            # empty case is here for exhaustiveness
            pass

    for cmd, value, status in zip(
        response[1]["processedCommands"],
        response[1]["returnedValues"],
        response[1]["statusResults"],
    ):
        match status:
            case ServerStatusResult.SUCCESS:
                # empty case is here for exhaustiveness
                pass
            case ServerStatusResult.INVALID_COMMAND_ERROR:
                raise ValueError(f"Invalid command '{cmd}' sent to screenreader")
            case ServerStatusResult.JSON_ENCODE_ERROR:
                raise ValueError(
                    "Invalid JSON payload sent from client to screenreader"
                )
            case (
                (
                    ServerStatusResult.INTERNAL_SERVER_ERROR
                    | ServerStatusResult.RUNTIME_ERROR
                ) as error
            ):
                raise RuntimeError(f"{error} processing command '{cmd}'")
            case _:
                assert_never((cmd, value, status))

    return zip(
        response[1]["processedCommands"], response[1]["returnedValues"], strict=True
    )


@mod.action_class
class Actions:
    def addon_server_endpoint() -> Tuple[str, str, str]:
        """Returns the address, port, and valid commands for the addon server"""

    # We use a list and not a dict since we can have duplicate commands in the same payload
    def send_ipc_commands(
        commands: list[IPC_COMMAND],
    ) -> Tuple[list[IPC_COMMAND], list[RETURNED_VAL]]:
        """Sends a bundle of commands to the screenreader"""
        actions.user.tts("No screenreader running to send commands to")
        raise NotImplementedError

    # We need a separate command for single commands since we can't easily
    # pass in a list via a .talon file and thus this allows a single string instead
    def send_ipc_command(
        command: IPC_COMMAND,
    ) -> RETURNED_VAL:
        """
        Sends a single command to the screenreader.
        This is its own function since it is a clearer API than passing in
        a list for a single command
        """
        actions.user.tts("No screenreader running to send commands to")
        raise NotImplementedError


NVDAContext = Context()
NVDAContext.matches = r"""
tag: user.nvda_running
"""


@NVDAContext.action_class("user")
class NVDAActions:
    def addon_server_endpoint() -> Tuple[str, str, str]:
        """Returns the address, port, and valid commands for the addon server"""
        SPEC_FILE = os.path.expanduser(
            "~\\AppData\\Roaming\\nvda\\talon_server_spec.json"
        )

        with open(SPEC_FILE, "r") as f:
            spec: ServerSpec = json.load(f)
            address = spec["address"]
            port = spec["port"]
            valid_commands = spec["valid_commands"]

        try:
            if address == "localhost":
                ip = ipaddress.ip_address(socket.gethostbyname(address))
            else:
                ip = ipaddress.ip_address(address)
            assert ip.is_private, "Address is not a local IP address"
        except ValueError:
            raise ValueError(f"Invalid NVDA IP address: {address}")

        return address, port, valid_commands

    # Should be used only for single commands or debugging
    def send_ipc_commands(
        commands: list[IPC_COMMAND],
    ) -> Tuple[list[IPC_COMMAND], list[RETURNED_VAL]]:
        """Sends a list of commands or a single command string to the NVDA screenreader"""

        # this function can still be called if NVDA is running, since cron
        # is ran 400ms after the check, so we can check again here after the
        # scheduler runs the function
        if not actions.user.is_nvda_running():
            return

        ip, port, valid_commands = actions.user.addon_server_endpoint()

        for command in commands:
            if command not in valid_commands:
                raise ValueError(f"Invalid command: {command}")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.2)
        encoded = json.dumps(commands).encode()

        if settings.get("user.addon_debug"):
            print(f"Sending {commands} to {ip}:{port}")

        # Default response if nothing is set
        response = {
            "client": IPCClientResponse.NO_RESPONSE,
            "server": None,
            "values": [],
        }

        # Although the screenreader server will block while processing commands,
        # having a lock client-side prevents errors when sending multiple commands
        with lock:
            try:
                sock.connect((ip, int(port)))
                sock.sendall(encoded)
                # Block until we receive a response
                # We don't want to execute commands until
                # we know the screen reader has the proper settings
                server_response: IPCServerResponse = sock.recv(1024).decode()
                response["server"] = server_response
                response["client"] = IPCClientResponse.SUCCESS
                response["values"] = server_response["returnedValues"]

            except socket.timeout:
                response["client"] = IPCClientResponse.TIMED_OUT
            except Exception:
                response["client"] = IPCClientResponse.GENERAL_ERROR
            finally:
                sock.close()

        checked_result = check_ipc_result(
            (response["client"], response["server"], response["values"])
        )
        return checked_result

    def send_ipc_command(
        command: IPC_COMMAND,
    ) -> RETURNED_VAL:
        """Sends a single command to the screenreader"""
        result: Tuple[list, list] = actions.user.send_ipc_commands([command])
        returned_values = result[1]
        return returned_values[0] if returned_values else None


ORCAContext = Context()
ORCAContext.matches = r"""
tag: user.orca_running
"""


JAWSContext = Context()
JAWSContext.matches = r"""
tag: user.jaws_running
"""
