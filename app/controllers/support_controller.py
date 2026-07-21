"""Support Request System — 소모품 주문/A/S 접수 비즈니스 로직"""
import json
from typing import Dict, List, Optional
from app.db import fetch_one, fetch_all, insert, execute


# ─── 카탈로그 관리 ───────────────────────────────────────────

def get_catalog_list(active_only: bool = False) -> List[Dict]:
    """소모품 카탈로그 목록을 조회합니다."""
    if active_only:
        return fetch_all(
            "SELECT * FROM stk_support_catalog WHERE is_active = 1 ORDER BY sort_order, id"
        )
    return fetch_all("SELECT * FROM stk_support_catalog ORDER BY sort_order, id")


def get_catalog_item(item_id: int) -> Optional[Dict]:
    return fetch_one("SELECT * FROM stk_support_catalog WHERE id = %s", (item_id,))


def create_catalog_item(data: Dict) -> int:
    return insert(
        "INSERT INTO stk_support_catalog (category, name, description, unit_price, image_url, sort_order) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (data["category"], data["name"], data.get("description", ""),
         data.get("unit_price", 0), data.get("image_url", ""), data.get("sort_order", 0)),
    )


def update_catalog_item(item_id: int, data: Dict) -> int:
    return execute(
        "UPDATE stk_support_catalog SET category=%s, name=%s, description=%s, "
        "unit_price=%s, image_url=%s, sort_order=%s, is_active=%s WHERE id=%s",
        (data["category"], data["name"], data.get("description", ""),
         data.get("unit_price", 0), data.get("image_url", ""),
         data.get("sort_order", 0), data.get("is_active", 1), item_id),
    )


def delete_catalog_item(item_id: int) -> int:
    return execute("DELETE FROM stk_support_catalog WHERE id = %s", (item_id,))


# ─── 유튜브 동영상 관리 ──────────────────────────────────────

def get_video_list(active_only: bool = False) -> List[Dict]:
    """자가해결 유튜브 동영상 목록을 조회합니다."""
    if active_only:
        return fetch_all(
            "SELECT * FROM stk_support_videos WHERE is_active = 1 ORDER BY sort_order, id"
        )
    return fetch_all("SELECT * FROM stk_support_videos ORDER BY sort_order, id")


def get_video_item(video_id: int) -> Optional[Dict]:
    return fetch_one("SELECT * FROM stk_support_videos WHERE id = %s", (video_id,))


def create_video(data: Dict) -> int:
    return insert(
        "INSERT INTO stk_support_videos (category, title, youtube_url, description, sort_order) "
        "VALUES (%s, %s, %s, %s, %s)",
        (data["category"], data["title"], data["youtube_url"],
         data.get("description", ""), data.get("sort_order", 0)),
    )


def update_video(video_id: int, data: Dict) -> int:
    return execute(
        "UPDATE stk_support_videos SET category=%s, title=%s, youtube_url=%s, "
        "description=%s, sort_order=%s, is_active=%s WHERE id=%s",
        (data["category"], data["title"], data["youtube_url"],
         data.get("description", ""), data.get("sort_order", 0),
         data.get("is_active", 1), video_id),
    )


def delete_video(video_id: int) -> int:
    return execute("DELETE FROM stk_support_videos WHERE id = %s", (video_id,))


# ─── 접수 관리 ───────────────────────────────────────────────

def create_request(data: Dict) -> int:
    """POS에서 접수된 요청을 저장합니다."""
    items_json = json.dumps(data.get("items", []), ensure_ascii=False)
    return insert(
        "INSERT INTO stk_support_requests "
        "(store_code, store_name, terminal_id, request_type, items, memo) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (data["store_code"], data.get("store_name", ""),
         data.get("terminal_id", ""), data["request_type"],
         items_json, data.get("memo", "")),
    )


def get_requests(status: Optional[str] = None, store_code: Optional[str] = None,
                 request_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """접수 목록을 조회합니다."""
    sql = "SELECT * FROM stk_support_requests WHERE 1=1"
    params = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if store_code:
        sql += " AND store_code = %s"
        params.append(store_code)
    if request_type:
        sql += " AND request_type = %s"
        params.append(request_type)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    rows = fetch_all(sql, tuple(params))
    for row in rows:
        if row.get("items") and isinstance(row["items"], str):
            try:
                row["items"] = json.loads(row["items"])
            except (json.JSONDecodeError, TypeError):
                pass
    return rows


def get_request_detail(request_id: int) -> Optional[Dict]:
    row = fetch_one("SELECT * FROM stk_support_requests WHERE id = %s", (request_id,))
    if row and row.get("items") and isinstance(row["items"], str):
        try:
            row["items"] = json.loads(row["items"])
        except (json.JSONDecodeError, TypeError):
            pass
    return row


def update_request_status(request_id: int, status: str, admin_note: str = "",
                          resolution_data: Optional[Dict] = None) -> int:
    """접수 상태 변경 + 해결 기록 저장 (DONE 시 육하원칙)."""
    if status == "DONE" and resolution_data:
        from datetime import datetime
        return execute(
            "UPDATE stk_support_requests SET status=%s, admin_note=%s, "
            "resolved_by=%s, resolved_at=%s, resolution_location=%s, "
            "root_cause=%s, resolution=%s, parts_used=%s WHERE id=%s",
            (status, admin_note,
             resolution_data.get("resolved_by", ""),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             resolution_data.get("resolution_location", ""),
             resolution_data.get("root_cause", ""),
             resolution_data.get("resolution", ""),
             resolution_data.get("parts_used", ""),
             request_id),
        )
    return execute(
        "UPDATE stk_support_requests SET status=%s, admin_note=%s WHERE id=%s",
        (status, admin_note, request_id),
    )


def get_pending_count() -> int:
    """PENDING 상태 접수 건수를 반환합니다."""
    row = fetch_one("SELECT COUNT(*) AS cnt FROM stk_support_requests WHERE status = 'PENDING'")
    return row["cnt"] if row else 0
