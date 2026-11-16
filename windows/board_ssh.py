#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过 IPv6 链路本地地址登录 I.MX6ULL 板子（dropbear），读取板子网络/系统信息。
用法: python board_ssh.py [ifindex] [密码...]
"""
import socket
import sys

import paramiko

IFINDEX = int(sys.argv[1]) if len(sys.argv) > 1 else 58
TARGET = "fe80::a86c:f9ff:fe2e:483d"
PASSWORDS = sys.argv[2:] or ["root", "123456", "888888", "toor", "alientek", "atk", ""]
USER = "root"

CMD = (
    "echo '=== uname ==='; uname -a; "
    "echo '=== hostname ==='; hostname; "
    "echo '=== ipv4 ==='; ip -4 addr show 2>/dev/null || ifconfig 2>/dev/null; "
    "echo '=== ipv6 ==='; ip -6 addr show 2>/dev/null || ifconfig 2>/dev/null; "
    "echo '=== route ==='; ip route 2>/dev/null || route -n 2>/dev/null; "
    "echo '=== cpu ==='; grep -m2 -E 'Hardware|model name|Processor' /proc/cpuinfo; "
    "echo '=== mem ==='; head -3 /proc/meminfo; "
    "echo '=== rootfs ==='; df -h | head -8; "
    "echo '=== usb ==='; ls /sys/bus/usb/devices 2>/dev/null; "
    "echo '=== who ==='; whoami; id"
)


class TrustAll(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        return


def main():
    for pw in PASSWORDS:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.settimeout(6)
        try:
            sock.connect((TARGET, 22, 0, IFINDEX))
        except OSError as e:
            print(f"连接失败: {e}")
            return 2

        t = paramiko.Transport(sock)
        # 兼容 dropbear 2015 的老算法
        try:
            t._preferred_keys = (
                "ssh-rsa", "rsa-sha2-512", "rsa-sha2-256",
                "ecdsa-sha2-nistp256", "ssh-ed25519",
            )
            t._preferred_kex = (
                "curve25519-sha256@libssh.org", "curve25519-sha256",
                "ecdh-sha2-nistp256", "diffie-hellman-group14-sha1",
                "diffie-hellman-group-exchange-sha256",
            )
        except Exception:
            pass
        try:
            t.start_client(timeout=10)
        except Exception as e:
            print(f"SSH 握手失败: {e}")
            sock.close()
            return 3

        try:
            t.auth_password(USER, pw)
        except paramiko.AuthenticationException:
            print(f"--- 口令 [{pw!r}] 被拒绝")
            t.close()
            sock.close()
            continue
        except Exception as e:
            print(f"--- 认证异常: {e}")
            t.close()
            sock.close()
            continue

        print(f">>> 登录成功: {USER} / {pw!r}")
        ch = t.open_session()
        ch.exec_command(CMD)
        out = b""
        while True:
            data = ch.recv(65536)
            if not data:
                break
            out += data
        txt = out.decode("utf-8", "replace")
        try:
            print(txt)
        except UnicodeEncodeError:
            print(txt.encode("gbk", "replace").decode("gbk", "replace"))
        ch.close()
        t.close()
        sock.close()
        return 0

    print("所有口令都失败（板子可能改了 root 密码）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
