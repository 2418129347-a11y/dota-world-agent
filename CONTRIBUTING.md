# Contributing

感谢你帮助改进 DOTA 每日游报。

## 开发流程

1. Fork 仓库并从 `main` 创建分支。
2. 保持改动范围清晰，不要提交生成输出、状态缓存或私人凭据。
3. 运行测试：

   ```bash
   python -m unittest discover -s tests -v
   ```

4. 使用演示数据检查输出：

   ```bash
   python .agents/skills/dota-world-digest/scripts/dota_digest.py \
     --fixture tests/fixtures/sample_items.json \
     --output-dir output \
     --summarizer fallback \
     --ignore-seen
   ```

5. 提交 Pull Request，说明变化、原因、测试结果和内容安全影响。

## 信息源贡献

新增来源时必须说明：

- 原始出版方和 URL；
- 来源层级与建议可信度；
- 是否需要登录、付费或绕过访问控制；
- 失败时的降级行为；
- 对敏感消息的交叉验证方式。

禁止加入需要绕过付费墙、认证、robots 控制或反爬机制的采集方式。

## 编辑策略贡献

- 比分、日期、选手、英雄、晋级和淘汰结论必须可追溯。
- 位置推断必须保留其推断属性。
- “本报 MVP”不得描述成赛事官方奖项。
- 不得为了填满版面而降低消息可信度门槛。
- 修改中国俱乐部或旅外选手名单时，请附上可靠来源。

## 安全

不要在 Issue、PR、测试夹具或日志中提交真实邮箱、SMTP 授权码、Token 或 API Key。安全问题请遵循 [SECURITY.md](SECURITY.md)。
