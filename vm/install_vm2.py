#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二轮：解掉 packagekitd 的锁 -> apt update -> 安装 -> 严格校验。"""
import os
import socket
import sys
import time

import paramiko

HOST = os.environ.get("VM_HOST", "192.168.229.129")
USER = os.environ.get("VM_USER", "ashes")
PASSWORD = os.environ.get("VM_PASS", "")
PUBKEY = ("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFNOPRP24d/gZBk2CEChwhXHnUmlugLtRjFxAanXmWCf "
          "383688183@qq.com")
PKGS = ("gcc-arm-linux-gnueabihf g++-arm-linux-gnueabihf binutils-arm-linux-gnueabihf "
        "make build-essential bc bison flex libssl-dev libelf-dev libncurses-dev "
        "device-tree-compiler u-boot-tools rsync sshpass")

SCRIPT = """#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
APTOPT="-o Acquire::http::Timeout=25 -o Acquire::Retries=3 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"

echo "=== [1] 解除 apt 锁（packagekitd / 其它 apt）==="
systemctl stop packagekit 2>/dev/null && echo "packagekit 已停" || echo "packagekit 未运行"
pkill -x packagekitd 2>/dev/null && { echo "已杀 packagekitd"; sleep 2; } || echo "无 packagekitd"
pkill -f unattended-upgrade 2>/dev/null || true
sleep 1
rm -f /var/lib/apt/lists/lock /var/cache/apt/archives/lock /var/lib/dpkg/lock-frontend 2>/dev/null
dpkg --configure -a 2>&1 | tail -2

echo "=== [2] apt-get update ==="
apt-get update $APTOPT 2>&1 | tail -8
if ! ls /var/lib/apt/lists/*Packages* >/dev/null 2>&1; then
  echo "!! 索引仍然为空，终止"
  echo "INSTALL_FAILED"
  exit 1
fi
echo "索引包数: $(grep -hc '^Package:' /var/lib/apt/lists/*Packages* 2>/dev/null | paste -sd+ | bc 2>/dev/null || echo '?')"

echo "=== [3] 确认目标包在索引里 ==="
for p in gcc-arm-linux-gnueabihf binutils-arm-linux-gnueabihf make bison flex; do
  if apt-cache policy $p 2>/dev/null | grep -q 'Candidate: [0-9]'; then
    echo "  OK   $p -> $(apt-cache policy $p | awk '/Candidate:/{print $2}')"
  else
    echo "  MISS $p"
  fi
done

echo "=== [4] 安装 ==="
apt-get install -y --no-install-recommends $APTOPT __PKGS__ 2>&1 | tail -15

echo "=== [5] 严格校验 ==="
FAIL=0
for x in gcc g++ ar ld readelf objcopy; do
  if command -v arm-linux-gnueabihf-$x >/dev/null 2>&1; then
    printf '  OK   arm-linux-gnueabihf-%-8s %s\\n' "$x" "$(command -v arm-linux-gnueabihf-$x)"
  else
    printf '  MISS arm-linux-gnueabihf-%-8s\\n' "$x"; FAIL=1
  fi
done
arm-linux-gnueabihf-gcc --version 2>/dev/null | head -1
if [ $FAIL -eq 0 ]; then
  echo "INSTALL_OK"
else
  echo "INSTALL_FAILED"
fi
"""

SCRIPT = SCRIPT.replace("__PKGS__", PKGS)


