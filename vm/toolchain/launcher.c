/* ARM 交叉编译器启动器（Windows）
 * 依据自身文件名决定 zig 子命令，然后原样转发参数：
 *   arm-linux-gnueabihf-gcc.exe        -> zig cc  -target arm-linux-gnueabihf.2.23
 *   arm-linux-gnueabihf-g++.exe        -> zig c++ -target arm-linux-gnueabihf.2.23
 *   arm-linux-gnueabihf-gcc-static.exe -> zig cc  -target arm-linux-musleabihf -static
 *   arm-linux-gnueabihf-ar.exe         -> zig ar
 *   arm-linux-gnueabihf-ranlib.exe     -> zig ranlib
 * 这样在 make / 批处理里可以直接调用，不会有 .cmd 嵌套调用退出的问题。
 */
#include <process.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ZIG_EXE "C:\\Users\\38368\\miniconda3\\lib\\site-packages\\ziglang\\zig.exe"
#define PYTHON_EXE "C:\\Users\\38368\\miniconda3\\python.exe"
#define ELF_INFO_PY "C:\\Users\\38368\\toolchain\\arm-linux-gnueabihf\\elf_info.py"

#define TARGET_GLIBC "arm-linux-gnueabihf.2.23"
#define TARGET_MUSL "arm-linux-musleabihf"

static int contains(const char *hay, const char *needle)
{
    return strstr(hay, needle) != NULL;
}

int main(int argc, char **argv)
{
    const char *self = argv[0];
    const char *base = self;
    const char *p;

    for (p = self; *p; ++p) {
        if (*p == '\\' || *p == '/')
            base = p + 1;
    }

    /* readelf：直接用 python 解析 ELF，输出机器/位宽/动态链接器/glibc 依赖 */
    if (contains(base, "readelf")) {
        const char **rargv = (const char **)calloc((size_t)argc + 3, sizeof(char *));
        if (!rargv)
            return 1;
        int m = 0;
        rargv[m++] = PYTHON_EXE;
        rargv[m++] = ELF_INFO_PY;
        for (int i = 1; i < argc; ++i)
            rargv[m++] = argv[i];
        rargv[m] = NULL;
        intptr_t rrc = _spawnv(_P_WAIT, PYTHON_EXE, rargv);
        free((void *)rargv);
        return rrc == -1 ? 127 : (int)rrc;
    }

    const char *sub;
    const char *target = TARGET_GLIBC;
    int is_static = 0;

    if (contains(base, "g++") || contains(base, "c++")) {
        sub = "c++";
    } else if (contains(base, "ranlib")) {
        sub = "ranlib";
    } else if (contains(base, "ar.") || strstr(base, "-ar") != NULL) {
        sub = "ar";
    } else {
        sub = "cc";
    }

    if (contains(base, "static")) {
        is_static = 1;
        target = TARGET_MUSL;
    }

    if (argc < 2) {
        fprintf(stderr, "%s: no arguments given\n", base);
        return 1;
    }

    /* zig ar / ranlib 不需要 -target */
    int need_target = (strcmp(sub, "cc") == 0 || strcmp(sub, "c++") == 0);

    const char **nargv = (const char **)calloc((size_t)argc + 8, sizeof(char *));
    if (!nargv)
        return 1;

    int n = 0;
    nargv[n++] = ZIG_EXE;
    nargv[n++] = sub;
    if (need_target) {
        nargv[n++] = "-target";
        nargv[n++] = target;
    }
    if (is_static)
        nargv[n++] = "-static";
    for (int i = 1; i < argc; ++i)
        nargv[n++] = argv[i];
    nargv[n] = NULL;

    intptr_t rc = _spawnv(_P_WAIT, ZIG_EXE, nargv);
    free((void *)nargv);

    if (rc == -1) {
        fprintf(stderr, "[x] cannot execute zig: %s\n", ZIG_EXE);
        fprintf(stderr, "    install it with: python -m pip install ziglang\n");
        return 127;
    }
    return (int)rc;
}
