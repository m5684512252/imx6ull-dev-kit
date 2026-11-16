# I.MX6ULL 阿尔法开发板 · 开发工具与文档集

围绕 **正点原子 阿尔法 I.MX6ULL（Cortex-A7 / ARMv7 硬浮点）** 整理的一套可复用工具、脚本和规范化流程文档。
包含：板子发现与网络探测、交叉编译工具链搭建、内核编译流程、TFTP/NFS 调试环境、程序下发。

---

## 目录结构

```
.
├─ docs/
│  ├─ IMX6ULL_开发流程规范.md    # 对齐官方课程（4期+P盘资料）的完整流程：P0~P6 阶段、验收标准、踩坑清单
│  └─ board_deploy_guide.md      # 在板子上跑程序的实操手册：接线、设IP、编译、传输、自启动、故障速查
├─ windows/                      # 在 Windows 宿主机上跑的脚本
│  ├─ check_imx6ull.ps1          # 串口/USB 检测：查 CH340 是否枚举、COM 口、驱动缺失
│  ├─ check_board_link.ps1       # 链路检测：按 MAC 精确认板子，探 IPv6 链路本地 + 端口
│  ├─ find_board_ipv4.ps1        # 扫描常见网段找板子 IPv4（需管理员，自动切网段并还原）
│  ├─ probe_ipv6_ll.ps1          # IPv6 链路本地端口探测
│  ├─ capture_vm_window.ps1      # 抓取 VMware 窗口截图（排障用）
│  ├─ click_vm.ps1               # 向 VMware 窗口注入鼠标点击（坐标点击）
│  ├─ elf_info.py                # ELF 解析：架构/位宽/硬浮点/动态链接器/glibc 依赖
│  ├─ push_to_board.py           # 通过 SFTP 推送二进制到板子并执行（兼容老 dropbear）
│  └─ board_ssh.py               # 通过 IPv6 链路本地 SSH 到板子（paramiko）
├─ vm/                           # 在 Ubuntu 虚拟机上跑的脚本
│  ├─ install_cross_gcc.sh       # 安装官方 GNU 交叉工具链（apt）
│  ├─ setup_tftp_nfs.sh          # 配置 TFTP + NFS（对齐官方手册，适配 Ubuntu 22.04）
│  ├─ board_probe.sh             # 板子侧一次性体检：系统/glibc/包管理器/网络/CPU
│  ├─ install_vm.py              # 远程安装交叉工具链（paramiko 驱动，需环境变量 VM_PASS）
│  ├─ install_vm2.py             # 同上，第二轮：解 apt 锁 + 严格校验
│  └─ toolchain/
│     ├─ launcher.c              # Windows 侧 arm-linux-gnueabihf-* 启动器源码（zig/clang 后端）
│     └─ install_toolchain.py    # 生成上述启动器与目录结构
└─ .gitignore
```

---

## 环境事实（本套脚本对应的实际环境）

| 项 | 值 |
|---|---|
| 开发板 | 正点原子 阿尔法 I.MX6ULL，4GB eMMC，wm8960 音频 |
| 板子 MAC | `AA:6C:F9:2E:48:3D`（内核随机 MAC，EUI-64 推出 IPv6 LL） |
| 板子 IPv6 LL | `fe80::a86c:f9ff:fe2e:483d%<ifIndex>` |
| 板子 SSH | 22 端口，`SSH-2.0-dropbear_2015.71` |
| 宿主系统 | Windows 11（`ASHES\38368`），VMware Workstation + Ubuntu 22.04.5 |
| 虚拟机 | `192.168.229.129`（VMnet8 NAT），用户 `ashes` |
| 官方工具链 | `gcc-linaro-4.9.4-2017.01-x86_64_arm-linux-gnueabihf` → `/opt/` |
| 系统工具链 | `arm-linux-gnueabihf-gcc 11.4.0` → `/usr/bin` |
| 工作目录 | `~/linux/{tftp,nfs/rootfs,source,output}` |
| 内核源码 | `linux-imx-4.1.15-2.1.0-e48931b1-v2.8` |

---

## 三个最容易踩的坑（都在文档里详述）

1. **defconfig 名字**：是 `imx_alientek_emmc_defconfig`，**不是** `imx6ull_alientek_emmc_defconfig`（v2.8 源码里没有 `6ull`）。
2. **老内核 + 新 GCC**：Ubuntu 22.04 的 host gcc 11 默认 `-fno-common`，编 `scripts/dtc` 会报
   `multiple definition of 'yylloc'`。修法：`Makefile` 里 `HOSTCFLAGS` 加 `-fcommon`。
3. **编内核必须用官方 4.9.4**：用系统 gcc 11 编 4.1.15 会撞一堆 `implicit declaration` / `-Werror`。
   交叉编译器只管"给板子跑的东西"，`scripts/dtc` 这类**宿主工具**仍然用系统 gcc。

---

## 快速开始

### 板子不在手上（只做编译）

```bash
# 虚拟机内
export ARCH=arm
export CROSS_COMPILE=/opt/gcc-linaro-4.9.4-2017.01-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-
cd ~/linux/source/linux-imx-4.1.15
make imx_alientek_emmc_defconfig
make zImage -j$(nproc)
make dtbs
```

### 板子到手后（网络调试环境）

```bash
# 虚拟机内一次性配置
bash vm/setup_tftp_nfs.sh
showmount -e                      # 应看到 /home/<user>/linux/nfs

# 板子侧（串口）
ifconfig eth0 192.168.1.20 netmask 255.255.255.0 up
tftp -g -r zImage 192.168.1.100   # 验证 TFTP
```

### u-boot 网络启动

```sh
setenv ipaddr    192.168.1.20
setenv serverip  192.168.1.100
setenv bootcmd 'tftp 80800000 zImage;tftp 83000000 imx6ull-alientek-emmc.dtb;bootz 80800000 - 83000000'
setenv bootargs 'console=ttymxc0,115200 root=/dev/nfs nfsroot=192.168.1.100:/home/ashes/linux/nfs/rootfs,proto=tcp rw ip=192.168.1.20:192.168.1.100:192.168.1.1:255.255.255.0::eth0:off'
saveenv
boot
```

---

## 安全说明

- 脚本中的口令一律通过**环境变量**传入（`VM_PASS`），仓库里不含任何明文密码。
- `push_to_board.py`、`board_ssh.py` 使用交互式 `getpass` 或 SSH 公钥认证。
- 提交的 SSH 公钥仅为公钥，可公开。

## 许可

个人学习用途。相关内核/u-boot 源码版权归 NXP / 正点原子，本仓库只含自写脚本与文档。
