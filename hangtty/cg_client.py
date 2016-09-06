import re
import fnmatch
import sys
import signal
import curses
import asyncio
import hangups
from enum import Enum
from pync import Notifier

import logging
logger = logging.getLogger(__name__)

CG_PROMPT = "hangtty! # "
CG_INFO = "\n=======> "
CG_TABS = 7

CG_INIT = 1
CG_CONNECTING = 2
CG_CONNECTED = 2
CG_CONVLOADING = 3
CG_CONVLOADED = 4
CG_HISTORYLOADING = 6
CG_HISTORYLOADED = 7
CG_EXITING = 8
CG_READY = 20

class CGClient():
        def __init__(self, dev_debug_enable, keys, cg_token_path):
            self.cg_loop = None

            self.cg_bw = None # initscr base window
            self.cg_mw = None # main window
            self.cg_bar = None # status bar
            self.cg_st = CG_INIT
            self.cg_mx = 0 # max X
            self.cg_my = 0 # max Y
            self.cg_tabs = []
            self.cg_tabconvs = []
            self.cg_tabix = 0

            self.cg_cur_chat_user = None
            self.cg_cur_conv = None
            self.cg_buf = []
            self.cg_history = []
            self.cg_hix = 0
            self.cg_keys = keys
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
                    "help" : CGClient.cgx_help,
                    }
            signal.signal(signal.SIGINT, self.cg_ctrlc)
            signal.siginterrupt(signal.SIGINT, False)

        def cg_ctrlc(self, signum, frame):
            if(self.cg_tabix != 0):
                self.cg_info("Leaving conversation " + self.cg_cur_chat_user)
                self.cg_tabs.remove(self.cg_cur_chat_user)
                self.cg_tabconvs.remove(self.cg_cur_conv)
                self.cg_tabix = 0
                self.cg_mw.erase()
                self.lx = len(CG_PROMPT) + 1
                self.cg_prompt()
                self.cg_update()
            else:
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
            self.cg_info("Connected")
            self.cg_st = CG_CONNECTED
            self.cg_info("Loading conversations... Please wait ... ")
            self.lx = 1 + len(CG_PROMPT)
            self.cg_loop.call_later(0.1, self.cg_io_callback)
            self.cg_ulist, self.cg_clist = (
                yield from hangups.build_user_conversation_list(self.cg_client)
            )
            self.cg_clist.on_event.add_observer(self.cg_conv_event)
            self.cg_st = CG_CONVLOADING

        # display functions
        def cg_get_prompt(self):
            if(self.cg_tabix != 0):
                return "Myself >> "
            else:
                return CG_PROMPT

        def cg_prompt(self):
            strx = self.cg_get_prompt()
            self.cg_mw.addstr(strx)
            self.cg_update()

        def cg_write_byte(self, ch):
            self.cg_mw.addch(ch);
            self.cg_update()

        def cg_info(self, text):
            self.cg_mw.attron(curses.color_pair(3))
            self.cg_write_nop(CG_INFO + text);
            self.cg_mw.attroff(curses.color_pair(3))

        def cg_write_nop(self, text):
            self.cg_mw.addstr(text);
            self.cg_update()

        def cg_write_tab(self):
            if(self.cg_bar != None):
                self.cg_bar.attron(curses.color_pair(4))
                self.cg_bar.hline(' ', self.cg_bar_len)
                self.cg_bar.attroff(curses.color_pair(4))
                sz = int(self.cg_bar_len / CG_TABS)
                cur = 0
                pos = 0
                for item in self.cg_tabs:
                    lft = sz - len(item)
                    strx = ""
                    for i in range(int(lft/2)):
                        strx += " "
                    strx += item
                    for i in range(int(lft/2)):
                        strx += " "
                    if(self.cg_tabix == cur):
                        self.cg_bar.attron(curses.color_pair(5))
                        self.cg_bar.addstr(0, pos, strx)
                        self.cg_bar.attroff(curses.color_pair(5))
                    else:
                        self.cg_bar.attron(curses.color_pair(4))
                        self.cg_bar.addstr(0, pos, strx)
                        self.cg_bar.attroff(curses.color_pair(4))
                    pos += int(sz)
                    cur += 1
                self.cg_bar.refresh()

        def cg_update(self):
            y, x = self.cg_mw.getyx()
            self.cg_write_tab()
            self.cg_mw.refresh()
            self.cg_mw.move(y, x)

        # end display functions

        def cg_start_screen(self):
            self.cg_bw = curses.initscr()
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_RED, -1)
            curses.init_pair(3, curses.COLOR_BLUE, -1)
            curses.init_pair(4, -1, curses.COLOR_CYAN)
            curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)
            curses.noecho()
            curses.cbreak()
            curses.halfdelay(10)
            self.cg_bw.keypad(1)
            self.cg_bw.scrollok(1)
            self.cg_bw.idlok(1)

            self.cg_my, self.cg_mx = self.cg_bw.getmaxyx()
            self.cg_mw = curses.newwin(self.cg_my - 2, self.cg_mx, 0, 0)
            self.cg_mw.keypad(1)
            self.cg_mw.scrollok(1)
            self.cg_mw.idlok(1)
            self.cg_mw.refresh()

            self.cg_bar_len = self.cg_mx
            self.cg_bar = curses.newwin(1, self.cg_mx, self.cg_my - 1, 0)
            self.cg_bar.refresh()
            self.cg_tabs.append("Shell")
            self.cg_tabconvs.append(None)
            self.cg_info("Connecting to Google Hangouts... Please wait ... ");

        def cg_reset_screen(self):
            curses.nocbreak()
            self.cg_bw.keypad(0)
            curses.echo()
            curses.endwin()

        def cg_io_callback(self):
            if(self.cg_st == CG_READY):
                self.cg_try_accept_input()
            elif(self.cg_st == CG_CONVLOADING):
                if(self.cg_clist != None and self.cg_ulist != None):
                    self.cg_st = CG_READY
                    self.cg_info("Done\n")
                    self.cg_prompt()
            elif(self.cg_st == CG_HISTORYLOADING):
                self.cg_write_nop(".")
            elif(self.cg_st == CG_HISTORYLOADED):
                self.cg_st = CG_READY
                self.cg_show_history()
                self.cg_prompt()
            else:
                pass
            if(self.cg_st != CG_EXITING):
                self.cg_io = self.cg_loop.call_later(0.1, self.cg_io_callback)

        def cg_backch(self):
            if(len(self.cg_buf) == 0):
                return
            y, x = self.cg_mw.getyx()
            if(x >= self.lx):
                self.cg_mw.delch(y, x - 1)
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
            if(isinstance(conv_event, hangups.ChatMessageEvent) == False):
                return
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
            y, x = self.cg_mw.getyx()
            self.cg_mw.move(y, 0)
            if(me == 0):
                self.cg_mw.attron(curses.color_pair(1))
            self.cg_write_nop(mstr)
            if(me == 0):
                self.cg_mw.attroff(curses.color_pair(1))

        def cg_conv_event(self, conv_event):
            conv = self.cg_clist.get(conv_event.conversation_id)
            user_name = self._cgutil_get_conv_name(conv)
            user = conv.get_user(conv_event.user_id)
            if(user.is_self):
                return
            notmsg = "Message from " + user_name
            Notifier.notify(notmsg, title='hangtty!')
            if(conv == self.cg_cur_conv and self.cg_tabix != 0):
                mstr = self.cg_cur_chat_user + " << " + conv_event.text + "\n"
                y, x = self.cg_mw.getyx()
                self.cg_mw.move(y, 0)
                self.cg_mw.attron(curses.color_pair(1))
                self.cg_write_nop(mstr)
                self.cg_mw.attroff(curses.color_pair(1))
                self.cg_write_nop("Myself >> " + ''.join(self.cg_buf))
            else:
                mstr = "[ " + user_name + " << " + conv_event.text + " ]\n"
                y, x = self.cg_mw.getyx()
                self.cg_mw.move(y, 0)
                self.cg_mw.attron(curses.color_pair(2))
                self.cg_write_nop(mstr)
                self.cg_mw.attroff(curses.color_pair(2))
                self.cg_write_nop(self.cg_get_prompt())

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
            self.cg_st = CG_HISTORYLOADED
            future.result()

        def cg_is_present_conv(self, label):
            i = 0
            for lbl in self.cg_tabs:
                if(lbl == label):
                    return i
                i += 1
            return -1

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
                    ix = self.cg_is_present_conv(label)
                    if(ix != -1):
                        self.cg_goindex(ix)
                        return
                    if(len(self.cg_tabs) >= CG_TABS):
                        self.cg_info("No more tabs. Leave some conversation")
                        return
                    self.cg_info("Conversation with " + label)
                    self.cg_cur_chat_user = label
                    self.cg_tabs.append(label)
                    self.cg_tabconvs.append(conv)
                    self.cg_tabix = len(self.cg_tabs) - 1
                    self.lx = len("Myself >> ") + 1
                    self.cg_cur_conv = conv
                    self.cg_st = CG_HISTORYLOADING
                    future =  asyncio.async(self.cg_download_msgs())
                    future.add_done_callback(self.cg_download_callback)
                    self.cg_info("Loading history... Please wait ... ")
                    return
                i = i + 1

        def cgx_listconv(self, args):
            do_mat = 0
            if(self.cg_clist == None):
                return
            limit = 10
            if(args != None):
                if(len(args) == 2 and args == "-a"):
                    limit = 1000
                else:
                    limit = 1000
                    do_mat = 1
                    regex = fnmatch.translate(args)
                    pat = re.compile(regex)
            self.cg_write_byte('\n')
            i = 1
            convs = sorted(self.cg_clist.get_all(), reverse=True, key=lambda c:c.last_modified)
            for conv in convs:
                label = self._cgutil_get_conv_name(conv)
                if(do_mat == 1):
                    if(bool(pat.match(label))):
                        self.cg_write_nop(str(i) + ") " + label + "\n")
                else:
                    self.cg_write_nop(str(i) + ") " + label + "\n")
                i = i + 1
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
            self.cg_st = CG_EXITING

        def cgx_cls(self, cmd):
            self.cg_mw.erase()
            self.cg_prompt()

        def cgx_help(self, cmd):
            f = open('help.txt', 'r')
            if(f == None):
                self.cg_info("Could not find help file")
                return
            for line in f:
                self.cg_write_nop(line)

        def cgx_quitconv(self, cmd):
            if(self.cg_cur_chat_user == None):
                return
            self.cg_info("Leaving conversation " + self.cg_cur_chat_user)
            self.cg_cur_chat_user = None
            self.lx = len(CG_PROMPT) + 1
            self.cg_cur_conv = None

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
            self.cg_history.insert(0, cmd)
            self.cg_hix = 0

        def cg_downkey(self):
            if(self.cg_tabix == 0):
                pass
            elif(self.cg_hix > 0):
                self.cg_hix -= 1
                self.cg_buf = []
                cmd = ''.join(self.cg_history[self.cg_hix])
                y, x = self.cg_mw.getyx()
                self.cg_mw.move(y, 0)
                self.cg_mw.clrtoeol()
                self.cg_prompt()
                for x in cmd:
                    self.cg_handlech(x)

        def cg_upkey(self):
            if(self.cg_tabix == 0):
                pass
            elif(len(self.cg_history) > self.cg_hix):
                self.cg_buf = []
                cmd = ''.join(self.cg_history[self.cg_hix])
                y, x = self.cg_mw.getyx()
                self.cg_mw.move(y, 0)
                self.cg_mw.clrtoeol()
                self.cg_prompt()
                for x in cmd:
                    self.cg_handlech(x)
                self.cg_hix += 1

        def cg_takeactions(self, op, val):
            if(op != 0):
                # its a command
                self.cg_log_history(val)
                parts = val.split(None, 1)
                self.cg_menu_op(parts)
            else:
                # its a message
                if(len(val) > 0):
                    self.cg_send_chat(val)

        def cg_runcmd(self):
            if(len(self.cg_buf) > 0):
                if(self.cg_tabix == 0):
                    op = 1
                else:
                    op = 0
                cmd = ''.join(self.cg_buf)
                self.cg_buf = []
                self.cg_takeactions(op, cmd)

        def cg_goindex(self, ix):
            self.cg_tabix = ix
            self.cg_mw.erase()
            if(self.cg_tabix != 0):
                self.cg_cur_chat_user = self.cg_tabs[self.cg_tabix]
                self.cg_cur_conv = self.cg_tabconvs[self.cg_tabix]
                self.cg_show_history()
            self.cg_prompt()
            self.cg_update()

        def cg_goleft(self):
            if(self.cg_tabix == 0):
                self.cg_tabix = len(self.cg_tabs) - 1
            else:
                self.cg_tabix -= 1
            self.cg_mw.erase()
            if(self.cg_tabix != 0):
                self.cg_cur_chat_user = self.cg_tabs[self.cg_tabix]
                self.cg_cur_conv = self.cg_tabconvs[self.cg_tabix]
                self.cg_show_history()
            self.cg_prompt()
            self.cg_update()

        def cg_goright(self):
            if(self.cg_tabix == len(self.cg_tabs) - 1):
                self.cg_tabix = 0
            else:
                self.cg_tabix += 1
            self.cg_mw.erase()
            if(self.cg_tabix != 0):
                self.cg_cur_chat_user = self.cg_tabs[self.cg_tabix]
                self.cg_cur_conv = self.cg_tabconvs[self.cg_tabix]
                self.cg_show_history()
            self.cg_prompt()
            self.cg_update()

        def cg_handle_input(self, ch):
            if(ch == curses.KEY_MOUSE):
                return

            if ch == ord('\n'):
                self.cg_runcmd()
                self.cg_write_byte('\n')
                self.cg_prompt()
            elif ch == curses.KEY_BACKSPACE:
                self.cg_backch()
            elif ch == curses.KEY_UP:
                self.cg_upkey()
            elif ch == curses.KEY_DOWN:
                self.cg_downkey()
            elif ch == curses.KEY_SLEFT:
                self.cg_goleft()
            elif ch == curses.KEY_SRIGHT:
                self.cg_goright()
            else:
                self.cg_handlech(chr(ch))

        def cg_try_accept_input(self):
            while 1:
                ch = self.cg_mw.getch()
                if(ch == -1):
                    return
                self.cg_handle_input(ch)

        def cg_run(self):
            self.cg_start_screen()
            cookies = self.cg_login2hangouts(self.cg_token_path)
            self.cg_client = hangups.Client(cookies)
            self.cg_client.on_connect.add_observer(self.cg_on_connect_callback)
            self.cg_client.on_disconnect.add_observer(self.cg_on_disconnect_callback())

            self.cg_st = CG_CONNECTING
            self.cg_loop = asyncio.get_event_loop()
            try:
                self.cg_loop.run_until_complete(self.cg_client.connect())
            finally:
                self.cg_reset_screen()
                self.cg_loop.close()
