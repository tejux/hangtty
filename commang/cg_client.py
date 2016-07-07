import sys
import hangups

class CGClient:
        def __init__(self, dev_debug_enable, cg_token_path):
            self.dev_debug_enable = dev_debug_enable
            self.cg_debug("ctor" + str(self))
            self.cg_debug("token in " + cg_token_path)
            self.cg_token_path = cg_token_path

            
        def cg_debug(self, debug_str):
            sys.stderr.write("[Debug] " + debug_str + "\n")
            
            
        def cg_login2hangouts(self, token_file):
            try:
                cookies = hangups.auth.get_auth_stdin(token_file)
                self.cg_debug(str(cookies))
                return cookies
            except hangups.GoogleAuthError as e:
                print("Failed!!! " + str(e))
                return None
            
        def cg_run(self):
            self.cg_login2hangouts(self.cg_token_path)
            