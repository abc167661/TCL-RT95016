# AGENTS.md — SkyHome 项目操作约束

给编码 agent / 自动化脚本的操作手册。人类读者看 `webremote.md`。

## 项目是什么

一套跑在老款 Android TV（API 17）上的自编译 launcher + 网页遥控服务。
目标是让这台 2016 年的电视还能被正常使用，而不是换硬件。

## 硬约束（违反会砖）

### ❌ 绝对不能做

| 禁止 | 原因 |
| --- | --- |
| 改动 `init.rc` / `init.*.rc` | 开机链路，写错电视无法启动且现场救不回来 |
| 改动 `/system/etc/inetd.conf` | 同上 |
| 替换 `/system/bin/sserver` | 同上；而且它是厂商 root 通道，动它可能触发校验 |
| 写 `persist.*` 属性 | 持久化分区，写坏需要工厂模式 |
| `pm disable` / `pm enable` 系统包 | 会破坏厂商 OTA 与开机流程 |
| 刷固件 / 改分区表 | 不可逆 |
| 假设按键走 `input keyevent` | 这台 ROM 会丢弃，实测无效 |

### ✅ 允许做

- 替换 `/system/app/SkyHome.apk`（唯一允许改写的系统文件）
- 安装/卸载第三方应用（`adb install` / `pm uninstall`）
- 读写 `/sdcard`、`/data/local/tmp`
- 调用 `WebRemote` 的 HTTP 接口
- 通过 8090 通道执行**只读**或**部署类**命令

## 验证纪律

**「接口返回 ok」不是成功判据。** 设备上的 root 通道永远回 `ok`。

必须用副作用验收：

| 操作 | 验收方式 |
| --- | --- |
| 按键 | 前台 Activity 变化（`dumpsys window | grep mCurrentFocus`）或截图差异 > 0 |
| 音量 | `adb logcat -d | grep "SetVolume\["` 出现且数值单调 |
| 部署 APK | `adb pull /system/app/SkyHome.apk` 后比 SHA256 |
| 界面变化 | `/api/shot` 前后两张图字节不同 |
| 应用启动 | `mCurrentFocus` 变成目标包名 |

## 构建与部署

```powershell
# 构建（会跑三道门：dex 一致 / 平台签名 / zipalign）
powershell -ExecutionPolicy Bypass -File build-newui.ps1

# 部署
adb connect <TV_IP>:5555
adb push project-newui/build/skyhome.apk /data/local/tmp/skyhome.apk
# 经 8090 通道复制进 /system（注意：该通道约 15 条命令后会假成功）
powershell -ExecutionPolicy Bypass -File rootexec.ps1 `
  -Command "mount -o rw,remount /system; cp -f /data/local/tmp/skyhome.apk /system/app/SkyHome.apk; sync"

adb reboot     # 必须重启才生效
# 等约 75 秒后 pull 回来核对 SHA256
```

**如果 pull 回来的哈希对不上**：8090 通道已经进入假成功状态。
重启电视后重试，不要怀疑构建。

## 代码地图

| 文件 | 职责 | 改动风险 |
| --- | --- | --- |
| `MainActivity.java` | 桌面、卡片、胶囊、抽屉、`webKey` | 中 |
| `WebRemote.java` | HTTP 服务、全部接口、按键注入 | 中 |
| `LiveActivity.java` | 直播播放、切台 | 中 |
| `AppCatalog.java` / `AppOrder.java` | 应用枚举与顺序持久化 | 低 |
| `GlassCard.java` | 毛玻璃渲染 | 低（注意性能） |
| `InstallCenter.java` / `SilentInstaller.java` | 安装面板与静默安装 | 高（涉及 pm） |
| `assets/webremote.html` | 手机页面（单文件） | 低，但**改完必须 `node --check`** |

## 已知陷阱（都踩过）

1. **写错输入设备**：`event5`(面板) 会产生 `3253x` 垃圾键码，App 忽略。必须用 `event0`(venus_IR)。
2. **按下/松开挤在一瞬间**：驱动会折叠这对事件，必须中间 `Thread.sleep(45)`。
3. **`AudioManager.setStreamVolume` 空转**：音量只能靠 `input keyevent 24/25`。
4. **`screencap` 加 `>` 重定向得 0 字节**：让它直接写文件。
5. **截图判完成不能看文件大小**：上一张同尺寸会误判，要比 `lastModified()`。
6. **HTML 用 Java 字符串拼**：一个转义错误整段 JS 静默失效，页面看着正常但按钮全死。
7. **焦点动画 + 渐变重建**：老芯片上表现为闪屏，焦点态只改描边颜色。
8. **`attach()` 只写在 `onCreate`**：Activity 复用后按键失灵，必须放 `onResume`。
9. **Windows 上内联 Python**：PowerShell 会吃掉引号，一律写 `.py` 再跑。
10. **`adb push` 远端路径**：需要 `MSYS_NO_PATHCONV=1`，否则被改写成 `C:/...`。

## 安全

设备存在 `0.0.0.0:8090` 的**无认证 root 命令通道**。
- 只在可信局域网使用
- 不要做端口映射
- 本项目日常运行不依赖它（按键/截图除外）

详见 `webremote.md` 的「安全说明」一节。

## 换到别的机型时（重要）

**本项目的 `event0` / 键码是验证机上探测出来的，不是通用值。**
别的电视几乎不可能一样。

接手一台新机器，**第一步永远是跑探测脚本**，不要抄常量：

```bash
python probe_tv_input.py <TV_IP>:5555
```

脚本会输出该机型应使用的设备节点、键码、以及 `input_event` 结构体大小。
拿到输出后：

1. 按输出改 `WebRemote.KEY_DEVICE` 和十个 `KEY_*` 常量
2. **做一次真实注入实测**（静态推断不等于能生效，见 webremote.md 第 ⑤ 步）
3. 若实测左右相反，把 `KEY_LEFT` 与 `KEY_RIGHT` 的值对调
4. 跑 `live/accept_final.py` 验收

遇到 `/system` 只读或所有通道都被拦截时，看 `webremote.md`
「适配时最可能遇到的三种情况」一节，改走无障碍服务方案。

## 改动后的最小验收

```bash
python live/accept_final.py       # 21 项：按键四向、OK、第三方 App、音量、截图、排序、页面
```

全绿才算完成。任何一项红，先看 `webremote.md` 的排查手册，不要盲改。
