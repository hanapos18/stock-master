# -*- coding: utf-8 -*-
"""
StockMaster 라이센스 모듈 (머신 바인딩)
POS 라이센스와 독립된 별도 라이센스 시스템.
하드웨어 fingerprint 기반으로 다른 PC에서 복사 사용을 방지합니다.
"""
import hashlib
import json
import os
import re
import subprocess
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

PRODUCT_PREFIX = "STK"
LICENSE_CACHE_FILE = "license_cache_stk.json"
SIGNATURE_SALT = "HANA_STOCKMASTER_2026_LICENSE_SIGN"
CHECKSUM_SALT = "STK_LIC_CHECKSUM_SALT_2026"
BETA_MACHINE_ID = "BETA0000BETA0000"

PERIOD_MAP = {
    1: "01M",
    3: "03M",
    6: "06M",
    12: "12M",
    0: "PERM",
}
PERIOD_LABELS = {
    1: "1 Month",
    3: "3 Months",
    6: "6 Months",
    12: "12 Months",
    0: "Permanent",
}
WARNING_DAYS = 30
CRITICAL_DAYS = 7


def get_machine_id() -> str:
    """Windows 하드웨어 fingerprint (MAC + BIOS UUID + 디스크 시리얼)."""
    parts = []
    parts.append(str(uuid.getnode()))
    try:
        result = subprocess.check_output(
            "wmic csproduct get uuid", shell=True, text=True,
            stderr=subprocess.DEVNULL, timeout=5,
        )
        lines = [ln.strip() for ln in result.strip().splitlines() if ln.strip() and ln.strip().upper() != "UUID"]
        if lines:
            parts.append(lines[0])
    except Exception:
        pass
    try:
        result = subprocess.check_output(
            "wmic diskdrive get serialnumber", shell=True, text=True,
            stderr=subprocess.DEVNULL, timeout=5,
        )
        lines = [ln.strip() for ln in result.strip().splitlines() if ln.strip() and ln.strip().upper() != "SERIALNUMBER"]
        if lines:
            parts.append(lines[0])
    except Exception:
        pass
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _get_cache_path() -> str:
    """라이센스 캐시 파일 경로."""
    import sys
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, LICENSE_CACHE_FILE)


def _generate_signature(data: Dict[str, Any]) -> str:
    """캐시 데이터 서명 생성 (변조 방지)."""
    sign_str = (
        f"{data.get('license_key', '')}|"
        f"{data.get('machine_id', '')}|"
        f"{data.get('period_months', 0)}|"
        f"{data.get('activated_at', '')}|"
        f"{SIGNATURE_SALT}"
    )
    return hashlib.sha256(sign_str.encode()).hexdigest()


def generate_license_key(machine_id: str, period_months: int = 0, seq: int = 1) -> str:
    """
    라이센스 키 생성 (딜러용).
    형식: STK-[머신ID앞8]-[기간코드][회차]-[체크섬6]
    seq: 발급 회차 (1=최초, 2=갱신1회, 3=갱신2회...)
    """
    period_code = PERIOD_MAP.get(period_months, "PERM")
    raw = f"{machine_id}|{period_months}|{seq}|{CHECKSUM_SALT}"
    checksum = hashlib.sha256(raw.encode()).hexdigest()[:6].upper()
    mid_short = machine_id[:8].upper()
    return f"{PRODUCT_PREFIX}-{mid_short}-{period_code}{seq}-{checksum}"


def validate_license_key(key: str, machine_id: str) -> Tuple[bool, int]:
    """
    라이센스 키 검증.
    Returns: (유효 여부, 기간 months — 0=영구, -1=실패)
    """
    key = key.strip().upper()
    pattern = re.compile(r"^STK-([A-Z0-9]{8})-(\w+?)(\d+)-([A-F0-9]{6})$")
    match = pattern.match(key)
    if not match:
        print("[STK 라이센스] 키 형식 불일치")
        return False, -1
    key_mid = match.group(1)
    period_code = match.group(2)
    seq = int(match.group(3))
    key_checksum = match.group(4)
    is_beta = key_mid == BETA_MACHINE_ID[:8].upper()
    check_mid = BETA_MACHINE_ID if is_beta else machine_id
    if not is_beta and key_mid != machine_id[:8].upper():
        print("[STK 라이센스] 머신 ID 불일치 - 이 PC에서 사용할 수 없는 키입니다")
        return False, -1
    reverse_period = {v: k for k, v in PERIOD_MAP.items()}
    period_months = reverse_period.get(period_code)
    if period_months is None:
        print(f"[STK 라이센스] 알 수 없는 기간 코드: {period_code}")
        return False, -1
    raw = f"{check_mid}|{period_months}|{seq}|{CHECKSUM_SALT}"
    expected_checksum = hashlib.sha256(raw.encode()).hexdigest()[:6].upper()
    if key_checksum != expected_checksum:
        print("[STK 라이센스] 체크섬 불일치")
        return False, -1
    tag = "BETA " if is_beta else ""
    print(f"[STK 라이센스] {tag}검증 성공! 기간: {PERIOD_LABELS.get(period_months, 'Unknown')}, 회차: {seq}")
    return True, period_months


