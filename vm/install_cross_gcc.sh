#!/usr/bin/env bash
# 在 Ubuntu / Debian 上安装 i.MX6ULL 交叉编译工具链（真 GNU gcc）
# 用法（在你的 Ubuntu 虚拟机里执行）：
#     bash install_cross_gcc.sh
# 或从 Windows 一键远程执行（只输一次 sudo 密码）：
#     ssh ubuntu@192.168.229.129 'bash -s' < install_cross_gcc.sh
set -e

BLUE='\033[1;34m'; GREEN='\033[1;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
step() { printf "${BLUE}==> %s${NC}\n" "$*"; }
ok()   { printf "${GREEN}[ok] %s${NC}\n" "$*"; }
warn() { printf "${YELLOW}[!] %s${NC}\n" "$*"; }

step "0. 系统信息"
. /etc/os-release 2>/dev/null || true
echo "  ${PRETTY_NAME:-unknown}  $(uname -m)  kernel $(uname -r)"
case "${ID:-}" in
  ubuntu|debian|linuxmint|pop) : ;;
  *) warn "不是 Debian 系发行版，apt 可能不可用，下面步骤可能失败" ;;
esac

step "1. 更新 apt 索引（需要 sudo 密码，会提示）"
sudo apt-get update -qq

step "2. 安装交叉工具链 + 常用构建工具"
sudo apt-get install -y --no-install-recommends \
    gcc-arm-linux-gnueabihf \
    g++-arm-linux-gnueabihf \
    binutils-arm-linux-gnueabihf \
    make build-essential bc bison flex libssl-dev \
    device-tree-compiler libncurses-dev \
    u-boot-tools sshpass rsync

step "3. 验证"
if command -v arm-linux-gnueabihf-gcc >/dev/null 2>&1; then
    ok "arm-linux-gnueabihf-gcc 已安装"
    arm-linux-gnueabihf-gcc --version | head -1
    echo "  which: $(command -v arm-linux-gnueabihf-gcc)"
    echo "  make : $(make --version | head -1)"
else
    warn "安装后仍找不到 arm-linux-gnueabihf-gcc，检查 /usr/bin"
    ls /usr/bin | grep -i 'arm-linux' || true
    exit 1
fi

step "4. 冒烟测试（编一个给板子的 hello）"
TMP=$(mktemp -d)
cat > "$TMP/hello.c" <<'EOF'
#include <stdio.h>
int main(void){ printf("hello from real GNU gcc cross toolchain\n"); return 0; }
EOF
arm-linux-gnueabihf-gcc -O2 -mcpu=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=hard \
    -o "$TMP/hello_dyn" "$TMP/hello.c"
arm-linux-gnueabihf-gcc -O2 -static -o "$TMP/hello_static" "$TMP/hello.c"
file "$TMP/hello_dyn" "$TMP/hello_static"
echo
arm-linux-gnueabihf-readelf -h "$TMP/hello_static" | grep -E 'Class|Machine|Flags'
ok "编译通过，产物在 $TMP"
echo
echo "现在可以直接用："
echo "  export CROSS_COMPILE=arm-linux-gnueabihf-"
echo "  arm-linux-gnueabihf-gcc -O2 -o app main.c"
