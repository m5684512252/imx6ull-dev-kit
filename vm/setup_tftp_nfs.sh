#!/bin/bash
# 按正点原子官方流程配置 TFTP + NFS（适配 Ubuntu 22.04 / 用户 ashes）
set -e
export DEBIAN_FRONTEND=noninteractive
TFTPDIR=/home/ashes/linux/tftp
NFSDIR=/home/ashes/linux/nfs

echo "=== [1] 安装 tftp 服务端与客户端 ==="
apt-get install -y -qq tftp-hpa tftpd-hpa >/dev/null 2>&1
echo "    tftp-hpa: $(dpkg -l tftp-hpa | awk '/^ii/{print $3}')"
echo "    tftpd-hpa: $(dpkg -l tftpd-hpa | awk '/^ii/{print $3}')"

echo "=== [2] 配置 /etc/default/tftpd-hpa ==="
cat > /etc/default/tftpd-hpa <<EOF
TFTP_USERNAME="tftp"
TFTP_DIRECTORY="$TFTPDIR"
TFTP_ADDRESS="0.0.0.0:69"
TFTP_OPTIONS="--secure --create"
EOF
cat /etc/default/tftpd-hpa

echo "=== [3] 启动 tftpd-hpa ==="
systemctl enable tftpd-hpa >/dev/null 2>&1 || true
systemctl restart tftpd-hpa || true
sleep 1
systemctl is-active tftpd-hpa || true

echo "=== [4] 配置 /etc/exports ==="
if ! grep -q "linux/nfs" /etc/exports 2>/dev/null; then
    echo "$NFSDIR *(rw,sync,no_root_squash,no_subtree_check)" >> /etc/exports
    echo "    已追加"
else
    echo "    已存在，跳过"
fi
grep -n "nfs" /etc/exports || true

echo "=== [5] Ubuntu 18.04+ 的 NFS 兼容设置（uboot 走 NFS 启动必需）==="
if ! grep -q '^RPCNFSDOPTS' /etc/default/nfs-kernel-server 2>/dev/null; then
    echo 'RPCNFSDOPTS="--nfs-version 2,3,4 --debug --syslog"' >> /etc/default/nfs-kernel-server
    echo "    已写入 RPCNFSDOPTS"
else
    echo "    已存在"
fi

echo "=== [6] 关防火墙 ==="
ufw disable 2>/dev/null || echo "    ufw 未启用"

echo "=== [7] 重启 NFS 并导出 ==="
systemctl restart nfs-kernel-server
exportfs -ra
sleep 1
systemctl is-active nfs-kernel-server || true
exportfs -v | grep -E "nfs" || true

echo "=== [8] 目录权限 ==="
mkdir -p "$TFTPDIR" "$NFSDIR/rootfs"
chmod 777 "$TFTPDIR" "$NFSDIR" "$NFSDIR/rootfs"
ls -ld "$TFTPDIR" "$NFSDIR/rootfs"

echo "=== DONE ==="
