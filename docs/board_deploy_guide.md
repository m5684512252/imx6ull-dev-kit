# 在那块 I.MX6ULL 板子上跑程序 —— 完整操作手册

> 针对昨晚实测到的那台板子：
> - MAC `AA:6C:F9:2E:48:3D`，IPv6 链路本地 `fe80::a86c:f9ff:fe2e:483d%58`
> - SSH 22 开放，`SSH-2.0-dropbear_2015.71`
> - 根文件系统：eMMC 4GB（`mmcblk1p2`，ext3），内核启动日志里有 `wm8960-audio`
> - 串口控制台：CH340 → Windows `COM3`，115200 8N1，**进去直接是 root（`#`）**
> - glibc 版本未知 → **一律编静态二进制**

---

## 第 0 步：接线（三选一，按你手头有的）

| 方式 | 接线 | 能做什么 |
|---|---|---|
| **A. 串口**（必备，万能后门） | 板子 `USB_UART` → PC USB | 看启动日志、进 u-boot、root shell、设密码、改 IP |
| **B. 网口**（传文件、跑程序） | 板子网口 → USB转RJ45 → PC Type-C | scp / FileZilla / ssh / tftp / nfs |
| **C. 串口 + 网口**（推荐） | A + B 都接 | 网络出问题时还能从串口救回来 |

串口工具：PuTTY → Serial → `COM3` → 速度 **115200** → 打开就会看到启动日志，按回车出现 `#`。

---

## 第 1 步：让板子有一个你能连上的 IP

板子出厂是 DHCP 客户端或静态地址，你 PC 直接插上去**不会自动通**（昨晚实测：PC 拿到的是 `169.254.36.223` 这种失效地址，说明板子不发 DHCP）。

### 办法 1（最稳）：从串口里给板子设地址

在 PuTTY 的 `#` 提示符下敲：

```sh
ifconfig eth0 192.168.1.20 netmask 255.255.255.0 up
ifconfig eth0
```

看到 `inet addr:192.168.1.20` 就成了。

### 办法 2：顺手把 root 密码设成你知道的

板子串口是免密 root，但 **SSH 的密码我们试过 `root`/`123456` 全被拒**。所以：

```sh
passwd root
# 输两遍新密码
```

设完 `ssh root@192.168.1.20` 就能进 —— 这一步做了，后面 scp、FileZilla 全部可用。

### 办法 3：PC 侧把网卡设成同网段

Windows：设置 → 网络 → 那个 USB 网卡 → IPv4 → 手动：

```
IP 地址     192.168.1.100
子网掩码    255.255.255.0
网关        留空
```

或者用我写好的扫描脚本（管理员 PowerShell），它会自动切网段找出板子：

```powershell
cd "C:\Users\38368\OneDrive\文档\deepseek-harness\default-workspace"
powershell -NoProfile -ExecutionPolicy Bypass -File .\find_board_ipv4.ps1
```

### 办法 4：不设 IPv4，直接走 IPv6

板子开机就有链路本地地址，实测 ping 通、22 端口开：

```powershell
ssh root@fe80::a86c:f9ff:fe2e:483d%58
```

`%58` 是网卡索引（`Get-NetAdapter` 里看 ifIndex）。缺点：tftp/nfs 这些老工具不认 IPv6。

---

## 第 2 步：在虚拟机里编译（一律静态）

```bash
# 登录 Ubuntu 虚拟机
ssh ashes@192.168.229.129

cd ~/imx6ull-demo

# 单文件
arm-linux-gnueabihf-gcc -O2 -Wall -static -s -o hello hello.c

# 多文件工程
make static          # 生成 app_static
```

产物自检（必须看到 `ARM` + `hard-float`）：

```bash
LC_ALL=C arm-linux-gnueabihf-readelf -h hello | grep -E 'Class|Machine|Flags'
#   Class:   ELF32
#   Machine: ARM
#   Flags:   0x5000400, Version5 EABI, hard-float ABI

# 不用板子就能验证能不能跑
qemu-arm-static ./hello
#   Hello, i.MX6ULL!
```

---

## 第 3 步：把二进制传到板子

### 办法 A：scp（一条命令，最常用）

在虚拟机里：

```bash
scp hello root@192.168.1.20:/root/
```

