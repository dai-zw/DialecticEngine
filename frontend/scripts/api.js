/**
 * DialecticEngine API Client
 * 前后端分离架构
 * 
 * 注意：通过 debug_server.py 代理到后端 API
 * 或直接连接 http://localhost:8000
 */

const API_BASE_URL = window.location.origin + '/api';

class DialecticAPI {
    constructor(baseUrl = API_BASE_URL) {
        this.baseUrl = baseUrl;
        this._abortController = null;
        this._enableSearch = true;
    }

    setEnableSearch(enabled) {
        this._enableSearch = enabled;
    }

    /**
     * 中断当前流式请求
     */
    abortStream() {
        if (this._abortController) {
            this._abortController.abort();
            this._abortController = null;
        }
    }

    /**
     * 流式对话请求
     * @param {string} query - 用户问题
     * @param {string} sessionId - 会话ID
     * @param {Object} callbacks - 回调函数
     * @returns {Promise} - 完成后的最终数据
     */
    async chatStream(query, sessionId, callbacks = {}) {
        const {
            onSkillSelected = () => {},
            onSkillStart = () => {},
            onMessage = () => {},
            onDone = () => {},
            onError = () => {},
            onSearchResults = () => {}
        } = callbacks;

        this._abortController = new AbortController();

        const response = await fetch(`${this.baseUrl}/chat/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query,
                session_id: sessionId,
                enable_search: this._enableSearch !== false
            }),
            signal: this._abortController.signal
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResult = null;
        let lastEventType = '';

        try {
            while (true) {
                const { done, value } = await reader.read();

                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('event:')) {
                        const eventType = line.slice(6).trim();
                        lastEventType = eventType;
                        continue;
                    }

                    if (line.startsWith('data:')) {
                        const data = line.slice(5).trim();
                        if (!data) continue;

                        try {
                            const parsed = JSON.parse(data);

                            if (lastEventType === 'search_results') {
                                onSearchResults(parsed);
                            } else if (parsed.skill_ids) {
                                onSkillSelected(parsed);
                            } else if (parsed.skill_id) {
                                onSkillStart(parsed);
                            } else if (parsed.content !== undefined) {
                                onMessage(parsed);
                            } else if (parsed.session_id) {
                                finalResult = parsed;
                            }
                        } catch (e) {
                            console.warn('Parse error:', e, 'Data:', data);
                        }
                    }
                }
            }

            // 处理剩余 buffer
            if (buffer.trim()) {
                if (buffer.startsWith('data:')) {
                    const data = buffer.slice(5).trim();
                    try {
                        const parsed = JSON.parse(data);
                        if (parsed.session_id) {
                            finalResult = parsed;
                        }
                    } catch (e) {}
                }
            }

            onDone(finalResult || {});
            return finalResult;

        } catch (error) {
            onError(error);
            throw error;
        }
    }

    /**
     * 非流式对话请求
     */
    async chat(query, sessionId) {
        const response = await fetch(`${this.baseUrl}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query,
                session_id: sessionId
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    /**
     * 提交反馈
     */
    async submitFeedback(decisionId, rating, comment = '') {
        const response = await fetch(`${this.baseUrl}/feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                decision_id: decisionId,
                rating,
                comment
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    /**
     * 获取技能列表
     */
    async getSkills() {
        const response = await fetch(`${this.baseUrl}/skills`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }

    /**
     * 健康检查
     */
    async healthCheck() {
        const response = await fetch(`${this.baseUrl}/health`);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    }
}

// 导出全局实例
window.dialecticAPI = new DialecticAPI();
