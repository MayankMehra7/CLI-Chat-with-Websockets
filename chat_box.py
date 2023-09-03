import os
import time
import asyncio
from collections import defaultdict
from copy import deepcopy
from typing import List, Any, Dict, Optional

from rich.align import Align
from rich.text import Text
from rich.console import RenderableType

from textual import events
from textual.app import App
from textual.layouts.dock import DockLayout
from textual.widgets import ScrollView, TreeClick, Static, TreeControl, TreeNode, Header, Placeholder
from textual.widget import Widget
from rich.table import Table
from rich.console import RenderableType
from rich.panel import Panel
from textual import events
from textual_inputs import IntegerInput, TextInput

from message import Message
from client import WsClient

BotList = ["Alice", "Dian"]

def colored(text: str, color: str) -> str:
    return f"[{color}]{text}[/{color}]"

def link_colored(text: str, link: str, color: str) -> str:
    return f"[link={link}][underline]{colored(text, color)}[/underline][/link]"

seperator = f"{colored('─' * 50, 'bold dim black')}"

HELP_TEXT = f"""
{colored("Welcome to ChatBot ...","hot_pink3")}
{colored("ChatBot is TUI (Text User Interface) chat application with a great responsive UI and feel!" , "hot_pink3")}

{seperator}
Bot list:
"""
for botname in BotList:
    HELP_TEXT += \
f"""
    talk with {link_colored(botname, "#", "green")}
"""

class ChatScreen(TreeControl):
    """
    A screen for providing chats
    """
    # colors: https://rich.readthedocs.io/en/stable/appendix/colors.html
    SysColor = "dark_red"
    TextColor = [SysColor, "bright_green", "bright_blue", "navy_blue", "dark_cyan", "purple4"]
    UserNameColor = [SysColor, "plum4", "medium_orchid", "purple", "rosy_brown", "dark_khaki"]
    TimeColor = "bright_black"

    def __init__(self, name: str = "", user: str = ""):
        super().__init__(name, name)
        self.msgs = []
        self.user = user
        self.user_colors_index_dict = {}
        self.user_colors_idx = 0
        self._get_user_color_index("System")
        self._get_user_color_index(user)
        self._tree.hide_root = True

    def _get_user_color_index(self, name):
        if not name:
            return None
        if name in self.user_colors_index_dict:
            return self.user_colors_index_dict[name]

        self.user_colors_index_dict[name] = self.user_colors_idx
        self.user_colors_idx += 1
        return self.user_colors_index_dict[name]

    def set_user(self, user: str):
        self.user = user
        self._get_user_color_index(user)

    def render_node(self, node: TreeNode) -> RenderableType:
        meta = {
            "@click": f"click_label({node.id})",
            "tree_node": node.id,
            "cursor": node.is_cursor,
        }
        self.log(node.label, node.data)
        msg = node.data
        if msg:
            sender = msg.sender
            color_idx = self._get_user_color_index(sender)
            time_str = msg.send_time
            if sender == self.user:
                align = "right"
                label = f"[{self.TimeColor}]{time_str} [{self.TextColor[color_idx]}]{msg.text} :[{self.UserNameColor[color_idx]}]{sender}"
            else:
                align = "left"
                label = f"[{self.UserNameColor[color_idx]}]{sender}: [{self.TextColor[color_idx]}]{msg.text} [{self.TimeColor}]{time_str}"
        else:
            align = "left"
            label = node.label

        label = Text.from_markup(label, justify=align)
        if node.id == self.hover_node:
            label.stylize("bold")

        label.apply_meta(meta)

        return label

    async def clear_chat(self):
        self.root.children.clear()
        self.root.tree.children.clear()
        self.refresh()

    async def push_text(self, msg: Message) -> None:
        if not self.root.expanded:
            await self.root.expand()

        self.msgs.append(msg)
        await self.root.add("", msg)
        self.refresh()

class Headbar(Header):
    """
    Custom Header for Gupshup showing status for the server and a Welcome message
    """

    def __init__(self):
        HEADER_BG = "black"
        HEADER_FG = "magenta"
        super().__init__(tall=False, style=f"{HEADER_FG} on {HEADER_BG}")
        self.status = " Online"

    def watch_status(self, _: str):
        self.refresh()

    def render(self) -> RenderableType:
        header_table = Table.grid(padding=(1, 1), expand=True)
        header_table.style = self.style
        header_table.add_column(justify="left", ratio=0, width=20)
        header_table.add_column("title", justify="center", ratio=1)
        header_table.add_column("clock", justify="center", width=10)
        header_table.add_row(
            self.status,
            self.full_title,
            self.get_clock() if self.clock else "",
        )
        header: RenderableType
        header = Panel(header_table, style=self.style) if self.tall else header_table
        return header

    def watch_tall(self, _: bool) -> None:
        self.tall = False
        self.layout_size = 1

    def on_click(self, _: events.Click) -> None:
        self.tall = False

