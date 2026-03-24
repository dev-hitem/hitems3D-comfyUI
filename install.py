import os
import subprocess
import sys

_root = os.path.dirname(os.path.abspath(__file__))
_req = os.path.join(_root, "requirements.txt")
if os.path.isfile(_req):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", _req],
        cwd=_root,
    )
