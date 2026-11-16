# 正点原子 阿尔法 I.MX6ULL —— 规范化开发流程（对齐官方课程 + 你本机实际环境）

> 依据：`【正点原子】阿尔法Linux开发板-视频PPT与笔记`（4 期课程）+ `A盘-基础资料`（例程/镜像/工具/手册）
> 本文把官方流程**翻译成你机器上的具体命令**，路径、IP、用户名都换成你实际在用的。
> 官方手册里的 `/home/alientek/...` 一律换成 `/home/ashes/...`，`192.168.10.x` 换成你的实际网段。

---

## 一、资料地图（两个目录里什么值得看）

### 1. 视频 PPT 与笔记（学习路径）

| 期 | 目录 | 内容 | 什么时候看 |
|---|---|---|---|
| 第1期 (B盘) | Ubuntu入门篇 | VMware、vim、gcc、Makefile、shell | 现在就看（你已装好环境，可跳读 15/16/17 讲） |
| 第2期 (C盘) | ARM(IMX6U)裸机篇 | 寄存器、时钟、GPIO、中断、LCD —— **不跑 Linux** | 想懂底层硬件时看 |
| **第3期 (D盘)** | **系统移植与根文件系统** | **u-boot 编译/移植、内核编译/移植、设备树、BusyBox、MfgTool 烧写** | **主线，必须看** |
| 第4期 (E盘) | Linux 驱动开发篇 | 字符设备、platform、I2C/SPI、input、LCD 驱动 | 主线看完接这个 |

### 2. A盘基础资料（工具和素材）

| 目录 | 内容 | 用途 |
|---|---|---|
| `01、例程源码` | 裸机例程 / 驱动例程 / **正点原子Uboot和Linux出厂源码** / NXP原版 / BusyBox / buildroot / Qt 例程 / C应用例程 | 抄代码、对着改 |
| `05、开发工具/01、交叉编译器` | **gcc-linaro-4.9.4-2017.01-x86_64**（78MB）、i686 版、Yocto SDK | 官方指定工具链 |
| `08、系统镜像/01、出厂系统镜像` | u-boot `.imx`（ddr256/ddr512 × emmc/nand）、kernel `linux-imx-4.1.15-2.1.0` + 一堆 `.dtb`、文件系统 | 救砖、对照验证 |
| `09、文档教程` | **驱动开发指南 V2.0.1**、C应用编程指南 V1.6、Qt 开发指南 | 主力教材 |
| `10、用户手册` | **快速体验 V2.8**、**TFTP&NFS 搭建 V1.3.2**、虚拟机使用手册、文件拷贝与固件更新 | 工具书，随时查 |

**最该先读的三份**：
1. `10、用户手册/01【正点原子】I.MX6U用户快速体验V2.8.pdf` —— 整体流程（123 页，看第 2 章"使用前准备"）
2. `10、用户手册/03【正点原子】I.MX6U网络环境TFTP&NFS搭建手册V1.3.2.pdf` —— 网络调试环境
3. `09、文档教程/【正点原子】I.MX6U嵌入式Linux驱动开发指南V2.0.1.pdf` —— 第 2 章开发环境、第 3 章 C 语言、后面全是驱动

---

## 二、环境标准（当前已就绪状态）

### 2.1 双工具链策略（重要，官方没明说但必须这么做）

| 工具链 | 路径 | 版本 | 用途 |
|---|---|---|---|
| **官方 4.9.4** | `/opt/gcc-linaro-4.9.4-2017.01-x86_64_arm-linux-gnueabihf/bin` | Linaro GCC 4.9-2017.01 | **编 u-boot 2016.03 / 内核 4.1.15 / 驱动模块 —— 必须用这个** |
| 系统 11.4.0 | `/usr/bin/arm-linux-gnueabihf-gcc` | Ubuntu 22.04 自带 | 编用户态应用程序、快速验证 |

原因：内核 4.1.15 是 2016 年的代码，用 GCC 11 编会撞上大量新版严格检查（`-Werror` 直接失败、隐式声明、内联汇编语法）。**老内核必须配老编译器**。

已验证 4.9.4 可用：

