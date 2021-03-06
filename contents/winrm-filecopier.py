import winrm
import argparse
import os
import sys
import base64
import time
from base64 import b64encode

from winrm.protocol import Protocol

class RemoteCommandError(Exception):
    def __init__(self, command, return_code, std_out='', std_err=''):
        super(RemoteCommandError, self).__init__(
            'Remote execution of "{}" failed with exit code {}. '
            'STDOUT: {}. STDERR: {}.'.format(
                command, return_code, std_out, std_err
            )
        )


class WinRmError(RemoteCommandError):
    pass

class CopyFiles(object):

    def __init__(self, session):
        self.session=session

    def winrm_upload(
            self,
            remote_path,
            local_path,
            step=1024,
            winrm_kwargs=dict(),
            quiet=False,
            **kwargs
    ):
        
        self.session.run_ps('if (Test-Path {0}) {{ Remove-Item {0} }}'.format(remote_path))
        size = os.stat(local_path).st_size
        start = time.time()
        with open(local_path, 'rb') as f:
            for i in range(0, size, step):
                script = (
                    'add-content -value '
                    '$([System.Convert]::FromBase64String("{}")) '
                    '-encoding byte -path {}'.format(
                        base64.b64encode(f.read(step)),
                        remote_path
                    )
                )
                while True:
                    result = self.session.run_ps(script)
                    code=result.status_code
                    stdout=result.std_out
                    stderr=result.std_err

                    if code == 0:
                        break
                    elif code == 1 and 'used by another process' in stderr:
                        # Small delay so previous write can settle down
                        time.sleep(0.1)
                    else:
                        raise WinRmError(script, code, stdout, stderr)
                if not quiet:
                    transferred = i + step
                    if transferred > size:
                        transferred = size
                    progress_blocks = transferred * 30 // size
                    percentage_string = str(
                        (100 * transferred) // size
                    ) + ' %'
                    percentage_string = (
                        ' ' * (5 - len(percentage_string)) +
                        percentage_string
                    )
                    sys.stdout.flush()


parser = argparse.ArgumentParser(description='Run Bolt command.')
parser.add_argument('username', help='the username')
parser.add_argument('hostname', help='the hostname')
parser.add_argument('source', help='Source File')
parser.add_argument('destination', help='Destination File')
args = parser.parse_args()

#it is necesarry to avoid the debug error
print args.destination

password=None
authentication = "basic"
transport = "http"
port = "5985"
nossl=False
debug=False

if "RD_CONFIG_PASSWORD_STORAGE_PATH" in os.environ:
    password = os.getenv("RD_CONFIG_PASSWORD_STORAGE_PATH")

if "RD_CONFIG_AUTHTYPE" in os.environ:
    authentication = os.getenv("RD_CONFIG_AUTHTYPE")

if "RD_CONFIG_WINRMTRANSPORT" in os.environ:
    transport = os.getenv("RD_CONFIG_WINRMTRANSPORT")

if "RD_CONFIG_WINRMPORT" in os.environ:
    port = os.getenv("RD_CONFIG_WINRMPORT")

if "RD_CONFIG_NOSSL" in os.environ:
    nossl = os.getenv("RD_CONFIG_NOSSL")

endpoint=transport+'://'+args.hostname+':'+port


if(nossl):
    session  = winrm.Session(endpoint, auth=(args.username, password),
                                       transport=authentication,
                                       server_cert_validation='ignore')
else:
    session  = winrm.Session(endpoint, auth=(args.username, password),
                                       transport=authentication)

copy = CopyFiles(session)
copy.winrm_upload(args.destination,args.source)
