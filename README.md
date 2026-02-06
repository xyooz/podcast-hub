# 🎙️ Podcast Hub - 播客聚合平台

一个现代、时尚的播客聚合播放器，支持小宇宙、网易云等平台。

## 功能特性

- 🔍 搜索播客和节目
- ➕ 添加小宇宙分享链接，自动获取 RSS
- ❤️ 收藏喜欢的播客
- 📻 网页直接播放
- 📚 订阅管理
- 🕐 播放历史
- 🌙 现代暗色界面

## 快速开始

### 1. 安装依赖

```bash
pip install flask flask-cors requests beautifulsoup4 peewee
```

### 2. 运行服务

```bash
cd podcast-hub
python app.py
```

### 3. 访问

打开浏览器访问：`http://localhost:5000`

## API 接口

### 获取播客信息

```bash
GET /api/podcast/<podcast_id>
```

### 添加播客

```bash
POST /api/podcast
{
    "url": "小宇宙分享链接"
}
```

### 获取节目列表

```bash
GET /api/podcast/<podcast_id>/episodes
```

### 播放历史

```bash
GET /api/history
POST /api/history
{
    "episode_id": "xxx"
}
```

## 配置

在 `app.py` 中修改：

```python
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000
DATABASE_PATH = "podcasts.db"
```

## 部署

### 使用 Caddy

```Caddyfile
podcast.2001.life {
    reverse_proxy localhost:5000
}
```

## License

MIT
