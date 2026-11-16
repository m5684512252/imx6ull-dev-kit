#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 Ubuntu 虚拟机（ashes@192.168.229.129）上自动安装 i.MX6ULL 交叉工具链。
做法：把安装脚本传上去，用 sudo -S 跑一遍，实时回显，最后逐项验证。
"""
import os
import socket
import sys
import time

import paramiko

HOST = "192.168.229.129"
USER = "ashes"
PASSWORD = os.environ.get("VM_PASS", "")
PUBKEY = ("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFNOPRP24d/gZBk2CEChwhXHnUmlugLtRjFxAanXmWCf "
          "383688183@qq.com")
LOG = r"C:\Users\38368\OneDrive\文档\deepseek-harness\default-workspace\linux\vm_install.log"

PKGS = ("gcc-arm-linux-gnueabihf g++-arm-linux-gnueabihf binutils-arm-linux-gnueabihf "
        "make build-essential bc bison flex libssl-dev libelf-dev libncurses-dev "
        "device-tree-compiler u-boot-tools rsync sshpass")

REMOTE_SCRIPT = f"""#!/bin/bash
set -o pipefail
export DEBIAN_FRONTEND=noninteractive

echo "=== [1/3] apt-get update ==="
apt-get update -o Acquire::Retries=3 2>&1 | tail -6

echo "=== [2/3] 安装交叉工具链与内核编译依赖 ==="
apt-get install -y --no-install-recommends {PKGS} 2>&1 | tail -15

echo "=== [3/3] 版本核对 ==="
for x in gcc g++ ar ld readelf objcopy; do
  printf '%-8s ' "arm-linux-gnueabihf-$x"
  command -v arm-linux-gnueabihf-$x || echo MISSING
done
arm-linux-gnueabihf-gcc --version | head -1
arm-linux-gnueabihf-g++ --version | head -1
make --version | head -1
echo "=== 安装阶段结束 rc=0 ==="
"""

SMOKE = r"""set -e
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
echo '--- readelf -h hello_static ---'
arm-linux-gnueabihf-readelf -h hello_static | grep -E 'Class|Machine|Flags'
ls -l hello_dyn hello_static hello_cpp
"""

log_lines = []


def log(msg):
    print(msg, flush=True)
    log_lines.append(msg)


def connect():
    s = socket.create_connection((HOST, 22), timeout=10)
    t = paramiko.Transport(s)
    t.start_client(timeout=15)
    t.auth_password(USER, PASSWORD)
    return t, s


def stream(t, cmd, feed=None, timeout=2400, prefix="    "):
    """执行命令并实时回显，返回 (rc, 全文)"""
    ch = t.open_session()
    ch.settimeout(timeout)
    ch.exec_command(cmd)
    if feed is not None:
        time.sleep(0.3)
        try:
            ch.sendall(feed.encode())
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
        if ch.recv_stderr_ready():
            d = ch.recv_stderr(65536)
            out += d
            got = True
        if got:
            last = time.time()
            continue
        if ch.exit_status_ready():
            while ch.recv_ready():
                out += ch.recv(65536)
            while ch.recv_stderr_ready():
                out += ch.recv_stderr(65536)
            break
        if time.time() - last > 900:
            log(f"{prefix}[!] 900 秒无输出，主动断开")
            break
        time.sleep(0.1)
    rc = ch.recv_exit_status()
    ch.close()
    text = out.decode("utf-8", "replace")
    for line in text.splitlines():
        if line.strip():
            log(prefix + line)
    return rc, text


def main():
    log(f"[*] 连接 {USER}@{HOST} ...")
    t, s = connect()
    log("[+] 登录成功")

    log("\n===== 0. 系统与 sudo 权限 =====")
    stream(t, "hostname; . /etc/os-release && echo $PRETTY_NAME; uname -r; nproc; "
              "free -h | head -2; df -h / | tail -1")
    rc, out = stream(t, "sudo -S -p '' -k true && echo SUDO_OK", feed=PASSWORD + "\n")
    if "SUDO_OK" not in out:
        log("[x] sudo 不可用，终止")
        return 2

    log("\n===== 1. 上传安装脚本 =====")
    sftp = t.open_sftp_client()
    with sftp.open("/tmp/dsh_install.sh", "w") as f:
        f.write(REMOTE_SCRIPT)
    sftp.chmod("/tmp/dsh_install.sh", 0o755)
    sftp.close()
    log("    已上传 /tmp/dsh_install.sh")

    log("\n===== 2. 执行安装（apt，可能要几分钟）=====")
    t0 = time.time()
    rc, out = stream(t, "sudo -S -p '' -k bash /tmp/dsh_install.sh", feed=PASSWORD + "\n")
    log(f"    -> rc={rc}, 总耗时 {time.time()-t0:.0f}s")
    if "安装阶段结束" not in out:
        log("[x] 安装阶段异常，见上方输出")
        return 3

    log("\n===== 3. 冒烟测试（C / C++ / 静态）=====")
    rc, out = stream(t, SMOKE)
    ok = rc == 0 and "ARM" in out and "ELF 32-bit" in out
    log(f"    -> rc={rc}, 交叉编译验证: {'通过' if ok else '失败'}")

    log("\n===== 4. 配置 ~/.bashrc（CROSS_COMPILE / ARCH）=====")
    rc, out = stream(
        t,
        "grep -q 'CROSS_COMPILE=arm-linux-gnueabihf-' ~/.bashrc && echo ALREADY || "
        "{ printf '\\n# --- i.MX6ULL cross toolchain (dsh) ---\\nexport CROSS_COMPILE=arm-linux-gnueabihf-\\n"
        "export ARCH=arm\\n' >> ~/.bashrc; echo ADDED; }")
    log(f"    -> {out.strip().splitlines()[-1] if out.strip() else '?'}")

    log("\n===== 5. 授权公钥（以后免密 ssh）=====")
    rc, out = stream(
        t,
        f"mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
        f"chmod 600 ~/.ssh/authorized_keys && "
        f"(grep -q 'FNOPRP24d' ~/.ssh/authorized_keys && echo ALREADY || "
        f"{{ echo '{PUBKEY}' >> ~/.ssh/authorized_keys; echo ADDED; }})")
    log(f"    -> {out.strip().splitlines()[-1] if out.strip() else '?'}")

    log("\n===== 6. 最终确认 =====")
    stream(t, "bash -lc 'echo CROSS_COMPILE=$CROSS_COMPILE ARCH=$ARCH'; "
              "$(command -v arm-linux-gnueabihf-gcc) --version | head -1; "
              "ls -l /tmp/dsh_cross/ 2>/dev/null | tail -4; "
              "dpkg -l | grep -c arm-linux-gnueabihf")

    t.close()
    s.close()
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    log(f"\n[OK] 完成。日志: {LOG}")
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())

# 运行前先设置环境变量，例如：
#   export VM_PASS="你的虚拟机密码"   （bash）
#   $env:VM_PASS="你的虚拟机密码"     （PowerShell）
