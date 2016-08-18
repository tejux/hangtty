# hangtty is a command-line-hangout client.
# it uses the hangups hangout library (https://github.com/tdryer/hangups)
# a lot of code was done by reading https://github.com/xmikos/hangupsbot

import os
import sys
import logging
import argparse

from cg_client import CGClient
from appdirs import AppDirs

import logging
logger = logging.getLogger(__name__)

__cgversion__ = "1.0.0"

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# developer debug level, dumps detailed debug logs on stderr
dev_debug_enable = 0

def cg_start_client(args):
    global cg_token_path

    cg = CGClient(dev_debug_enable, {
                  'next_tab' : args.key_next_tab, 
                  'prev_tab' : args.key_prev_tab,
                  'close_tab' : args.key_close_tab, 
                  'quit' : args.key_quit
                  },
                  cg_token_path)
    cg_log('created object' + str(cg))
    cg.cg_run()

def cg_log(debug_str):
    global dev_debug_enable

    if dev_debug_enable == 1:
        logger.log(logging.DEBUG, debug_str)
    else:
        logger.log(logging.DEBUG, debug_str)

def cg_create_default_dirs(args):
    for path in [args.log, args.token]:
        dirn = os.path.dirname(path)
        if dirn and not os.path.isdir(dirn):
            try:
                os.makedirs(dirn)
            except Exception as e:
                sys.exit('Could not create directory: {}').format(e)

def cg_log_init():
    global dev_debug_enable

    dpath = os.path.join(os.path.abspath(os.path.curdir), '.debug')
    if os.path.isfile(dpath):
        print("enable debug")
        dev_debug_enable = 1

def cg_main():
    global cg_token_path
    global dev_debug_enable

    cg_log_init()
    cgdirs = AppDirs('hangtty', 'hangtty')
    cg_log("Log directory " + cgdirs.user_log_dir)
    cg_log("Data directory " + cgdirs.user_data_dir)
    cg_log_path = os.path.join(cgdirs.user_log_dir, 'hangtty.log')
    cg_token_path = os.path.join(cgdirs.user_data_dir, 'hangttytoken.dat')

    # command line options
    parser = argparse.ArgumentParser(prog='hangtty', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose logging with debug information')
    parser.add_argument('-V', '--version', action='version', version='%(prog)s {}'.format(__cgversion__), help='version information')
    # paths
    parser.add_argument('--log', default=cg_log_path, help='log file path')
    parser.add_argument('--token', default=cg_token_path, help='token storage path')
    # keys
    key_group = parser.add_argument_group('Keybindings')
    key_group.add_argument('--key-next_tab', default='ctrl n')
    key_group.add_argument('--key-prev-tab', default='ctrl p')
    key_group.add_argument('--key-close_tab', default='ctrl q')
    key_group.add_argument('--key-quit', default='ctrl x')

    args = parser.parse_args()
    cg_create_default_dirs(args)
    logging.basicConfig(filename=args.log, level=logging.DEBUG, format=LOG_FORMAT)
    cg_start_client(args)

if __name__ == '__main__':
    cg_main()

