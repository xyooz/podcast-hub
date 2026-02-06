// 🎙️ Podcast Hub - Modern Frontend
(function() {
    'use strict';
    
    const API_BASE = '/api';
    let podcasts = [];
    let playQueue = [];
    let queueIndex = 0;
    let isPlaying = false;
    let audio = null;
    
    // Queue persistence
    function saveQueueState() {
        try {
            localStorage.setItem('podcastQueue', JSON.stringify(playQueue));
            localStorage.setItem('podcastQueueIndex', queueIndex);
        } catch(e) {}
    }
    
    function restoreQueueState() {
        try {
            var saved = localStorage.getItem('podcastQueue');
            if (saved) {
                playQueue = JSON.parse(saved);
                queueIndex = parseInt(localStorage.getItem('podcastQueueIndex') || '0');
            }
        } catch(e) {}
    }
    
    // Toast notification - modern style
    window.showToast = function(msg, icon) {
        var toast = document.getElementById('toast');
        var toastMsg = document.getElementById('toast-message');
        var toastIcon = document.getElementById('toast-icon');
        
        if (toast && toastMsg) {
            toastMsg.textContent = msg;
            if (toastIcon) toastIcon.textContent = icon || '✅';
            toast.classList.remove('hidden');
            toast.style.animation = 'none';
            toast.offsetHeight; // trigger reflow
            toast.style.animation = 'slideDown 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
            
            setTimeout(function() {
                toast.classList.add('hidden');
            }, 2500);
        }
    };
    
    window.addToQueue = function(episodeId, episodeTitle) {
        playQueue.push({id: episodeId, title: episodeTitle});
        saveQueueState();
        showToast('已加入队列 (' + playQueue.length + ')', '📋');
    };
    
    window.playFromQueue = function(index) {
        if (index >= 0 && index < playQueue.length) {
            queueIndex = index;
            saveQueueState();
            var ep = playQueue[queueIndex];
            playEpisode(ep.id);
        }
    };
    
    window.clearQueue = function() {
        playQueue = [];
        queueIndex = 0;
        saveQueueState();
        showToast('队列已清空', '✨');
    };
    
    // Initialize
    function init() {
        audio = document.getElementById('audio-player');
        if (audio) {
            audio.addEventListener('ended', onAudioEnded);
        }
        restoreQueueState();
        loadPodcasts();
    }
    
    // Tab navigation
    window.showTab = function(tab) {
        document.querySelectorAll('.tab-btn').forEach(function(btn) {
            if (btn.dataset.tab === tab) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        document.querySelectorAll('.tab-content').forEach(function(content) {
            content.classList.add('hidden');
        });
        var tabContent = document.getElementById('tab-' + tab);
        if (tabContent) {
            tabContent.classList.remove('hidden');
            tabContent.style.animation = 'none';
            tabContent.offsetHeight;
            tabContent.style.animation = 'fadeIn 0.3s ease';
        }
        
        if (tab === 'podcasts') {
            loadPodcasts();
        } else if (tab === 'favorites') {
            loadFavorites();
        } else if (tab === 'history') {
            loadHistory();
        }
    };
    
    // Load podcasts
    function loadPodcasts() {
        fetch(API_BASE + '/podcast')
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.success) {
                    podcasts = res.data;
                    renderPodcasts(podcasts, 'podcasts-grid');
                }
            });
    }
    
    // Render podcasts
    function renderPodcasts(list, containerId) {
        var container = document.getElementById(containerId);
        if (!container) return;
        
        container.innerHTML = '';
        
        if (list.length === 0) {
            container.innerHTML = '<div class="col-span-full text-center py-12 text-gray-500">暂无内容</div>';
            return;
        }
        
        list.forEach(function(podcast, index) {
            var card = document.createElement('div');
            card.className = 'podcast-card rounded-2xl overflow-hidden cursor-pointer';
            card.style.animationDelay = (index * 0.05) + 's';
            card.onclick = function() { showEpisodes(podcast.id); };
            
            var img = podcast.image_url || 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect fill="#1e293b" width="200" height="200"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#64748b" font-size="48">🎙️</text></svg>');
            
            card.innerHTML = 
                '<div class="cover-container aspect-square relative">' +
                    '<img src="' + img + '" class="w-full h-full object-cover">' +
                    '<div class="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent"></div>' +
                    '<div class="absolute bottom-3 left-3 right-3">' +
                        '<h3 class="text-white font-semibold text-sm truncate drop-shadow-lg">' + podcast.title + '</h3>' +
                        '<p class="text-white/70 text-xs mt-1">' + podcast.episode_count + ' 集</p>' +
                    '</div>' +
                '</div>' +
                '<div class="p-2 flex gap-1 bg-gradient-to-r from-white/5 to-transparent">' +
                    '<button onclick="event.stopPropagation(); addFavorite(' + podcast.id + ')" ' +
                        'class="flex-1 py-2 rounded-lg text-xs bg-white/10 hover:bg-white/20 transition-colors">❤️</button>' +
                    '<button onclick="event.stopPropagation(); deletePodcast(' + podcast.id + ')" ' +
                        'class="flex-1 py-2 rounded-lg text-xs bg-white/10 hover:bg-red-500/30 transition-colors">🗑️</button>' +
                '</div>';
            
            container.appendChild(card);
        });
    }
    
    // Add podcast
    window.addPodcast = function() {
        var url = document.getElementById('add-podcast-url').value.trim();
        if (!url) {
            showToast('请输入播客链接', '⚠️');
            return;
        }
        
        showToast('添加中...', '⏳');
        
        fetch(API_BASE + '/podcast', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url: url})
        })
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.success) {
                showToast('添加成功!', '✅');
                document.getElementById('add-podcast-url').value = '';
                loadPodcasts();
            } else {
                showToast('添加失败: ' + res.error, '❌');
            }
        })
        .catch(function(e) {
            showToast('添加失败', '❌');
        });
    };
    
    // Delete podcast
    window.deletePodcast = function(id) {
        if (!confirm('确定取消订阅?')) return;
        
        fetch(API_BASE + '/podcast/' + id, {method: 'DELETE'})
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.success) {
                    showToast('已取消订阅', '✅');
                    loadPodcasts();
                }
            });
    };
    
    // Show episodes modal
    window.showEpisodes = function(podcastId) {
        var podcast = podcasts.find(function(p) { return p.id === podcastId; });
        if (!podcast) return;
        
        var modal = document.getElementById('episodes-modal');
        var cover = document.getElementById('modal-cover');
        var title = document.getElementById('modal-title');
        var author = document.getElementById('modal-author');
        var count = document.getElementById('modal-count');
        
        if (cover) cover.src = podcast.image_url || '';
        if (title) title.textContent = podcast.title;
        if (author) author.textContent = podcast.author || '';
        if (count) count.textContent = podcast.episode_count + ' 集';
        
        modal.classList.remove('hidden');
        modal.style.animation = 'none';
        modal.offsetHeight;
        modal.style.animation = 'fadeIn 0.2s ease';
        
        var list = document.getElementById('episodes-list');
        list.innerHTML = '<div class="p-8 text-center text-gray-500">加载中...</div>';
        
        fetch(API_BASE + '/podcast/' + podcastId + '/episodes')
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.success && res.data.length > 0) {
                    window.currentEpisodes = res.data;
                    renderEpisodes(res.data);
                } else {
                    list.innerHTML = '<div class="p-8 text-center text-gray-500">暂无节目</div>';
                }
            });
    };
    
    window.filterEpisodes = function(query) {
        if (!window.currentEpisodes) return;
        var filtered = window.currentEpisodes.filter(function(ep) {
            return ep.title.toLowerCase().includes(query.toLowerCase());
        });
        renderEpisodes(filtered);
    };
    
    function renderEpisodes(list) {
        var container = document.getElementById('episodes-list');
        container.innerHTML = '';
        
        list.forEach(function(episode) {
            var div = document.createElement('div');
            div.className = 'episode-item glass-card rounded-xl p-4 flex items-center gap-3 cursor-pointer';
            div.onclick = function() { 
                playEpisode(episode.id); 
            };
            
            var dateStr = episode.pub_date ? formatTime(episode.pub_date) : '';
            var safeTitle = (episode.title || '').replace(/'/g, "\\'");
            
            div.innerHTML = 
                '<div class="flex-1 min-w-0">' +
                    '<h4 class="text-white font-medium text-sm truncate">' + episode.title + '</h4>' +
                    '<div class="flex items-center gap-2 mt-1">' +
                        '<span class="text-gray-500 text-xs">' + (episode.duration_str || '--:--') + '</span>' +
                        '<span class="text-gray-600 text-xs">' + dateStr + '</span>' +
                    '</div>' +
                '</div>' +
                '<div class="flex gap-1">' +
                    '<button onclick="event.stopPropagation(); addToQueue(' + episode.id + ', \'' + safeTitle + '\')" ' +
                        'class="w-9 h-9 rounded-lg bg-white/10 flex items-center justify-center hover:bg-white/20 transition-colors">📋</button>' +
                    '<button onclick="event.stopPropagation(); addFavorite(' + episode.podcast_id + ')" ' +
                        'class="w-9 h-9 rounded-lg bg-white/10 flex items-center justify-center hover:bg-white/20 transition-colors">❤️</button>' +
                '</div>';
            
            container.appendChild(div);
        });
    }
    
    window.closeModal = function() {
        document.getElementById('episodes-modal').classList.add('hidden');
    };
    
    // Play episode
    window.playEpisode = function(episodeId) {
        fetch(API_BASE + '/play/' + episodeId, {method: 'POST'})
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (!res.success) {
                    showToast('播放失败: ' + res.error, '❌');
                    return;
                }
                
                var data = res.data;
                
                var playerBar = document.getElementById('player-bar');
                var playerCover = document.getElementById('player-cover');
                var playerTitle = document.getElementById('player-title');
                var playerPodcast = document.getElementById('player-podcast');
                
                if (playerBar) playerBar.classList.remove('hidden');
                if (playerCover) playerCover.src = data.image_url || '';
                if (playerTitle) playerTitle.textContent = data.title;
                if (playerPodcast) playerPodcast.textContent = data.podcast_title;
                
                if (audio) {
                    audio.src = data.audio_url;
                    audio.play();
                    isPlaying = true;
                    updatePlayButton();
                }
                
                closeModal();
                showToast('开始播放: ' + data.title.substring(0, 20) + '...', '🎵');
            });
    };
    
    window.togglePlay = function() {
        if (!audio || !audio.src) return;
        
        if (isPlaying) {
            audio.pause();
        } else {
            audio.play();
        }
        isPlaying = !isPlaying;
        updatePlayButton();
    };
    
    function updatePlayButton() {
        var icon = document.getElementById('play-icon');
        if (icon) {
            icon.textContent = isPlaying ? '⏸️' : '▶️';
        }
    }
    
    function onAudioEnded() {
        isPlaying = false;
        updatePlayButton();
    }
    
    window.closePlayer = function() {
        if (audio) {
            audio.pause();
            audio.src = '';
        }
        isPlaying = false;
        document.getElementById('player-bar').classList.add('hidden');
    };
    
    window.updateProgress = function() {
        if (!audio || !audio.duration) return;
        var progress = (audio.currentTime / audio.duration) * 100;
        document.getElementById('player-progress').style.width = progress + '%';
        document.getElementById('player-current').textContent = formatTimeSimple(audio.currentTime);
        document.getElementById('player-duration').textContent = formatTimeSimple(audio.duration);
    };
    
    window.seekPlayer = function(e) {
        if (!audio || !audio.duration) return;
        var rect = e.target.getBoundingClientRect();
        var percent = (e.clientX - rect.left) / rect.width;
        audio.currentTime = percent * audio.duration;
    };
    
    function formatTime(seconds) {
        if (!seconds) return '';
        var date = new Date(seconds);
        var now = new Date();
        var diff = now - date;
        
        if (diff < 60000) return '刚刚';
        if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
        if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
        if (diff < 604800000) return Math.floor(diff / 86400000) + '天前';
        
        return date.toLocaleDateString('zh-CN');
    }
    
    function formatTimeSimple(seconds) {
        var h = Math.floor(seconds / 3600);
        var m = Math.floor((seconds % 3600) / 60);
        var s = Math.floor(seconds % 60);
        if (h > 0) {
            return h + ':' + (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
        }
        return m + ':' + (s < 10 ? '0' : '') + s;
    }
    
    // Favorites
    function loadFavorites() {
        fetch(API_BASE + '/favorite')
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.success) {
                    renderPodcasts(res.data, 'favorites-list');
                }
            });
    }
    
    window.addFavorite = function(podcastId) {
        fetch(API_BASE + '/favorite/' + podcastId, {method: 'POST'})
            .then(function(r) { return r.json(); })
            .then(function(res) {
                showToast(res.success ? '已添加收藏' : '取消收藏', res.success ? '❤️' : '💔');
            });
    }
    
    // History
    function loadHistory() {
        fetch(API_BASE + '/history')
            .then(function(r) { return r.json(); })
            .then(function(res) {
                var container = document.getElementById('history-list');
                if (!res.success || !res.data.length) {
                    container.innerHTML = '<div class="text-center py-8 text-gray-500">暂无历史</div>';
                    return;
                }
                
                container.innerHTML = '';
                res.data.forEach(function(item) {
                    var div = document.createElement('div');
                    div.className = 'glass-card rounded-xl p-4 flex items-center gap-3 cursor-pointer episode-item';
                    div.onclick = function() { playEpisode(item.id); };
                    div.innerHTML = 
                        '<div class="flex-1 min-w-0">' +
                            '<h4 class="text-white font-medium text-sm truncate">' + item.title + '</h4>' +
                            '<p class="text-gray-500 text-xs mt-1">' + formatTime(item.played_at) + '</p>' +
                        '</div>';
                    container.appendChild(div);
                });
            });
    }
    
    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
