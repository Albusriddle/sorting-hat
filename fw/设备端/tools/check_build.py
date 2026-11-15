#!/usr/bin/env python3
"""
对 sorting_hat_base 做"准编译"检查。

做四件事：
  1) 括号配对检查
  2) 逐个 .cpp 编译，带真实 ESP32 宏（OFF / ERROR / SS）逼出宏撞名
  3) 两种配置都编：全部硬件关闭 / 全部硬件打开（含 Opus）
  4) 把 .ino 改写成 main.cpp 再编一次（模拟最坏情况：不依赖 IDE 自动原型）

用法：
  python check_build.py <固件目录> [<组长驱动目录>]
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ESP32_MACROS = ['-DOFF=0x03', '-DERROR=0xFFFFFFFD', '-DSS=1']
CXX_FLAGS = ['-std=c++17', '-Wall', '-Wextra', '-Wno-unused-parameter']

HERE = os.path.dirname(os.path.abspath(__file__))

ALL_ON = ['-DHAT_ENABLE_MIC', '-DHAT_ENABLE_SPK', '-DHAT_ENABLE_LED',
          '-DHAT_ENABLE_BTN', '-DHAT_ENABLE_OPUS', '-DHAT_ENABLE_VAD']


def strip_comments(text):
    out, i, n, in_str = [], 0, len(text), None
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == '\\' and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if ch == in_str: in_str = None
            i += 1; continue
        if ch in '"\'':
            in_str = ch; out.append(ch); i += 1; continue
        if text.startswith('//', i):
            j = text.find('\n', i); i = n if j < 0 else j; continue
        if text.startswith('/*', i):
            j = text.find('*/', i + 2); i = n if j < 0 else j + 2; continue
        out.append(ch); i += 1
    return ''.join(out)


def check_pairing(text):
    t = strip_comments(text)
    t = re.sub(r'"(\\.|[^"\\])*"', '""', t)
    t = re.sub(r"'(\\.|[^'\\])*'", "''", t)
    errs = []
    for a, b in [('{', '}'), ('(', ')'), ('[', ']')]:
        if t.count(a) != t.count(b):
            errs.append(f'{a}{b} 不配对：{t.count(a)}/{t.count(b)}')
    return errs


def prepare(fw_dir, drv_dir):
    tmp = tempfile.mkdtemp(prefix='hatcheck_')
    for name in os.listdir(fw_dir):
        # .h.example 是 secrets.h 的模板，git 里只提交它，检查时也要带上
        if name.endswith(('.h', '.cpp', '.ino', '.h.example')):
            shutil.copy(os.path.join(fw_dir, name), tmp)
    if drv_dir and os.path.isdir(drv_dir):
        for name in os.listdir(drv_dir):
            if name.endswith(('.h', '.cpp')) and name not in ('Arduino.h', 'Wire.h'):
                shutil.copy(os.path.join(drv_dir, name), tmp)
    for name in ('Arduino.h', 'ArduinoJson.h'):
        shutil.copy(os.path.join(HERE, name), tmp)
    sys.path.insert(0, HERE)
    import make_stubs
    make_stubs.write_all(tmp)
    return tmp


def compile_cpp(tmp, macros, label):
    print(f'\n--- {label} ---')
    ok = True
    cpps = [n for n in sorted(os.listdir(tmp)) if n.endswith('.cpp')]
    for name in cpps:
        cmd = ['g++'] + CXX_FLAGS + ['-fsyntax-only'] + ESP32_MACROS + macros + ['-I', tmp, os.path.join(tmp, name)]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0:
            print(f'  ✓ {name}')
        else:
            ok = False
            print(f'  ✗ {name}')
            for line in p.stderr.splitlines()[:10]:
                print('     ', line)
    return ok


def compile_ino(tmp, macros, label):
    print(f'\n--- {label} ---')
    src = os.path.join(tmp, 'sorting_hat_base.ino')
    with open(src, encoding='utf-8') as f:
        s = f.read()
    s = s.replace('#include <Wire.h>', '')
    s = re.sub(r'^//.*$', '', s, flags=re.M)
    main = os.path.join(tmp, 'main_check.cpp')
    with open(main, 'w', encoding='utf-8') as f:
        f.write(s)
    cmd = ['g++'] + CXX_FLAGS + ['-fsyntax-only'] + ESP32_MACROS + macros + ['-I', tmp, main]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode == 0:
        print('  ✓ .ino 当纯 C++ 编译通过')
        return True
    print('  ✗ .ino 编译失败')
    for line in p.stderr.splitlines()[:10]:
        print('     ', line)
    return False


def main():
    fw_dir = sys.argv[1]
    drv_dir = sys.argv[2] if len(sys.argv) > 2 else None
    tmp = prepare(fw_dir, drv_dir)
    print('临时目录:', tmp)

    print('\n--- 1) 括号配对 ---')
    ok = True
    for name in sorted(os.listdir(tmp)):
        if name.endswith(('.h', '.cpp', '.ino')) and name not in ('Arduino.h',):
            with open(os.path.join(tmp, name), encoding='utf-8') as f:
                errs = check_pairing(f.read())
            if errs:
                ok = False
                print(f'  ✗ {name}: {errs}')
    if ok:
        print('  ✓ 全部配对')

    # 驱动文件原样编译（组长给的，不改）
    ok &= compile_cpp(tmp, [], '2) 编译（硬件全关，驱动原样）')
    ok &= compile_ino(tmp, [], '3) .ino（硬件全关）')
    ok &= compile_cpp(tmp, ALL_ON, '4) 编译（硬件全开：MIC/SPK/LED/BTN/OPUS/VAD）')
    ok &= compile_ino(tmp, ALL_ON, '5) .ino（硬件全开）')

    print('\n结论:', '全部通过' if ok else '有错误，见上方 ✗')


if __name__ == '__main__':
    main()
