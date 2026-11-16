#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ELF 头解析：确认产物是 ARM 32 位硬浮点 Linux 可执行文件。"""
import struct
import sys

# Windows 控制台默认 936 代码页会把中文输出打成乱码，先切到 UTF-8
try:
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

EM = {3: "x86", 8: "MIPS", 20: "PPC", 40: "ARM", 62: "x86-64", 183: "AArch64", 243: "RISC-V"}
MACHINE_FLAGS = {
    (40, 0x05000000): "EF_ARM_ABI_FLOAT_HARD (硬浮点)",
    (40, 0x04000000): "EF_ARM_ABI_FLOAT_SOFT (软浮点)",
}


def inspect(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"\x7fELF":
        print(f"{path}: 不是 ELF")
        return
    ei_class = data[4]
    ei_data = data[5]
    endian = "<" if ei_data == 1 else ">"
    e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags = struct.unpack(
        endian + "HHIIIII", data[16:40])
    print(f"\n{path}")
    print(f"  类型      : {'EXEC 可执行' if e_type == 2 else 'DYN/PIE' if e_type == 3 else e_type}")
    print(f"  架构      : {EM.get(e_machine, e_machine)} ({'32 位' if ei_class == 1 else '64 位'}) "
          f"{'小端' if ei_data == 1 else '大端'}")
    print(f"  入口地址  : 0x{e_entry:x}")
    print(f"  e_flags   : 0x{e_flags:x}", end="")
    for (mach, flag), name in MACHINE_FLAGS.items():
        if e_machine == mach and (e_flags & flag) == flag:
            print(f"  -> {name}", end="")
    print()

    # 程序头：找 PT_INTERP（动态链接器）和 PT_LOAD
    e_phnum = struct.unpack(endian + "H", data[44:46])[0]
    interp = None
    for i in range(e_phnum):
        off = e_phoff + i * 32
        p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = struct.unpack(
            endian + "IIIIIIII", data[off:off + 32])
        if p_type == 3:  # PT_INTERP
            interp = data[p_offset:p_offset + p_filesz].rstrip(b"\x00").decode()
    if interp:
        print(f"  动态链接器: {interp}")
        print("  链接方式  : 动态 (glibc)")
    else:
        print("  链接方式  : 静态 (libc 已打包进文件，换任何 ARMv7 Linux 都能跑)")
    # 找 GLIBC 版本字符串
    vers = sorted(set(
        s.decode() for s in __import__("re").findall(rb"GLIBC_2\.\d+", data)
    ))
    if vers:
        print(f"  依赖 glibc: {', '.join(vers)}")


for p in sys.argv[1:]:
    inspect(p)
