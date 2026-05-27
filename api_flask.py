"""
DialecticEngine - Flask 入口
提供 HTTP API 接口
"""

import json
import time
import uuid
import warnings
from pathlib import Path
from typing import Optional

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, Response, jsonify, send_from_directory  # Flask Web 框架核心组件
from flask_cors import CORS  # 跨域资源共享支持，允许前端跨域请求

from main_entry import DialecticEngine  # 从项目主入口导入核心引擎类
from memory_store import MemoryStore
from web_search import web_search

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
DEBUG_LOG_PATH = ROOT_DIR / "debug-7ce45e.log"
DEBUG_SESSION_ID = "7ce45e"


def _debug_log(location: str, message: str, data: dict, hypothesis_id: str) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": DEBUG_SESSION_ID,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
            "hypothesisId": hypothesis_id,
        }
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


# 创建 Flask 应用实例，__name__ 传入应用包名用于资源定位
app = Flask(__name__)
# 启用 CORS，允许所有来源的跨域请求
CORS(app)

# 全局变量，存储 DialecticEngine 单例实例，初始为 None
_engine: Optional[DialecticEngine] = None


def get_engine() -> DialecticEngine:
    """
    获取或初始化引擎实例（单例模式）
    返回全局唯一的 DialecticEngine 实例
    """
    global _engine
    if _engine is None:
        _engine = DialecticEngine(long_term_memory_enabled=False)
    return _engine


@app.route("/api/health")
@app.route("/health")
def health():
    """健康检查（供前端 /api/health 与探活使用）"""
    _debug_log("api_flask.py:health", "health_check", {"path": request.path}, "A")
    return jsonify({"status": "ok", "service": "DialecticEngine"})


