#!/usr/bin/env python3
import pysftp
import os


class SFTPClient:
    def __init__(self, *, hostname, port, username, password):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password

    def listdir(self, path):
        with self.connection() as sftp:
            raw_files = sftp.listdir(path)
            print(f"listdir({path})", raw_files)
            files = []
            for file in raw_files:
                # import pdb
                # pdb.set_trace()
                filepath = f'{path}{file}'
                s = sftp.stat(filepath)
                print(f"stat({filepath})", s)
                stats = dict(atime=s.st_atime,
                             mtime=s.st_mtime,
                             gid=s.st_gid,
                             uid=s.st_uid,
                             size=s.st_size)
                files.append(
                    dict(name=file, isdir=sftp.isdir(filepath), **stats))
            return files

    def get(self, path, output_path):
        with self.connection() as sftp:
            sftp.get(path, output_path)

    def connection(self):
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        return pysftp.Connection(self.hostname,
                                 port=self.port,
                                 username=self.username,
                                 password=self.password,
                                 cnopts=cnopts)


if __name__ == "__main__":
    import os

    client = SFTPClient(hostname=os.getenv('DEFAULT_SFTP_HOSTNAME'),
                        port=os.getenv('DEFAULT_SFTP_PORT'),
                        username=os.getenv('DEFAULT_SFTP_USERNAME'),
                        password=os.getenv('DEFAULT_SFTP_PASSWORD'))
    print(client.listdir('/'))
