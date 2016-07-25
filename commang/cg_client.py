import sys
import urwid
import asyncio
import hangups
from enum import Enum

import logging
logging.getLogger(__name__)

class CGState(Enum):
    INIT = 1
    CONNECTING = 1
    CONNECTED = 2

cg_palette = [
              ('loading', '', ''),
              ('userlist', '', ''),
              ('active_chat', '', ''),
              ('inactive_notify', '', ''),
              ]

class CGClient:
        def __init__(self, dev_debug_enable, cg_token_path):
            self.cg_state = CGState.INIT
            self.dev_debug_enable = dev_debug_enable
            self.cg_debug("ctor" + str(self))
            self.cg_debug("token in " + cg_token_path)
            self.cg_token_path = cg_token_path

            
        def cg_active_widget(self):
            if self.cg_state == CGState.INIT:
                text = urwid.Text(('loading', "Connecting to hangouts..."))
                widget = urwid.Filler(text)
                return widget                            
            
        def cg_debug(self, debug_str):
            if self.dev_debug_enable == 1:
                logging.log(logging.DEBUG, debug_str)
            else:
                logging.log(logging.DEBUG, debug_str)
            
            
        def cg_login2hangouts(self, token_file):
            try:
                cookies = hangups.auth.get_auth_stdin(token_file)
                self.cg_debug(str(cookies))
                return cookies
            except hangups.GoogleAuthError as e:
                self.cg_debug("Login failed: " + str(e));
                print("Login failed: " + str(e))
                sys.exit(1)
            
        @asyncio.coroutine
        def cg_on_connect_callback(self):
            print("connected")
            self.cg_debug("[cb] connected")
        
        
        def cg_input_filter(self, keys, _):
            if keys == [self._keys['menu']]:
                if self._urwid_loop.widget == self._tabbed_window:
                    self._show_menu()
                else:
                    self._hide_menu()
            elif keys == [self._keys['quit']]:
                self._on_quit()
            else:
                return keys
        
        def cg_run(self):
            cookies = self.cg_login2hangouts(self.cg_token_path)
            self.cg_client = hangups.Client(cookies)
            self.cg_client.on_connect.add_observer(self.cg_on_connect_callback)
            loop = asyncio.get_event_loop()
            self.cg_urwid_loop = urwid.MainLoop(self.cg_active_widget(),
                                                cg_palette,
                                                handle_mouse=False,
                                                input_filter=self.cg_input_filter,
                                                event_loop=urwid.AsyncioEventLoop(loop=loop))
            self.cg_urwid_loop.screen.set_terminal_properties()
            self.cg_urwid_loop.start()
            try:
                loop.run_until_complete(self.cg_client.connect())
            finally:
                self.cg_urwid_loop.stop()
                loop.close()
