# SkyHome · Android TV 桌面与手机网页遥控

> 给老款 Android TV（Android 4.2 / API 17）做一套「能看的桌面 + 能用手机控的遥控」。
> 包含自制桌面、直播页、以及一个局域网网页遥控台，手机浏览器打开就能操作电视。

<p align="center">
  <b>Android 4.2.1 · API 17 · armv7 · 无 Google 服务</b>
</p>

---

## 目录

- [这个项目解决什么问题](#这个项目解决什么问题)
- [功能](#功能)
- [工作原理](#工作原理)
- [快速开始](#快速开始)
- [手机遥控使用](#手机遥控使用)
- [HTTP API](#http-api)
- [技术笔记：这台电视教会我们的事](#技术笔记这台电视教会我们的事)
- [给 AI / Agent 的接入说明](#给-ai--agent-的接入说明)
- [适配其他机型（给 AI 的探测流程）](#适配其他机型给-ai-的探测流程)
- [排查手册](#排查手册)
- [安全说明：设备上的 root 命令通道](#安全说明设备上的-root-命令通道)
- [已知限制](#已知限制)
- [目录结构](#目录结构)
- [许可](#许可)

---

## 验证环境

本文所有结论都在下面这台真机上跑过，不是模拟器：

| 项 | 值 |
| --- | --- |
| 整机 | TCL 智能电视（2016 年产） |
| **机芯 / 平台** | **Realtek RTD299x**（`ro.board.platform=rtd299x`） |
| 产品型号 | `rtd299x_tv030` |
| **固件版本** | **`V8-RT95016-LF1V506`**（Bootcode `V8-RT95016-LB1V088`） |
| **Android 版本** | **4.2.1**（API 17，`JOP40D`） |
| 构建指纹 | `realtek/rtd299x_tv030/rtd299x_tv030:4.2.1/JOP40D/eng.ffeng.20161024.151326:eng/test-keys` |
| **CPU 架构** | **armeabi-v7a**（32 位 ARM，2 核） |
| 内存 | 957 MB 可用（`MemTotal` 980,272 kB） |
| 屏幕 | 1920×1080，density 1.5 |
| 系统签名 | `test-keys`（工程版，可写 `/system`） |

> 版本号可以在电视上直接核对：
> ```bash
> adb shell getprop ro.software.version_id   # V8-RT95016-LF1V506
> adb shell getprop ro.board.platform        # rtd299x
> adb shell getprop ro.build.version.sdk     # 17
> ```

> ⚠️ **上表是「我验证时用的那台机器」，不是运行前提。**
> 别人的电视几乎不可能同型号同固件。**设备节点名、键码、可用注入通道都会不一样**，
> 直接抄本文的任何 `eventN` 或键码都有很大概率不工作。
>
> **正确做法**：按 [适配其他机型](#适配其他机型给-ai-的探测流程) 一节跑一遍探测流程，
> 让脚本自己得出结论，而不是套用本文的样本值。

## 这个项目解决什么问题

很多 2015 年前后的国产智能电视，硬件还能用，但：

- 原厂桌面塞满广告，且不跟随内容更新
- 官方遥控 App 早已下架或连不上服务器
- 系统是 Android 4.2，绝大多数新 App 装不上（`minSdk` 早已 21+）
- 想从手机装个 APK，得插 U 盘、再点一堆确认

这个项目用一套自编译 APK 解决上述全部：**替换桌面 → 内置直播 → 手机网页遥控 + 上传安装**。

> 全部代码基于公开的 Android SDK 手工构建，不依赖第三方加固或私有 SDK。

## 功能

| 模块 | 说明 |
| --- | --- |
| **SkyHome 桌面** | 单排卡片式主页，毛玻璃卡片，自定义应用顺序 |
| **直播页** | 内置 40+ 央视频道，多源回退，死源自动跳过 |
| **手机遥控台** | 浏览器打开 `http://<TV_IP>:8087`，方向键/确定/返回/主页/音量 |
| **远程看画面** | 点一下就能把电视当前画面拉回手机（JPEG，用完即删） |
| **APK 上传安装** | 手机选文件 → 电视静默安装 |
| **安装包清理** | 递归扫描存储里的 `.apk` 残留，一键删除 |
| **硬件监控** | 内存 / CPU / 存储 / 负载实时显示 |
| **排序编辑** | 首页卡片和抽屉应用都能在网页上直接调顺序 |

## 工作原理

```
┌─────────────────┐         HTTP :8087          ┌──────────────────────┐
│  手机浏览器      │ ──────────────────────────▶ │  WebRemote (Java)    │
│  webremote.html │ ◀────────────────────────── │  HTTP server in-app  │
└─────────────────┘                             └──────────┬───────────┘
                                                           │
                                    ┌──────────────────────┼──────────────────────┐
                                    ▼                      ▼                      ▼
                            ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
                            │ 写 input 设备 │      │ 桌面/直播页   │      │ PackageManager│
                            │ 模拟遥控按键  │      │  Activity     │      │ 静默安装/查询  │
                            └──────────────┘      └──────────────┘      └──────────────┘
```

关键点：**遥控不是「往自己 App 里塞按键」，而是写内核输入设备**，所以能在任意第三方 App 里生效。

## 直接安装（不用编译）

`release/SkyHome-1.0.apk` 是已经编译、签名、验证过的成品。

```bash
adb connect <TV_IP>:5555
adb install -r release/SkyHome-1.0.apk
```

### 安装前必须确认三件事

| 检查 | 命令 | 期望 |
| --- | --- | --- |
| 系统版本够不够 | `adb shell getprop ro.build.version.sdk` | **≥ 17**（Android 4.2） |
| CPU 架构对不对 | `adb shell getprop ro.product.cpu.abi` | 含 `armeabi-v7a` |
| 能不能覆盖安装 | 见下方说明 | — |

### 关于签名（重要）

这个 APK 用的是 **AOSP 公开测试平台密钥**（`CN=Android`，SHA-1 `27196e386b875e76adf700e7ea84e4c6eee33dfa`），
不是某台机器独有的密钥。这带来两个结果：

- ✅ **可以直装在同样使用 AOSP testkey 的设备上**（2015 年前后不少国产电视就是）
- ⚠️ **如果你的电视用的是厂商私有平台密钥**，`adb install` 会报
  `INSTALL_FAILED_UPDATE_INCOMPATIBLE` 或签名冲突

**第一步先试普通安装**：

```bash
adb install -r release/SkyHome-1.0.apk
```

- 成功 → 装成普通应用，能用遥控台，但**不能接管 HOME 键**
- 失败（签名冲突）→ 需要系统权限，走下面的「装成系统应用」

### 装成系统应用（接管 HOME 键）

```bash
adb root                      # 需要设备支持
adb remount                   # 或 adb shell "mount -o rw,remount /system"
adb push release/SkyHome-1.0.apk /system/app/SkyHome.apk
adb shell chmod 644 /system/app/SkyHome.apk
adb shell sync
adb reboot
```

重启后按 HOME 键即进入 SkyHome。

> ⚠️ **只替换 `/system/app/SkyHome.apk` 这一个文件。**
> 不要动 `init.rc`、`inetd.conf`、`persist.*`——这些是开机链路，写错电视起不来。

### 校验下载完整性

```bash
sha256sum -c release/SkyHome-1.0.apk.sha256
# 应输出: SkyHome-1.0.apk: OK
```

### 装不上怎么办

| 报错 | 原因 | 处理 |
| --- | --- | --- |
| `INSTALL_FAILED_OLDER_SDK` | 系统低于 API 17 | 无解，这套只支持 4.2+ |
| `INSTALL_FAILED_CPU_ABI_INCOMPATIBLE` | CPU 架构不符 | 无解，只有 armeabi-v7a |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 签名冲突 | 先 `pm uninstall com.cleantv.ui`，或改用系统应用方式 |
| `INSTALL_FAILED_VERIFICATION_FAILURE` | 系统校验器拦截 | `adb shell settings put global verifier_verify_adb_installs 0` 后重试 |
| `INSTALL_PARSE_FAILED_NO_CERTIFICATES` | 下载损坏 | 重下并用 sha256 校验 |

### 装完先跑探测

即使装上了，**按键也可能不工作**——因为不同机型的输入设备不同。
装完第一件事：

```bash
python probe_tv_input.py <TV_IP>:5555
```

它会告诉你这台机器该用哪个设备节点和键码。详见 [适配其他机型](#适配其他机型给-ai-的探测流程)。

## 快速开始

### 前置条件

- Android TV，`API 17` 以上（本项目在 Android 4.2.1 上验证）
- 电视与手机/电脑同一局域网
- 电视开启 ADB（网络调试）
- 构建机需要：`aapt2`、`ecj`、`d8`、`zipalign`、`apksigner`、平台签名密钥

### 构建

```powershell
powershell -ExecutionPolicy Bypass -File build-newui.ps1
```

流水线：`aapt2 compile` → `aapt2 link` → `ecj` → `d8` → `zipalign` → `apksigner`。

构建脚本内置三道校验，任一不过即中止：

1. **DEX 字节一致性** —— 编译产物与源码改动对应
2. **签名者指纹** —— 必须用平台密钥签名（否则无法装为系统应用）
3. **zipalign 结果** —— 4 字节对齐

> 构建脚本是 PowerShell（Windows）。在 Linux/macOS 上需把脚本里的工具路径改成对应二进制，
> 或用你惯用的构建方式复现同一套参数：`--min-sdk-version 17 --target-sdk-version 17`。

### 部署到电视

```bash
export TV=<TV_IP>

adb connect $TV:5555
adb push build/skyhome.apk /data/local/tmp/

# 桌面必须装成系统应用才能接管 HOME 键
adb shell "mount -o rw,remount /system"
adb shell "cp -f /data/local/tmp/skyhome.apk /system/app/SkyHome.apk"
adb shell sync

adb reboot
```

重启后按 HOME 键即进入 SkyHome。

> ⚠️ **只替换 `/system/app/SkyHome.apk`，不要动开机链路的任何其他文件。**
> 改 `init.rc`、`inetd`、`persist.*` 等一旦出错，电视可能无法启动且难以恢复。

### 验证部署

```bash
adb pull /system/app/SkyHome.apk /tmp/check.apk
shasum -a 256 /tmp/check.apk build/skyhome.apk   # 两者应完全一致
```

## 手机遥控使用

电视和手机连同一个 WiFi/局域网，浏览器打开：

```
http://<TV_IP>:8087
```

页面分区：

| 区块 | 作用 |
| --- | --- |
| 状态条 | 内存 / CPU / 存储 / 负载，5 秒刷新 |
| 方向键 | 上、下、左、右、确定 |
| 系统键 | 返回、主页、菜单、音量 ± |
| 首页卡片 | 点即打开；`◀ ▶` 调整顺序 |
| 应用 | 点即启动；`↑ ↓` 调整顺序 |
| 上传 | 选 APK → 静默安装 |
| 看现在画面 | 截取电视当前画面 |
| 清理安装包 | 扫描并删除残留 APK |

## HTTP API

所有接口都在同一个端口，返回 JSON（`/api/shot` 返回 JPEG）。

### 状态与设备

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/sys` | 内存 / CPU / 存储 / 负载 / 开机时长 |
| `GET` | `/api/state` | 设备型号、SDK 版本、音量 |
| `GET` | `/api/diag` | 调试：前台 Activity、当前焦点控件、最后按键 |

### 遥控

| 方法 | 路径 | 参数 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/api/key` | `c=up\|down\|left\|right\|ok\|back\|home\|menu` | 发送按键 |
| `GET` | `/api/vol` | `d=1\|-1` | 音量增减 |

### 内容

| 方法 | 路径 | 参数 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/api/tiles` | — | 首页卡片列表 |
| `GET` | `/api/tile` | `i=N` | 打开第 N 张卡片 |
| `GET` | `/api/tilemove` | `i=N&d=±1` | 移动卡片顺序 |
| `GET` | `/api/apps` | — | 应用列表（按自定义顺序） |
| `GET` | `/api/appmove` | `pkg=…&d=±1` | 移动应用顺序 |
| `GET` | `/api/launch` | `pkg=…` | 启动应用 |
| `GET` | `/api/drawer` | — | 打开应用抽屉 |
| `GET` | `/api/back` | — | 关闭当前面板 |
| `GET` | `/api/install` | — | 打开安装面板（选 APK / 上传页入口） |
| `GET` | `/api/wallpaper` | — | 切换到下一张本地壁纸 |
| `GET` | `/api/channels` | — | 频道列表（名称 + 当前可用源） |

### 直播

| 方法 | 路径 | 参数 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/api/live` | `ch=N` | 切到第 N 个频道 |

### 文件

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/up` | 上传 APK 并安装 |
| `GET` | `/api/clean` | 扫描并删除残留 APK |
| `GET` | `/api/shot` | 当前画面（JPEG，960×540，用时约 8~10s） |

## 技术笔记：这台电视教会我们的事

这一节是整份文档最有价值的部分。以下每条都来自实际翻车与验证，不是推测。

### 1. 注入按键：三条路，只有一条走得通

目标是「让手机点的方向键，在任意 App 里都生效」。

| 方案 | 结果 | 为什么 |
| --- | --- | --- |
| `InputManager.injectInputEvent()` | ❌ | 被 ROM 的 InputDispatcher 丢弃，日志 `Asynchronous input event injection failed` |
| Activity 内 `dispatchKeyEvent()` | ❌ | 只能驱动**自己的窗口**。进第三方 App 就失效；弹窗盖住时反而还在操作底层界面 |
| **写 `/dev/input/eventN`** | ✅ | 走完整内核输入链路，任何前台窗口都能收到 |

### 2. 写哪个设备？这是第二次翻车

设备列表（`getevent -pl`）：

```
event0  venus_IR_input            ← 真遥控器（红外）
event1  venus_IR_mouse
event2  xcuts
event3  sim-kb                    ← 模拟键盘
event4  sim-mouse
event5  Realtek Keypad Device     ← 面板按键
```

一开始写了 `event5`（面板），看起来「能收到更多事件」，实测却是这样：

| 写入设备 | App 收到的事件 | 其中垃圾键码 |
| --- | --- | --- |
| `event0` | 6 条 | **0** |
| `event3` | 9 条 | 0 |
| `event5` | 18 条 | **24 个** |

`event5` 表面事件更多，是因为它一半被厂商定制层改写成了 `3253x` 这类无效键码，App 直接忽略。
**看起来工作，实际一半是垃圾** —— 所以要用「App 侧真正处理了多少」而不是「发了多少」来验收。

### 3. 键码要按设备各自的 `.kl` 文件来

不同设备有各自的键位映射表，**同一个功能在不同设备上可能是不同数字**：

| 功能 | `venus_IR_input.kl` | `Realtek_Keypad_Device.kl` |
| --- | --- | --- |
| 上 / 下 / 左 / 右 | 103 / 108 / 105 / 106 | 103 / 108 / 105 / 106 |
| **确定** | **28** | **353** |
| 返回 / 主页 / 菜单 | 158 / 102 / 139 | 158 / 102 / 139 |

```bash
# 查看设备的原始能力与键位表
getevent -pl /dev/input/event0
cat /system/usr/keylayout/venus_IR_input.kl
```

> 用错映射的典型症状：**确定键没反应**（用了 353，但那个设备里 28 才是 DPAD_CENTER）。

### 4. 时序：按下和松开不能挤在同一时刻

写 `input_event` 时，按下与松开之间必须有间隔，否则驱动会把这一对折叠掉：

```java
// ✅ 正确
write(ev, EV_KEY, code, 1);   // 按下
write(ev, EV_SYN, 0, 0);      // 同步
Thread.sleep(45);
write(ev, EV_KEY, code, 0);   // 松开
write(ev, EV_SYN, 0, 0);      // 同步
```

用 shell 拼 `sendevent ...; usleep 40000; sendevent ...` 在交互终端里没问题，但**经后台服务执行时 `usleep` 不一定生效**，两条命令落进同一个 jiffy，于是产生垃圾键码。**在 Java 里自己控制时序最可靠。**

### 5. 按键卡住会造成「连跳」

如果只发出了「按下」而「松开」丢失，系统会认为键一直被按住并自动连发 —— 表现是「按一下左，光标直接跳到最左边」。

排查方法：

```bash
getevent -pl /dev/input/event0     # 被按住的键会带 * 标记
```

修复：确保每条代码路径都会发 release；进程退出/异常时补发 release。

### 6. 音量：`AudioManager` 在这台机器上是空转

| 尝试 | 结果 |
| --- | --- |
| `Settings.System.volume_music` | 改了不出声 |
| `AudioManager.setStreamVolume()` | 返回成功，硬件不动 |
| `service call audio` | 无效 |
| **`input keyevent 24/25`** | ✅ 日志出现 `TvJni SetVolume[n]` → `RtkTv setVolume` |

这台电视的真实音量走厂商私有通道，只有音量键能触达。
另外**它没有硬上限**（连续加能到 65+），代码里不要假设 `15/27` 这类天花板。

### 7. 截图：`screencap` 慢，且重定向会写 0 字节

- `screencap` 在旧 SoC 上约 **7 秒**
- 如果执行环境给命令加了 `> 某文件`，`screencap -p 目标` 的输出会被重定向吞掉，得到 **0 字节文件**
- 判定「截图完成」不能只看文件大小不变（上一张同尺寸会误判），要比 `lastModified()`

正确做法：后台启动截图 → 轮询文件「大小 + 修改时间」连续两次一致 → 读取 → 立刻删除。

### 8. 网页 UI 用实体文件，别用字符串拼

早期把 HTML 拼在 Java 字符串里，一个转义符号出错就会让整段 `<script>` 静默失效 —— 页面看着正常，所有按钮都没反应。

改法：HTML 放 `assets/`，用文件加载，并在构建前跑语法检查：

```bash
node --check page.js
```

### 9. 焦点动画会拖垮老芯片

毛玻璃卡片每次获得焦点都重建 `LinearGradient` 并做缩放动画，在 2016 年的 SoC 上表现为**闪烁**。

优化：
- 焦点切换只更新描边颜色，不重建渐变
- 去掉 `scaleX/scaleY` 缩放动画

### 10. 回到前台后按键失灵

`WebRemote.attach(activity)` 如果只写在 `onCreate()`，Activity 被复用后句柄会指向旧窗口。
**必须在每个 Activity 的 `onResume()` 里重新 attach。**

## 给 AI / Agent 的接入说明

本项目从设计上就适合被自动化脚本或 AI agent 驱动。这一节是给 agent 看的「怎么用」，
人类读者可以跳过。

### 机器可读契约

仓库里另外提供三份给机器读的文件：

| 文件 | 用途 |
| --- | --- |
| `llms.txt` | 精简单页说明，符合 [llms.txt](https://llmstxt.org/) 约定，供模型快速摄取 |
| `api.json` | OpenAPI 3.0 描述，可直接喂给支持 tool-calling 的框架 |
| `AGENTS.md` | 给编码 agent 的操作约束：能改什么、不能碰什么、验收怎么判 |

### 三条硬约束（agent 必读）

1. **不要碰开机链路。** 只允许替换 `/system/app/SkyHome.apk`。
   `init.rc`、`inetd.conf`、`sserver`、`persist.*`、分区表——一律不动。
   写错会导致电视无法启动，且现场无法恢复。
2. **不要用「接口返回 ok」当成功判据。** 设备上的 root 通道永远回 `ok`。
   真正的成功判据是**副作用**：
   - 按键 → 前台 Activity 变了 / 画面差异 > 0
   - 音量 → 日志出现 `TvJni SetVolume[n]`
   - 部署 → `pull` 回来的 APK SHA256 与本地一致
3. **不要改键码，除非你有设备侧的日志证据。**
   `event0` + `28=OK` + Java 直写这套已经用「App 侧处理条数」和「截图差异」双重验证过。

### 推荐的调用顺序

```text
1. GET  /api/diag          确认服务活着、看前台是哪个 Activity
2. GET  /api/sys           确认设备状态（内存/CPU 是否异常）
3. GET  /api/tiles         拿到首页卡片索引
4. GET  /api/tile?i=N      打开目标卡片
5. GET  /api/shot          截图确认结果（注意：视频层截不到，会是黑帧）
```

### 幂等与副作用

| 接口 | 幂等 | 说明 |
| --- | --- | --- |
| `/api/sys`、`/api/state`、`/api/diag`、`/api/tiles`、`/api/apps`、`/api/channels` | ✅ | 纯读取 |
| `/api/key`、`/api/vol` | ❌ | 每次调用都会产生一次按键/音量变化 |
| `/api/tile`、`/api/launch`、`/api/live` | ❌ | 会切换前台界面 |
| `/api/tilemove`、`/api/appmove` | ❌ | 修改并持久化顺序，越界会返回 `ok:false` |
| `/api/clean` | ❌ | **会真实删除文件**，调用前先确认 |
| `POST /up` | ❌ | 会安装应用 |

### 并发注意

`WebRemote` 是**单线程**的 `ServerSocket` 循环。并发请求会排队，
不要同时发多个 `/api/key`——按键时序会乱。

### 超时建议

| 接口 | 建议超时 |
| --- | --- |
| 读取类 | 5 s |
| `/api/key`、`/api/vol` | 15 s（内部有 45 ms 按键间隔 + root 通道往返） |
| `/api/shot` | 45 s（`screencap` 单次约 7 s，加压缩与删除） |
| `POST /up` | 300 s（取决于 APK 大小与电视写入速度） |

### 一段可直接用的最小客户端

```python
import json, urllib.request

TV = "http://192.168.1.20:8087"          # 换成你的电视 IP

def call(path, timeout=15):
    with urllib.request.urlopen(TV + path, timeout=timeout) as r:
        body = r.read()
    if path.startswith("/api/shot"):
        return body                    # JPEG 原始字节
    return json.loads(body)

# 看一眼当前状态
print(call("/api/diag"))
print(call("/api/sys")["ramPct"], "%")

# 按一次确定
call("/api/key?c=ok")
```

### 给 agent 的验收模板

任何改动之后，跑这四条，全过才算完：

```bash
# 1. 服务活着
curl -s http://<TV_IP>:8087/api/diag

# 2. 按键真的生效（对比前后截图，差异 > 0）
curl -s http://<TV_IP>:8087/api/shot -o before.jpg
curl -s "http://<TV_IP>:8087/api/key?c=right"
curl -s http://<TV_IP>:8087/api/shot -o after.jpg
# 用任意工具比较两张图，像素不同才算生效

# 3. 音量真的变了（看厂商日志，不是看接口返回值）
adb logcat -d | grep "SetVolume\["
```

## 适配其他机型（给 AI 的探测流程）

**这一节是整份文档最重要的部分，如果你不是在这台 RTD299x 上跑，先读这里。**

不同厂商、不同机芯的 Android TV，在「怎么注入按键」这件事上差异极大。
下面是一套**可以自动跑完、自己得出结论**的探测流程。不要凭本文的样本值硬编码。

### 探测总览（按顺序做，每步都有判据）

```
① 摸清系统底细      → getprop
② 列出所有输入设备  → getevent -pl
③ 找到"真遥控器"    → 看设备名 + 能力集
④ 读它的键位映射表  → /system/usr/keylayout/*.kl
⑤ 实测哪条通道有效  → 逐设备注入 + 看 App 侧反应
⑥ 写回配置         → 只写探测出来的值
```

### ① 摸清系统底细

```bash
adb shell getprop ro.product.model
adb shell getprop ro.board.platform        # 机芯，决定 SoC 家族
adb shell getprop ro.build.version.sdk     # API level，决定能用哪些 API
adb shell getprop ro.build.version.release
adb shell getprop ro.product.cpu.abi       # 32 位还是 64 位，决定 input_event 结构体大小
adb shell getprop ro.build.tags            # test-keys 才能写 /system
```

**判据**：

- `test-keys` → 可以 `mount -o rw,remount /system`，能装系统应用
- `release-keys` → `/system` 通常只读，**换思路**：用普通应用 + 无障碍服务，或放弃接管 HOME
- `ro.product.cpu.abi` 含 `64` → `input_event` 结构体是 **24 字节**（`timeval` 两个 8 字节）；32 位是 **16 字节**

### ② 列出所有输入设备

```bash
adb shell getevent -pl
```

输出形如：

```
add device 1: /dev/input/event5
  name:     "Realtek Keypad Device"
  events:
    KEY (0001): KEY_HOME  KEY_UP  KEY_LEFT  KEY_RIGHT  KEY_DOWN  KEY_POWER  KEY_SELECT
```

**把所有 `add device` / `name` 抄下来**。常见命名规律（仅供参考，不要当铁律）：

| 名字里含 | 通常是什么 | 能不能注入 |
| --- | --- | --- |
| `IR` / `rc` / `remote` | 红外遥控接收器 | ✅ **首选**，最接近真遥控 |
| `keypad` / `panel` | 机身按键 | ⚠️ 可能被厂商定制层拦截 |
| `sim-kb` / `gpio-keys` | 模拟键盘 / GPIO 按键 | ✅ 通常可用 |
| `mouse` / `touch` | 鼠标、触摸 | ❌ 不适合发方向键 |
| `xcuts` / 厂商私有名 | 不明，需实测 | ❓ 先跳过 |

### ③ 找到"真遥控器"

判据：**能力集里同时有 `KEY_UP` `KEY_DOWN` `KEY_LEFT` `KEY_RIGHT`，且设备名像遥控器**。

```bash
# 把这几个候选都记下来
for d in /dev/input/event*; do
  echo "== $d =="
  getevent -pl $d 2>/dev/null | head -12
done
```

优先选**名字带 IR / remote / rc** 的那个。没有的话，按 ④ 逐个实测。

### ④ 读它的键位映射表

设备名 → 布局文件名，规则是把名字里的空格换成下划线：

```bash
ls /system/usr/keylayout/
# 找到对应文件，例如：
#   venus_IR_input.kl        ← 对应设备名 "venus_IR_input"
#   Realtek_Keypad_Device.kl ← 对应 "Realtek Keypad Device"
#   Generic.kl               ← 兜底默认

cat /system/usr/keylayout/<对应文件>.kl
```

**从里面抄出这几个值**（不同机型数字可能完全不同）：

```
DPAD_UP      → ?
DPAD_DOWN    → ?
DPAD_LEFT    → ?
DPAD_RIGHT   → ?
DPAD_CENTER  → ?   ← 最容易踩坑：有的机型是 28，有的是 353
BACK         → ?
HOME         → ?
MENU         → ?
VOLUME_UP    → ?
VOLUME_DOWN  → ?
```

> **真实案例**：本项目验证机上 `venus_IR_input.kl` 里 `DPAD_CENTER = 28`，
> 而 `Realtek_Keypad_Device.kl` 里 `DPAD_CENTER = 353`。
> 同一个「确定」键，两张表两个数字。**用错表就是「确定没反应」。**

### ⑤ 实测哪条通道有效（关键步骤）

**不要假设写进去就生效。** 每台机器的厂商定制层（TCL 叫 `PhoneWindowManager-kofi`，
别家可能叫别的）可能拦截、改写、甚至反转某些键。

用**对照实验**判定，而不是看「命令有没有报错」：

```bash
# 准备：打开一个能显示焦点的界面（系统设置最好）
adb shell am start -n com.android.settings/.Settings

# 对每个候选设备，逐个试：
DEV=/dev/input/event0
CODE=108          # 换成你在 ④ 里查到的 DPAD_DOWN

adb shell "sendevent $DEV 1 $CODE 1; sendevent $DEV 0 0 0; \
           usleep 40000; \
           sendevent $DEV 1 $CODE 0; sendevent $DEV 0 0 0"

# 然后看焦点有没有动
adb shell uiautomator dump /sdcard/u.xml
adb shell cat /sdcard/u.xml | grep -o 'text="[^"]*"[^>]*focused="true"'
```

**判据**：

| 现象 | 结论 |
| --- | --- |
| 焦点动了、方向正确 | ✅ 这个设备可用 |
| 焦点动了、但方向相反 | ⚠️ 设备可用，但**把这台的左右对调** |
| 焦点不动，日志有 `Asynchronous input event injection failed` | ❌ 这条通道被 ROM 丢弃，换下一个 |
| 焦点不动，但 App 日志出现 `keyCode=32xxx` | ❌ 产生了垃圾键码（设备不认这个 code），换设备 |
| 焦点不动，日志有 `interceptKey` / `handlePanelButton` | ❌ 被厂商定制层劫持，换设备 |

### ⑥ 把探测结果写成配置

**不要改代码里的常量**，而是让程序在启动时自己探测。推荐结构：

```java
// 启动时探测一次，结果缓存
static String resolveKeyDevice() {
    // 1. 遍历 /sys/class/input/eventN/device/name
    // 2. 优先匹配名字含 "ir" / "remote" / "rc" 的设备
    // 3. 没匹配到就用第一个能读到 keylayout 的设备
    // 4. 全失败则回退到 /dev/input/event0
}
```

然后把探测结果暴露在诊断接口里，方便验证：

```bash
curl -s http://<TV_IP>:8087/api/diag | grep keyDevice
```

### 一份可直接跑的探测脚本

仓库里已经带了这个脚本，直接跑即可：

```bash
python probe_tv_input.py <TV_IP>:5555
```

它会把上面 ①②③④ 四步全做完，并直接打印出**适合你这台机器的配置**，形如：

```
== 候选设备（方向键齐全的）==
  +10  /dev/input/event0      venus_IR_input
   +0  /dev/input/event3      sim-kb
   -5  /dev/input/event5      Realtek Keypad Device

== 键位表 /system/usr/keylayout/venus_IR_input.kl ==
  DPAD_UP        103
  DPAD_CENTER    28
  ...

== 建议写入代码的配置 ==
KEY_DEVICE = "/dev/input/event0";   // venus_IR_input
private static final int KEY_SELECT  = 28;
```

**它做的判断**：

| 步骤 | 逻辑 |
| --- | --- |
| 选设备 | 方向键齐全的设备里，名字含 `ir`/`remote`/`rc` 加分，含 `keypad`/`panel` 减分，含 `mouse`/`touch` 大幅减分 |
| 读键表 | 设备名把空格换成 `_` 再加 `.kl`；找不到就退回 `Generic.kl` |
| 推结构体 | `ro.product.cpu.abi` 含 `64` → 24 字节，否则 16 字节 |

⚠️ **这只是静态推断，不是最终答案**。选出的设备仍需按 ⑤ 做一次真实注入实测，
因为「键位表写得对」和「注入后真的生效」是两件事——本项目的验证机上就有设备键表齐全但注入被拦截的情况。

### 适配时最可能遇到的三种情况

| 情况 | 表现 | 对策 |
| --- | --- | --- |
| **`/system` 只读** | `mount -o rw,remount` 失败 | 放弃替换桌面，改成普通应用 + 无障碍服务；或找厂商解锁方式 |
| **所有设备都被拦截** | 注入后焦点都不动，日志有 `intercept` | 改用无障碍服务（`AccessibilityService` 发 `dispatchGesture`）或 `uiautomator` |
| **没有可写输入设备** | `/dev/input/event*` 权限 `crw-------` | 必须 root；否则只能走无障碍 |

### 给 AI 的一句话总结

> **不要抄本文的 `event0` 和 `28`。**
> 先跑上面的脚本，它会告诉你**你这台机器**该用哪个设备、哪个键码。
> 抄样本值是不工作的最常见原因。

## 排查手册

| 症状 | 可能原因 | 处理 |
| --- | --- | --- |
| 网页按钮全都没反应 | JS 语法错误导致整段脚本不执行 | `node --check` 检查页面脚本 |
| 方向键在第三方 App 里无效 | 写错了输入设备 | 换成真遥控器设备（见笔记 2），用 App 侧日志验收 |
| 确定键没反应 | 键码用了别的设备的映射 | 核对目标设备的 `.kl` 文件 |
| 按一下跳很远 | 按键卡在按下状态 | `getevent -pl` 看 `*` 标记，补发 release |
| 音量 ± 无效果 | 走了 `AudioManager` | 改用 `input keyevent 24/25` |
| 截图 0 字节 | 命令被加了 stdout 重定向 | 让 `screencap` 直接写文件，不要重定向 |
| 连拍拿到同一张图 | 用文件大小判完成 | 比较 `lastModified()` |
| 界面闪烁 | 焦点动画 + 渐变重建 | 去掉缩放动画，缓存渐变 |
| 从 App 返回后遥控失灵 | `attach()` 只在 `onCreate` | 移到 `onResume` |
| 部署后 APK 哈希不一致 | 后台命令通道静默失败 | 重启电视后重试，并 `pull` 回来比对 SHA256 |

## 安全说明：设备上的 root 命令通道

**这一节必须读完再决定要不要把这个项目暴露到不可信网络。**

### 这是一台已经 root 且带无认证命令通道的设备

在这台 TCL 电视上，存在一个厂商预置的、**以 uid 0 运行、无任何认证**的命令服务：

| 项 | 实测值 |
| --- | --- |
| 监听 | `0.0.0.0:8090`（**所有网卡**，不是仅回环） |
| 进程 | `/system/bin/sserver`，属主 **root** |
| 权限 | `-rwxr-xr-x root shell` |
| 协议 | 纯文本，一行一条命令，`\r\n` 结尾 |
| 认证 | **无**。连上就能发命令 |
| 回执 | 永远回 `ok`，**不代表执行成功**（要看副作用） |
| 执行方式 | `system("<你的命令> 2> /data/mtinfo")`，以 root 身份 |

实测从同一局域网的任意主机直连即可执行：

```bash
printf 'id > /mnt/sdcard/_probe.txt 2>&1\r\n' | nc <TV_IP> 8090
```

### 影响面

- 同一局域网内**任何人**（不需要密码、不需要配对、不需要电视端确认）都能以 **root** 身份在这台电视上执行任意命令
- 可以读写 `/system`、安装/卸载应用、读取所有应用数据、发起任意网络请求
- 电视通常长期在线，且用户不会察觉

### 这个项目的态度

本项目**只用它做部署**（把 APK 复制进 `/system/app`），日常运行不依赖它：

- 按键注入：改为 Java 直接写 `/dev/input/eventN`（`0666` 权限，**不需要 root**）
- 音量：走 `input keyevent 24/25`（需要 root，但这是唯一有效路径）
- 截图：需要 root 执行 `screencap`

### 加固建议（按代价从低到高）

1. **不要把 8090 暴露到公网**，路由器上也不要给它做端口映射
2. 电视只连**可信局域网**；访客网络与 IoT 网络隔离
3. 用 iptables 限制来源（需要 root，且重启会失效，需持久化）：
   ```bash
   iptables -A INPUT -p tcp --dport 8090 -s 192.168.1.0/24 -j ACCEPT
   iptables -A INPUT -p tcp --dport 8090 -j DROP
   ```
4. 不用时直接停掉：
   ```bash
   # 注意：停掉后本项目的部署脚本会失效，且可能影响厂商 OTA
   setprop ctl.stop sserver
   ```
5. 终极方案：刷入可信固件，或把这台电视放在物理隔离的网段

> ⚠️ 修改 `init.rc` / `inetd` 配置 / `sserver` 二进制属于**开机链路**，
> 一旦写错电视可能无法启动且难以救回。本项目的所有脚本都不碰这些文件。

### 同样的问题也存在于网页遥控端口（8087）

`WebRemote` 只校验来源是否私有网段（`10/8`、`172.16/12`、`192.168/16`），**没有身份认证**。
同一网段内任何人都能打开遥控台、上传并安装 APK。若要收紧，需要自行加 token 校验。

## 已知限制

- **播放器画面无法截图**：视频走硬件叠加层，`screencap` 只能拿到黑帧（UI 层正常）
- **直播源会失效**：频道来自公开源，挂掉是常态。已实现多源回退，但无法保证长期可用
- **局域网无鉴权**：服务只放行私有网段（`10/8`、`172.16/12`、`192.168/16`）。同一网段内任何人都能控制电视
- **系统应用安装需要重启**：替换 `/system/app` 下的 APK 后必须重启才生效
- **`/mnt/sdcard` 与 `/data` 可能同分区**：硬件监控里两者数值相同属正常现象

## 目录结构

```
.
├── project-newui/
│   ├── app/
│   │   └── src/main/
│   │       ├── java/…/ui/
│   │       │   ├── MainActivity.java      # 桌面：卡片、胶囊、抽屉
│   │       │   ├── LiveActivity.java      # 直播播放（含 onNewIntent 切台）
│   │       │   ├── AppsActivity.java      # 应用抽屉
│   │       │   ├── WebRemote.java         # HTTP 服务 + 全部接口 + 按键注入
│   │       │   ├── GlassCard.java         # 毛玻璃卡片（焦点态渲染）
│   │       │   ├── AppTileAdapter.java    # 卡片/应用列表适配器
│   │       │   ├── AppCatalog.java        # 应用枚举、排序入口
│   │       │   ├── AppOrder.java          # 顺序持久化（SharedPreferences）
│   │       │   ├── InstallCenter.java     # 安装面板
│   │       │   ├── SilentInstaller.java   # 静默安装
│   │       │   └── BackgroundLoader.java  # 模糊背景与图标异步加载
│   │       ├── assets/
│   │       │   ├── webremote.html         # 手机遥控页面（单文件，无外部依赖）
│   │       │   └── channels.txt           # 频道表：名称/图标/多个备用源
│   │       └── res/                       # 布局、图标、主题
│   └── build/
│       └── skyhome.apk                    # 构建产物
├── build-newui.ps1                        # 构建脚本（含三道校验）
└── webremote.md                           # 本文档
```

## 许可

MIT。使用前请自行确认当地关于接收公开电视流的法规，以及设备的保修条款。
