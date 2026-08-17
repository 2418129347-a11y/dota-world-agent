# 刀塔世界新闻 Agent

每天聚合 Dota 2 官方新闻、职业比赛数据和有限的社区信号，完成去重、排序、中文摘要、HTML/纯文本渲染，并可通过 QQ SMTP 或 Resend 发送邮件。

## 本地演示

无需网络和密钥：

```powershell
python .agents/skills/dota-world-digest/scripts/dota_digest.py `
  --fixture tests/fixtures/sample_items.json `
  --output-dir output `
  --summarizer fallback `
  --ignore-seen
```

联网但不发送：

```powershell
python .agents/skills/dota-world-digest/scripts/dota_digest.py --output-dir output
```

## 启用 AI 中文摘要

设置 `OPENAI_API_KEY`，可选设置 `OPENAI_MODEL`；默认使用 `gpt-5.4-nano`。`--summarizer auto` 会在密钥存在时调用 OpenAI Responses API，失败则降级为确定性摘要。

## 启用 QQ SMTP 邮件（推荐）

先在 QQ 邮箱中开启 SMTP 服务并生成授权码。配置以下环境变量后显式添加 `--send`：

- `MAIL_PROVIDER=smtp`
- `SMTP_USERNAME`，完整 QQ 邮箱地址
- `SMTP_PASSWORD`，QQ 邮箱授权码，不是 QQ 密码
- `DIGEST_TO`，收件地址
- 可选：`DIGEST_FROM`，不设置时等于 `SMTP_USERNAME`
- 可选：`SMTP_HOST`，默认 `smtp.qq.com`
- 可选：`SMTP_PORT`，默认 `465`（SSL）；其他端口使用 STARTTLS

GitHub Actions 中把 `SMTP_USERNAME`、`SMTP_PASSWORD` 和 `DIGEST_TO` 保存为 Secrets，把仓库变量 `ENABLE_SEND` 设为 `true` 才会发送。保持该变量不为 `true` 即为影子运行。

为兼容已有仓库配置，工作流也接受 `EMAIL_USER`、`EMAIL_PASSWORD`、`EMAIL_TO` 这组三个 Secret 名称。

## 使用 Resend

将 `MAIL_PROVIDER` 设为 `resend`，并配置：

- `RESEND_API_KEY`
- `DIGEST_FROM`，例如 `刀塔世界 <daily@updates.example.com>`
- `DIGEST_TO`

如需 AI 中文摘要，再把 `OPENAI_API_KEY` 保存为 Secret。

## 安全约束

采集文本始终按不可信输入处理；不会执行文章中的指令，不绕过付费墙或登录，不复制全文。凭据不得提交到仓库。