def save_license_cache(license_key: str, machine_id: str, period_months: int, is_beta: bool = False) -> Tuple[bool, str]:
    """검증된 라이센스를 캐시에 저장.
    동일 키 재입력 시: 유효하면 유지, 만료됐으면 차단 (새 키 필요).
    """
    if is_beta:
        machine_id = BETA_MACHINE_ID
    existing = _load_raw_cache()
    if existing and existing.get("license_key", "").upper() == license_key.strip().upper():
        if period_months != 0:
            status, days = check_license_expiration(existing)
            if status == "expired":
                print(f"[STK 라이센스] 만료된 키 재활성화 차단: {license_key}")
                return False, "This license key has expired. A new key is required."
            if status in ("active", "warning", "critical", "permanent"):
                print(f"[STK 라이센스] 기존 활성 키 유지 (남은 {days}일)")
                return True, f"License already active ({days} days remaining)"
    now = datetime.now()
    if period_months == 0:
        expires_at = ""
    else:
        expires_at = (now + timedelta(days=30 * period_months)).strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "license_key": license_key,
        "machine_id": machine_id,
        "period_months": period_months,
        "period_label": PERIOD_LABELS.get(period_months, "Permanent"),
        "activated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "expires_at": expires_at,
    }
    data["signature"] = _generate_signature(data)
    try:
        cache_path = _get_cache_path()
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[STK 라이센스] 캐시 저장: {cache_path}")
        return True, "License activated successfully"
    except Exception as e:
        return False, f"Cache save failed: {e}"


def _load_raw_cache() -> Optional[Dict[str, Any]]:
    """서명/머신 검증 없이 캐시 파일만 로드 (재활성화 체크용)."""
    cache_path = _get_cache_path()
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_license_cache() -> Optional[Dict[str, Any]]:
    """캐시된 라이센스를 로드하고 서명을 검증."""
    cache_path = _get_cache_path()
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    stored_sig = data.pop("signature", "")
    expected_sig = _generate_signature(data)
    if stored_sig != expected_sig:
        print("[STK 라이센스] 캐시 서명 불일치 (변조 감지)")
        return None
    cached_mid = data.get("machine_id", "")
    is_beta = cached_mid == BETA_MACHINE_ID
    if not is_beta:
        current_mid = get_machine_id()
        if cached_mid != current_mid:
            print("[STK 라이센스] 머신 ID 불일치 (다른 PC에서 복사됨)")
            return None
    data["signature"] = stored_sig
    data["is_beta"] = is_beta
    return data


def check_license_expiration(cache: Dict[str, Any]) -> Tuple[str, int]:
    """
    라이센스 만료 상태 확인.
    Returns: (상태, 남은 일수)
    상태: 'permanent', 'active', 'warning', 'critical', 'expired'
    """
    period_months = cache.get("period_months", 0)
    if period_months == 0:
        return "permanent", 99999
    expires_at_str = cache.get("expires_at", "")
    if not expires_at_str:
        return "permanent", 99999
    try:
        expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return "expired", 0
    now = datetime.now()
    days_remaining = (expires_at - now).days
    if days_remaining < 0:
        return "expired", days_remaining
    if days_remaining <= CRITICAL_DAYS:
        return "critical", days_remaining
    if days_remaining <= WARNING_DAYS:
        return "warning", days_remaining
    return "active", days_remaining


def check_license() -> Tuple[bool, str, Dict[str, Any]]:
    """
    라이센스 전체 검증 (캐시 로드 + 만료 확인).
    Returns: (유효 여부, 메시지, 정보 dict)
    """
    cache = load_license_cache()
    if not cache:
        return False, "License not activated", {"status": "none"}
    status, days_remaining = check_license_expiration(cache)
    info = {
        **cache,
        "status": status,
        "days_remaining": days_remaining,
    }
    if status == "expired":
        return False, f"License expired {abs(days_remaining)} days ago. Please renew.", info
    if status == "critical":
        return True, f"License expires in {days_remaining} days! Renew soon.", info
    if status == "warning":
        return True, f"License valid ({days_remaining} days remaining)", info
    if status == "permanent":
        return True, "Permanent license active", info
    return True, f"License active ({days_remaining} days remaining)", info


def get_license_status() -> Dict[str, Any]:
    """라이센스 상태 조회 (라우트/템플릿용)."""
    cache = load_license_cache()
    if not cache:
        return {
            "activated": False,
            "status": "none",
            "machine_id": get_machine_id(),
            "message": "License not activated",
        }
    status, days_remaining = check_license_expiration(cache)
    is_valid = status != "expired"
    return {
        "activated": is_valid,
        "license_key": cache.get("license_key", ""),
        "machine_id": cache.get("machine_id", ""),
        "period_months": cache.get("period_months", 0),
        "period_label": cache.get("period_label", "Permanent"),
        "activated_at": cache.get("activated_at", ""),
        "expires_at": cache.get("expires_at", ""),
        "status": status,
        "days_remaining": days_remaining,
        "message": _status_message(status, days_remaining),
    }


def delete_license_cache() -> bool:
    """라이센스 캐시 삭제."""
    cache_path = _get_cache_path()
    if os.path.exists(cache_path):
        os.remove(cache_path)
        return True
    return False


def _status_message(status: str, days_remaining: int) -> str:
    if status == "expired":
        return f"License expired {abs(days_remaining)} days ago"
    if status == "critical":
        return f"License expires in {days_remaining} days!"
    if status == "warning":
        return f"License valid ({days_remaining} days remaining)"
    if status == "permanent":
        return "Permanent license"
    if status == "none":
        return "License not activated"
    return f"License active ({days_remaining} days remaining)"