```bash
/opt/gcc-linaro-4.9.4-2017.01-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-gcc --version
# arm-linux-gnueabihf-gcc (Linaro GCC 4.9-2017.01) 4.9.4
```

### 2.2 目录规范（和官方一致，只是换了用户名）

```
/home/ashes/linux/
├─ tftp/                 ← TFTP 工作目录（zImage、dtb 放这里）
│  └─ tftp_test.txt
├─ nfs/
│  └─ rootfs/            ← NFS 根文件系统（解压 rootfs.tar.bz2 到这里）
└─ source/               ← 建议：内核、u-boot、BusyBox 源码都放这
```

权限：三个目录都 `chmod 777`（官方要求，避免 tftp/nfs 匿名访问被拒）。

### 2.3 服务状态（已配好并实测）

| 服务 | 配置 | 状态 | 实测 |
|---|---|---|---|
| **TFTP** | `/etc/default/tftpd-hpa` → `TFTP_DIRECTORY=/home/ashes/linux/tftp`，`--secure --create` | `active` | `tftp 127.0.0.1 -c get tftp_test.txt` 取回成功 |
| **NFS** | `/etc/exports` → `/home/ashes/linux/nfs *(rw,sync,no_root_squash,no_subtree_check)` | `active` | `mount -t nfs -o nolock,nfsvers=3` 挂载成功 |
| 防火墙 | `ufw disable` | 已关 | — |

NFS 版本现状（`cat /proc/fs/nfsd/versions` → `+3 +4 +4.1 +4.2`）：

- **v2 不可用** —— Ubuntu 22.04 的 6.8 内核已移除 NFSv2 服务端支持，`RPCNFSDOPTS` 里写 `--nfs-version 2` 也无效。
- **不影响本流程**：我们的方案是 **u-boot 用 TFTP 载内核** + **内核侧 NFS 挂根文件系统**（`root=/dev/nfs`），走的是 v3，够用。
- 只有当你让 **u-boot 自己**去 nfs 载文件时才会报 `Loading: * ERROR: File lookup fail` —— 那种情况才需要 v2，现在这条路走不通，改用 tftp。

### 2.4 交叉编译器环境变量

`/etc/profile.d/imx6ull-toolchain.sh` 已设置 `CROSS_COMPILE=arm-linux-gnueabihf-`、`ARCH=arm`。

编内核/u-boot 时**显式指定官方工具链**，不要靠 PATH（避免误用 11.4）：

```bash
export CROSS_COMPILE=/opt/gcc-linaro-4.9.4-2017.01-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-
export ARCH=arm
```

---

## 三、网络拓扑（必须先定，否则 TFTP/NFS 全废）

你那台虚拟机现在是 **NAT（192.168.229.129）**，板子根本看不到它。要让板子访问虚拟机的 TFTP/NFS，必须满足「板子 / Windows / 虚拟机 三者同网段」。

| 方案 | 做法 | 适用 | 注意 |
|---|---|---|---|
| **A. 全部接同一个路由器**（官方 1.2 节） | 板子网口 → 路由器；Windows 连同一路由器（网线或 WiFi）；VMware 网卡设 **桥接** | 最省心，推荐 | 桥接要选对物理网卡（无线网卡桥接有时不稳） |
| **B. 板子直连电脑网口，电脑 WiFi 上网**（官方 1.4 节） | 板子 → USB转RJ45 → PC；VMware 加一块 **仅主机(VMnet1)** 或桥接到该 USB 网卡 | 你现在这套硬件最适合 | 需要 VMware 双网卡：VMnet8(NAT) 上网 + VMnet1 连板子 |
| **C. 板子直连电脑，电脑没网**（官方 1.5 节） | 同上，但虚拟机也只能离线 | 应急 | apt 装不了包 |

**标准 IP 规划（本文后续都用这套）**：

```
开发板   192.168.1.20
虚拟机   192.168.1.100        ← TFTP/NFS 服务器
Windows  192.168.1.200        ← 只做串口终端 + FileZilla
网关     192.168.1.1（直连时可留空）
掩码     255.255.255.0
```

配套命令：

```bash
# 开发板（串口里）
ifconfig eth0 192.168.1.20 netmask 255.255.255.0 up
# 验证三方互通
ping 192.168.1.100        # 虚拟机
ping 192.168.1.200        # Windows
```

