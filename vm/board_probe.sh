#!/bin/sh
# 板子上跑一次，30 秒内把"这块板到底能不能本机装 gcc / 该不该装"全部问清楚
# 用法：把下面 3 行分别粘进 PuTTY（COM3）的 # 提示符后面回车即可
echo "===== 1. 系统 ====="; cat /etc/os-release 2>/dev/null || cat /etc/issue 2>/dev/null; uname -a; echo
echo "===== 2. glibc / 编译环境 ====="; ldd --version 2>&1 | head -2; ls -l /lib/libc-*.so* /lib/libc.so* 2>/dev/null; which gcc cc make ld python3 opkg apt apt-get dpkg 2>/dev/null; echo "(以上为已存在的命令，空行表示没有)"
echo "===== 3. 资源 / 存储 ====="; grep -E 'MemTotal|MemFree' /proc/meminfo; df -h / /tmp 2>/dev/null; nproc
echo "===== 4. 网络 ====="; ip -4 addr show 2>/dev/null || ifconfig 2>/dev/null; ip route 2>/dev/null
echo "===== 5. CPU 型号 ====="; grep -E 'Hardware|model name|Processor|Revision' /proc/cpuinfo | head -3