class Banner(Widget):
    """
    A Banner widget to show the current house/group
    """

    text = Text("Chating", style="bold blue")

    def set_text(self, text: str):
        self.text = Text(text, style="blue")
        self.refresh()

    def render(self) -> RenderableType:
        return Panel(Align.center(self.text))

def percent(percent, total):
    return int(percent * total / 100)


class ChatBox(App):
    """
    The UI Class for Gupshup
    """

    def __init__(
        self,
        user: str,
        ws_url: str,
        *kargs,
        **kwargs,
    ) -> None:
        super().__init__(*kargs, **kwargs)
        self.user = user
        self.ws_url = ws_url
        # client related
        self.cli = WsClient(self.user, self.ws_url)


    @classmethod
    def run(
        cls,
        user: str,
        ws_url: str,
        *kargs,
        **kwargs,
    ) -> None:
        """
        Run the app.
        """

        async def run_ui(app) -> None:
            await app.process_messages()

        app = cls(user, ws_url, *kargs, **kwargs)
        tasks = asyncio.wait([app.cli.repl(), app.server_listen(), run_ui(app)])
        #asyncio.run(tasks)
        asyncio.get_event_loop().run_until_complete(tasks)
        

    async def on_load(self, _: events.Load) -> None:

        # sets up default screen
        self.current_screen = f"{self.user}'s talk"
        self.help_menu_loaded = False

        # some keybindings
        await self.bind(
            "ctrl+b",
            "view.toggle('house_tree')",
            "toggle house tree",
        )
        await self.bind("ctrl+q", "quit", "Quit")
        await self.bind(
            "escape",
            "reset_focus",
            "resets focus to the header",
            show=False,
        )

    async def load_help_menu(self):
        banner = """
        ┬ ┬┌─┐┬  ┌─┐  ┌┬┐┌─┐┌┐┌┬ ┬
        ├─┤├┤ │  ├─┘  │││├┤ ││││ │
        ┴ ┴└─┘┴─┘┴    ┴ ┴└─┘┘└┘└─┘
        """
        await self._clear_screen()
        await self.view.dock(
            Static(Align.center(Text(banner, style="magenta"), vertical="middle")),
            size=percent(20, os.get_terminal_size()[1]),
        )
        await self.view.dock(
            Static(
                Align.center(
                    Text("-- Press ctrl+p to exit --", style="bold magenta"),
                    vertical="middle",
                )
            ),
            edge="bottom",
            size=percent(10, os.get_terminal_size()[1]),
        )
        await self.view.dock(self.help_scroll)

    async def on_key(self, event: events.Key):
        if event.key == "ctrl+p":
            if self.help_menu_loaded:
                await self.refresh_screen()
            else:
                await self.load_help_menu()

            self.help_menu_loaded = not self.help_menu_loaded
            return

        if self.help_menu_loaded:
            if event.key in ("j", "down"):
                self.help_scroll.scroll_up()
            elif event.key in ("k", "up"):
                self.help_scroll.scroll_down()
            elif event.key in ("g", "home"):
                await self.help_scroll.key_home()
            elif event.key in ("G", "end"):
                await self.help_scroll.key_end()
            else:
                return

        if event.key == "enter":
            await self.action_send_message()

    async def perform_connection_disable(self, *_) -> None:
        self.headbar.status = "ﮡ Can't connect"

    async def perform_connection_enable(self, *_) -> None:
        self.headbar.status = " Online"

    async def perform_push_text(self, message: Message, local=False) -> None:
        """
        Performs adding all the text messages to their respective locations
        """
        screen = self.current_screen
        await self.chat_screen[screen].push_text(message)
        await self.chat_scroll[screen].key_end()

        if not local:  # check if local/offline data is not being pushed
            self.chat_screen[screen].refresh(layout=True)

    async def perform_clear_chat(self, message: Message) -> None:
        screen = self.current_screen
        await self.chat_screen[screen].clear_chat()
        self.chat_screen[screen].refresh()

    async def execute_message(self, message: Message) -> None:
        """
        Executes the messages recieved from the server
        """

        cmd = f"self.perform_{message.action}(message)"
        await eval(cmd)

    async def on_mount(self, _: events.Mount) -> None:
        y = os.get_terminal_size()[1]

        self.title = "ChatBox"
        self.headbar = Headbar()
        self.input_box = TextInput(
            placeholder=Text("Say something here...", style="dim white")
        )

        self.banner = Banner()
        self.banner.set_text(f'{self.user} is talking to Bot')
        self.help_scroll = ScrollView(Align.center(HELP_TEXT))
        self.chat_screen = defaultdict(ChatScreen)
        self.chat_scroll = defaultdict(ScrollView)

        await self.populate_local_data()
        await self.refresh_screen()
        await self.input_box.focus()

    async def populate_local_data(self) -> None:
        """
        Populates the app with offline data stored in the system
        """

        self.refresh()

    async def on_resize(self, _: events.Resize) -> None:
        await self.refresh_screen()

    async def action_quit(self) -> None:
        """
        Clean quit saving the data
        """
