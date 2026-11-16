#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把交叉编译好的二进制推到 i.MX6ULL 板子上并可选执行。

用法（PowerShell / cmd / bash 均可）：
    python push_to_board.py hello_glibc
    python push_to_board.py hello_glibc --dest /tmp --run
    python push_to_board.py hello_glibc --host fe80::a86c:f9ff:fe2e:483d%58 --user root
    python push_to_board.py hello_glibc --ifindex 58          # 只要给链路本地地址就会自动补 scope

认证：优先用 SSH 私钥（~/.ssh/id_rsa|id_ed25519），没有就提示输密码。
传输：SFTP（走 dropbear 的 sftp-server；若板子没装 sftp，自动退回 scp 命令）。
"""
import argparse
import getpass
import os
import socket
import sys


def split_scope(host, ifindex):
    """fe80::x%58 或 --ifindex 58 -> (纯地址, scope_id)"""
    scope = ifindex
    if "%" in host:
        host, tail = host.split("%", 1)
        try:
            scope = int(tail)
        except ValueError:
            pass
    return host, scope


def open_transport(addr, scope, port, timeout=10):
    import paramiko

    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((addr, port, 0, scope or 0))
    t = paramiko.Transport(sock)
    # 兼容 dropbear 2015 的老算法
    try:
        t._preferred_keys = ("ssh-rsa", "rsa-sha2-512", "rsa-sha2-256",
                             "ecdsa-sha2-nistp256", "ssh-ed25519")
        t._preferred_kex = ("curve25519-sha256@libssh.org", "curve25519-sha256",
                            "ecdh-sha2-nistp256", "diffie-hellman-group14-sha1")
    except Exception:
        pass
    t.start_client(timeout=timeout)
    return t


def auth(t, user, password=None):
    """先试公钥，再试密码"""
    keys = [os.path.expanduser(p) for p in ("~/.ssh/id_ed25519", "~/.ssh/id_rsa")]
    for k in keys:
        if os.path.exists(k):
            try:
                t.auth_publickey(user, __import__("paramiko").RSAKey.from_private_key_file(k))
                print(f"[+] 用私钥登录成功: {k}")
                return True
            except Exception:
                pass
    if password is None:
        password = getpass.getpass(f"{user} 的密码: ")
    try:
        t.auth_password(user, password)
        return True
    except Exception as e:
        print(f"[x] 认证失败: {e}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("local", help="本地文件（交叉编译产物）")
    ap.add_argument("--host", default="fe80::a86c:f9ff:fe2e:483d",
                    help="板子地址，链路本地要带 %%ifindex，如 fe80::1%%58")
    ap.add_argument("--ifindex", type=int, default=0, help="IPv6 链路本地 scope id（网卡索引）")
    ap.add_argument("--port", type=int, default=22)
    ap.add_argument("--user", default="root")
    ap.add_argument("--dest", default="/tmp", help="板子上的目录")
    ap.add_argument("--run", action="store_true", help="上传后立刻执行")
    args = ap.parse_args()

    if not os.path.isfile(args.local):
        print(f"[x] 找不到本地文件: {args.local}")
        return 2

    addr, scope = split_scope(args.host, args.ifindex)
    print(f"[*] 连接 {addr}%{scope}:{args.port} ...")
    try:
        t = open_transport(addr, scope, args.port)
    except Exception as e:
        print(f"[x] 连接失败: {e}")
        print("    提示: 链路本地地址必须带 %%网卡索引，用 Get-NetAdapter 查 ifIndex；")
        print("          或者先在板子上 ifconfig eth0 192.168.1.20，用 IPv4 连。")
        return 3

    if not auth(t, args.user):
        return 4

    remote = args.dest.rstrip("/") + "/" + os.path.basename(args.local)
    try:
        sftp = t.open_sftp_client()
        print(f"[*] 上传 -> {remote}")
        sftp.put(args.local, remote)
        sftp.chmod(remote, 0o755)
        sftp.close()
    except Exception as e:
        print(f"[!] SFTP 不可用({e})，改用 scp over ssh")
        ch = t.open_session()
        ch.exec_command(f"cat > {remote} && chmod +x {remote}")
        with open(args.local, "rb") as f:
            ch.sendall(f.read())
        ch.shutdown_write()
        ch.recv_exit_status()
        ch.close()

    print(f"[+] 已上传: {remote}")

    ch = t.open_session()
    ch.exec_command(f"ls -l {remote}; file {remote} 2>/dev/null; uname -m")
    print(ch.recv(65535).decode("utf-8", "replace"))

    if args.run:
        print(f"[*] 执行 {remote}")
        ch2 = t.open_session()
        ch2.exec_command(remote)
        out, err = b"", b""
        while True:
            d = ch2.recv_stderr(4096)
            if not d:
                break
            err += d
        out = ch2.recv(65535) if ch2.recv_ready() else b""
        print(out.decode("utf-8", "replace"))
        if err:
            print("stderr:", err.decode("utf-8", "replace"))

    t.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
