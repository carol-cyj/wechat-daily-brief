# 🚀 从零开始使用指南

## 前置条件

你需要准备：
1. **一台电脑**（Windows / Mac / Linux 都行）
2. **Python 3.9+**（[下载地址](https://www.python.org/downloads/)）
3. **Docker Desktop**（[下载地址](https://www.docker.com/products/docker-desktop/)）
4. **一个 LLM API Key**（推荐 DeepSeek，最便宜）

---

## 第一步：准备环境（10分钟）

### 1.1 安装 Python

下载安装 Python，安装时**勾选 "Add Python to PATH"**。

验证安装：
```bash
python --version
# 应该显示 Python 3.9 或更高版本
```

### 1.2 安装 Docker

下载 Docker Desktop 并安装，启动后确认 Docker 在运行：
```bash
docker --version
# 应该显示 Docker version xx.x.x
```

### 1.3 获取 LLM API Key

**推荐 DeepSeek（最便宜）**：
1. 打开 https://platform.deepseek.com/
2. 注册账号
3. 进入「API Keys」页面
4. 点击「创建 API Key」
5. 复制 Key（格式如 `sk-xxx`）

---

## 第二步：部署 WeWe-RSS 数据源（10分钟）

WeWe-RSS 负责自动抓取你关注的公众号文章。

### 2.1 一键启动

**Windows 用户（最简单）：**

直接双击运行项目里的 `start-wewe-rss.bat` 文件即可。

**Mac/Linux 用户：**

打开终端，复制粘贴下面整段命令（注意是一行）：

```bash
docker run -d --name wewe-rss -p 4000:4000 -e DATABASE_TYPE=sqlite -e AUTH_CODE=yourpassword -v "$(pwd)/wewe-data:/app/data" cooderl/wewe-rss
```

**如果上面都不行，手动分步执行：**

```bash
# 1. 先创建数据文件夹
mkdir ~/wewe-data

# 2. 再启动容器（Windows CMD 用下面这行）
docker run -d --name wewe-rss -p 4000:4000 -e DATABASE_TYPE=sqlite -e AUTH_CODE=yourpassword -v "%USERPROFILE%/wewe-data:/app/data" cooderl/wewe-rss

# 2. 或者（Windows PowerShell 用下面这行）
docker run -d --name wewe-rss -p 4000:4000 -e DATABASE_TYPE=sqlite -e AUTH_CODE=yourpassword -v "$env:USERPROFILE/wewe-data:/app/data" cooderl/wewe-rss
```

### 2.2 配置公众号

1. 浏览器打开 http://localhost:4000
2. 用微信扫码登录「微信读书」
3. 在搜索框搜索你关注的公众号（如"量子位"、"财联社"）
4. 点击「添加」
5. 重复添加所有你关注的公众号

### 2.3 获取 RSS 地址

添加完公众号后，每个公众号旁边会有一个 RSS 图标，点击复制 RSS 地址。
格式类似：`http://localhost:4000/feed/xxxxx`

---

## 第三步：配置工具（5分钟）

### 3.1 解压项目

把 `wechat-daily-brief.zip` 解压到任意文件夹。

### 3.2 安装依赖

打开终端，进入项目文件夹：

```bash
cd wechat-daily-brief
pip install -r requirements.txt
```

### 3.3 创建配置文件

```bash
cp config.example.yaml config.yaml
```

### 3.4 编辑配置文件

用任意文本编辑器打开 `config.yaml`，修改以下内容：

```yaml
# ① WeWe-RSS 地址（第二步部署的）
data_source:
  wewe_base_url: "http://localhost:4000"
  wewe_auth_code: "yourpassword"  # 改成你设置的密码

# ② LLM API Key（第一步获取的）
llm:
  api_key: "sk-你的DeepSeek密钥"
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"

# ③ 公众号 RSS 地址（第二步获取的）
categories:
  ai:
    accounts:
      - name: "量子位"
        rss_url: "http://localhost:4000/feed/你的RSS地址"
      - name: "机器之心"
        rss_url: "http://localhost:4000/feed/你的RSS地址"
```

---

## 第四步：运行（1分钟）

```bash
python main.py
```

成功后会在 `output/` 文件夹生成：
- `2025-05-06_brief.md` — Markdown 文字简报
- `2025-05-06_brief.mp3` — 语音简报（可戴耳机听）

### 其他命令

```bash
python main.py --text-only   # 只生成文字，不生成语音
python main.py --date 2025-05-01  # 生成指定日期的简报
python main.py -v             # 查看详细日志
```

---

## 第五步：推送到 GitHub（可选）

### 5.1 安装 gh-cli

**Windows**：
```bash
winget install GitHub.cli
```

**Mac**：
```bash
brew install gh
```

### 5.2 登录 GitHub

```bash
gh auth login
# 按提示选择浏览器登录
```

### 5.3 推送代码

```bash
cd wechat-daily-brief
git init
git add .
git commit -m "Initial commit: 公众号内容聚合与有声化工具 v2.0"
gh repo create wechat-daily-brief --public --source=. --push
```

---

## 常见问题

### Q: Docker 启动失败？
确保 Docker Desktop 正在运行，然后重试。

### Q: pip install 报错？
尝试：`pip install -r requirements.txt --break-system-packages`

### Q: 没有抓到文章？
1. 确认 WeWe-RSS 正在运行（浏览器打开 http://localhost:4000）
2. 确认已添加公众号并获取了 RSS 地址
3. 确认 config.yaml 中的 rss_url 填写正确

### Q: LLM 调用失败？
1. 确认 API Key 正确
2. 确认账户有余额
3. 尝试换一个模型（如 `deepseek-chat`）

### Q: Edge TTS 语音合成失败？
沙箱环境无法连接微软服务器，但在你的本地电脑上应该可以正常使用。

---

## 项目文件说明

```
wechat-daily-brief/
├── main.py                  ← 运行这个
├── config.yaml              ← 编辑这个
├── config.example.yaml      ← 配置模板
├── requirements.txt         ← 依赖清单
├── templates/
│   └── brief_template.html  ← Web 简报模板（示例）
├── src/
│   ├── config.py            # 配置管理
│   ├── fetcher.py           # 文章抓取
│   ├── parser.py            # 正文解析
│   ├── summarizer.py        # AI 提炼（摘要/标签/术语）
│   ├── clustering.py        # 主题聚类
│   ├── aggregator.py        # 简报聚合
│   ├── tts.py               # 语音合成
│   └── utils.py             # 工具函数
└── output/                  ← 输出目录（自动创建）
```