@app.route("/chat/stream", methods=["POST"])
@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """
    流式对话接口 - Server-Sent Events (SSE)
    支持实时流式响应，适用于 AI 对话场景
    """
    _debug_log(
        "api_flask.py:chat_stream",
        "chat_stream_request",
        {"path": request.path, "method": request.method},
        "B",
    )
    # 从请求体获取 JSON 数据，若无数据则默认为空字典
    data = request.get_json() or {}
    # 提取用户查询文本，默认空字符串
    query = data.get("query", "")
    # 获取会话 ID，若未提供则生成新的 UUID 作为会话标识
    session_id = data.get("session_id") or str(uuid.uuid4())
    enable_search = data.get("enable_search", True)

    def generate():
        """
        生成器函数，用于流式返回 SSE 事件
        每次 yield 发送一个事件给客户端
        """
        engine = get_engine()  # 获取引擎实例

        try:
            # 调用引擎的路由方法，根据用户查询决定使用哪些技能
            decision = engine.route(query=query)

            # 构建技能选择事件数据
            skill_event = {
                "skill_ids": decision.selected_skills,  # 选中的技能 ID 列表
                "mode": decision.execution_mode.value,  # 执行模式（如 "parallel"、"sequential"）
                "confidence": decision.confidence,      # 决策置信度
                "reasoning": decision.reasoning,        # 决策推理过程
            }
            # 发送 skill_selected 事件，通知客户端已选择技能
            yield f"event: skill_selected\ndata: {json.dumps(skill_event, ensure_ascii=False)}\n\n"

            # 联网搜索
            search_context = ""
            search_results_data = []
            if enable_search:
                try:
                    search_history = ""
                    try:
                        session_summaries = MemoryStore.get_session_summaries(session_id, limit=5)
                        if session_summaries:
                            history_parts = []
                            for s in session_summaries:
                                q = s.get("query_summary", s.get("user_query", ""))
                                a = s.get("response_summary", "")
                                if q:
                                    history_parts.append(f"用户：{q}")
                                if a:
                                    history_parts.append(f"助手：{a}")
                            search_history = "\n".join(history_parts)
                    except Exception:
                        pass

                    search_type = "general"
                    news_keywords = ["新闻", "最新消息", "热点", "时事", "今天", "昨天", "近期"]
                    if any(kw in query for kw in news_keywords):
                        search_type = "news"

                    search_resp = web_search(query, max_results=10, history=search_history, search_type=search_type)
                    if search_resp.results:
                        search_context = search_resp.to_context_text()
                        search_results_data = [
                            {"title": r.title, "url": r.url, "snippet": r.snippet, "source": r.source}
                            for r in search_resp.results
                        ]
                        search_event = {
                            "query": query,
                            "search_keywords": search_resp.search_keywords,
                            "results": search_results_data,
                        }
                        yield f"event: search_results\ndata: {json.dumps(search_event, ensure_ascii=False)}\n\n"
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"联网搜索失败: {e}")

            for skill_id in decision.selected_skills:
                # 去掉 "-perspective" 后缀得到技能显示名称
                skill_name = skill_id.replace("-perspective", "")
                # 构建技能开始事件数据
                start_event = {"skill_id": skill_id, "name": skill_name}
                # 发送 skill_start 事件
                yield f"event: skill_start\ndata: {json.dumps(start_event, ensure_ascii=False)}\n\n"

            # 流式回调函数：每个 token 到达时立即 yield 给客户端
            def stream_callback(text: str):
                msg_event = {"content": text}
                # 使用 generator 的 send 机制不可行，改为写入队列
                # 这里利用闭包和非局部变量收集，但更好的方式是直接 yield
                # 由于 callback 是同步调用，我们需要一个能实时 yield 的方案
                pass

            # 使用队列 + 线程实现真正的实时流式推送
            import queue
            import threading

            msg_queue = queue.Queue()

            def real_stream_callback(text: str):
                msg_event = {"content": text}
                msg_queue.put(f"event: message\ndata: {json.dumps(msg_event, ensure_ascii=False)}\n\n")

            memory_context = ""
            try:
                context_text, _ = MemoryStore.build_context_from_summaries(session_id, max_turns=5)
                if context_text:
                    memory_context = context_text
            except Exception:
                pass

            def execute_in_thread():
                try:
                    result = engine.executor.execute_stream(
                        decision=decision,
                        user_query=query,
                        callback=real_stream_callback,
                        memory_context=memory_context,
                        search_context=search_context,
                    )
                    msg_queue.put({"_done": True, "result": result})
                except Exception as e:
                    msg_queue.put({"_done": True, "error": e})

            thread = threading.Thread(target=execute_in_thread)
            thread.start()

            # 实时从队列读取并 yield
            while True:
                item = msg_queue.get()
                if isinstance(item, dict) and item.get("_done"):
                    if "error" in item:
                        raise item["error"]
                    result = item["result"]
                    break
                yield item

            # 构建完成事件数据
            done_event = {
                "session_id": session_id,
                "decision_id": decision.decision_id,
                "skill_outputs": result.get("skill_outputs", []),
            }
            yield f"event: done\ndata: {json.dumps(done_event, ensure_ascii=False)}\n\n"

            # 后台保存记忆（不阻塞响应）
            import threading

            def _save_memory():
                try:
                    metadata = {
                        "decision_id": decision.decision_id,
                    }
                    host_opening = result.get("host_opening", "")
                    if host_opening:
                        metadata["host_opening"] = host_opening

                    memory_id = MemoryStore.save(
                        session_id=session_id,
                        user_query=query,
                        selected_skills=decision.selected_skills,
                        execution_mode=decision.execution_mode.value,
                        full_response=result.get("response", ""),
                        turns=result.get("chain_history", []),
                        synthesis=result.get("synthesis", ""),
                        skill_outputs=result.get("skill_outputs", []),
                        confidence=decision.confidence,
                        reasoning=decision.reasoning,
                        metadata=metadata,
                    )
                    print(f"[记忆] 已保存: {memory_id}")
                except Exception as e:
                    print(f"[记忆] 保存失败: {e}")

            threading.Thread(target=_save_memory, daemon=True).start()

        except Exception as e:  # 捕获所有异常
            # 构建错误事件数据
            error_event = {"error": str(e)}  # 将异常信息转为字符串
            # 发送 error 事件，通知客户端发生错误
            yield f"event: error\ndata: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    # 返回 Response 对象，配置 SSE 相关 headers
    return Response(
        generate(),  # 生成器函数作为响应体
        mimetype="text/event-stream",  # MIME 类型为 Server-Sent Events
        headers={
            "Cache-Control": "no-cache",     # 禁止缓存，确保实时性
            "Connection": "keep-alive",       # 保持连接不关闭
            "X-Accel-Buffering": "no",       # 禁用 Nginx 缓冲，实现真正流式
        }
    )


