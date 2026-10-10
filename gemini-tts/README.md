# Gemini TTS 配音模块（用于 Remotion）

本目录是独立的配音工具，位于 `dreamforfree/remotion` 仓库中。Python 3.10+ 即可运行，不需要安装 Python 第三方包，也不需要为了配音编译仓库根目录的 Remotion 源码。

已提供：Gemini TTS 调用、WAV 保存、音频时长与帧数元数据、可选 1.2 倍变速、不覆盖已有输出、离线测试。尚未完成：真实 API 调用验证、逐句字幕对齐、视频工程渲染验证；这些需要在配置密钥及 Remotion 视频工程后执行。

## 在 Codex 云端创建环境

1. 设置 → Codex Cloud → Environments → Create environment。
2. 选择 `dreamforfree/remotion`，使用 `main` 分支。
3. 告诉配置助手：本次只配置 `gemini-tts` 目录的 Python 配音工具，不要自动构建仓库根目录的完整 Remotion 源码；另外需要视频制作时，在独立目录创建 Remotion 视频工程。
4. 确认 `python3` 可用。如需精确变速，安装 `ffmpeg`；Linux 常见安装命令为 `sudo apt-get update && sudo apt-get install -y ffmpeg`，以实际环境权限为准。
5. 配置以下网络密钥并允许访问 Google API 域名。
6. 发布环境，并从发布后的环境启动新任务。

### 新版界面的密钥配置

| 配置字段 | 内容 |
| --- | --- |
| Network secret / 网络密钥 Key | `GEMINI_API_KEY` |
| Value | 在配置界面粘贴你的 Gemini API Key |
| Allowed domains | `generativelanguage.googleapis.com` |
| Privacy / Who can use | `Only me` |

脚本使用系统 HTTP/HTTPS 代理，并把密钥占位值直接放入 HTTPS 请求头 `x-goog-api-key`，不会写入代码、URL 或输出元数据。新版 Codex 网络密钥在允许目的地由代理替换成真实值。

也可以在 Personal vault 中保存同名网络密钥，但环境必须请求该 Key，而且允许域名必须包含上述目的地。个人保险库的值不会自动注入所有任务。

如果程序需要直接读取真实值，也可使用环境变量 `GEMINI_API_KEY`；这意味着运行中的程序能读取真实密钥。旧版仅在 setup 阶段提供的 Secrets 不能用于后续任务里的动态配音。不要将密钥落盘来绕过这一限制。

密钥只适用于选择此环境的任务；不要假定其他 Work 对话已经获得它。这个仓库目前为公开仓库，真实密钥、文稿和生成媒体都不应提交；只有示例文稿属于仓库。

## 检查及生成配音

从仓库根目录运行：

```bash
cd gemini-tts
python3 gemini_tts.py --check
python3 gemini_tts.py --text narration.txt --out output/test-001.wav
```

`--check` 只检查配置是否存在，不验证密钥有效性，也不调用 API。第二条命令才会实际调用 API，使用 Google 项目的配额并可能产生费用。

替换 `narration.txt` 为你的 UTF-8 口播稿。需要之前视频用的精确 1.2 倍速度时：

```bash
python3 gemini_tts.py --text narration.txt --out output/test-002.wav --speed 1.2
```

变速通过 FFmpeg `atempo` 完成，保留音高。不要同时要求模型用 1.2 倍语速，否则会叠加速度变化。每次使用新的输出文件名，工具会拒绝覆盖已有文件。

输出包括 WAV 和同名 JSON，JSON 记录变速后的实际时长、30fps 帧数、模型、音色和文稿，不包含密钥。

## 模型和音色

编辑 `config.json`：

- `model`：默认 `gemini-3.8-flash-tts`。可根据账号可用性改为同一接口格式的 `gemini-3.8-flash-lite-tts`。
- `voice`：默认 `Kore`，可替换为 Google 官方列表中的音色。
- `style`：普通话、语气和叙述风格。

当前脚本按 Google 官方 Gemini 3.8 TTS 的 Interactions REST 格式实现；较早的 2.5/3.1 Preview 模型的请求及音频格式不同，不能只改模型名就保证兼容。实际模型权限、计费和配额需用你自己的账号验证。

## 给 Remotion 使用

把生成的 WAV 复制到你的视频工程的 `public/audio/` 目录。例如：

```bash
mkdir -p ../my-video/public/audio
cp output/test-001.wav ../my-video/public/audio/test-001.wav
```

在视频组件中引用：

```tsx
import {Audio} from '@remotion/media';
import {staticFile} from 'remotion';

export const Narration = () => (
  <Audio src={staticFile('audio/test-001.wav')} />
);
```

需在视频工程里安装与 `remotion` 同版本的 `@remotion/media`。视频时长参考输出 JSON 的 `durationInFrames`（默认 30fps）；如工程使用其他帧率，生成时传入 `--fps`。音频已经执行 `--speed 1.2` 时，不要再设置 `playbackRate={1.2}`。

Gemini TTS 输出并不在这里提供逐字时间轴。真实字幕应以最终音频为依据另行对齐；JSON 中的 `captionTiming` 明确标记为 `not_generated`。字幕去逗号和句号可在字幕制作时处理，配音稿保留标点有助于自然停顿。

## 离线测试

```bash
cd gemini-tts
python3 -m unittest -v
```

测试使用模拟响应，不需要 API Key，不向 Google 发请求；变速测试需要 FFmpeg。覆盖请求认证、音频响应验证、时长、禁止覆盖、精确变速和检查模式。

## 后续给云端 Codex 的指令

> 使用当前仓库的 gemini-tts 目录。确认 GEMINI_API_KEY 已由云端网络密钥配置，不打印它。先执行 --check，再用示例文稿生成 output/test-001.wav，报告实际模型和时长。如果权限、配额或计费失败，说明原因，不擅自换到其他收费服务。之后把音频接入我的 Remotion 视频工程，按最终音频对齐字幕，字幕去掉逗号和句号。

## 官方参考

- [Gemini TTS](https://ai.google.dev/gemini-api/docs/speech-generation)
- [Gemini API Key](https://ai.google.dev/gemini-api/docs/api-key)
- [Codex 云端环境与网络密钥](https://learn.chatgpt.com/docs/environments/cloud-environments)
- [Remotion 音频](https://www.remotion.dev/docs/audio)
