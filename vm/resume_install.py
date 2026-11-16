#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接管卡住的 apt，换清华源重装交叉工具链，然后完整验证。"""
import shlex
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
PKGS = ("gcc-arm-linux-gnueabihf g++-arm-linux-gnueabihf binutils-arm-linux-gnueabihf "
        "make build-essential bc bison flex libssl-dev libelf-dev libncurses-dev "
        "device-tree-compiler u-boot-tools rsync sshpass")

RESUME = f"""#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
echo "=== [0] 清理卡住的 apt ==="
pkill -f 'apt-get install' 2>/dev/null && sleep 3 || true
dpkg --configure -a 2>&1 | tail -3
echo "=== [1] 切换清华镜像 ==="
if [ ! -f /etc/apt/sources.list.bak-dsh ]; then cp /etc/apt/sources.list /etc/apt/sources.list.bak-dsh; fi
sed -i -E 's|https?://[a-zA-Z.]*archive\\.ubuntu\\.com|https://mirrors.tuna.tsinghua.edu.cn|g; s|https?://security\\.ubuntu\\.com|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list
grep -m3 '^deb ' /etc/apt/sources.list
echo "=== [2] apt-get update ==="
apt-get update -o Acquire::http::Timeout=20 -o Acquire::Retries=2 2>&1 | tail -5
echo "=== [3] 安装工具链（复用已下载的 203 个包）==="
apt-get install -y --no-install-recommends -o Acquire::http::Timeout=20 -o Acquire::Retries=2 {PKGS} 2>&1 | tail -20
echo "=== [4] 版本核对 ==="
for x in gcc g++ ar ld readelf objcopy; do
  printf '%-28s ' "arm-linux-gnueabihf-$x"
  command -v arm-linux-gnueabihf-$x || echo MISSING
done
arm-linux-gnueabihf-gcc --version | head -1
arm-linux-gnueabihf-g++ --version | head -1
make --version | head -1
echo "=== INSTALL_DONE ==="
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
echo "=== SMOKE_DONE ==="
"""

log_lines = []


def log(m):
    print(m, flush=True)
    log_lines.append(m)


def main():
    s = socket.create_connection((HOST, 22), timeout=10)
    t = paramiko.Transport(s)
    t.start_client(timeout=15)
    t.auth_password(USER, PASSWORD)
    log(f"[+] 已登录 {USER}@{HOST}")

    sftp = t.open_sftp_client()
    with sftp.open("/tmp/dsh_resume.sh", "w") as f:
        f.write(RESUME)
    sftp.chmod("/tmp/dsh_resume.sh", 0o755)
    sftp.close()
    log("[+] 脚本已上传 /tmp/dsh_resume.sh")

    def stream(cmd, feed=None, timeout=3000, prefix="  | "):
        ch = t.open_session()
        ch.settimeout(timeout)
        ch.exec_command(cmd)
        if feed:
            time.sleep(0.5)
            try:
                ch.sendall(feed.encode())
            except OSError:
                pass
        out = b""
        last = time.time()
        while True:
            got = False
            if ch.recv_ready():
                out += ch.recv(65536)
                got = True
            if ch.recv_stderr_ready():
                out += ch.recv_stderr(65536)
                got = True
            if got:
                for line in out.decode("utf-8", "replace").splitlines()[-1:]:
                    pass
                last = time.time()
                # 增量回显（只打印新增的完整行）
                try:
                    text = out.decode("utf-8", "replace")
                    printed = getattr(stream, "_n", 0)
                    lines = text.splitlines()
                    for ln in lines[printed:]:
                        if ln.strip():
                            log(prefix + ln)
                    stream._n = len(lines)
                except Exception:
                    pass
                continue
            if ch.exit_status_ready():
                break
            if time.time() - last > 600:
                log(prefix + "[!] 10 分钟无输出")
                break
            time.sleep(0.2)
        try:
            ch.settimeout(20)
            while ch.recv_ready():
                out += ch.recv(65536)
            while ch.recv_stderr_ready():
                out += ch.recv_stderr(65536)
        except Exception:
            pass
        rc = ch.recv_exit_status()
        ch.close()
        return rc, out.decode("utf-8", "replace")

    log("\n===== 执行：清理卡死 apt → 换清华源 → 安装 =====")
    t0 = time.time()
    rc, out = stream('sudo -S -p "" bash /tmp/dsh_resume.sh', feed=PASSWORD + "\n")
    log(f"\n    rc={rc}, 耗时 {time.time()-t0:.0f}s")

    if "INSTALL_DONE" not in out:
        log("[x] 安装未完成")
        return 3

    log("\n===== 冒烟测试 =====")
    rc, out = stream(SMOKE)
    log(f"    rc={rc}, 校验: {'通过' if ('ARM' in out and 'ELF 32-bit' in out) else '失败'}")

    log("\n===== 写 ~/.bashrc =====")
    rc, out = stream(
        "grep -q 'CROSS_COMPILE=arm-linux-gnueabihf-' ~/.bashrc && echo ALREADY || "
        "{ printf '\\n# --- i.MX6ULL cross toolchain (dsh) ---\\nexport CROSS_COMPILE=arm-linux-gnueabihf-\\n"
        "export ARCH=arm\\n' >> ~/.bashrc; echo ADDED; }")

    log("===== 授权公钥 =====")
    rc, out = stream(
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
        "chmod 600 ~/.ssh/authorized_keys && "
        f"(grep -q 'FNOPRP24d' ~/.ssh/authorized_keys && echo ALREADY || "
        f"{{ echo '{PUBKEY}' >> ~/.ssh/authorized_keys; echo ADDED; }})")

    log("===== 最终确认 =====")
    stream("bash -lc 'echo CROSS_COMPILE=$CROSS_COMPILE ARCH=$ARCH'; "
           "command -v arm-linux-gnueabihf-gcc; arm-linux-gnueabihf-gcc --version | head -1; "
           "ls -l /tmp/dsh_cross/; df -h / | tail -1")

    t.close()
    s.close()
    with open(r"C:\Users\38368\OneDrive\文档\deepseek-harness\default-workspace\linux\vm_install.log",
              "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    log("\n[OK] 全部完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# 运行前先设置环境变量，例如：
#   export VM_PASS="你的虚拟机密码"   （bash）
#   $env:VM_PASS="你的虚拟机密码"     （PowerShell）