def main():
    s = socket.create_connection((HOST, 22), timeout=10)
    t = paramiko.Transport(s)
    t.start_client(timeout=15)
    t.auth_password(USER, PASSWORD)
    print(f"[+] 登录 {USER}@{HOST}", flush=True)

    sftp = t.open_sftp_client()
    with sftp.open("/tmp/dsh_fix.sh", "w") as f:
        f.write(SCRIPT)
    sftp.chmod("/tmp/dsh_fix.sh", 0o755)
    sftp.close()

    ch = t.open_session()
    ch.settimeout(2400)
    ch.exec_command('sudo -S -p "" bash /tmp/dsh_fix.sh')
    time.sleep(0.6)
    try:
        ch.sendall((PASSWORD + "\n").encode())
    except OSError:
        pass

    out = b""
    last = time.time()
    while True:
        got = False
        if ch.recv_ready():
            d = ch.recv(65536)
            out += d
            got = True
            txt = out.decode("utf-8", "replace")
            for line in txt.splitlines()[-40:]:
                pass
        if ch.recv_stderr_ready():
            out += ch.recv_stderr(65536)
            got = True
        if got:
            last = time.time()
            continue
        if ch.exit_status_ready():
            break
        if time.time() - last > 900:
            print("[!] 长时间无输出")
            break
        time.sleep(0.2)
    try:
        while ch.recv_ready():
            out += ch.recv(65536)
        while ch.recv_stderr_ready():
            out += ch.recv_stderr(65536)
    except Exception:
        pass
    rc = ch.recv_exit_status()
    ch.close()

    text = out.decode("utf-8", "replace")
    print(text)
    print(f"\n[rc={rc}]", flush=True)

    ok = "INSTALL_OK" in text

    if ok:
        print("\n===== 冒烟测试 =====", flush=True)
        smoke = r"""set -e
rm -rf /tmp/dsh_cross; mkdir -p /tmp/dsh_cross; cd /tmp/dsh_cross
cat > hello.c <<'EOF'
#include <stdio.h>
int main(void){ printf("hello from real GNU gcc (Ubuntu cross toolchain)\n"); return 0; }
EOF
cat > hello.cpp <<'EOF'
#include <iostream>
int main(){ std::cout << "c++ cross ok" << std::endl; return 0; }
EOF
arm-linux-gnueabihf-gcc -O2 -mcpu=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=hard -o hello_dyn hello.c
arm-linux-gnueabihf-gcc -O2 -static -o hello_static hello.c
arm-linux-gnueabihf-g++ -O2 -static -o hello_cpp hello.cpp
file hello_dyn hello_static hello_cpp
echo '--- readelf -h ---'
arm-linux-gnueabihf-readelf -h hello_static | grep -E 'Class|Machine|Flags'
ls -l /tmp/dsh_cross/
"""
        ch2 = t.open_session()
        ch2.settimeout(300)
        ch2.exec_command(smoke)
        o2 = b""
        while True:
            if ch2.recv_ready():
                o2 += ch2.recv(65536)
            elif ch2.recv_stderr_ready():
                o2 += ch2.recv_stderr(65536)
            elif ch2.exit_status_ready():
                break
            else:
                time.sleep(0.1)
        print(o2.decode("utf-8", "replace"), flush=True)
        ch2.close()

        # .bashrc + 公钥
        for cmd in [
            "grep -q 'CROSS_COMPILE=arm-linux-gnueabihf-' ~/.bashrc && echo ALREADY || "
            "{ printf '\\n# --- i.MX6ULL cross toolchain (dsh) ---\\nexport CROSS_COMPILE=arm-linux-gnueabihf-\\n"
            "export ARCH=arm\\n' >> ~/.bashrc; echo BASHRC_ADDED; }",
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
            "chmod 600 ~/.ssh/authorized_keys && "
            f"(grep -q 'FNOPRP24d' ~/.ssh/authorized_keys && echo KEY_ALREADY || "
            f"{{ echo '{PUBKEY}' >> ~/.ssh/authorized_keys; echo KEY_ADDED; }})",
        ]:
            ch3 = t.open_session()
            ch3.settimeout(30)
            ch3.exec_command(cmd)
            time.sleep(1.2)
            r = b""
            while ch3.recv_ready():
                r += ch3.recv(65536)
            print("  " + r.decode("utf-8", "replace").strip(), flush=True)
            ch3.close()

    t.close()
    s.close()
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())

# 运行前先设置环境变量，例如：
#   export VM_PASS="你的虚拟机密码"   （bash）
#   $env:VM_PASS="你的虚拟机密码"     （PowerShell）
