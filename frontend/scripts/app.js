/**
 * DialecticEngine Frontend Application
 * 对话页面 - 流式输出
 */

// 视角名称映射
const SKILL_NAMES = {
    'rujia-perspective': '儒家',
    'daojia-perspective': '道家',
    'fajia-perspective': '法家',
    'mojia-perspective': '墨家',
    'mingjia-perspective': '名家',
    'yinyangjia-perspective': '阴阳家',
    'fojia-perspective': '佛家',
    'xinxue-perspective': '心学',
    'bingjia-perspective': '兵家',
    'shijia-perspective': '史家',
    'lixue-perspective': '理学',
    'zonghengjia-perspective': '纵横家',
    'zajia-perspective': '杂家',
    'huanglao-perspective': '黄老',
    'newrujia-perspective': '新儒',
    'yijia-perspective': '医家',
    'jingxue-perspective': '经学',
    'nongjia-perspective': '农家',
    'xiaoshuojia-perspective': '小说家',
    'shushujia-perspective': '术数家',
    'xuanxue-perspective': '玄学'
};

// Markdown 渲染配置
if (typeof marked !== 'undefined') {
    marked.setOptions({
        gfm: true,
        breaks: true,
        headerIds: false,
        mangle: false
    });
}

// 视角配色
const SKILL_COLORS = {
    'rujia-perspective': '#8E44AD',
    'daojia-perspective': '#27AE60',
    'fajia-perspective': '#E74C3C',
    'mojia-perspective': '#3498DB',
    'mingjia-perspective': '#F39C12',
    'yinyangjia-perspective': '#9B59B6',
    'fojia-perspective': '#E67E22',
    'xinxue-perspective': '#1ABC9C',
    'bingjia-perspective': '#C0392B',
    'shijia-perspective': '#2980B9',
    'lixue-perspective': '#16A085',
    'zonghengjia-perspective': '#D35400',
    'zajia-perspective': '#7F8C8D',
    'huanglao-perspective': '#34495E',
    'newrujia-perspective': '#9B59B6',
    'yijia-perspective': '#2ECC71',
    'jingxue-perspective': '#8E6F3E',
    'nongjia-perspective': '#6B8E23',
    'xiaoshuojia-perspective': '#DB7093',
    'shushujia-perspective': '#483D8B',
    'xuanxue-perspective': '#6A5ACD'
};

class ChatApp {
    constructor() {
        this.sessionId = this.generateSessionId();
        this.messages = [];
        this.isLoading = false;
        this.currentSkillIds = [];
        this.currentDecisionId = null;
        this.historyLoaded = false;

        this.initElements();
        this.bindEvents();
        this.loadHistory();
    }

    initElements() {
        this.elements = {
            messages: document.getElementById('messages'),
            userInput: document.getElementById('userInput'),
            sendBtn: document.getElementById('sendBtn'),
            stopBtn: document.getElementById('stopBtn'),
            loadingOverlay: document.getElementById('loadingOverlay'),
            loadingText: document.getElementById('loadingText'),
            skillsPanel: document.getElementById('skillsPanel'),
            skillsList: document.getElementById('skillsList'),
            confidenceFill: document.getElementById('confidenceFill'),
            confidenceText: document.getElementById('confidenceText'),
            toggleSkills: document.getElementById('toggleSkills'),
            quickBtns: document.querySelectorAll('.quick-btn'),
            screenshotBtn: document.getElementById('screenshotBtn'),
            saveDropdown: document.getElementById('saveDropdown'),
            saveMenuWrapper: document.querySelector('.save-menu-wrapper'),
            searchToggle: document.getElementById('searchToggle'),
            menuBtn: document.getElementById('menuBtn'),
            sidebarClose: document.getElementById('sidebarClose'),
            historySidebar: document.getElementById('historySidebar'),
            historyList: document.getElementById('historyList'),
            newChatBtn: document.getElementById('newChatBtn'),
        };
    }

