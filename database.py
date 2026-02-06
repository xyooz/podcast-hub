#!/usr/bin/env python3
"""
Podcast Hub 数据库模型
SQLite + Peewee ORM
"""

from peewee import *
from datetime import datetime

# 数据库路径
DATABASE_PATH = "podcasts.db"

# 创建数据库
db = SqliteDatabase(DATABASE_PATH)


class BaseModel(Model):
    class Meta:
        database = db


class Podcast(BaseModel):
    """播客"""
    id = AutoField()
    title = CharField(max_length=200)           # 播客名称
    description = TextField(null=True)         # 简介
    image_url = CharField(max_length=500, null=True)  # 封面图
    rss_url = CharField(max_length=500)         # RSS 地址
    feed_url = CharField(max_length=500)        # 原始链接
    author = CharField(max_length=100, null=True)    # 作者
    category = CharField(max_length=50, null=True)    # 分类
    episode_count = IntegerField(default=0)      # 节目数
    created_at = DateTimeField(default=datetime.now)  # 创建时间
    updated_at = DateTimeField(default=datetime.now)  # 更新时间
    is_subscribed = BooleanField(default=True)  # 是否订阅


class Episode(BaseModel):
    """节目"""
    id = AutoField()
    podcast = ForeignKeyField(Podcast, backref="episodes")
    title = CharField(max_length=300)          # 节目标题
    description = TextField(null=True)         # 简介
    audio_url = CharField(max_length=500)      # 音频地址
    duration = IntegerField(default=0)         # 时长（秒）
    pub_date = DateTimeField(null=True)        # 发布日期
    episode_num = IntegerField(null=True)       # 节目编号
    created_at = DateTimeField(default=datetime.now)  # 创建时间
    is_played = BooleanField(default=False)    # 是否已播放
    progress = IntegerField(default=0)         # 播放进度（秒）
    played_at = DateTimeField(null=True)       # 最后播放时间


class Favorite(BaseModel):
    """收藏"""
    id = AutoField()
    podcast = ForeignKeyField(Podcast, backref="favorites")
    created_at = DateTimeField(default=datetime.now)  # 创建时间


class PlayHistory(BaseModel):
    """播放历史"""
    id = AutoField()
    episode = ForeignKeyField(Episode, backref="history")
    podcast = ForeignKeyField(Podcast, backref="history")
    played_at = DateTimeField(default=datetime.now)  # 播放时间
    progress = IntegerField(default=0)         # 播放进度
    duration = IntegerField(default=0)          # 节目时长（秒）


def init_db():
    """初始化数据库"""
    db.connect()
    db.create_tables([
        Podcast,
        Episode,
        Favorite,
        PlayHistory,
    ])
    print("✅ 数据库初始化完成")
    db.close()


def get_db():
    """获取数据库连接"""
    if db.is_closed():
        db.connect()
    return db


if __name__ == "__main__":
    init_db()