#        self.client.save_chats()
#        self.client.close_connection()

        await super().action_quit()

    async def _clear_screen(self) -> None:
        # clears all the widgets from the screen..and re render them all
        # Why? you ask? this was the only way at the time of this writing

        if isinstance(self.view.layout, DockLayout):
            self.view.layout.docks.clear()
        self.view.widgets.clear()

    async def refresh_screen(self) -> None:
        """
        Refresh the screen by repainting all the widgets
        """

        await self._clear_screen()
        x, y = os.get_terminal_size()

        rseperator = lseperator = "\n" * percent(10, y) + "┃\n" * percent(
            75, y
        )

        if self.current_screen not in self.chat_scroll:
            self.chat_screen[self.current_screen].set_user(self.user)
            self.chat_scroll[self.current_screen] = ScrollView(
                self.chat_screen[self.current_screen],
                gutter=(0, 1),
            )

        self.chat_scroll[self.current_screen].animate(
            "y",
            10**5,
            # A large enough value to make sure it really scrolls down to the end
            # ..will have to probably change this
            easing="none",
            speed=1000,
        )

        await self.view.dock(self.headbar, name="headbar")
        # RIGHT WIDGETS

        await self.view.dock(
            ScrollView(),
            edge="right",
            size=int(0.15 * x),
            name="member_list",
        )
        await self.view.dock(
            Static(rseperator),
            edge="right",
            size=1,
            name="rs",
        )

        # LEFT WIDGETS
        await self.view.dock(
            ScrollView(),
            edge="left",
            size=percent(20, x),
            name="house_tree",
        )
        await self.view.dock(
            Static(lseperator),
            edge="left",
            size=1,
            name="ls",
        )

        # MIDDLE WIDGETS
        await self.view.dock(
            self.banner,
            size=percent(10, y),
            name="banner",
        )
        await self.view.dock(
            self.chat_scroll[self.current_screen],
            size=percent(75, y),
            name="chat_screen",
        )

        await self.view.dock(
            self.input_box,
            size=percent(10, y),
            name="input_box",
        )
        self.refresh(layout=True)  # A little bit too cautious

    async def action_reset_focus(self):
        await self.headbar.focus()

    async def server_listen(self) -> None:
        """
        Method to continously listen for new messages from the server
        """

        # Is being called every 0.1 seconds to update
        # Proposal for a `call_threaded` function has not been merged yet..
        # see: https://github.com/Textualize/textual/issues/85

        # recv message from queue
        while True:
            msg = await self.cli.arecv()
            await self.on_flush_message(msg)

    async def on_flush_message(self, message: Message):
        if message.action:
            await self.execute_message(message)
        else:
            await self.perform_push_text(message, local=True)

    async def action_send_message(self):
        """
        Empties the input box and sends the message to the server
        """

        value = self.input_box.value.strip()
        if not value:
            return

        msg = Message(
            sender=self.user,
            text=value,
            created_at=int(time.time())
        )
        await self.on_flush_message(msg)
        self.input_box.value = ""
        # to send message
        await self.cli.asend(msg)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='chat log')
    parser.add_argument("-u", '--user_name', help="chat user name", type=str, default="User")
    parser.add_argument("-s", '--ws_url', help="ws url", type=str, default="ws://localhost:5555")
    args = parser.parse_args()
    ws_url = f'{args.ws_url}/ws/{args.user_name}?token=default_tokne'
    ChatBox.run(user=args.user_name, ws_url=ws_url)

if __name__ == '__main__':
    main()
