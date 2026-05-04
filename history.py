"""
语音输入识别历史的 SQLite 存储。

DB 路径遵循 XDG 规范：$XDG_DATA_HOME/voice-input/history.db，
默认 ~/.local/share/voice-input/history.db。

表结构只存文本元信息，不存原始音频（音频文件会很快堆爆盘）。
"""
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple


def _db_path() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "voice-input" / "history.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    REAL    NOT NULL,       -- unix epoch 秒
    text         TEXT    NOT NULL,
    duration_ms  INTEGER,                -- F9 按下到松开的毫秒数
    wm_class     TEXT,                   -- 目标窗口 WM_CLASS（xdotool getwindowclassname）
    window_title TEXT                    -- 目标窗口标题
);
CREATE INDEX IF NOT EXISTS idx_history_ts ON history(timestamp);
"""


def _conn() -> sqlite3.Connection:
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.executescript(_SCHEMA)
    return conn


def record(text: str, duration_ms: Optional[int] = None,
           wm_class: Optional[str] = None, window_title: Optional[str] = None) -> None:
    """插入一条识别记录。text 为空或全空白时跳过。"""
    if not text or not text.strip():
        return
    with _conn() as c:
        c.execute(
            "INSERT INTO history (timestamp, text, duration_ms, wm_class, window_title) "
            "VALUES (?, ?, ?, ?, ?)",
            (time.time(), text, duration_ms, wm_class, window_title),
        )


def query(limit: int = 20, search: Optional[str] = None,
          today: bool = False, since_days: Optional[int] = None) -> List[Tuple]:
    """返回 [(id, ts, text, duration_ms, wm_class, window_title), ...]，按时间降序。"""
    sql = "SELECT id, timestamp, text, duration_ms, wm_class, window_title FROM history"
    clauses: List[str] = []
    params: list = []

    if search:
        clauses.append("text LIKE ?")
        params.append(f"%{search}%")
    if today:
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        clauses.append("timestamp >= ?")
        params.append(start)
    elif since_days is not None:
        start = (datetime.now() - timedelta(days=since_days)).timestamp()
        clauses.append("timestamp >= ?")
        params.append(start)

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with _conn() as c:
        return c.execute(sql, params).fetchall()


def stats() -> dict:
    """返回总计信息：条数、总时长、今日条数、DB 文件大小。"""
    with _conn() as c:
        total, total_ms = c.execute(
            "SELECT COUNT(*), COALESCE(SUM(duration_ms), 0) FROM history"
        ).fetchone()
        today_start = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ).timestamp()
        today_count, = c.execute(
            "SELECT COUNT(*) FROM history WHERE timestamp >= ?", (today_start,)
        ).fetchone()
        first_ts, = c.execute("SELECT MIN(timestamp) FROM history").fetchone()
    try:
        db_bytes = _db_path().stat().st_size
    except FileNotFoundError:
        db_bytes = 0
    return {
        "total": total,
        "total_minutes": round(total_ms / 60000, 2) if total_ms else 0,
        "today": today_count,
        "db_bytes": db_bytes,
        "first_ts": first_ts,
    }


def prune(days: int) -> int:
    """删除 days 天之前的记录，返回删除条数。VACUUM 回收空间。"""
    cutoff = (datetime.now() - timedelta(days=days)).timestamp()
    with _conn() as c:
        cur = c.execute("DELETE FROM history WHERE timestamp < ?", (cutoff,))
        deleted = cur.rowcount
    # VACUUM 必须在事务外
    conn = sqlite3.connect(str(_db_path()))
    try:
        conn.execute("VACUUM")
    finally:
        conn.close()
    return deleted
