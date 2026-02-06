// 🎙️ Podcast Hub - Simplified Frontend
(function() {
    'use strict';
    
    const API_BASE = '/api';
    let podcasts = [];
    let isPlaying = false;
    let audio = null;
    
    // Initialize when DOM is ready
    function init() {
        audio = document.getElementById('audio-player');
        if (audio) {
            audio.addEventListener('ended', onAudioEnded);
        }
        loadPodcasts();
        console.log('✓ Podcast Hub initialized');
    }
    
    // Tab navigation
    window.showTab = function(tab) {
        console.log('Switching to tab:', tab);
        
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(function(btn) {
            if (btn.dataset.tab === tab) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        // Show/hide content
        document.querySelectorAll('.tab-content').forEach(function(content) {
            content.classList.add('hidden');
        });
        var tabContent = document.getElementById('tab-' + tab);
        if (tabContent) {
            tabContent.classList.remove('hidden');
        }
        
        // Load tab data
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
        showLoading(true);
        fetch(API_BASE + '/podcast')
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.success) {
                    podcasts = res.data;
                    renderPodcasts(podcasts, 'podcasts-grid');
                }
            })
            .catch(function(e) { console.error('Load podcasts error:', e); })
            .finally(function() { showLoading(false); });
    }
    
    // Render podcasts
    function renderPodcasts(list, containerId) {
        var container = document.getElementById(containerId);
        if (!container) return;
        
        container.innerHTML = '';
        
        if (list.length === 0) {
            container.innerHTML = '<div class="text-center py-12 text-gray-400">暂无内容</div>';
            return;
        }
        
        list.forEach(function(podcast) {
            var card = document.createElement('div');
            card.className = 'glass-card rounded-xl overflow-hidden fade-in cursor-pointer';
            card.style.aspectRatio = '1';
            card.onclick = function() { showEpisodes(podcast.id); };
            
            var img = podcast.image_url || 'https://via.placeholder.com/200x200?text=🎙️';
            
            card.innerHTML = 
                '<div class="relative h-full">' +
                    '<img src="' + img + '" class="w-full h-full object-cover">' +
                    '<div class="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent"></div>' +
                    '<div class="absolute bottom-2 left-2 right-2">' +
                        '<h3 class="text-white font-semibold text-xs truncate">' + podcast.title + '</h3>' +
                        '<p class="text-white/60 text-xs">' + podcast.episode_count + ' 集</p>' +
                    '</div>' +
                '</div>' +
                '<div class="p-2 flex gap-1">' +
                    '<button onclick="event.stopPropagation(); addFavorite(' + podcast.id + ')" ' +
                        'class="btn-glass px-2 py-1 rounded text-xs flex-1 text-center">❤️</button>' +
                '</div>';
            
            container.appendChild(card);
        });
    }
    
    // Load favorites
    function loadFavorites() {
        fetch(API_BASE + '/favorite')
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.success) {
                    renderPodcasts(res.data, 'favorites-list');
                }
            });
    }
    
    // Load history
    function loadHistory() {
        fetch(API_BASE + '/history')
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.success) {
                    renderHistory(res.data);
                }
            });
    }
    
    // Render history
    function renderHistory(list) {
        var container = document.getElementById('history-list');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (list.length === 0) {
            container.innerHTML = '<div class="text-center py-12 text-gray-400">暂无记录</div>';
            return;
        }
        
        list.forEach(function(item) {
            var div = document.createElement('div');
            div.className = 'glass-card rounded-xl p-3 flex items-center gap-3 fade-in cursor-pointer';
            div.onclick = function() { playEpisode(item.episode_id); };
            
            var img = getPodcastImage(item.podcast_id) || 'https://via.placeholder.com/60x60';
            
            div.innerHTML = 
                '<img src="' + img + '" class="w-12 h-12 rounded-lg object-cover flex-shrink-0">' +
                '<div class="flex-1 min-w-0">' +
                    '<h4 class="text-white font-medium text-sm truncate">' + item.title + '</h4>' +
                    '<p class="text-gray-400 text-xs truncate">' + item.podcast_title + '</p>' +
                '</div>' +
                '<span class="text-gray-500 text-xs whitespace-nowrap">' + formatTime(item.played_at) + '</span>';
            
            container.appendChild(div);
        });
    }
    
    function getPodcastImage(id) {
        var podcast = podcasts.find(function(p) { return p.id === id; });
        return podcast ? podcast.image_url : null;
    }
    
    // Add podcast
    window.addPodcast = function() {
        var url = document.getElementById('add-podcast-url').value.trim();
        if (!url) {
            alert('请输入播客链接');
            return;
        }
        
        var btn = document.querySelector('button[onclick="addPodcast()"]');
        btn.disabled = true;
        btn.textContent = '添加中...';
        
        fetch(API_BASE + '/podcast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        })
            .then(function(r) { return r.json(); })
            .then(function(res) {
                document.getElementById('add-podcast-url').value = '';
                if (res.success) {
                    alert('添加成功！');
                    loadPodcasts();
                } else {
                    alert('添加失败: ' + res.error);
                }
            })
            .catch(function(e) { alert('添加失败: ' + e.message); })
            .finally(function() {
                btn.disabled = false;
                btn.textContent = '添加播客';
            });
    };
    
    // Add favorite
    window.addFavorite = function(id) {
        fetch(API_BASE + '/favorite/' + id, { method: 'POST' })
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (res.success) {
                    alert('收藏成功！');
                    loadFavorites();
                } else {
                    alert('收藏失败: ' + res.error);
                }
            });
    };
    
    // Show episodes modal
    function showEpisodes(podcastId) {
        var podcast = podcasts.find(function(p) { return p.id === podcastId; });
        if (!podcast) return;
        
        var modal = document.getElementById('episodes-modal');
        if (!modal) return;
        
        var titleEl = document.getElementById('modal-title');
        var authorEl = document.getElementById('modal-author');
        var countEl = document.getElementById('modal-count');
        var coverEl = document.getElementById('modal-cover');
        
        if (titleEl) titleEl.textContent = podcast.title;
        if (authorEl) authorEl.textContent = podcast.author || '';
        if (countEl) countEl.textContent = podcast.episode_count + ' 集';
        if (coverEl) coverEl.src = podcast.image_url || 'https://via.placeholder.com/100x100';
        
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        
        loadEpisodes(podcastId);
    }
    
    // Close modal
    window.closeModal = function() {
        var modal = document.getElementById('episodes-modal');
        if (modal) {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        }
    };
    
    // Load episodes
    function loadEpisodes(podcastId) {
        var container = document.getElementById('episodes-list');
        if (!container) return;
        
        container.innerHTML = '<div class="text-center py-8 text-gray-400">加载中...</div>';
        
        fetch(API_BASE + '/podcast/' + podcastId + '/episodes')
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (!res.success || res.data.length === 0) {
                    container.innerHTML = '<div class="text-center py-8 text-gray-400">暂无节目</div>';
                    return;
                }
                
                container.innerHTML = '';
                res.data.forEach(function(episode) {
                    var div = document.createElement('div');
                    div.className = 'glass-card rounded-lg p-3 flex items-center gap-3 cursor-pointer list-item';
                    div.onclick = function() { playEpisode(episode.id); };
                    
                    div.innerHTML = 
                        '<div class="flex-1 min-w-0">' +
                            '<h4 class="text-white font-medium text-sm truncate">' + episode.title + '</h4>' +
                            '<p class="text-gray-500 text-xs">' + (episode.duration_str || '--:--') + '</p>' +
                        '</div>' +
                        '<button onclick="event.stopPropagation(); addFavorite(' + podcastId + ')" ' +
                            'class="btn-glass w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0">❤️</button>';
                    
                    container.appendChild(div);
                });
            })
            .catch(function(e) {
                container.innerHTML = '<div class="text-center py-8 text-red-400">加载失败</div>';
            });
    }
    
    // Play episode
    function playEpisode(episodeId) {
        fetch(API_BASE + '/play/' + episodeId, { method: 'POST' })
            .then(function(r) { return r.json(); })
            .then(function(res) {
                if (!res.success) {
                    alert('播放失败: ' + res.error);
                    return;
                }
                
                var data = res.data;
                
                var playerBar = document.getElementById('player-bar');
                var playerCover = document.getElementById('player-cover');
                var playerTitle = document.getElementById('player-title');
                var playerPodcast = document.getElementById('player-podcast');
                
                if (playerBar) playerBar.classList.remove('hidden');
                if (playerCover) playerCover.src = data.image_url || 'https://via.placeholder.com/100x100';
                if (playerTitle) playerTitle.textContent = data.title;
                if (playerPodcast) playerPodcast.textContent = data.podcast_title;
                
                if (audio) {
                    audio.src = data.audio_url;
                    audio.play();
                    isPlaying = true;
                    updatePlayButton();
                }
                
                closeModal();
            })
            .catch(function(e) {
                alert('播放失败: ' + e.message);
            });
    }
    
    // Toggle play
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
    
    // Close player
    window.closePlayer = function() {
        if (audio) {
            audio.pause();
            audio.src = '';
        }
        isPlaying = false;
        var playerBar = document.getElementById('player-bar');
        if (playerBar) playerBar.classList.add('hidden');
    };
    
    // Show/hide loading
    function showLoading(show) {
        var loading = document.getElementById('loading');
        if (loading) {
            loading.classList.toggle('hidden', !show);
        }
    }
    
    // Format time
    function formatTime(isoString) {
        if (!isoString) return '';
        var date = new Date(isoString);
        var now = new Date();
        var diff = now - date;
        
        if (diff < 60000) return '刚刚';
        if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
        if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
        if (diff < 604800000) return Math.floor(diff / 86400000) + '天前';
        
        return date.toLocaleDateString('zh-CN');
    }
    
    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
