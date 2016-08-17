import sys
import signal
import curses
import asyncio
import hangups
from enum import Enum

import logging
logger = logging.getLogger(__name__)

CG_PROMPT = "hangtty! # "
CG_INFO = "\n=======> "

class CGState(Enum):
    INIT = 1
    CONNECTED = 2
    CHATTING = 3
    EXITING = 4

CG_INCHAT_CMD = 1
CG_CMD = 2
CG_INCHAT_MSG = 3

class CGClient():
        def __init__(self, dev_debug_enable, keys, cg_token_path):
            self.cg_win = ""
            self.cg_download_state = 0
            self.cg_downloading = 0
            self.cg_loop = ""
            self.cg_cur_chat_user = ""
            self.cg_cur_conv = None
            self.cg_buf = []
            self.cg_history = []
            self.cg_keys = keys
            self.cg_state = CGState.INIT
            self.dev_debug_enable = dev_debug_enable
            self.cg_debug("ctor" + str(self))
            self.cg_debug("token in " + cg_token_path)
            self.cg_token_path = cg_token_path
            self.cg_ulist = None
            self.cg_clist = None
            self.cg_commands_dict = {
                    "quit" : CGClient.cgx_quit,
                    "exit" : CGClient.cgx_quit,
                    "ls"   : CGClient.cgx_list,
                    "ps"   : CGClient.cgx_listconv,
                    "go"   : CGClient.cgx_gochat,
                    "qq"   : CGClient.cgx_quitconv,
                    "cls"  : CGClient.cgx_cls,
                    }
            signal.signal(signal.SIGINT, self.cg_ctrlc)
            signal.siginterrupt(signal.SIGINT, False)

        def cg_ctrlc(self, signum, frame):
            self.cgx_quit(None)

        def cg_debug(self, debug_str):
            if self.dev_debug_enable == 1:
                logger.log(logging.DEBUG, debug_str)
            else:
                logger.log(logging.DEBUG, debug_str)

        def cg_login2hangouts(self, token_file):
            try:
                cookies = hangups.auth.get_auth_stdin(token_file)
                self.cg_debug(str(cookies))
                return cookies
            except Exception as e:
                self.cg_debug(e);
                self.cg_reset_screen()
                print("Login failed. Exiting...")

        @asyncio.coroutine
        def cg_on_disconnect_callback(self):
            self.cg_info("Disconnecting. Exiting ...")

        @asyncio.coroutine
        def cg_on_connect_callback(self):
            self.cg_info("Connected\n")
            self.cg_state = CGState.CONNECTED
            self.lx = 1 + len(CG_PROMPT)
            self.cg_prompt()
            self.cg_loop.call_later(0.1, self.cg_io_callback)
            self.cg_ulist, self.cg_clist = (
                yield from hangups.build_user_conversation_list(self.cg_client)
            )
            self.cg_clist.on_event.add_observer(self.cg_conv_event)

        # display functions
        def cg_get_prompt(self):
            if(self.cg_state == CGState.CHATTING):
                return "Myself >> "
            else:
                return CG_PROMPT

        def cg_prompt(self):
            strx = self.cg_get_prompt()
            self.cg_win.addstr(strx)
            self.cg_update()

        def cg_write_byte(self, ch):
            self.cg_win.addch(ch);
            self.cg_update()

        def cg_info(self, text):
            self.cg_win.attron(curses.color_pair(3))
            self.cg_write_nop(CG_INFO + text);
            self.cg_win.attroff(curses.color_pair(3))

        def cg_write_nop(self, text):
            self.cg_win.addstr(text);
            self.cg_update()

        def cg_update(self):
            self.cg_win.refresh()
        # end display functions

        def cg_start_screen(self):
            self.cg_win = curses.initscr()
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
            curses.init_pair(3, curses.COLOR_BLUE, -1)
            curses.noecho()
            curses.cbreak()
            curses.halfdelay(10)
            self.cg_win.keypad(1)
            self.cg_win.scrollok(1)
            self.cg_win.idlok(1)
            self.cg_info("Connecting to Google Hangouts... Please wait ... ");

        def cg_reset_screen(self):
            curses.nocbreak()
            self.cg_win.keypad(0)
            curses.echo()
            curses.endwin()

        def cg_io_callback(self):
            if(self.cg_download_state == 1):
                if(self.cg_downloading == 0):
                    self.cg_show_history()
                    self.cg_download_state = 0
                    self.cg_prompt()
            else:
                self.cg_try_accept_input()
            if(self.cg_state != CGState.EXITING):
                self.cg_io = self.cg_loop.call_later(0.1, self.cg_io_callback)

        def cg_backch(self):
            y, x = self.cg_win.getyx()
            if(x >= self.lx):
                self.cg_win.delch(y, x - 1)
                self.cg_buf.pop()
                self.cg_update()

        def cg_handlech(self, ch):
            self.cg_buf.append(ch)
            self.cg_write_byte(ch)

        def cgx_talk(self, args):
            self.cg_write_nop("Initiating session to " + args)

        # from hangups.ui utils
        def _cgutil_get_conv_name(self, conv, truncate=False, show_unread=False):
            num_unread = len([conv_event for conv_event in conv.unread_events if
                              isinstance(conv_event, hangups.ChatMessageEvent) and
                              not conv.get_user(conv_event.user_id).is_self])
            if show_unread and num_unread > 0:
                postfix = ' ({})'.format(num_unread)
            else:
                postfix = ''
            if conv.name is not None:
                return conv.name + postfix
            else:
                participants = sorted(
                    (user for user in conv.users if not user.is_self),
                    key=lambda user: user.id_
                )
                names = [user.first_name for user in participants]
                if len(participants) == 0:
                    return "Empty Conversation" + postfix
                if len(participants) == 1:
                    return participants[0].full_name + postfix
                elif truncate and len(participants) > 2:
                    return (', '.join(names[:2] + ['+{}'.format(len(names) - 2)]) +
                            postfix)
                else:
                    return ', '.join(names) + postfix

        def cg_send_chat(self, val):
            segments = hangups.ChatMessageSegment.from_str(val)
            future = asyncio.async(self.cg_cur_conv.send_message(segments, image_file=None))
            future.add_done_callback(lambda future: future.result())

        def cg_conv_event_with_self(self, conv_event):
            conv = self.cg_clist.get(conv_event.conversation_id)
            user_name = self._cgutil_get_conv_name(conv)
            user = conv.get_user(conv_event.user_id)
            if(user.is_self):
                me = 1
                lbl = "Myself >> "
            else:
                me = 0
                lbl = user_name + " << "
            mstr = lbl + conv_event.text + "\n"
            y, x = self.cg_win.getyx()
            self.cg_win.move(y, 0)
            if(me == 0):
                self.cg_win.attron(curses.color_pair(1))
            self.cg_write_nop(mstr)
            if(me == 0):
                self.cg_win.attroff(curses.color_pair(1))

        def cg_conv_event(self, conv_event):
            conv = self.cg_clist.get(conv_event.conversation_id)
            user_name = self._cgutil_get_conv_name(conv)
            user = conv.get_user(conv_event.user_id)
            if(user.is_self):
                return
            if(conv == self.cg_cur_conv):
                mstr = self.cg_cur_chat_user + " << " + conv_event.text + "\n"
                y, x = self.cg_win.getyx()
                self.cg_win.move(y, 0)
                self.cg_win.attron(curses.color_pair(1))
                self.cg_write_nop(mstr)
                self.cg_win.attroff(curses.color_pair(1))
                self.cg_write_nop("Myself >> " + ''.join(self.cg_buf))
            else:
                mstr = "[ " + user_name + " << " + conv_event.text + " ]\n"
                y, x = self.cg_win.getyx()
                self.cg_win.move(y, 0)
                self.cg_win.attron(curses.color_pair(2))
                self.cg_write_nop(mstr)
                self.cg_win.attroff(curses.color_pair(2))
                if(self.cg_state == CGState.CHATTING):
                    self.cg_write_nop("Myself >> " + ''.join(self.cg_buf))
                else:
                    self.cg_write_nop(CG_PROMPT + ''.join(self.cg_buf))

        def cg_show_history(self):
            if(self.cg_cur_conv.events):
                for event in self.cg_cur_conv.events:
                    self.cg_conv_event_with_self(event)

        @asyncio.coroutine
        def cg_download_msgs(self):
            conv_events = yield from self.cg_cur_conv.get_events(
                self.cg_cur_conv.events[0].id_
            )

        def cg_download_callback(self, future):
            self.cg_downloading = 0
            future.result()

        def cgx_gochat(self, args):
            if(args == None):
                self.cg_info("usage: go <conversation_index>")
                return
            if(self.cg_clist == None):
                return
            find = int(args)
            i = 1
            convs = sorted(self.cg_clist.get_all(), reverse=True, key=lambda c:c.last_modified)
            for conv in convs:
                label = self._cgutil_get_conv_name(conv)
                if(i == find):
                    self.cg_info("Conversation with " + label)
                    self.cg_cur_chat_user = label
                    self.lx = len("Myself >> ") + 1
                    self.cg_cur_conv = conv
                    self.cg_state = CGState.CHATTING
                    self.cg_download_msgs()
                    self.cg_downloading = 1
                    self.cg_download_state = 1
                    future =  asyncio.async(self.cg_download_msgs())
                    future.add_done_callback(self.cg_download_callback)
                    self.cg_info("Loading history...")
                    return
                i = i + 1

        def cgx_listconv(self, args):
            if(self.cg_clist == None):
                return
            limit = 10
            if(args != None and args == "-a"):
                limit = 1000
            self.cg_write_byte('\n')
            i = 1
            convs = sorted(self.cg_clist.get_all(), reverse=True, key=lambda c:c.last_modified)
            for conv in convs:
                label = self._cgutil_get_conv_name(conv)
                self.cg_write_nop(str(i) + ") " + label)
                i = i + 1
                self.cg_write_nop("\n")
                if(i > limit):
                    return

        def cgx_list(self, cmd):
            if(self.cg_ulist == None):
                return
            i = 1
            self.cg_write_byte('\n')
            for user in sorted(self.cg_ulist.get_all(), key=lambda u: u.full_name):
                dstr = user.full_name
                self.cg_write_nop(str(i) + ") " + dstr)
                i = i + 1
                self.cg_write_nop("\n")

        def cgx_quit(self, cmd):
            future = asyncio.async(self.cg_client.disconnect())
            future.add_done_callback(lambda future: future.result())
            self.cg_info("Exiting . . .")
            self.cg_state = CGState.EXITING

        def cgx_cls(self, cmd):
            self.cg_win.erase()
            self.cg_prompt()

        def cgx_quitconv(self, cmd):
            self.cg_info("Leaving conversation " + self.cg_cur_chat_user)
            self.cg_cur_chat_user = None
            self.lx = len(CG_PROMPT) + 1
            self.cg_cur_conv = None
            self.cg_state = CGState.CONNECTED

        def cg_menu_op(self, args):
            if(len(args) == 0):
                return
            if args[0] in self.cg_commands_dict:
                if len(args) == 1:
                    vargs = None
                else:
                    vargs = args[1]
                self.cg_commands_dict[args[0]](self, vargs)

        def cg_log_history(self, cmd):
            self.cg_history.append(cmd)

        def cg_upkey(self):
            pass

        def cg_takeactions(self, op, val):
            if(op == CG_CMD):
                self.cg_log_history(val)
                parts = val.split(None, 1)
                self.cg_menu_op(parts)
            elif(op == CG_INCHAT_MSG):
                if(len(val) > 0):
                    self.cg_send_chat(val)
            elif(op == CG_INCHAT_CMD):
                if(len(val) > 0):
                    val = val[1:]
                    parts = val.split(None, 1)
                    self.cg_menu_op(parts)

        def cg_runcmd(self):
            if(len(self.cg_buf) > 0):
                if(self.cg_state == CGState.CHATTING and self.cg_buf[0] == '\\'):
                    op = CG_INCHAT_CMD
                elif(self.cg_state == CGState.CHATTING):
                    op = CG_INCHAT_MSG
                else:
                    op = CG_CMD
                cmd = ''.join(self.cg_buf)
                self.cg_buf = []
                self.cg_takeactions(op, cmd)

        def cg_handle_input(self, ch):
            if ch == ord('\n'):
                self.cg_runcmd()
                self.cg_write_byte('\n')
                self.cg_prompt()
            elif ch == curses.KEY_BACKSPACE:
                self.cg_backch()
            elif ch == curses.KEY_UP:
                self.cg_upkey()
            else:
                self.cg_handlech(chr(ch))

        def cg_try_accept_input(self):
            while 1:
                ch = self.cg_win.getch()
                if(ch == -1):
                    return
                self.cg_handle_input(ch)

        def cg_run(self):
            print("Connecting... Please wait...\n")
            cookies = self.cg_login2hangouts(self.cg_token_path)
            self.cg_client = hangups.Client(cookies)
            self.cg_client.on_connect.add_observer(self.cg_on_connect_callback)
            self.cg_client.on_disconnect.add_observer(self.cg_on_disconnect_callback())
            self.cg_start_screen()

            try:
                self.cg_loop = asyncio.get_event_loop()
            except NotImplementedError:
                pass
            try:
                self.cg_loop.run_until_complete(self.cg_client.connect())
            finally:
                self.cg_reset_screen()
                self.cg_loop.close()