---

## 四、标准开发流程（6 个阶段，每阶段有验收标准）

### P0 环境自检（一次性）

```bash
# 1. 工具链
/opt/gcc-linaro-4.9.4-2017.01-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-gcc --version
# 2. 服务
systemctl is-active tftpd-hpa nfs-kernel-server
showmount -e                                  # 应看到 /home/ashes/linux/nfs
# 3. 目录
ls -ld ~/linux/tftp ~/linux/nfs/rootfs
```

**验收**：三条命令都正常，`showmount -e` 能看到共享目录。

---

### P1 固化系统（首次 / 救砖时）

官方两条路：

| 方式 | 工具 | 位置 | 说明 |
|---|---|---|---|
| **OTG 方式** | MfgTool | `05、开发工具/03、NXP官方原版MFG_TOOL烧写工具` 或 `04、正点原子MFG_TOOL出厂固件烧录工具` | 板子 `USB_OTG` 接电脑，拨码开关拨到 **USB 启动**，MfgTool 里点 Start，进度条走完断电重开 |
| **脚本方式** | 官方脚本 | `快速体验 V2.8` 第 2.2.2 节 | 系统已能启动时用，跑脚本自动 dd 到 eMMC |

镜像选择（对应 `08、系统镜像/01、出厂系统镜像`）：

```
u-boot : u-boot-imx6ull-14x14-ddr512-emmc.imx     ← 注意 ddr256 / ddr512 和 emmc / nand 别选错
kernel : linux-imx-4.1.15-2.1.0-e48931b1-v2.8/
         ├─ zImage
         └─ imx6ull-14x14-emmc-7-1024x600-c.dtb   ← 按你屏幕选（7寸1024x600/800x480、4.3寸、10.1寸、HDMI、VGA）
rootfs : 03、文件系统/
```

**验收**：串口能打印 u-boot → 内核 → `Please press Enter to activate this console` → 出现 `#`。

---

### P2 串口登录（一切调试的入口）

| 项 | 值 |
|---|---|
| 硬件 | 板子 `USB_UART` 口（**不是** `USB_OTG`）→ PC USB |
| 驱动 | CH340（资料在 `03、软件/CH340驱动`） |
| 终端 | PuTTY / SecureCRT / XCOM，**115200 8N1 无流控** |
| 控制台设备 | `ttymxc0` |

**验收**：能进 `#`，`uname -a`、`ifconfig` 都有输出。

> 板子不认 U 盘/网口时，串口永远是你的救命通道 —— 优先保证它可用。

---

### P3 搭建网络调试环境（TFTP + NFS）—— 已在虚拟机里做完

官方步骤（`TFTP&NFS搭建手册` 第 2、3 章），对应到你的机器：

```bash
# TFTP（官方用 xinetd，Ubuntu 22.04 用 systemd 服务更简单，效果一样）
sudo apt install tftp-hpa tftpd-hpa
sudo vi /etc/default/tftpd-hpa
#   TFTP_DIRECTORY="/home/ashes/linux/tftp"
#   TFTP_OPTIONS="--secure --create"
sudo systemctl restart tftpd-hpa

# NFS
sudo apt install nfs-kernel-server
sudo vi /etc/exports
#   /home/ashes/linux/nfs *(rw,sync,no_root_squash,no_subtree_check)
sudo exportfs -ra && sudo systemctl restart nfs-kernel-server
showmount -e
```

板子侧验证：

```sh
# TFTP 拉文件
tftp -g -r test.txt 192.168.1.100
# NFS 挂载
mkdir -p /mnt/get
mount -t nfs -o nolock,nfsvers=3 192.168.1.100:/home/ashes/linux/nfs /mnt/get
df -h | grep get
umount /mnt/get
```

**验收**：板子上能 `cat` 到 tftp 拉下来的文件；`df` 能看到 NFS 挂载点。

> **这一步通了，后面开发效率提升 10 倍** —— 改代码不用再拷来拷去。

---

### P4 编译 u-boot 与内核（官方第3期主线）