@app.route("/")
def serve_index():
    """根路径返回前端页面（避免只启动 api_flask 时无法访问 UI）"""
    _debug_log(
        "api_flask.py:serve_index",
        "serve_frontend_index",
        {"frontend_dir": str(FRONTEND_DIR), "exists": FRONTEND_DIR.is_dir()},
        "A",
    )
    if not FRONTEND_DIR.is_dir():
        return jsonify({"status": "error", "message": "frontend 目录不存在"}), 500
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def serve_frontend_static(filename: str):
    """托管 frontend 下的静态资源（scripts、styles 等）"""
    if filename.startswith("api/"):
        return jsonify({"status": "error", "message": "not found"}), 404
    target = FRONTEND_DIR / filename
    if not target.is_file():
        _debug_log(
            "api_flask.py:serve_frontend_static",
            "static_not_found",
            {"filename": filename},
            "C",
        )
        return jsonify({"status": "error", "message": "not found"}), 404
    return send_from_directory(FRONTEND_DIR, filename)


@app.route("/api/memory/save", methods=["POST"])
def save_memory():
    """保存中断/手动触发的记忆"""
    from memory_store import MemoryStore

    data = request.get_json(force=True)
    try:
        memory_id = MemoryStore.save(
            session_id=data.get("session_id", ""),
            user_query=data.get("user_query", ""),
            selected_skills=data.get("selected_skills", []),
            execution_mode=data.get("execution_mode", "interrupted"),
            full_response=data.get("full_response", ""),
            turns=data.get("turns", []),
            synthesis=data.get("synthesis", ""),
            skill_outputs=data.get("skill_outputs", []),
            confidence=data.get("confidence", 0),
            reasoning=data.get("reasoning", ""),
            metadata=data.get("metadata", {}),
        )
        return jsonify({"status": "ok", "memory_id": memory_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/memory/list", methods=["GET"])
def list_memories():
    """列出摘要记忆"""
    from memory_store import MemoryStore

    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)
    topic = request.args.get("topic")
    skill = request.args.get("skill")
    summaries = MemoryStore.list_summaries(limit=limit, offset=offset, topic=topic, skill=skill)
    return jsonify({"status": "ok", "memories": summaries})


@app.route("/api/memory/session/<session_id>", methods=["GET"])
def get_session_memories(session_id: str):
    """获取指定会话的原文记忆列表"""
    from memory_store import MemoryStore

    raws = MemoryStore.get_session_raws(session_id)
    return jsonify({"status": "ok", "memories": raws})


@app.route("/api/memory/<memory_id>", methods=["GET"])
def get_memory(memory_id: str):
    """获取一对记忆（原文+摘要）"""
    from memory_store import MemoryStore

    raw, summary = MemoryStore.get_pair(memory_id)
    if not raw and not summary:
        return jsonify({"status": "error", "message": "not found"}), 404
    return jsonify({"status": "ok", "raw": raw, "summary": summary})


@app.route("/api/memory/search", methods=["GET"])
def search_memories():
    """搜索记忆"""
    from memory_store import MemoryStore

    query = request.args.get("q", "")
    top_k = request.args.get("top_k", 5, type=int)
    results = MemoryStore.search_by_query(query, top_k=top_k)
    return jsonify({"status": "ok", "memories": results})


def main():
    """
    启动函数
    初始化并运行 Flask 开发服务器
    """
    print("=" * 60)  # 打印分隔线
    print("DialecticEngine Flask Server Started")  # 服务启动提示
    print("  前端页面: http://localhost:8000/")  # 浏览器访问入口
    print("  API:      http://localhost:8000/api/")  # API 前缀
    print("  (可选) debug_server 代理: http://localhost:8080/")  # 开发代理
    print("=" * 60)  # 打印分隔线
    # 启动 Flask 服务器
    # host="0.0.0.0" 允许所有网络接口访问
    # port=8000 指定监听端口
    # debug=True 开启调试模式（热重载）
    # threaded=True 启用多线程支持
    app.run(host="0.0.0.0", port=8000, debug=True, threaded=True)


if __name__ == "__main__":
    # 仅当直接运行此脚本时执行 main()
    # 导入模块时不会执行
    main()
