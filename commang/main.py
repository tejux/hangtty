# commang is a command-line-hangout client.
# it uses the hangups hangout library (https://github.com/tdryer/hangups)
# a lot of code was done by reading https://github.com/xmikos/hangupsbot

import os
import sys
import logging
import argparse

from cg_client import CGClient    
from appdirs import AppDirs

__cgversion__ = "1.0.0"

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
 
# developer debug level, dumps detailed debug logs on stderr
dev_debug_enable = 0

def cg_start_client():
    global cg_token_path
    
    cg = CGClient(dev_debug_enable, cg_token_path)  
    cg_log('created object' + str(cg))
    cg.cg_run()

def cg_log(debug_str):
    global dev_debug_enable
    
    if dev_debug_enable == 1:
        logging.log(logging.DEBUG, debug_str)
    else:
        logging.log(logging.INFO, debug_str)

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
        dev_debug_enable = 1
        
def cg_main():
    global cg_token_path
    
    cg_log_init()
    cgdirs = AppDirs('commang', 'commang')
    cg_log("Log directory " + cgdirs.user_log_dir)
    cg_log("Data directory " + cgdirs.user_data_dir)
    cg_log_path = os.path.join(cgdirs.user_log_dir, 'commang.log')
    cg_token_path = os.path.join(cgdirs.user_data_dir, 'commangtoken.dat')
    
    # command line options
    parser = argparse.ArgumentParser(prog='commang', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose logging with debug information')
    parser.add_argument('-V', '--version', action='version', version='%(prog)s {}'.format(__cgversion__), help='version information')
    # paths
    parser.add_argument('--log', default=cg_log_path, help='log file path')
    parser.add_argument('--token', default=cg_token_path, help='token storage path')
    args = parser.parse_args()
    cg_create_default_dirs(args)
    cgl = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(filename=args.log, level=cgl, format=LOG_FORMAT)
    cg_start_client()

if __name__ == '__main__':
    cg_main()
    