    bindEvents() {
        // 发送按钮
        this.elements.sendBtn.addEventListener('click', () => this.handleSend());

        // 输入框回车发送
        this.elements.userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSend();
            }
        });

        // 自动调整输入框高度
        this.elements.userInput.addEventListener('input', () => {
            this.elements.userInput.style.height = 'auto';
            this.elements.userInput.style.height = Math.min(this.elements.userInput.scrollHeight, 100) + 'px';
        });

        // 快捷问题按钮
        this.elements.quickBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const topic = btn.textContent;
                const examples = {
                    '人生抉择': '我应该考研还是直接工作？',
                    '人际处世': '朋友借钱不还，我该催吗？',
                    '事业发展': '想辞职但舍不得，该怎么办？'
                };
                this.elements.userInput.value = examples[topic] || topic;
                this.handleSend();
            });
        });

        // 关闭视角面板
        this.elements.toggleSkills.addEventListener('click', () => {
            this.elements.skillsPanel.classList.remove('visible');
        });

        // 保存菜单
        this.elements.screenshotBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.elements.saveMenuWrapper.classList.toggle('open');
        });

        document.addEventListener('click', (e) => {
            if (!this.elements.saveMenuWrapper.contains(e.target)) {
                this.elements.saveMenuWrapper.classList.remove('open');
            }
        });

        this.elements.saveDropdown.querySelectorAll('.save-option').forEach(btn => {
            btn.addEventListener('click', () => {
                this.elements.saveMenuWrapper.classList.remove('open');
                const action = btn.dataset.action;
                switch (action) {
                    case 'screenshot': this.takeScreenshot(); break;
                    case 'html': this.exportHTML(); break;
                    case 'markdown': this.exportMarkdown(); break;
                    case 'print': this.printConversation(); break;
                }
            });
        });

        // 中断按钮
        this.elements.stopBtn.addEventListener('click', () => this.handleStop());

        // 联网搜索开关
        this.elements.searchToggle.addEventListener('click', () => {
            const btn = this.elements.searchToggle;
            btn.classList.toggle('active');
            const enabled = btn.classList.contains('active');
            window.dialecticAPI.setEnableSearch(enabled);
        });

        // 侧边栏开关
        this.elements.menuBtn.addEventListener('click', () => this.toggleSidebar(true));
        this.elements.sidebarClose.addEventListener('click', () => this.toggleSidebar(false));

        // 新对话
        this.elements.newChatBtn.addEventListener('click', () => this.startNewChat());

        // 点击遮罩关闭侧边栏
        this._sidebarOverlay = document.createElement('div');
        this._sidebarOverlay.className = 'sidebar-overlay';
        document.body.appendChild(this._sidebarOverlay);
        this._sidebarOverlay.addEventListener('click', () => this.toggleSidebar(false));
    }

    generateSessionId() {
        return 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    toggleSidebar(open) {
        if (open) {
            this.elements.historySidebar.classList.add('open');
            this._sidebarOverlay.classList.add('visible');
            if (!this.historyLoaded) this.loadHistory();
        } else {
            this.elements.historySidebar.classList.remove('open');
            this._sidebarOverlay.classList.remove('visible');
        }
    }

    startNewChat() {
        this.sessionId = this.generateSessionId();
        this.currentSkillIds = [];
        this.currentDecisionId = null;
        this.elements.messages.innerHTML = `
            <div class="message welcome">
                <div class="avatar bot">
                    <svg viewBox="0 0 24 24" width="32" height="32">
                        <circle cx="12" cy="12" r="10" fill="#4A90D9"/>
                        <path d="M8 10h8M8 14h5" stroke="white" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </div>
                <div class="content">
                    <p>你好，我是<strong>辩证思考顾问</strong>。</p>
                    <p>我可以帮你从儒、道、佛、法、墨等中国传统哲学视角，深入分析你的人生困惑、处世难题或决策纠结。</p>
                    <p class="example">试试问我：<em>"创业还是打工，怎么选？"</em></p>
                </div>
            </div>
        `;
        this.toggleSidebar(false);
        this.loadHistory();
    }

    async loadHistory() {
        try {
            const resp = await fetch(`${window.dialecticAPI.baseUrl}/memory/list?limit=50`);
            const data = await resp.json();
            if (data.status === 'ok' && data.memories) {
                this.renderHistory(data.memories);
                this.historyLoaded = true;
            }
        } catch (e) {
            console.warn('加载历史记录失败:', e);
        }
    }

    renderHistory(memories) {
        const listEl = this.elements.historyList;
        if (!memories || memories.length === 0) {
            listEl.innerHTML = '<div class="history-empty">暂无历史记录</div>';
            return;
        }

        const groups = {};
        for (const mem of memories) {
            const sid = mem.session_id || 'unknown';
            if (!groups[sid]) {
                groups[sid] = {
                    sessionId: sid,
                    firstQuery: mem.query_summary || '未知问题',
                    timestamp: mem.timestamp,
                    skills: [],
                    count: 0,
                };
            }
            groups[sid].count++;
            if (mem.timestamp > groups[sid].timestamp) {
                groups[sid].timestamp = mem.timestamp;
                groups[sid].firstQuery = mem.query_summary || groups[sid].firstQuery;
            }
            for (const s of (mem.selected_skills || [])) {
                if (!groups[sid].skills.includes(s)) {
                    groups[sid].skills.push(s);
                }
            }
        }

        const sorted = Object.values(groups).sort((a, b) =>
            b.timestamp.localeCompare(a.timestamp)
        );

        let html = '';
        for (const g of sorted) {
            const isActive = g.sessionId === this.sessionId;
            const date = this._formatTimestamp(g.timestamp);
            const skillDots = g.skills.slice(0, 5).map(s =>
                `<span class="history-skill-dot" style="background:${SKILL_COLORS[s] || '#4A90D9'}"></span>`
            ).join('');
            const turnsLabel = g.count > 1 ? `${g.count}轮对话` : '单轮对话';

            html += `
                <div class="history-item ${isActive ? 'active' : ''}"
                     data-session-id="${this.escapeHtml(g.sessionId)}">
                    <div class="history-item-title">${this.escapeHtml(g.firstQuery)}</div>
                    <div class="history-item-meta">
                        <span>${date}</span>
                        <span>·</span>
                        <span>${turnsLabel}</span>
                    </div>
                    <div class="history-item-skills">${skillDots}</div>
                </div>
            `;
        }

        listEl.innerHTML = html;

        listEl.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', () => {
                const sid = item.dataset.sessionId;
                if (sid === this.sessionId) {
                    this.toggleSidebar(false);
                    return;
                }
                this._loadSessionHistory(sid);
            });
        });
    }

    async _loadSessionHistory(sessionId) {
        try {
            const resp = await fetch(
                `${window.dialecticAPI.baseUrl}/memory/session/${encodeURIComponent(sessionId)}`
            );
            const data = await resp.json();
            if (data.status !== 'ok' || !data.memories || data.memories.length === 0) return;

            this.sessionId = sessionId;
            this.currentSkillIds = [];
            this.elements.messages.innerHTML = '';

            const sorted = data.memories.sort((a, b) =>
                a.timestamp.localeCompare(b.timestamp)
            );

            for (const mem of sorted) {
                this.addUserMessage(mem.user_query || '');

                let fullText = mem.full_response || '';
                if (mem.synthesis && fullText && !fullText.includes(mem.synthesis.substring(0, 50))) {
                    fullText += '\n\n---\n\n### 【主持人】综合结论\n\n' + mem.synthesis;
                } else if (!fullText && mem.synthesis) {
                    fullText = mem.synthesis;
                }
                const skills = mem.selected_skills || [];
                this.addBotMessage(fullText, skills);
            }

            this.toggleSidebar(false);
            this.loadHistory();
        } catch (e) {
            console.warn('加载会话历史失败:', e);
        }
    }

    _formatTimestamp(ts) {
        if (!ts) return '';
        try {
            const d = new Date(ts);
            const now = new Date();
            const diffMs = now - d;
            const diffMin = Math.floor(diffMs / 60000);
            if (diffMin < 1) return '刚刚';
            if (diffMin < 60) return `${diffMin}分钟前`;
            const diffHr = Math.floor(diffMin / 60);
            if (diffHr < 24) return `${diffHr}小时前`;
            const diffDay = Math.floor(diffHr / 24);
            if (diffDay < 7) return `${diffDay}天前`;
            return `${d.getMonth() + 1}/${d.getDate()}`;
        } catch {
            return '';
        }
    }

    async handleSend() {
        const query = this.elements.userInput.value.trim();

        if (!query || this.isLoading) return;

        // 清空输入
        this.elements.userInput.value = '';
        this.elements.userInput.style.height = 'auto';

        // 添加用户消息
        this.addUserMessage(query);

        // 开始加载
        this.startLoading('思考中...');

        // 显示中断按钮
        this.elements.stopBtn.style.display = 'flex';
        this.elements.sendBtn.style.display = 'none';

        // 调用 API
        try {
            await this.streamResponse(query);
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('用户中断了生成');
            } else {
                console.error('Error:', error);
                this.addBotMessage('抱歉，服务暂时不可用，请稍后再试。');
            }
        } finally {
            this.stopLoading();
            this.elements.stopBtn.style.display = 'none';
            this.elements.sendBtn.style.display = 'flex';
        }
    }

    handleStop() {
        window.dialecticAPI.abortStream();
    }

    addUserMessage(content) {
        const html = `
            <div class="message user">
                <div class="avatar"></div>
                <div class="content">
                    <p>${this.escapeHtml(content)}</p>
                </div>
            </div>
        `;

        this.elements.messages.insertAdjacentHTML('beforeend', html);
        this.scrollToBottom();
    }

    addBotMessage(content, skillIds = []) {
        const skillTagsHtml = skillIds.length > 0 ? `
            <div class="skill-tags">
                ${skillIds.map(id => `
                    <span class="tag" style="background: ${SKILL_COLORS[id] || '#4A90D9'}">
                        ${SKILL_NAMES[id] || id.replace('-perspective', '')}
                    </span>
                `).join('')}
            </div>
        ` : '';

        const html = `
            <div class="message bot">
                <button class="save-turn-btn" title="保存此轮对话" onclick="window.chatApp._saveTurn(this)">
                    <svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                </button>
                <div class="avatar">
                    <svg viewBox="0 0 24 24" width="32" height="32">
                        <circle cx="12" cy="12" r="10" fill="#4A90D9"/>
                        <path d="M8 10h8M8 14h5" stroke="white" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </div>
                <div class="content">
                    <div class="markdown-body">${this.renderMarkdown(content)}</div>
                    ${skillTagsHtml}
                </div>
            </div>
        `;

        this.elements.messages.insertAdjacentHTML('beforeend', html);
        this.scrollToBottom();
    }

    addStreamingBotMessage() {
        const html = `
            <div class="message bot streaming" id="streamingMessage">
                <div class="avatar">
                    <svg viewBox="0 0 24 24" width="32" height="32">
                        <circle cx="12" cy="12" r="10" fill="#4A90D9"/>
                        <path d="M8 10h8M8 14h5" stroke="white" stroke-width="2" stroke-linecap="round"/>
                    </svg>
                </div>
                <div class="content">
                    <div class="markdown-body" id="streamingText"></div>
                    <span class="typing-cursor" id="streamingCursor"></span>
                    <div class="skill-tags" id="streamingSkills"></div>
                </div>
            </div>
        `;

        this.elements.messages.insertAdjacentHTML('beforeend', html);
        return {
            messageEl: document.getElementById('streamingMessage'),
            textEl: document.getElementById('streamingText'),
            skillsEl: document.getElementById('streamingSkills')
        };
    }

    updateStreamingSkills(skillIds) {
        const skillsEl = document.getElementById('streamingSkills');
        if (!skillsEl) return;

        skillsEl.innerHTML = skillIds.map(id => `
            <span class="tag" style="background: ${SKILL_COLORS[id] || '#4A90D9'}">
                ${SKILL_NAMES[id] || id.replace('-perspective', '')}
            </span>
        `).join('');
    }

    async streamResponse(query) {
        const { textEl, skillsEl } = this.addStreamingBotMessage();

        let fullResponse = '';
        let firstMessageReceived = false;
        let pendingText = '';
        let wasAborted = false;
        let lastScrollTime = 0;
        const MARKDOWN_RENDER_INTERVAL = 300;

        const doRender = () => {
            if (pendingText) {
                fullResponse += pendingText;
                pendingText = '';
            }
            textEl.innerHTML = this.renderMarkdown(fullResponse);
            const now = Date.now();
            if (now - lastScrollTime > 200) {
                lastScrollTime = now;
                this.scrollToBottom();
            }
        };

        let renderTimer = null;
        const startRenderLoop = () => {
            if (renderTimer) return;
            doRender();
            renderTimer = setInterval(() => {
                if (pendingText) {
                    doRender();
                }
            }, MARKDOWN_RENDER_INTERVAL);
        };
        const stopRenderLoop = () => {
            if (renderTimer) {
                clearInterval(renderTimer);
                renderTimer = null;
            }
        };

        try {
            await window.dialecticAPI.chatStream(
                query,
                this.sessionId,
                {
                    onSkillSelected: (data) => {
                        this.currentSkillIds = data.skill_ids || [];
                        this.updateSkillsPanel(data);
                        this.updateStreamingSkills(this.currentSkillIds);
                    },

                    onSkillStart: (data) => {
                        this.elements.loadingText.textContent = `${SKILL_NAMES[data.skill_id] || data.skill_id} 视角思考中...`;
                    },

                    onMessage: (data) => {
                        if (!firstMessageReceived) {
                            firstMessageReceived = true;
                            this.stopLoading();
                            startRenderLoop();
                        }
                        pendingText += data.content;
                    },

                    onSearchResults: (data) => {
                        this.showSearchResults(data);
                    },

                    onDone: (data) => {
                        this.currentDecisionId = data.decision_id;
                        this.updateStreamingSkills(this.currentSkillIds);
                        setTimeout(() => this.loadHistory(), 2000);
                    },

                    onError: (error) => {
                        if (error.name === 'AbortError') {
                            wasAborted = true;
                        } else {
                            textEl.textContent = '抱歉，服务暂时不可用，请稍后再试。';
                            console.error('Stream error:', error);
                        }
                    }
                }
            );
        } catch (error) {
            if (error.name === 'AbortError') {
                wasAborted = true;
            } else {
                throw error;
            }
        } finally {
            stopRenderLoop();
        }

        // 流式结束后最终渲染 Markdown
        fullResponse += pendingText;

        if (wasAborted && fullResponse) {
            fullResponse += '\n\n---\n\n*⏹ 生成已中断*';
        }

        textEl.innerHTML = this.renderMarkdown(fullResponse);
        this.scrollToBottom();

        // 移除打字光标
        const cursor = document.getElementById('streamingCursor');
        if (cursor) cursor.remove();

        // 清除流式消息的固定 ID，避免下一轮冲突
        const streamingMsg = document.getElementById('streamingMessage');
        if (streamingMsg) {
            streamingMsg.removeAttribute('id');
            if (!streamingMsg.querySelector('.save-turn-btn')) {
                const btn = document.createElement('button');
                btn.className = 'save-turn-btn';
                btn.title = '保存此轮对话';
                btn.onclick = () => this._saveTurn(btn);
                btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>';
                streamingMsg.insertAdjacentElement('afterbegin', btn);
            }
        }
        if (textEl) textEl.removeAttribute('id');
        const streamingSkills = document.getElementById('streamingSkills');
        if (streamingSkills) streamingSkills.removeAttribute('id');

        // 中断时也保存已回复内容到记忆
        if (wasAborted && fullResponse) {
            this._saveInterruptedMemory(query, fullResponse);
        }
    }

    async _saveInterruptedMemory(query, partialResponse) {
        try {
            await fetch(`${window.dialecticAPI.baseUrl}/memory/save`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    user_query: query,
                    selected_skills: this.currentSkillIds,
                    execution_mode: 'interrupted',
                    full_response: partialResponse,
                    confidence: 0,
                    reasoning: '用户中断生成',
                })
            });
            console.log('中断内容已保存到记忆');
        } catch (e) {
            console.warn('保存中断记忆失败:', e);
        }
    }

    updateSkillsPanel(data) {
        const { skill_ids = [], confidence = 0, reasoning = '' } = data;

        // 更新视角标签
        this.elements.skillsList.innerHTML = skill_ids.map(id => `
            <span class="skill-tag" style="background: ${SKILL_COLORS[id] || '#4A90D9'}">
                ${SKILL_NAMES[id] || id.replace('-perspective', '')}
            </span>
        `).join('') || '<span style="color: var(--color-text-light); font-size: 12px;">正在分析...</span>';

        // 更新置信度
        const percent = Math.round(confidence * 100);
        this.elements.confidenceFill.style.width = `${percent}%`;
        this.elements.confidenceText.textContent = `${percent}%`;

        // 显示面板
        this.elements.skillsPanel.classList.add('visible');
    }

    startLoading(text = '加载中...') {
        this.isLoading = true;
        this.elements.loadingOverlay.classList.add('visible');
        this.elements.loadingText.textContent = text;
        this.elements.sendBtn.disabled = true;
    }

    stopLoading() {
        this.isLoading = false;
        this.elements.loadingOverlay.classList.remove('visible');
        this.elements.sendBtn.disabled = false;

        // 3秒后隐藏视角面板
        setTimeout(() => {
            this.elements.skillsPanel.classList.remove('visible');
        }, 3000);
    }

    scrollToBottom() {
        const container = document.querySelector('.chat-container');
        container.scrollTop = container.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 将 Markdown 转为安全 HTML
     */
    renderMarkdown(text) {
        if (!text) return '';
        if (typeof marked === 'undefined') {
            return this.escapeHtml(text).replace(/\n/g, '<br>');
        }
        const html = marked.parse(text);
        let safeHtml = html;
        if (typeof DOMPurify !== 'undefined') {
            safeHtml = DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
        }
        return this._wrapCollapsibleSections(safeHtml);
    }

    _wrapCollapsibleSections(html) {
        const SKILL_SECTION_PATTERN = /<h3[^>]*>\s*(?:###\s*)?([\u4e00-\u9fff]+(?:视角)?(?:（[^）]*）)?)\s*<\/h3>/g;
        const HOST_PATTERN = /<h3[^>]*>\s*(?:###\s*)?【主持人】[^<]*<\/h3>/g;

        const parts = [];
        let lastIndex = 0;
        const sections = [];

        const allHeadings = [];
        let match;

        const skillPattern = /<h3[^>]*>\s*(?:###\s*)?([\u4e00-\u9fff]+(?:视角)?(?:（[^）]*）)?)\s*<\/h3>/g;
        while ((match = skillPattern.exec(html)) !== null) {
            const title = match[1];
            if (title.includes('辩证综合') || title.includes('主持人')) continue;
            allHeadings.push({
                index: match.index,
                length: match[0].length,
                title: title,
                type: 'skill'
            });
        }

        const hostPattern = /<h3[^>]*>\s*(?:###\s*)?【主持人】([^<]*)<\/h3>/g;
        while ((match = hostPattern.exec(html)) !== null) {
            allHeadings.push({
                index: match.index,
                length: match[0].length,
                title: '【主持人】' + match[1],
                type: 'host'
            });
        }

        allHeadings.sort((a, b) => a.index - b.index);

        if (allHeadings.length === 0) return html;

        let result = '';
        let cursor = 0;

        for (let i = 0; i < allHeadings.length; i++) {
            const heading = allHeadings[i];
            const nextIndex = i + 1 < allHeadings.length ? allHeadings[i + 1].index : html.length;

            result += html.substring(cursor, heading.index);

            const sectionContent = html.substring(heading.index, nextIndex);

            if (heading.type === 'skill') {
                const skillName = heading.title.replace(/（[^）]*）/, '').trim();
                const skillColor = this._getSkillColor(skillName);
                const uid = 'coll_' + Math.random().toString(36).substr(2, 8);
                result += `<div class="skill-section" data-uid="${uid}">`;
                result += `<div class="skill-section-header" onclick="window.chatApp._toggleSection('${uid}')" style="border-left: 4px solid ${skillColor};">`;
                result += `<span class="skill-section-dot" style="background:${skillColor};"></span>`;
                result += `<span class="skill-section-title">${this.escapeHtml(heading.title)}</span>`;
                result += `<span class="skill-section-toggle" id="toggle_${uid}">▶ 点击展开</span>`;
                result += `</div>`;
                result += `<div class="skill-section-body" id="body_${uid}">`;
                result += sectionContent;
                result += `</div></div>`;
            } else {
                const uid = 'coll_' + Math.random().toString(36).substr(2, 8);
                result += `<div class="skill-section host-section" data-uid="${uid}">`;
                result += `<div class="skill-section-header host-header" onclick="window.chatApp._toggleSection('${uid}')">`;
                result += `<span class="skill-section-title">${this.escapeHtml(heading.title)}</span>`;
                result += `<span class="skill-section-toggle" id="toggle_${uid}">▶ 点击展开</span>`;
                result += `</div>`;
                result += `<div class="skill-section-body" id="body_${uid}">`;
                result += sectionContent;
                result += `</div></div>`;
            }

            cursor = nextIndex;
        }

        result += html.substring(cursor);
        return result;
    }

    _getSkillColor(name) {
        const colorMap = {
            '儒家': '#8E44AD', '道家': '#27AE60', '法家': '#E74C3C',
            '墨家': '#3498DB', '名家': '#F39C12', '阴阳家': '#9B59B6',
            '佛家': '#E67E22', '心学': '#1ABC9C', '兵家': '#C0392B',
            '史家': '#2980B9', '理学': '#16A085', '纵横家': '#D35400',
            '杂家': '#7F8C8D', '黄老': '#34495E', '新儒': '#9B59B6',
            '医家': '#2ECC71', '经学': '#8E6F3E', '农家': '#6B8E23',
            '小说家': '#DB7093', '术数家': '#483D8B', '玄学': '#6A5ACD',
        };
        for (const [key, color] of Object.entries(colorMap)) {
            if (name.includes(key)) return color;
        }
        return '#4A90D9';
    }

    _toggleSection(uid) {
        const body = document.getElementById('body_' + uid);
        const toggle = document.getElementById('toggle_' + uid);
        if (!body || !toggle) return;

        if (body.classList.contains('expanded')) {
            body.classList.remove('expanded');
            toggle.textContent = '▶ 点击展开';
        } else {
            body.classList.add('expanded');
            toggle.textContent = '▼ 收起';
            this.scrollToBottom();
        }
    }

    _expandAllSections() {
        document.querySelectorAll('.skill-section-body').forEach(el => {
            el.classList.add('expanded');
        });
        document.querySelectorAll('.skill-section-toggle').forEach(el => {
            el.textContent = '▼ 收起';
        });
    }

    _collapseAllSections() {
        document.querySelectorAll('.skill-section-body').forEach(el => {
            el.classList.remove('expanded');
        });
        document.querySelectorAll('.skill-section-toggle').forEach(el => {
            el.textContent = '▶ 点击展开';
        });
    }

    showSearchResults(data) {
        const existing = document.getElementById('search-results-panel');
        if (existing) existing.remove();

        const panel = document.createElement('div');
        panel.id = 'search-results-panel';
        panel.className = 'search-results-panel collapsed';

        const results = data.results || [];
        const keywords = data.search_keywords || data.query || '';
        const displayQuery = keywords.length > 60 ? keywords.substring(0, 60) + '...' : keywords;

        let html = `<div class="search-results-header" onclick="document.getElementById('search-results-panel').classList.toggle('collapsed')">
            <span class="search-results-icon">🔍</span>
            <span class="search-results-label">联网搜索：${this.escapeHtml(displayQuery)}</span>
            <span class="search-results-count">${results.length}条结果</span>
            <span class="search-results-toggle">▶ 点击展开</span>
            <button class="search-results-close" onclick="event.stopPropagation(); this.closest('.search-results-panel').remove()">✕</button>
        </div>`;

        html += '<div class="search-results-body">';
        for (const r of results) {
            const sourceTag = r.source ? `<span class="search-result-source">${this.escapeHtml(r.source)}</span>` : '';
            html += `<div class="search-result-item">
                <div class="search-result-title-row">
                    <a class="search-result-title" href="${this.escapeHtml(r.url)}" target="_blank" rel="noopener">${this.escapeHtml(r.title)}</a>
                    ${sourceTag}
                </div>
                <div class="search-result-snippet">${this.escapeHtml(r.snippet)}</div>
                <a class="search-result-url" href="${this.escapeHtml(r.url)}" target="_blank" rel="noopener">${this.escapeHtml(r.url)}</a>
            </div>`;
        }
        html += '</div>';

        panel.innerHTML = html;
        this.elements.messages.appendChild(panel);
        this.scrollToBottom();
    }

    /**
     * 分段截图超长内容并拼接为完整长图
     */
    async _captureLongContent(messages, captureWidth, scale) {
        const MAX_CHUNK_CANVAS = 14000;
        const chunkDOMHeight = Math.floor(MAX_CHUNK_CANVAS / scale);
        const totalHeight = messages.scrollHeight;
        const chunks = Math.ceil(totalHeight / chunkDOMHeight);
        const canvases = [];

        const origOverflow = messages.style.overflow;
        const origHeight = messages.style.height;
        const origMaxHeight = messages.style.maxHeight;
        const origScrollTop = messages.scrollTop;

        for (let i = 0; i < chunks; i++) {
            messages.scrollTop = i * chunkDOMHeight;
            await new Promise(r => setTimeout(r, 200));

            const visibleTop = i * chunkDOMHeight;
            const visibleHeight = Math.min(chunkDOMHeight, totalHeight - visibleTop);

            const chunkCanvas = await html2canvas(messages, {
                backgroundColor: '#FFFFFF',
                scale: scale,
                useCORS: true,
                logging: false,
                width: captureWidth,
                height: visibleHeight,
                windowWidth: captureWidth,
                windowHeight: visibleHeight,
                scrollX: 0,
                scrollY: 0,
                y: visibleTop,
            });
            canvases.push(chunkCanvas);
        }

        messages.style.overflow = origOverflow;
        messages.style.height = origHeight;
        messages.style.maxHeight = origMaxHeight;
        messages.scrollTop = origScrollTop;

        if (canvases.length === 1) {
            return canvases[0];
        }

        const totalW = canvases[0].width;
        const totalH = canvases.reduce((sum, c) => sum + c.height, 0);
        const MAX_MERGE_PIXELS = 100_000_000;

        if (totalW * totalH <= MAX_MERGE_PIXELS) {
            const mergedCanvas = document.createElement('canvas');
            mergedCanvas.width = totalW;
            mergedCanvas.height = totalH;
            const ctx = mergedCanvas.getContext('2d');
            ctx.fillStyle = '#FFFFFF';
            ctx.fillRect(0, 0, totalW, totalH);
            let offsetY = 0;
            for (const c of canvases) {
                ctx.drawImage(c, 0, offsetY);
                offsetY += c.height;
            }
            return mergedCanvas;
        }

        return { _chunked: true, canvases };
    }

    /**
     * 截图保存对话记录
     */
    async takeScreenshot() {
        const botMessages = this.elements.messages.querySelectorAll('.message.bot');
        if (botMessages.length === 0) {
            alert('暂无对话内容可保存');
            return;
        }

        const btn = this.elements.screenshotBtn;
        const originalHTML = btn.innerHTML;
        btn.querySelector('span').textContent = '保存中...';
        btn.disabled = true;

        try {
            const now = new Date();
            const ts = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}_${String(now.getHours()).padStart(2,'0')}-${String(now.getMinutes()).padStart(2,'0')}`;
            const totalTurns = botMessages.length;

            for (let i = 0; i < totalTurns; i++) {
                const botMsg = botMessages[i];
                const prevEl = botMsg.previousElementSibling;
                const userMsg = (prevEl && prevEl.classList.contains('user')) ? prevEl : null;

                const wrapper = document.createElement('div');
                wrapper.style.cssText = 'position:fixed;left:-9999px;top:0;width:800px;background:#F5F5F0;padding:24px;z-index:-1;';

                if (userMsg) {
                    const userClone = userMsg.cloneNode(true);
                    userClone.style.maxWidth = '85%';
                    userClone.style.marginLeft = 'auto';
                    userClone.style.marginBottom = '12px';
                    wrapper.appendChild(userClone);
                }

                const botClone = botMsg.cloneNode(true);
                const saveBtnInClone = botClone.querySelector('.save-turn-btn');
                if (saveBtnInClone) saveBtnInClone.remove();
                botClone.style.maxWidth = '85%';
                botClone.style.position = 'relative';

                const collapsedSections = botClone.querySelectorAll('.skill-section-body');
                collapsedSections.forEach(el => el.classList.add('expanded'));

                wrapper.appendChild(botClone);
                document.body.appendChild(wrapper);

                try {
                    if (typeof html2canvas !== 'undefined') {
                        const canvas = await html2canvas(wrapper, {
                            backgroundColor: '#F5F5F0',
                            scale: 2,
                            useCORS: true,
                            logging: false,
                            width: 800,
                            windowWidth: 800,
                        });
                        this._downloadSingleImage(canvas, `辩证思考顾问-${ts}_第${i+1}轮`);
                    } else {
                        this._exportTurnAsHTML(botMsg, userMsg);
                    }
                } catch (e) {
                    console.warn(`第${i+1}轮截图失败，降级为HTML:`, e);
                    this._exportTurnAsHTML(botMsg, userMsg);
                } finally {
                    document.body.removeChild(wrapper);
                }

                if (i < totalTurns - 1) {
                    await new Promise(r => setTimeout(r, 600));
                }
            }
        } catch (error) {
            console.error('保存失败:', error);
            alert('保存失败，请重试');
        } finally {
            btn.innerHTML = originalHTML;
            btn.disabled = false;
        }
    }

    _downloadSingleImage(canvas, ts) {
        const link = document.createElement('a');
        link.download = `辩证思考顾问-${ts}.png`;

        const tryDownload = (quality) => {
            canvas.toBlob((blob) => {
                if (!blob) {
                    if (quality > 0.3) {
                        tryDownload(quality - 0.2);
                    } else {
                        try {
                            const dataUrl = canvas.toDataURL('image/jpeg', 0.5);
                            if (dataUrl && dataUrl !== 'data:,') {
                                link.download = link.download.replace('.png', '.jpg');
                                link.href = dataUrl;
                                link.click();
                            } else {
                                this._fallbackToHTMLExport();
                            }
                        } catch (e) {
                            this._fallbackToHTMLExport();
                        }
                    }
                    return;
                }
                const url = URL.createObjectURL(blob);
                link.href = url;
                link.click();
                setTimeout(() => URL.revokeObjectURL(url), 5000);
            }, quality < 1 ? 'image/jpeg' : 'image/png', quality < 1 ? quality : undefined);
        };

        tryDownload(1);
    }

    async _downloadChunkedImages(canvases, ts) {
        const totalChunks = canvases.length;
        let downloaded = 0;

        for (let i = 0; i < totalChunks; i++) {
            const chunkCanvas = canvases[i];
            const blob = await new Promise((resolve) => {
                chunkCanvas.toBlob((b) => resolve(b), 'image/png');
            });

            if (!blob) {
                const jpegBlob = await new Promise((resolve) => {
                    chunkCanvas.toBlob((b) => resolve(b), 'image/jpeg', 0.8);
                });
                if (jpegBlob) {
                    this._downloadBlob(jpegBlob, `辩证思考顾问-${ts}_第${i+1}部分_共${totalChunks}部分.jpg`);
                    downloaded++;
                }
            } else {
                this._downloadBlob(blob, `辩证思考顾问-${ts}_第${i+1}部分_共${totalChunks}部分.png`);
                downloaded++;
            }

            if (i < totalChunks - 1) {
                await new Promise(r => setTimeout(r, 500));
            }
        }

        if (downloaded === 0) {
            this._fallbackToHTMLExport();
        } else if (downloaded < totalChunks) {
            alert(`已导出 ${downloaded}/${totalChunks} 张图片，部分片段因内容过长未能导出。建议使用"导出HTML"保存完整记录。`);
        }
    }

    _downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
    }

    _fallbackToHTMLExport() {
        if (confirm('截图因内容过长无法生成，是否改为导出HTML文件？（HTML保留完整格式，可用浏览器打开后打印为PDF）')) {
            this.exportHTML();
        }
    }

    async _saveTurn(btnEl) {
        if (typeof html2canvas === 'undefined') {
            alert('截图功能加载中，请稍后再试');
            return;
        }

        const botMsg = btnEl.closest('.message.bot');
        if (!botMsg) return;

        const prevEl = botMsg.previousElementSibling;
        const userMsg = (prevEl && prevEl.classList.contains('user')) ? prevEl : null;

        const wrapper = document.createElement('div');
        wrapper.style.cssText = 'position:fixed;left:-9999px;top:0;width:800px;background:#F5F5F0;padding:24px;z-index:-1;';

        if (userMsg) {
            const userClone = userMsg.cloneNode(true);
            userClone.style.maxWidth = '85%';
            userClone.style.marginLeft = 'auto';
            userClone.style.marginBottom = '12px';
            wrapper.appendChild(userClone);
        }

        const botClone = botMsg.cloneNode(true);
        const saveBtnInClone = botClone.querySelector('.save-turn-btn');
        if (saveBtnInClone) saveBtnInClone.remove();
        botClone.style.maxWidth = '85%';
        botClone.style.position = 'relative';
        wrapper.appendChild(botClone);

        document.body.appendChild(wrapper);

        try {
            const collapsedSections = botClone.querySelectorAll('.skill-section-body');
            collapsedSections.forEach(el => el.classList.add('expanded'));

            const canvas = await html2canvas(wrapper, {
                backgroundColor: '#F5F5F0',
                scale: 2,
                useCORS: true,
                logging: false,
                width: 800,
                windowWidth: 800,
            });

            const now = new Date();
            const ts = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}_${String(now.getHours()).padStart(2,'0')}-${String(now.getMinutes()).padStart(2,'0')}`;

            this._downloadSingleImage(canvas, `对话记录-${ts}`);
        } catch (e) {
            console.error('单轮截图失败:', e);
            this._exportTurnAsHTML(botMsg, userMsg);
        } finally {
            document.body.removeChild(wrapper);
        }
    }

    _exportTurnAsHTML(botMsg, userMsg) {
        let userText = '';
        if (userMsg) {
            const p = userMsg.querySelector('.content p');
            userText = p ? p.textContent : '';
        }

        const botContent = botMsg.querySelector('.content');
        const botHTML = botContent ? botContent.innerHTML : '';

        const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>对话记录</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;max-width:800px;margin:0 auto;padding:24px;background:#F5F5F0;color:#333;line-height:1.7;}
.user-msg{background:#4A90D9;color:white;padding:14px 18px;border-radius:12px;margin-bottom:16px;margin-left:auto;max-width:85%;}
.bot-msg{background:white;padding:14px 18px;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.1);max-width:85%;}
.bot-msg h3{margin-top:16px;padding-bottom:6px;border-bottom:1px solid #eee;}
.bot-msg ul,.bot-msg ol{padding-left:20px;}
.bot-msg code{background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:13px;}
.bot-msg blockquote{border-left:3px solid #4A90D9;margin:8px 0;padding:8px 16px;background:#f8f9fa;}
</style>
</head>
<body>
${userText ? `<div class="user-msg"><p>${userText.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</p></div>` : ''}
<div class="bot-msg">${botHTML}</div>
</body>
</html>`;

        const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
        const now = new Date();
        const ts = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}_${String(now.getHours()).padStart(2,'0')}-${String(now.getMinutes()).padStart(2,'0')}`;
        this._downloadBlob(blob, `对话记录-${ts}.html`);
    }

    _collectConversationData() {
        const messages = this.elements.messages;
        const result = [];
        const msgEls = messages.querySelectorAll('.message');

        for (const el of msgEls) {
            if (el.classList.contains('welcome')) continue;

            const isUser = el.classList.contains('user');
            const contentEl = el.querySelector('.content');
            if (!contentEl) continue;

            const skillSections = contentEl.querySelectorAll('.skill-section');
            if (skillSections.length > 0) {
                for (const sec of skillSections) {
                    const headerEl = sec.querySelector('.skill-section-header');
                    const bodyEl = sec.querySelector('.skill-section-body');
                    const title = headerEl ? headerEl.textContent.trim() : '';
                    const bodyHTML = bodyEl ? bodyEl.innerHTML : '';
                    const bodyText = bodyEl ? bodyEl.textContent.trim() : '';
                    result.push({ type: 'skill', title, bodyHTML, bodyText });
                }
            } else {
                const text = contentEl.textContent.trim();
                const html = contentEl.innerHTML;
                result.push({ type: isUser ? 'user' : 'bot', text, html });
            }
        }

        return result;
    }

    exportHTML() {
        const data = this._collectConversationData();
        if (data.length === 0) {
            alert('暂无对话内容可导出');
            return;
        }

        const now = new Date();
        const ts = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

        let bodyHTML = '';
        for (const item of data) {
            if (item.type === 'user') {
                bodyHTML += `<div class="msg-user"><div class="msg-avatar">👤</div><div class="msg-bubble user-bubble">${this.escapeHtml(item.text)}</div></div>\n`;
            } else if (item.type === 'skill') {
                bodyHTML += `<div class="msg-skill"><div class="skill-title">${this.escapeHtml(item.title)}</div><div class="skill-body">${item.bodyHTML}</div></div>\n`;
            } else {
                bodyHTML += `<div class="msg-bot"><div class="msg-avatar">🤖</div><div class="msg-bubble bot-bubble">${item.html}</div></div>\n`;
            }
        }

        const htmlDoc = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>辩证思考顾问 - 对话记录 ${ts}</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; background: #F7F5F2; color: #2C3E50; line-height: 1.7; padding: 20px; max-width: 860px; margin: 0 auto; }
h1 { text-align: center; font-size: 20px; color: #4A90D9; margin-bottom: 4px; }
.ts { text-align: center; color: #95A5A6; font-size: 13px; margin-bottom: 24px; }
.msg-user, .msg-bot { display: flex; gap: 10px; margin-bottom: 16px; align-items: flex-start; }
.msg-avatar { font-size: 24px; flex-shrink: 0; width: 36px; text-align: center; }
.msg-bubble { padding: 12px 16px; border-radius: 12px; max-width: 85%; word-break: break-word; }
.user-bubble { background: #4A90D9; color: white; }
.bot-bubble { background: #FFFFFF; border: 1px solid #E8E4DF; }
.msg-skill { margin-bottom: 16px; background: #FFFFFF; border-radius: 12px; border: 1px solid #E8E4DF; overflow: hidden; }
.skill-title { padding: 10px 16px; background: #F0EDE9; font-weight: 600; font-size: 14px; color: #4A90D9; }
.skill-body { padding: 16px; }
.skill-body h1, .skill-body h2, .skill-body h3, .skill-body h4 { margin: 16px 0 8px; color: #2C3E50; }
.skill-body h2 { font-size: 17px; border-bottom: 1px solid #E8E4DF; padding-bottom: 6px; }
.skill-body h3 { font-size: 15px; }
.skill-body p { margin: 8px 0; }
.skill-body ul, .skill-body ol { margin: 8px 0; padding-left: 24px; }
.skill-body li { margin: 4px 0; }
.skill-body strong { color: #2C3E50; }
.skill-body blockquote { border-left: 3px solid #4A90D9; padding: 8px 16px; margin: 8px 0; background: #F7F5F2; color: #5D6D7E; }
.skill-body code { background: #F0EDE9; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.skill-body pre { background: #2C3E50; color: #ECF0F1; padding: 12px 16px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
.skill-body pre code { background: none; color: inherit; padding: 0; }
hr { border: none; border-top: 1px solid #E8E4DF; margin: 16px 0; }
.search-results { background: #F7F5F2; border-radius: 8px; padding: 12px 16px; margin: 8px 0; font-size: 13px; }
.search-results a { color: #4A90D9; }
@media print { body { padding: 0; } .msg-bubble { max-width: 100%; } }
</style>
</head>
<body>
<h1>辩证思考顾问 · 对话记录</h1>
<p class="ts">${ts}</p>
${bodyHTML}
</body>
</html>`;

        this._downloadFile(htmlDoc, `辩证思考顾问-${ts.replace(/[: ]/g, '-')}.html`, 'text/html');
    }

    exportMarkdown() {
        const data = this._collectConversationData();
        if (data.length === 0) {
            alert('暂无对话内容可导出');
            return;
        }

        const now = new Date();
        const ts = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

        let md = `# 辩证思考顾问 · 对话记录\n\n> ${ts}\n\n---\n\n`;

        for (const item of data) {
            if (item.type === 'user') {
                md += `## 👤 用户\n\n${item.text}\n\n---\n\n`;
            } else if (item.type === 'skill') {
                md += `## ${item.title}\n\n${item.bodyText}\n\n---\n\n`;
            } else {
                md += `## 🤖 助手\n\n${item.text}\n\n---\n\n`;
            }
        }

        this._downloadFile(md, `辩证思考顾问-${ts.replace(/[: ]/g, '-')}.md`, 'text/markdown');
    }

    printConversation() {
        const data = this._collectConversationData();
        if (data.length === 0) {
            alert('暂无对话内容可打印');
            return;
        }

        const now = new Date();
        const ts = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;

        let bodyHTML = '';
        for (const item of data) {
            if (item.type === 'user') {
                bodyHTML += `<div style="margin-bottom:16px;display:flex;gap:10px;align-items:flex-start"><div style="font-size:24px">👤</div><div style="background:#4A90D9;color:white;padding:12px 16px;border-radius:12px;max-width:85%;word-break:break-word">${this.escapeHtml(item.text)}</div></div>`;
            } else if (item.type === 'skill') {
                bodyHTML += `<div style="margin-bottom:16px;background:#fff;border:1px solid #E8E4DF;border-radius:12px;overflow:hidden"><div style="padding:10px 16px;background:#F0EDE9;font-weight:600;color:#4A90D9">${this.escapeHtml(item.title)}</div><div style="padding:16px">${item.bodyHTML}</div></div>`;
            } else {
                bodyHTML += `<div style="margin-bottom:16px;display:flex;gap:10px;align-items:flex-start"><div style="font-size:24px">🤖</div><div style="background:#fff;border:1px solid #E8E4DF;padding:12px 16px;border-radius:12px;max-width:85%;word-break:break-word">${item.html}</div></div>`;
            }
        }

        const printWin = window.open('', '_blank');
        if (!printWin) {
            alert('请允许弹出窗口以使用打印功能');
            return;
        }

        printWin.document.write(`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>辩证思考顾问 - 对话记录</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; color: #2C3E50; line-height: 1.7; padding: 20px; max-width: 860px; margin: 0 auto; }
h1 { text-align: center; font-size: 20px; color: #4A90D9; margin-bottom: 4px; }
.ts { text-align: center; color: #95A5A6; font-size: 13px; margin-bottom: 24px; }
blockquote { border-left: 3px solid #4A90D9; padding: 8px 16px; margin: 8px 0; background: #F7F5F2; color: #5D6D7E; }
code { background: #F0EDE9; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
pre { background: #2C3E50; color: #ECF0F1; padding: 12px 16px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
pre code { background: none; color: inherit; padding: 0; }
@media print { body { padding: 0; } }
</style>
</head>
<body>
<h1>辩证思考顾问 · 对话记录</h1>
<p class="ts">${ts}</p>
${bodyHTML}
</body>
</html>`);
        printWin.document.close();
        printWin.focus();
        setTimeout(() => printWin.print(), 500);
    }

    _downloadFile(content, filename, mimeType) {
        const blob = new Blob([content], { type: `${mimeType};charset=utf-8` });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
    }
}

// 初始化应用
document.addEventListener('DOMContentLoaded', () => {
    window.chatApp = new ChatApp();
});