在 Windows 里（PowerShell 自带 scp）：

```powershell
scp "C:\Users\38368\toolchain\arm-linux-gnueabihf\demo\app_static" root@192.168.1.20:/root/
```

### 办法 B：FileZilla（图形界面，你已装好）

站点管理器 → 新建站点：

| 项 | 值 |
|---|---|
| 协议 | **SFTP - SSH File Transfer Protocol** |
| 主机 | `192.168.1.20`（或 `fe80::a86c:f9ff:fe2e:483d%58`） |
| 端口 | `22` |
| 登录类型 | 正常 |
| 用户 | `root` |
| 密码 | 第 1 步里 `passwd root` 设的那个 |

连上后左边选本地文件，右边 `/root`，直接拖。

### 办法 C：板子主动来拉（tftp，适合批量）

PC/虚拟机开 tftp 服务，板子上：

```sh
tftp -g -r hello 192.168.1.100
```

### 办法 D：只有串口、没有网络时的应急传输

板子上如果有 `rz`（lrzsz）：

```sh
rz          # 然后 PuTTY 里用 X/Y/Zmodem 发送文件
```

没有 `rz` 就用 base64 分块粘贴（只适合小文件，几百 KB 会很痛苦）—— 这条路能不用就不用。

### 办法 E：我写好的推送脚本（自动兼容老 dropbear）

```powershell
cd "C:\Users\38368\OneDrive\文档\deepseek-harness\default-workspace"
python push_to_board.py "C:\...\app_static" --host 192.168.1.20 --dest /root --run
```

---

## 第 4 步：在板子上跑

串口或 ssh 里：

```sh
cd /root
chmod +x hello        # 传过去经常丢执行权限，这步别忘
./hello
```

预期输出：

```
Hello, i.MX6ULL!
```

---

## 第 5 步（可选）：开机自动运行

板子用的是 SysV init（`/etc/init.d`），最省事的做法是往 `rc.local` 里加：

```sh
vi /etc/rc.local
# 在 exit 0 之前加一行：
/root/hello &
```

或者写成正规服务：

```sh
cat > /etc/init.d/myapp <<'EOF'
#!/bin/sh
case "$1" in
  start)  /root/hello & ;;
  stop)   killall hello ;;
esac
EOF
chmod +x /etc/init.d/myapp
update-rc.d myapp defaults 2>/dev/null || ln -s /etc/init.d/myapp /etc/rcS.d/S99myapp
```

想验证自启动有没有生效，串口里重启 `reboot`，看日志里有没有你的程序输出。

---

## 常见故障速查

| 现象 | 原因 | 解决 |
|---|---|---|
| `No such file or directory`（文件确实在） | 动态链接器缺 `ld-linux-armhf.so.3` | 改 `-static` 重编 |
| `Permission denied` | 没有执行权限 | `chmod +x 文件` |
| `Illegal instruction` | 软/硬浮点不匹配，或 CPU 不支持 NEON | 去掉 `-mfloat-abi=hard -mfpu=neon-vfpv4` 重编 |
| `GLIBC_2.xx not found` | 板子 glibc 比编译机旧 | `-static` 重编 |
| scp 报 `Connection refused` | 板子没跑 sshd | 串口里 `/etc/init.d/S50sshd restart` 或 `dropbear` |
| ssh 密码不对 | root 密码不是默认值 | 串口里 `passwd root` 重设 |
| ping 不通 | 网段不一致 / 线是充电线 | 核对 `ifconfig` 和 PC IP，换数据线 |
| 板子完全没反应 | 没上电 / 串口插错口 | 电源灯、插 `USB_UART` 口（不是 `USB_OTG`） |

---

## 一页纸总结（贴墙版）

```sh
# ① 串口（COM3 115200）里，设 IP + 设密码
ifconfig eth0 192.168.1.20 netmask 255.255.255.0 up
passwd root

# ② PC 网卡设 192.168.1.100/24

# ③ 虚拟机里编译
arm-linux-gnueabihf-gcc -O2 -Wall -static -s -o hello hello.c

# ④ 传
scp hello root@192.168.1.20:/root/

# ⑤ 跑
ssh root@192.168.1.20 "chmod +x /root/hello && /root/hello"
```
