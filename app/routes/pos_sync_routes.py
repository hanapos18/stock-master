"""POS 연동 API 라우트 — Webhook 수신 및 수동 동기화"""
from flask import Blueprint, request, jsonify, session
import config
from app.controllers import pos_sync_controller
from app.db import fetch_one

pos_sync_bp = Blueprint("pos_sync", __name__, url_prefix="/api/pos")


def _verify_api_key() -> bool:
    """API Key를 검증합니다 (일반 POS 또는 백원 POS)."""
    api_key = request.headers.get("X-API-Key", "")
    if not api_key:
        return False
    if api_key == config.POS_API_KEY:
        return True
    if api_key == config.BAEKWON_POS_API_KEY:
        return True
    return False


def _resolve_business(data: dict) -> dict:
    """요청 데이터에서 business 정보를 조회합니다."""
    business_id = data.get("business_id")
    if not business_id:
        pos_db_name = data.get("pos_db_name", config.POS_DB_NAME)
        biz = fetch_one(
            "SELECT id, type FROM stk_businesses WHERE pos_db_name = %s",
            (pos_db_name,),
        )
        if not biz:
            biz = fetch_one("SELECT id, type FROM stk_businesses ORDER BY id LIMIT 1")
        if biz:
            business_id = biz["id"]
            business_type = biz["type"]
        else:
            return {}
    else:
        biz = fetch_one("SELECT id, type FROM stk_businesses WHERE id = %s", (business_id,))
        business_type = biz["type"] if biz else "mart"
    store = fetch_one(
        "SELECT id FROM stk_stores WHERE business_id = %s AND is_active = 1 LIMIT 1",
        (business_id,),
    )
    store_id = store["id"] if store else None
    return {"business_id": business_id, "business_type": business_type, "store_id": store_id}


@pos_sync_bp.route("/webhook", methods=["POST"])
def webhook():
    """POS에서 호출하는 Webhook 엔드포인트.

    요청 JSON:
    {
        "type": "sale" | "stock_in" | "loss",
        "business_id": 1,           (선택)
        "pos_db_name": "order_sys", (선택, business_id 없을 시 사용)
        "items": [
            {"menu_code": "0101", "quantity": 2, "unit_cost": 1000, "reason": "..."}
        ]
    }
    """
    if not _verify_api_key():
        return jsonify({"success": False, "error": "Invalid API key"}), 401
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400
    sync_type = data.get("type", "")
    if not sync_type:
        return jsonify({"success": False, "error": "type required"}), 400
    # ── 백원 POS 타입 처리 (Firebird Bridge) ──────────────
    if sync_type in ("baekwon_sale", "baekwon_products"):
        if not config.BAEKWON_SYNC_ENABLED:
            return jsonify({"success": False, "error": "Baekwon sync disabled"}), 403
        return _handle_baekwon_webhook(sync_type, data)
    # ── 일반 POS 타입 처리 ──────────────────────────────
    items = data.get("items", [])
    if not items:
        return jsonify({"success": False, "error": "type and items required"}), 400
    biz = _resolve_business(data)
    if not biz.get("business_id") or not biz.get("store_id"):
        return jsonify({"success": False, "error": "Business/store not found"}), 404
    business_id = biz["business_id"]
    store_id = biz["store_id"]
    business_type = biz["business_type"]
    print(f"📡 POS Webhook 수신: type={sync_type}, items={len(items)}, biz={business_id}")
    if sync_type == "sale":
        result = pos_sync_controller.handle_sale(
            business_id, business_type, store_id, items,
        )
    elif sync_type == "stock_in":
        result = pos_sync_controller.handle_stock_in(
            business_id, store_id, items,
        )
    elif sync_type == "loss":
        result = pos_sync_controller.handle_loss(
            business_id, store_id, items,
        )
    else:
        return jsonify({"success": False, "error": f"Unknown type: {sync_type}"}), 400
    # 동기화 상세 로그 기록
    for item in items:
        menu_code = item.get("menu_code", "")
        quantity = float(item.get("quantity", 0))
        pos_record_id = int(item.get("pos_record_id", 0))
        status = "success" if result["processed"] > 0 else "skipped"
        pos_sync_controller.log_sync_detail(
            business_id, f"webhook_{sync_type}", pos_record_id,
            sync_type, menu_code, quantity, status,
        )
    return jsonify({"success": True, "result": result})


def _handle_baekwon_webhook(sync_type: str, data: dict):
    """백원 POS (Firebird Bridge) 데이터를 처리합니다."""
    biz = _resolve_business(data)
    if not biz.get("business_id"):
        # business_id가 없으면 기본 비즈니스 사용
        biz = _resolve_business({})
    if not biz.get("business_id") or not biz.get("store_id"):
        return jsonify({"success": False, "error": "Business/store not found"}), 404
    business_id = biz["business_id"]
    store_id = biz["store_id"]
    business_type = biz["business_type"]
    items = data.get("items", [])
    print(f"🔶 백원POS Webhook 수신: type={sync_type}, items={len(items)}, biz={business_id}")
    if sync_type == "baekwon_sale":
        result = pos_sync_controller.handle_baekwon_sale(
            business_id, business_type, store_id, data,
        )
        return jsonify({"success": True, "result": result})
    elif sync_type == "baekwon_products":
        result = pos_sync_controller.handle_baekwon_products(business_id, data)
        return jsonify({"success": True, "result": result})
    return jsonify({"success": False, "error": f"Unknown baekwon type: {sync_type}"}), 400


@pos_sync_bp.route("/sync", methods=["POST"])
def manual_sync():
    """수동 폴링 동기화 실행."""
    from app.routes.dashboard_routes import login_required as lr
    if "user" not in session:
        api_key = request.headers.get("X-API-Key", "")
        if api_key != config.POS_API_KEY or not api_key:
            return jsonify({"success": False}), 401
    business_id = None
    if "business" in session:
        business_id = session["business"]["id"]
    else:
        data = request.get_json(silent=True) or {}
        business_id = data.get("business_id")
    if not business_id:
        return jsonify({"success": False, "error": "business_id required"}), 400
    biz = fetch_one("SELECT id, type, pos_db_name FROM stk_businesses WHERE id = %s", (business_id,))
    if not biz:
        return jsonify({"success": False, "error": "Business not found"}), 404
    store = fetch_one(
        "SELECT id FROM stk_stores WHERE business_id = %s AND is_active = 1 LIMIT 1",
        (business_id,),
    )
    if not store:
        return jsonify({"success": False, "error": "Store not found"}), 404
    result = pos_sync_controller.run_full_sync(
        business_id, biz["type"], store["id"], biz.get("pos_db_name") or "",
    )
    return jsonify({"success": True, "result": result})


@pos_sync_bp.route("/status", methods=["GET"])
def sync_status():
    """동기화 상태 조회 (대시보드용)."""
    if "user" not in session:
        api_key = request.headers.get("X-API-Key", "")
        if api_key != config.POS_API_KEY or not api_key:
            return jsonify({"success": False}), 401
    business_id = request.args.get("business_id", type=int)
    if not business_id and "business" in session:
        business_id = session["business"]["id"]
    if not business_id:
        return jsonify({"success": False, "error": "business_id required"}), 400
    status = pos_sync_controller.load_sync_status(business_id)
    return jsonify({"success": True, "data": status})
