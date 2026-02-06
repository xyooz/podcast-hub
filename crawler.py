#!/usr/bin/env python3
"""
Podcast Hub 爬虫模块
解析小宇宙、网易云等平台的分享链接
"""

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PodcastParser:
    """播客链接解析器"""

    # 平台配置
    PLATFORMS = {
        "xiaoyuzhou": {
            "domains": ["xiaoyuzhoufm.com", "www.xiaoyuzhoufm.com", "xyzfm.space"],
            "feed_prefix": "https://feed.xiaoyuzhoufm.com/podcast/",
        },
        "netease": {
            "domains": ["music.163.com"],
            "feed_prefix": "https://podcastrx.netlify.app/feed/netease/",
        },
        "apple": {
            "domains": ["podcasts.apple.com"],
            "feed_prefix": None,
        },
        "spotify": {
            "domains": ["open.spotify.com"],
            "feed_prefix": None,
        },
        "rss": {
            "domains": ["feed.xyzfm.space", "feeds.danlirencomedy.com"],
            "feed_prefix": None,
        },
    }

    @classmethod
    def parse_url(cls, url: str):
        """解析播客分享链接"""
        # 检测平台
        platform = cls._detect_platform(url)

        if platform == "xiaoyuzhou":
            return cls._parse_xiaoyuzhou(url)
        elif platform == "netease":
            return cls._parse_netease(url)
        elif platform == "apple":
            return cls._parse_apple(url)
        elif platform == "spotify":
            return cls._parse_spotify(url)
        elif platform == "rss":
            return cls._parse_rss_url(url)
        else:
            raise ValueError(f"不支持的平台: {url}")

    @classmethod
    def _detect_platform(cls, url: str) -> str:
        """检测链接平台"""
        for platform, config in cls.PLATFORMS.items():
            for domain in config["domains"]:
                if domain in url:
                    return platform
        return "unknown"

    @classmethod
    def _parse_xiaoyuzhou(cls, url: str):
        """解析小宇宙链接"""
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        text = response.text
        
        import json
        
        # 从 schema:podcast-show 提取播客信息（更准确）
        schema_match = re.search(r'<script[^>]*name="schema:podcast-show"[^>]*>([^<]+)</script>', text)
        if schema_match:
            try:
                schema = json.loads(schema_match.group(1))
                title = schema.get("name", "")
                author = schema.get("author", {})
                if isinstance(author, dict):
                    author = author.get("name", "")
                else:
                    author = str(author)
                
                # 从 workExample 提取节目列表
                examples = schema.get("workExample", [])
                
                # 只从 JSON-LD 之后提取音频 URL
                json_ld_end = text.find('</script>', text.find('<script name="schema:podcast-show"'))
                after_json = text[json_ld_end + 9:] if json_ld_end > 0 else ""
                audio_urls = list(dict.fromkeys(re.findall(r'"(https://media\.xyzcdn\.net/[^"]+\.m4a[^"]*)"', after_json)))
                
                episodes = []
                for i, ex in enumerate(examples):
                    if ex.get("@type") == "AudioObject" and i < len(audio_urls):
                        episodes.append({
                            "title": ex.get("name", ""),
                            "audio_url": audio_urls[i],
                            "duration": cls._parse_duration(ex.get("duration", "")),
                            "pub_date": ex.get("datePublished", ""),
                        })
            except Exception as e:
                logger.error(f"解析 JSON-LD 失败: {e}")
                title, author, episodes = "", "", []
        else:
            title, author, episodes = "", "", ""
        
        # 如果提取失败，使用正则备用方案
        if not episodes:
            title_match = re.search(r'"title":"([^"]{5,100})"', text)
            title = title_match.group(1) if title_match else "未知播客"
            
            author_match = re.search(r'"author":"([^"]*)"', text)
            author = author_match.group(1) if author_match else ""
            
            episodes = cls._extract_xiaoyuzhou_episodes(text)
        
        # 尝试从 meta og:image 获取封面
        image_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', text)
        image_url = image_match.group(1) if image_match else ""
        
        # 提取播客 ID
        podcast_id_match = re.search(r'"podcast":\{"[^}]*"pid":"([a-zA-Z0-9]+)"', text)
        podcast_id = podcast_id_match.group(1) if podcast_id_match else ""
        
        # RSS URL
        rss_url = f"https://feed.xiaoyuzhoufm.com/podcast/{podcast_id}" if podcast_id else url
        
        return "xiaoyuzhou", {
            "title": title,
            "description": "",
            "image_url": image_url,
            "rss_url": rss_url,
            "feed_url": url,
            "author": author,
            "category": "小宇宙",
            "episode_count": len(episodes),
            "_raw_episodes": episodes,
        }

    @classmethod
    def _extract_xiaoyuzhou_episodes(cls, text: str) -> list:
        """从小宇宙页面提取节目列表"""
        episodes = []
        
        import json
        
        # 从 schema:podcast-show 提取（更准确）
        schema_match = re.search(r'<script[^>]*name="schema:podcast-show"[^>]*>([^<]+)</script>', text)
        if schema_match:
            try:
                schema = json.loads(schema_match.group(1))
                examples = schema.get("workExample", [])
                
                # 只从 JSON-LD 之后提取音频 URL
                json_ld_end = text.find('</script>', text.find('<script name="schema:podcast-show"'))
                after_json = text[json_ld_end + 9:] if json_ld_end > 0 else ""
                audio_urls = list(dict.fromkeys(re.findall(r'"(https://media\.xyzcdn\.net/[^"]+\.m4a[^"]*)"', after_json)))
                
                for i, ex in enumerate(examples):
                    if ex.get("@type") == "AudioObject" and i < len(audio_urls):
                        episodes.append({
                            "title": ex.get("name", ""),
                            "audio_url": audio_urls[i],
                            "duration": cls._parse_duration(ex.get("duration", "")),
                            "pub_date": ex.get("datePublished", ""),
                        })
                return episodes
            except Exception as e:
                logger.error(f"解析 JSON-LD 失败: {e}")
        
        return []

    @classmethod
    def _parse_netease(cls, url: str):
        """解析网易云播客链接"""
        podcast_id = None
        
        if "id=" in url:
            match = re.search(r"id=(\d+)", url)
            if match:
                podcast_id = match.group(1)
        elif "/djradio/" in url:
            match = re.search(r"/djradio/(\d+)", url)
            if match:
                podcast_id = match.group(1)
        
        if not podcast_id:
            raise ValueError(f"无法解析网易云链接: {url}")
        
        # 使用第三方 RSS
        rss_url = f"https://podcastrx.netlify.app/feed/netease/{podcast_id}"
        
        return "netease", {
            "title": "网易云播客",
            "description": "",
            "image_url": "",
            "rss_url": rss_url,
            "feed_url": url,
            "author": "",
            "category": "网易云",
            "episode_count": 0,
        }

    @classmethod
    def _parse_apple(cls, url: str):
        """解析 Apple Podcasts 链接"""
        match = re.search(r"id(\d+)", url)
        if match:
            podcast_id = match.group(1)
            rss_url = f"https://itunes.apple.com/lookup?id={podcast_id}&entity=podcast"
            
            try:
                response = requests.get(rss_url, timeout=10)
                data = response.json()
                
                if data.get("results"):
                    info = data["results"][0]
                    return "apple", {
                        "title": info.get("collectionName", "Apple 播客"),
                        "description": info.get("artistViewUrl", ""),
                        "image_url": info.get("artworkUrl600", ""),
                        "rss_url": info.get("feedUrl", ""),
                        "feed_url": url,
                        "author": info.get("artistName", ""),
                        "category": info.get("primaryGenreName", "Apple"),
                        "episode_count": 0,
                    }
            except Exception as e:
                logger.error(f"解析 Apple 播客失败: {e}")
        
        raise ValueError(f"无法解析 Apple Podcasts 链接: {url}")

    @classmethod
    def _parse_spotify(cls, url: str):
        """解析 Spotify 播客链接"""
        # Spotify 需要 API key
        return "spotify", {
            "title": "Spotify 播客",
            "description": "需要 Spotify API",
            "image_url": "",
            "rss_url": "",
            "feed_url": url,
            "author": "",
            "category": "Spotify",
            "episode_count": 0,
        }

    @classmethod
    def _parse_rss_url(cls, url: str):
        """解析 RSS 链接"""
        try:
            import feedparser
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=15)
            response.encoding = "utf-8"
            
            feed = feedparser.parse(response.text)
            
            if feed and feed.feed:
                # 尝试获取标题
                title = "未知播客"
                if hasattr(feed.feed, 'title') and feed.feed.title:
                    title = feed.feed.title
                elif hasattr(feed, 'channel') and hasattr(feed.channel, 'title'):
                    title = feed.channel.title
                
                description = feed.feed.get("description", "") if hasattr(feed.feed, 'description') else ""
                image_url = ""
                # 尝试多种方式获取封面
                if hasattr(feed.feed, 'image'):
                    if isinstance(feed.feed.image, dict):
                        image_url = feed.feed.image.get("href", "")
                    elif isinstance(feed.feed.image, str):
                        image_url = feed.feed.image
                
                # 优先从 itunes:image 标签获取封面
                import re
                itunes_match = re.search(r'<itunes:image[^>]*href="([^"]+)"', response.text, re.IGNORECASE)
                if itunes_match:
                    image_url = itunes_match.group(1)
                    # 如果没有扩展名，尝试添加 .png
                    if not image_url.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                        image_url = image_url + ".png"
                
                # 尝试从 channel image 获取
                if not image_url:
                    channel_match = re.search(r'<image[^>]*>\s*<url>([^<]+)</url>', response.text, re.IGNORECASE)
                    if channel_match:
                        image_url = channel_match.group(1).strip()
                
                # 尝试从小宇宙网站获取封面
                if not image_url and "xyzfm" in url:
                    # 从 URL 提取 podcast ID
                    match = re.search(r'/podcast/([a-zA-Z0-9]+)', url)
                    if match:
                        pid = match.group(1)
                        # 小宇宙默认封面
                        image_url = f"https://image.xyzcdn.net/common/{pid[:2]}/{pid}.jpg"
                
                # 计算节目数
                episode_count = len(feed.entries) if feed.entries else 0
                
                return "rss", {
                    "title": title,
                    "description": str(description)[:500] if description else "",
                    "image_url": image_url,
                    "rss_url": url,
                    "feed_url": url,
                    "author": feed.feed.get("author", "") if hasattr(feed.feed, 'author') else "",
                    "category": "RSS",
                    "episode_count": episode_count,
                }
        except Exception as e:
            logger.error(f"解析 RSS 失败: {e}")
        
        # 返回基本信息
        return "rss", {
            "title": "RSS 播客",
            "description": "",
            "image_url": "",
            "rss_url": url,
            "feed_url": url,
            "author": "",
            "category": "RSS",
            "episode_count": 0,
        }

    @staticmethod
    def get_episodes(rss_url: str) -> list:
        """获取节目列表"""
        # 小宇宙官方 RSS
        if "feed.xiaoyuzhoufm.com" in rss_url:
            return PodcastParser._get_rss_episodes(rss_url)
        
        # xyzfm.space RSS
        if "xyzfm.space" in rss_url or "danlirencomedy.com" in rss_url:
            return PodcastParser._get_rss_episodes(rss_url)
        
        # 小宇宙页面
        if "xiaoyuzhoufm.com" in rss_url:
            return PodcastParser._get_xiaoyuzhou_episodes(rss_url)
        
        # 其他 RSS
        return PodcastParser._get_rss_episodes(rss_url)

    @staticmethod
    def _get_xiaoyuzhou_episodes(url: str) -> list:
        """从小宇宙链接获取节目列表"""
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            return PodcastParser._extract_xiaoyuzhou_episodes(response.text)
        except Exception as e:
            logger.error(f"获取小宇宙节目失败: {e}")
            return []

    @staticmethod
    def _get_rss_episodes(rss_url: str) -> list:
        """从 RSS 获取节目"""
        try:
            import feedparser
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(rss_url, headers=headers, timeout=15)
            response.encoding = "utf-8"
            
            feed = feedparser.parse(response.text)
            
            entries = []
            for entry in feed.entries:
                duration = 0
                if hasattr(entry, 'itunes_duration'):
                    duration = PodcastParser._parse_duration(entry.itunes_duration)
                
                audio_url = ""
                if hasattr(entry, 'enclosures') and entry.enclosures:
                    audio_url = entry.enclosures[0].href
                
                entries.append({
                    "title": entry.get("title", ""),
                    "description": entry.get("description", ""),
                    "audio_url": audio_url,
                    "duration": duration,
                    "pub_date": entry.get("published", ""),
                })
            
            return entries
        except Exception as e:
            logger.error(f"解析 RSS 失败: {e}")
            return []

    @staticmethod
    def _parse_duration(duration_str: str) -> int:
        """解析时长字符串为秒数"""
        if not duration_str:
            return 0
        
        try:
            # 处理 ISO 8601 持续时间格式: PT40M43S, PT123M35S
            if duration_str.startswith("PT"):
                import re
                # 匹配小时、分钟、秒
                hours = re.search(r'(\d+)H', duration_str)
                minutes = re.search(r'(\d+)M', duration_str)
                seconds = re.search(r'(\d+)S', duration_str)
                
                total = 0
                if hours:
                    total += int(hours.group(1)) * 3600
                if minutes:
                    total += int(minutes.group(1)) * 60
                if seconds:
                    total += int(seconds.group(1))
                return total
            
            # 处理普通格式: 40:43, 1:23:35
            parts = duration_str.split(":")
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            else:
                return int(duration_str)
        except:
            return 0


if __name__ == "__main__":
    # 测试
    test_url = input("输入播客链接: ")
    try:
        platform, info = PodcastParser.parse_url(test_url)
        print(f"\n平台: {platform}")
        print(f"标题: {info['title']}")
        print(f"作者: {info['author']}")
        print(f"节目数: {info['episode_count']}")
        
        if '_raw_episodes' in info:
            print("\n前3个节目:")
            for ep in info['_raw_episodes'][:3]:
                print(f"- {ep['title'][:40]}")
    except Exception as e:
        print(f"错误: {e}")
