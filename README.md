# 公众号内容聚合与有声化工具

自动抓取订阅号最新文章，提炼要点，生成可播放的语音简报，部署到云端，手机随时查看。

## ✨ 功能特性

- 🔍 **全自动抓取**：基于 WeWe-RSS（微信读书接口），Docker 一键部署
- 🤖 **智能提炼**：LLM 提取核心观点、角度小标题、关键词高亮
- 📊 **主题聚类**：按区域分组，区域内按主题聚类，不强行凑主题
- 💬 **评论区高赞**：自动抓取文章评论区高赞内容（TOP3）
- 🔗 **原文跳转**：点击公众号名称直接跳转原文
- 🔊 **语音播报**：页面内嵌音频播放器，手机点击即听
- ⏰ **定时任务**：每天早上 7 点自动生成昨日简报
- ☁️ **云端部署**：部署到 Vercel，手机电脑随时打开链接查看，不需要 PC 开着

## 🚀 快速开始

### 前置条件

1. **Python 3.9+**
2. **Docker**（用于部署 WeWe-RSS 数据源）
3. **LLM API Key**（DeepSeek / OpenAI / 智谱）
4. **Node.js**（用于 Vercel CLI 部署，可选）

### 第一步：部署 WeWe-RSS（数据源）

```bash
docker run -d --name wewe-rss -p 4000:4000 -e DATABASE_TYPE=sqlite -e AUTH_CODE=你的密码 -v $(pwd)/wewe-data:/app/data cooderl/wewe-rss-sqlite
```

启动后：
1. 浏览器打开 `http://localhost:4000`
2. 用微信扫码登录微信读书
3. 搜索并添加你关注的公众号

### 第二步：安装本工具

```bash
cd wechat-daily-brief
pip install -r requirements.txt
```

### 第三步：编辑配置

打开 `config.yaml`，填入关键信息：

```yaml
data_source:
  wewe_base_url: "http://localhost:4000"
  wewe_auth_code: "你的密码"

llm:
  provider: "deepseek"
  api_key: "sk-xxx"
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"

categories:
  ai:
    accounts:
      - name: "量子位"
        rss_url: "http://localhost:4000/feeds/xxx.atom"
```

### 第四步：运行

```bash
# 生成今日简报（文字 + 语音）
python main.py

# 仅文字
python main.py --text-only
```

## ☁️ 云端部署（手机访问）

### 方案 A：Vercel 部署（推荐，免费）

部署后获得一个永久链接，手机电脑随时打开。

**首次部署：**

```bash
# 1. 安装 Vercel CLI
npm i -g vercel

# 2. 登录 Vercel（需要注册 https://vercel.com）
vercel login

# 3. 初始化项目
vercel

# 4. 部署
vercel --prod
```

部署成功后会得到一个链接，如 `https://daily-brief-xxx.vercel.app`

**生成简报后自动部署：**

```bash
python scheduler.py --deploy
```

### 方案 B：GitHub Actions（全自动，推荐）

1. 将项目推送到 GitHub
2. 在 GitHub 仓库 Settings → Secrets 中添加：
   - `DEEPSEEK_API_KEY`
   - `VERCEL_TOKEN`（从 https://vercel.com/account/tokens 获取）
   - `VERCEL_ORG_ID` 和 `VERCEL_PROJECT_ID`（运行 `vercel` 后在 `.vercel/project.json` 中找到）
3. GitHub Actions 会在每天北京时间 7:00 自动运行，生成简报并部署

### 方案 C：本地 Web 服务器（同一 WiFi）

```bash
# 启动服务器
python server.py

# PC 打开 http://localhost:8080
# 手机连同一 WiFi，打开显示的 LAN 地址
```

## ⏰ 定时任务

### Windows

```bash
# 双击运行，自动设置每天 7:00 的定时任务
setup-schedule.bat
```

### 手动测试

```bash
# 处理昨天的更新
python scheduler.py

# 生成并部署到云端
python scheduler.py --deploy
```

## 📁 项目结构

```
wechat-daily-brief/
├── main.py                 # Main entry
├── scheduler.py            # Scheduler + Vercel deploy
├── server.py               # Local web server
├── setup-schedule.bat      # Windows scheduler setup
├── start.bat               # Quick start
├── config.yaml             # User config
├── vercel.json             # Vercel config
├── requirements.txt
├── .github/workflows/
│   └── deploy.yml          # GitHub Actions auto-deploy
├── src/
│   ├── config.py
│   ├── fetcher.py
│   ├── parser.py           # Article parser + comment scraping
│   ├── summarizer.py       # LLM summarization + angle titles
│   ├── clustering.py       # Topic clustering
│   ├── aggregator.py
│   ├── tts.py
│   └── utils.py
└── output/                 # Generated briefs
    ├── 2025-01-15_brief.html
    ├── 2025-01-15_brief.md
    └── 2025-01-15_brief.mp3
```

## 📰 简报结构

```
📅 每日资讯简报
├── 🤖 AI向（2 个主题）
│   ├── 1 GPT-5发布
│   │   ▸ 性能大幅提升
│   │   OpenAI 发布新版本... 📌 量子位 ⏱ 3min [阅读原文 →]
│   │   └── 💬 评论区高赞 TOP3 ▾
│   │       🥇 太强了！👍 128
│   │       🥈 期待...👍 89
│   └── 2 AI芯片投资
│       ▸ 巨头押注
│       ...
├── 💰 财经向
├── 💼 求职向
├── 🏠 生活向
├── 🔊 语音播报 [▶ 播放]
├── 📖 术语速查
└── 📊 今日趋势点评
```

## ⚙️ LLM 配置

### DeepSeek（推荐）
```yaml
llm:
  provider: "deepseek"
  api_key: "sk-xxx"
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"
```

### OpenAI
```yaml
llm:
  provider: "openai"
  api_key: "sk-xxx"
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o-mini"
```

## 📄 License

MIT