```bash
export CROSS_COMPILE=/opt/gcc-linaro-4.9.4-2017.01-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-
export ARCH=arm
cd ~/linux/source

# ---- u-boot ----
tar -xvf u-boot-2016.03-xxx.tar.bz2 && cd u-boot-2016.03-xxx
make distclean
make mx6ull_alientek_emmc_defconfig          # NAND 版用 mx6ull_alientek_nand_defconfig
make -j$(nproc)
# 产物：u-boot.imx

# ---- 内核 ----
cd ~/linux/source
tar -xvf linux-imx-4.1.15-xxx.tar.bz2 && cd linux-imx-4.1.15-xxx
make distclean
make imx_alientek_emmc_defconfig
make zImage -j$(nproc)
make dtbs -j$(nproc)
# 产物：arch/arm/boot/zImage
#       arch/arm/boot/dts/imx6ull-alientek-emmc.dtb
```

拷到 TFTP 目录：

```bash
cp arch/arm/boot/zImage ~/linux/tftp/
cp arch/arm/boot/dts/imx6ull-alientek-emmc.dtb ~/linux/tftp/
chmod 777 ~/linux/tftp/*
```

**验收**：`make` 无 error；`file zImage` 显示 `ARM`；dtb 能被 `dtc -I dtb -O dts` 反编译。

---

### P5 u-boot 里网络启动（TFTP 载内核 + NFS 挂根文件系统）

板子上电、串口里狂按回车进 u-boot，然后（命令来自官方手册 p63-65）：

```sh
# 1) 清干净环境变量（避免以前的残留干扰）
env default -a
saveenv

# 2) 网络参数
setenv ipaddr    192.168.1.20
setenv ethaddr   00:04:9f:04:d2:35
setenv gatewayip 192.168.1.1
setenv netmask   255.255.255.0
setenv serverip  192.168.1.100
saveenv

# 3) 测试能否 ping 通虚拟机
ping 192.168.1.100

# 4) 启动命令：TFTP 取内核和设备树到 DDR，然后 bootz
setenv bootcmd 'tftp 80800000 zImage;tftp 83000000 imx6ull-alientek-emmc.dtb;bootz 80800000 - 83000000'
saveenv

# 5) 根文件系统走 NFS
setenv bootargs 'console=ttymxc0,115200 root=/dev/nfs nfsroot=192.168.1.100:/home/ashes/linux/nfs/rootfs,proto=tcp rw ip=192.168.1.20:192.168.1.100:192.168.1.1:255.255.255.0::eth0:off'
saveenv

# 6) 启动
boot
```

`bootargs` 格式速记（官方 p65 给的模板）：

```
console=串口,波特率  root=/dev/nfs  nfsroot=虚拟机IP:文件系统绝对路径,proto=tcp rw
ip=开发板IP:虚拟机IP:网关:掩码::eth0:off
```

**注意**：
- `bootz 80800000 - 83000000` 里那个 `-` 是英文减号，**两边各一个空格**，手敲不要复制。
- 地址固定：内核 `0x80800000`、设备树 `0x83000000`（I.MX6ULL 的 DDR 起始 0x80000000）。

**验收**：串口里看到内核解压 → 挂载 NFS 根文件系统 → 进 `#`。此时板子的 `/` 就是虚拟机的 `~/linux/nfs/rootfs` —— 你在虚拟机里改东西，板子上立刻生效。

---

### P6 应用开发 / 驱动开发

**应用程序**（`C应用编程指南`，第 3 期之后）：

```bash
# 简单程序：直接编静态二进制，scp 过去跑
arm-linux-gnueabihf-gcc -O2 -static -s -o app main.c
scp app root@192.168.1.20:/root/
# 或者直接扔进 NFS 共享目录，板子上 /mnt/get/app 就能跑
cp app ~/linux/nfs/rootfs/root/     # 已挂 NFS 根的话，板子上就是 /root/app
```

**驱动**（`驱动开发指南 V2.0.1`）：

```bash
# 必须用「和板子内核完全一致」的源码树 + 官方 4.9.4 工具链
cd ~/linux/source/linux-imx-4.1.15-xxx
make ARCH=arm CROSS_COMPILE=$CROSS_COMPILE modules_prepare   # 首次准备
cd ~/linux/source/驱动例程/xxx_driver
make            # 例程 Makefile 里通常写死 KDIR
# 产物：xxx.ko
cp xxx.ko ~/linux/nfs/rootfs/root/
```

