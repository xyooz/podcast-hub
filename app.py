#!/usr/bin/env python3
"""
🎙️ Podcast Hub - 播客聚合平台 API
Flask + SQLite
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_compress import Compress
from datetime import datetime
import os
import logging

# 配置
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db, Podcast, Episode, Favorite, PlayHistory, init_db
from crawler import PodcastParser

app = Flask(__name__)
app.config["SECRET_KEY"] = "podcast-hub-2024"
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400  # 静态文件缓存 1 天
app.config['COMPRESS_MIN_SIZE'] = 500  # 小于 500 字节不压缩
app.config['COMPRESS_LEVEL'] = 6  # 压缩级别
CORS(app)
Compress(app)

# 日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), "static")
TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), "templates")


# ==================== 测试路由 ====================

@app.route("/simple")
def simple():
    """调试页面"""
    return send_from_directory(TEMPLATE_FOLDER, "debug.html")


# ==================== API 接口 ====================

@app.route("/")
def index():
    """首页"""
    return send_from_directory(TEMPLATE_FOLDER, "simple.html")


@app.route("/static/<path:path>")
def static_files(path):
    """静态文件"""
    return send_from_directory(STATIC_FOLDER, path)


# ---------- 播客相关 ----------

@app.route("/api/podcast", methods=["GET"])
def get_podcasts():
    """获取订阅列表"""
    podcasts = Podcast.select().where(Podcast.is_subscribed == True).order_by(
        Podcast.updated_at.desc()
    )
    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in podcasts]
    })


@app.route("/api/podcast", methods=["POST"])
def add_podcast():
    """添加播客（通过链接）"""
    data = request.json
    
    if not data or "url" not in data:
        return jsonify({"success": False, "error": "缺少 url 参数"}), 400
    
    url = data["url"]
    
    try:
        # 解析链接
        platform, info = PodcastParser.parse_url(url)
        logger.info(f"解析播客: {info['title']}")
        
        # 检查是否已存在
        existing = Podcast.select().where(Podcast.rss_url == info["rss_url"]).first()
        if existing:
            return jsonify({
                "success": True,
                "message": "播客已存在",
                "data": existing.to_dict()
            })
        
        # 保存到数据库
        podcast = Podcast.create(
            title=info["title"],
            description=info.get("description", ""),
            image_url=info.get("image_url", ""),
            rss_url=info["rss_url"],
            feed_url=info.get("feed_url", ""),
            author=info.get("author", ""),
            category=info.get("category", platform),
            episode_count=info.get("episode_count", 0),
        )
        
        # 同步节目列表（如果有原始数据直接使用）
        raw_episodes = info.get("_raw_episodes", [])
        _sync_episodes(podcast.id, info["rss_url"], raw_episodes)
        
        return jsonify({
            "success": True,
            "message": "添加成功",
            "data": podcast.to_dict()
        })
        
    except Exception as e:
        logger.error(f"添加播客失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/podcast/<int:podcast_id>", methods=["GET"])
def get_podcast(podcast_id):
    """获取播客详情"""
    try:
        podcast = Podcast.get_by_id(podcast_id)
        return jsonify({"success": True, "data": podcast.to_dict()})
    except Podcast.DoesNotExist:
        return jsonify({"success": False, "error": "播客不存在"}), 404


@app.route("/api/podcast/<int:podcast_id>", methods=["DELETE"])
def delete_podcast(podcast_id):
    """删除播客（取消订阅）- 同时删除节目、收藏、历史记录"""
    try:
        podcast = Podcast.get_by_id(podcast_id)
        
        # 删除关联数据
        Episode.delete().where(Episode.podcast == podcast_id).execute()
        Favorite.delete().where(Favorite.podcast == podcast_id).execute()
        PlayHistory.delete().where(PlayHistory.podcast == podcast_id).execute()
        
        # 删除播客
        podcast.delete_instance()
        
        return jsonify({"success": True, "message": "已取消订阅"})
    except Podcast.DoesNotExist:
        return jsonify({"success": False, "error": "播客不存在"}), 404


@app.route("/api/podcast/<int:podcast_id>/refresh", methods=["POST"])
def refresh_podcast(podcast_id):
    """刷新播客（重新获取节目列表）"""
    try:
        podcast = Podcast.get_by_id(podcast_id)
        
        # 根据分类获取节目
        raw_episodes = []
        
        # 小宇宙页面
        if "xiaoyuzhoufm.com" in podcast.feed_url:
            from crawler import PodcastParser
            raw_episodes = PodcastParser._get_xiaoyuzhou_episodes(podcast.feed_url)
        # RSS feeds (xyzfm, danliren)
        elif podcast.category == "rss" or "xyzfm" in podcast.rss_url or "danliren" in podcast.rss_url:
            from crawler import PodcastParser
            raw_episodes = PodcastParser._get_rss_episodes(podcast.rss_url)
        
        _sync_episodes(podcast_id, podcast.rss_url, raw_episodes)
        
        # 重新获取更新后的播客信息
        podcast = Podcast.get_by_id(podcast_id)
        return jsonify({
            "success": True,
            "message": "刷新成功",
            "episode_count": podcast.episode_count
        })
    except Podcast.DoesNotExist:
        return jsonify({"success": False, "error": "播客不存在"}), 404


# ---------- 节目相关 ----------

@app.route("/api/podcast/<int:podcast_id>/episodes", methods=["GET"])
def get_episodes(podcast_id):
    """获取节目列表"""
    try:
        podcast = Podcast.get_by_id(podcast_id)
        episodes = (Episode.select()
                   .where(Episode.podcast == podcast_id)
                   .order_by(Episode.pub_date.desc()))
        
        # 限制返回字段，减少数据量
        return jsonify({
            "success": True,
            "data": [{
                "id": e.id,
                "podcast_id": e.podcast_id,
                "title": e.title[:200] if e.title else "",
                "audio_url": e.audio_url,
                "duration": e.duration,
                "duration_str": _format_duration(e.duration),
                "pub_date": e.pub_date.isoformat() if e.pub_date else None,
                "progress": e.progress or 0,
            } for e in episodes]
        })
    except Podcast.DoesNotExist:
        return jsonify({"success": False, "error": "播客不存在"}), 404


@app.route("/api/episode/<int:episode_id>", methods=["GET"])
def get_episode(episode_id):
    """获取节目详情"""
    try:
        episode = Episode.get_by_id(episode_id)
        return jsonify({"success": True, "data": episode.to_dict()})
    except Episode.DoesNotExist:
        return jsonify({"success": False, "error": "节目不存在"}), 404


# ---------- 播放相关 ----------

@app.route("/api/play/<int:episode_id>", methods=["POST"])
def play_episode(episode_id):
    """记录播放"""
    try:
        episode = Episode.get_by_id(episode_id)
        
        # 更新播放状态
        episode.is_played = True
        episode.save()
        
        # 记录历史
        PlayHistory.create(
            episode=episode_id,
            podcast=episode.podcast_id,
            progress=0,
            duration=episode.duration,
            created_at=datetime.now()
        )
        
        return jsonify({
            "success": True,
            "data": {
                "audio_url": episode.audio_url,
                "title": episode.title,
                "podcast_title": episode.podcast.get().title,
                "image_url": episode.podcast.get().image_url,
            }
        })
    except Episode.DoesNotExist:
        return jsonify({"success": False, "error": "节目不存在"}), 404


@app.route("/api/history", methods=["GET"])
def get_history():
    """获取播放历史"""
    history = (PlayHistory.select()
               .order_by(PlayHistory.played_at.desc())
               .limit(50))
    
    return jsonify({
        "success": True,
        "data": [h.to_dict() for h in history]
    })


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """获取播放统计"""
    try:
        # 总播放次数
        total_plays = PlayHistory.select().count()
        
        # 播放总时长（秒）
        from peewee import fn
        total_duration = PlayHistory.select(fn.SUM(PlayHistory.duration)).scalar() or 0
        
        # 按播客统计
        podcast_stats = []
        
        # 获取有播放历史的播客
        query = (PlayHistory
                 .select(PlayHistory.podcast_id, fn.COUNT(PlayHistory.id).alias('count'))
                 .where(PlayHistory.podcast_id.is_null(False))
                 .group_by(PlayHistory.podcast_id)
                 .order_by(fn.COUNT(PlayHistory.id).desc())
                 .limit(5))
        
        for h in query:
            try:
                podcast = Podcast.get_by_id(h.podcast_id)
                podcast_stats.append({
                    "id": h.podcast_id,
                    "title": podcast.title,
                    "count": h.count
                })
            except:
                pass
        
        # 格式化总时长
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        
        return jsonify({
            "success": True,
            "data": {
                "total_plays": total_plays,
                "total_duration": total_duration,
                "total_duration_str": f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟",
                "podcasts": podcast_stats
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/progress/<int:episode_id>", methods=["POST"])
def update_progress(episode_id):
    """更新播放进度"""
    try:
        data = request.json
        progress = data.get("progress", 0) if data else 0
        
        episode = Episode.get_by_id(episode_id)
        episode.progress = progress
        episode.played_at = datetime.now()
        episode.save()
        
        return jsonify({"success": True})
    except Episode.DoesNotExist:
        return jsonify({"success": False, "error": "节目不存在"}), 404


@app.route("/api/progress/<int:episode_id>", methods=["GET"])
def get_progress(episode_id):
    """获取播放进度"""
    try:
        episode = Episode.get_by_id(episode_id)
        return jsonify({
            "success": True,
            "data": {
                "progress": episode.progress,
                "duration": episode.duration,
                "played_at": episode.played_at.isoformat() if episode.played_at else None
            }
        })
    except Episode.DoesNotExist:
        return jsonify({"success": False, "error": "节目不存在"}), 404


# ---------- 收藏相关 ----------

@app.route("/api/favorite", methods=["GET"])
def get_favorites():
    """获取收藏列表"""
    favorites = (Favorite.select()
                .join(Podcast)
                .order_by(Favorite.created_at.desc())
                .limit(100))
    
    return jsonify({
        "success": True,
        "data": [f.podcast.to_dict() for f in favorites]
    })


@app.route("/api/favorite/<int:podcast_id>", methods=["POST"])
def add_favorite(podcast_id):
    """添加收藏"""
    try:
        podcast = Podcast.get_by_id(podcast_id)
        
        # 检查是否已收藏
        existing = Favorite.select().where(Favorite.podcast == podcast_id).first()
        if existing:
            return jsonify({"success": True, "message": "已收藏"})
        
        Favorite.create(podcast=podcast_id)
        return jsonify({"success": True, "message": "收藏成功"})
    except Podcast.DoesNotExist:
        return jsonify({"success": False, "error": "播客不存在"}), 404


@app.route("/api/favorite/<int:podcast_id>", methods=["DELETE"])
def remove_favorite(podcast_id):
    """取消收藏"""
    favorite = Favorite.select().where(Favorite.podcast == podcast_id).first()
    if favorite:
        favorite.delete_instance()
        return jsonify({"success": True, "message": "已取消收藏"})
    return jsonify({"success": False, "error": "未收藏"}), 404


# ==================== 辅助函数 ====================

def _sync_episodes(podcast_id: int, rss_url: str, raw_episodes: list = None):
    """同步节目列表"""
    try:
        # 如果有原始数据，直接使用
        if raw_episodes:
            entries = raw_episodes
        else:
            entries = PodcastParser.get_episodes(rss_url)
        
        # 更新节目数量
        Podcast.update(episode_count=len(entries)).where(Podcast.id == podcast_id).execute()
        
        # 获取已存在的音频 URL
        existing_urls = {ep.audio_url for ep in Episode.select(Episode.audio_url).where(Episode.podcast == podcast_id)}
        
        for entry in entries:
            audio_url = entry["audio_url"]
            if audio_url not in existing_urls:
                # 解析日期
                pub_date_str = entry.get("pub_date", "")
                pub_date = None
                if pub_date_str:
                    try:
                        from datetime import datetime
                        pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00").replace("+00:00", ""))
                    except:
                        pub_date = datetime.now()
                else:
                    pub_date = datetime.now()
                
                Episode.create(
                    podcast=podcast_id,
                    title=entry["title"],
                    description=entry.get("description", ""),
                    audio_url=audio_url,
                    duration=entry.get("duration", 0),
                    pub_date=pub_date,
                    episode_num=0
                )
                existing_urls.add(audio_url)
        
        logger.info(f"同步完成: {podcast_id}, {len(entries)} 集")
    except Exception as e:
        logger.error(f"同步节目失败: {e}")


# ==================== 模型扩展 ====================

class PodcastMixin:
    """播客模型扩展"""
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "image_url": self.image_url,
            "rss_url": self.rss_url,
            "author": self.author,
            "category": self.category,
            "episode_count": self.episode_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_subscribed": self.is_subscribed,
        }


class EpisodeMixin:
    """节目模型扩展"""
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "audio_url": self.audio_url,
            "duration": self.duration,
            "duration_str": _format_duration(self.duration),
            "pub_date": self.pub_date.isoformat() if self.pub_date else None,
            "episode_num": self.episode_num,
            "is_played": self.is_played,
        }


class PlayHistoryMixin:
    """播放历史模型扩展"""
    
    def to_dict(self):
        return {
            "id": self.id,
            "episode_id": self.episode_id,
            "podcast_id": self.podcast_id,
            "title": self.episode.get().title if self.episode else "",
            "podcast_title": self.podcast.get().title if self.podcast else "",
            "played_at": self.played_at.isoformat() if self.played_at else None,
        }


def _format_duration(seconds: int) -> str:
    """格式化时长"""
    if not seconds:
        return "00:00"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes >= 60:
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


# 绑定扩展方法
Podcast.to_dict = PodcastMixin.to_dict
Episode.to_dict = EpisodeMixin.to_dict
PlayHistory.to_dict = PlayHistoryMixin.to_dict


# ==================== 缓存控制 ====================

@app.after_request
def add_cache_control(response):
    """API 请求禁用缓存，静态文件启用缓存"""
    if request.path.startswith('/api/'):
        # API 无缓存
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    elif request.path.startswith('/static/'):
        # 静态文件缓存 7 天
        response.headers['Cache-Control'] = 'public, max-age=604800'
    return response


# ==================== 启动 ====================

if __name__ == "__main__":
    # 初始化数据库
    if not os.path.exists("podcasts.db"):
        init_db()
    
    # 启动服务
    logger.info(f"🚀 Podcast Hub 启动中...")
    logger.info(f"   访问地址: http://{SERVER_HOST}:{SERVER_PORT}")
    
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=True)
