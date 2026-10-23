#!/usr/bin/env python3
"""探测 Android TV 的按键注入通道，输出建议配置。

用法:
    python probe_tv_input.py 192.168.1.20:5555

不依赖本项目，任何 Android TV 都能跑。
"""
import re
import subprocess
import sys

TV = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.20:5555"


def sh(cmd, timeout=40):
    r = subprocess.run(["adb", "-s", TV, "shell", cmd],
                       capture_output=True, timeout=timeout)
    return (r.stdout + r.stderr).decode(errors="replace")


def main():
    # ---- 1. 系统底细 ----
    print("== 系统 ==")
    props = ["ro.product.model", "ro.board.platform", "ro.build.version.sdk",
             "ro.build.version.release", "ro.product.cpu.abi", "ro.build.tags"]
    for prop in props:
        print("  %-28s %s" % (prop, sh("getprop " + prop).strip()))

    try:
        sdk = int(sh("getprop ro.build.version.sdk").strip() or 0)
    except ValueError:
        sdk = 0
    abi = sh("getprop ro.product.cpu.abi").strip()
    evt_size = 24 if "64" in abi else 16
    print("  -> SDK=%d, input_event 结构体应为 %d 字节" % (sdk, evt_size))

    # ---- 2. 列出设备 ----
    print("\n== 输入设备 ==")
    raw = sh("getevent -pl 2>&1")
    devices = {}
    cur = None
    collecting_keys = False
    for line in raw.splitlines():
        m = re.search(r"add device \d+: (/dev/input/event\d+)", line)
        if m:
            cur = m.group(1)
            devices[cur] = {"name": "", "keys": []}
            collecting_keys = False
            continue
        m = re.search(r'name:\s+"(.+?)"', line)
        if m and cur:
            devices[cur]["name"] = m.group(1)
            continue
        if not cur:
            continue
        if "KEY (" in line or "BTN (" in line:
            collecting_keys = True
        if collecting_keys:
            devices[cur]["keys"] += re.findall(r"\b(?:KEY|BTN)_\w+\b", line)

    for dev, info in sorted(devices.items()):
        names = {k.replace("KEY_", "").replace("BTN_", "") for k in info["keys"]}
        dpad = [k for k in ("UP", "DOWN", "LEFT", "RIGHT") if k in names]
        print("  %-22s %-28s dpad=%s" % (dev, info["name"] or "(no name)",
                                         "/".join(dpad) if dpad else "无"))

    # ---- 3. 选候选 ----
    print("\n== 候选设备（方向键齐全的）==")
    cands = []
    for dev, info in sorted(devices.items()):
        names = {k.replace("KEY_", "").replace("BTN_", "") for k in info["keys"]}
        if {"UP", "DOWN", "LEFT", "RIGHT"}.issubset(names):
            lname = info["name"].lower()
            score = 0
            if any(t in lname for t in ("ir", "remote", "rc")):
                score += 10
            if "keypad" in lname or "panel" in lname:
                score -= 5
            if "mouse" in lname or "touch" in lname:
                score -= 10
            cands.append((score, dev, info["name"]))

    for score, dev, name in sorted(cands, reverse=True):
        print("  %+3d  %-22s %s" % (score, dev, name))

    if not cands:
        print("  !! 没有找到方向键齐全的设备，需要人工介入")
        return 1

    # ---- 4. 读键位表 ----
    best = sorted(cands, reverse=True)[0]
    dev_name = best[2]
    kl_name = dev_name.replace(" ", "_") + ".kl"
    print("\n== 键位表 /system/usr/keylayout/%s ==" % kl_name)
    kl = sh("cat /system/usr/keylayout/%s 2>&1" % kl_name)
    if "No such file" in kl or "not found" in kl.lower():
        print("  未找到，改用 Generic.kl")
        kl = sh("cat /system/usr/keylayout/Generic.kl")

    want = ["DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT",
            "DPAD_CENTER", "BACK", "HOME", "MENU", "VOLUME_UP", "VOLUME_DOWN"]
    found = {}
    for line in kl.splitlines():
        m = re.match(r"\s*key\s+(\d+)\s+(\w+)", line)
        if m and m.group(2) in want:
            found[m.group(2)] = int(m.group(1))

    for w in want:
        print("  %-14s %s" % (w, found.get(w, "?")))

    # ---- 5. 输出配置 ----
    print("\n== 建议写入代码的配置 ==")
    print('KEY_DEVICE = "%s";   // %s' % (best[1], dev_name))
    mapping = [("DPAD_UP", "KEY_UP"), ("DPAD_DOWN", "KEY_DOWN"),
               ("DPAD_LEFT", "KEY_LEFT"), ("DPAD_RIGHT", "KEY_RIGHT"),
               ("DPAD_CENTER", "KEY_SELECT"), ("BACK", "KEY_BACK"),
               ("HOME", "KEY_HOME"), ("MENU", "KEY_MENU"),
               ("VOLUME_UP", "KEY_VOLUP"), ("VOLUME_DOWN", "KEY_VOLDOWN")]
    for src, const in mapping:
        if src in found:
            print("private static final int %-11s = %d;" % (const, found[src]))
        else:
            print("// %s 未在键位表中找到，需人工确认" % const)

    print("\n注意：若实测左右相反，把 KEY_LEFT 与 KEY_RIGHT 的值对调。")
    print("注意：以上只是静态推断，务必按文档 ⑤ 做一次注入实测再定稿。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