板子上：

```sh
insmod /root/xxx.ko
lsmod
dmesg | tail -20
rmmod xxx
```

**验收**：`insmod` 后 `dmesg` 能看到你 printk 的日志，`/dev` 下出现设备节点。

---

## 五、官方 vs 你这台机器 对照表（最容易搞错的地方）

| 项 | 官方文档 | 你的机器 |
|---|---|---|
| 用户名 | `alientek` | `ashes` |
| 工作根目录 | `/home/alientek/linux/` | `/home/ashes/linux/` |
| TFTP 目录 | `/home/alientek/linux/tftp` | `/home/ashes/linux/tftp` |
| NFS 目录 | `/home/alientek/linux/nfs` | `/home/ashes/linux/nfs` |
| Ubuntu 版本 | 16.04 / 18.04 | **22.04.5** |
| 交叉工具链 | `gcc-linaro-4.9.4-2017.01-x86_64` | 已装 `/opt/gcc-linaro-4.9.4-...`（另有系统 11.4 备用） |
| 网段 | 192.168.10.x | **192.168.1.x**（按你路由器改） |
| 虚拟机网络 | 桥接 / 双网卡 | 现在是 **NAT 192.168.229.129，必须改桥接或加 VMnet1** |
| TFTP 服务方式 | xinetd | systemd `tftpd-hpa`（等价） |
| NFS 版本 | v2/v3 | **只有 v3/v4**（v2 已被内核移除） |

## 六、踩坑清单（都是 22.04 特有的）

| 坑 | 现象 | 解法 |
|---|---|---|
| 虚拟机 NAT 隔离 | 板子 ping 不通虚拟机 | VMware 网卡改**桥接**或加一块 VMnet1，别用 NAT |
| NFSv2 缺失 | u-boot 里 `nfs` 命令报 `File lookup fail` | 别用 u-boot 的 nfs，改 TFTP 载内核（本流程已如此） |
| 新 gcc 编老内核 | 一堆 `error: implicit declaration` / `-Werror` | 用官方 4.9.4 工具链，别用系统 gcc 11 |
| tftp 下载超时 | `tftp: timeout` | `systemctl status tftpd-hpa`；目录权限 777；`ufw disable` |
| 板子 IP 和虚拟机不同网段 | ping 不通 | 三方必须在同一网段（前三段数字相同） |
| dtb 选错 | LCD 黑屏/分辨率不对 | 按屏幕型号选 `imx6ull-14x14-emmc-7-1024x600-c.dtb` 等 |
| u-boot 镜像选错 | 烧完不启动 | `ddr512`/`ddr256`、`emmc`/`nand` 要和你的核心板一致 |
| 拨码开关错 | MfgTool 认不到设备 | OTG 烧写要拨到 **USB 启动**，正常启动拨回 **eMMC** |

## 七、一页纸流程

```
① 接线   串口(USB_UART) + 网口 → PC
② 固化   MfgTool 烧 u-boot/kernel/rootfs（或脚本）
③ 串口   115200 进 # 提示符
④ 网络   板子 ifconfig 192.168.1.20；虚拟机桥接 192.168.1.100
⑤ 服务   虚拟机 TFTP + NFS（已配好，systemctl is-active 确认）
⑥ 编译   CROSS_COMPILE=官方4.9.4  make zImage dtbs
⑦ 部署   cp 到 ~/linux/tftp → u-boot 里 tftp + bootz + NFS rootfs
⑧ 开发   应用：静态二进制 scp；驱动：make modules → insmod
```

**验收一条命令**：

```bash
# 在虚拟机里跑，全绿就可以开始开发
bash -c 'echo "工具链: $(/opt/gcc-linaro-4.9.4-2017.01-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-gcc -dumpversion)"; \
echo "TFTP: $(systemctl is-active tftpd-hpa)"; \
echo "NFS : $(systemctl is-active nfs-kernel-server)"; \
echo "共享: $(showmount -e | tail -n +2)"; \
echo "目录: $(ls -d ~/linux/tftp ~/linux/nfs/rootfs)"'
```
