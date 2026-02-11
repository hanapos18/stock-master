"""첨부파일 관리 비즈니스 로직 (영수증/배송원장 사진)"""
import io
from typing import Dict, List, Optional
from werkzeug.datastructures import FileStorage
from app.db import fetch_one, fetch_all, insert, execute

MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 업로드 허용 최대 10MB (리사이징 전)
MAX_IMAGE_DIMENSION: int = 1920  # 긴 변 최대 1920px (FHD)
JPEG_QUALITY: int = 85  # JPEG 압축 품질 (85% = 텍스트 선명 유지)
ALLOWED_TYPES: set = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


def _resize_image(file_data: bytes, file_type: str) -> tuple:
    """이미지를 자동 리사이징합니다. (최대 1920px, JPEG 85%)
    Returns: (resized_data, final_type, original_size, final_size)
    """
    if file_type == "application/pdf":
        return file_data, file_type
    try:
        from PIL import Image, ExifTags
        img = Image.open(io.BytesIO(file_data))
        # EXIF 회전 정보 반영 (모바일 카메라 사진)
        try:
            img = _apply_exif_rotation(img)
        except Exception:
            pass
        original_size = len(file_data)
        width, height = img.size
        max_dim = MAX_IMAGE_DIMENSION
        needs_resize = width > max_dim or height > max_dim
        if needs_resize:
            if width > height:
                new_width = max_dim
                new_height = int(height * (max_dim / width))
            else:
                new_height = max_dim
                new_width = int(width * (max_dim / height))
            img = img.resize((new_width, new_height), Image.LANCZOS)
            print(f"  이미지 리사이징: {width}x{height} → {new_width}x{new_height}")
        # RGBA → RGB 변환 (JPEG 저장용)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        resized_data = output.getvalue()
        final_size = len(resized_data)
        print(f"  이미지 압축: {original_size:,} bytes → {final_size:,} bytes "
              f"({final_size/original_size*100:.0f}%)")
        return resized_data, "image/jpeg"
    except ImportError:
        print("  Pillow 미설치 - 리사이징 건너뜀")
        return file_data, file_type
    except Exception as e:
        print(f"  리사이징 실패 ({e}) - 원본 저장")
        return file_data, file_type


def _apply_exif_rotation(img):
    """EXIF 회전 태그에 따라 이미지를 회전합니다."""
    from PIL import ExifTags
    exif = img.getexif()
    if not exif:
        return img
    orientation_key = None
    for key, val in ExifTags.TAGS.items():
        if val == "Orientation":
            orientation_key = key
            break
    if orientation_key is None or orientation_key not in exif:
        return img
    orientation = exif[orientation_key]
    rotations = {3: 180, 6: 270, 8: 90}
    if orientation in rotations:
        img = img.rotate(rotations[orientation], expand=True)
    return img


def save_attachment(business_id: int, reference_type: str, reference_id: int,
                    file: FileStorage, user_id: Optional[int] = None,
                    memo: str = "") -> Optional[int]:
    """첨부파일을 DB에 저장합니다 (이미지는 자동 리사이징)."""
    if not file or not file.filename:
        return None
    file_data = file.read()
    original_size = len(file_data)
    file_type = file.content_type or "application/octet-stream"
    if original_size > MAX_UPLOAD_SIZE:
        print(f"첨부파일 크기 초과: {original_size:,} bytes (최대 {MAX_UPLOAD_SIZE:,})")
        return None
    if file_type not in ALLOWED_TYPES:
        print(f"허용되지 않는 파일 타입: {file_type}")
        return None
    # 이미지 자동 리사이징 (PDF 제외)
    if file_type.startswith("image/"):
        file_data, file_type = _resize_image(file_data, file_type)
    file_size = len(file_data)
    # 파일명을 .jpg로 변경 (리사이징된 경우)
    file_name = file.filename
    if file_type == "image/jpeg" and not file_name.lower().endswith((".jpg", ".jpeg")):
        file_name = file_name.rsplit(".", 1)[0] + ".jpg"
    attachment_id = insert(
        "INSERT INTO stk_attachments "
        "(business_id, reference_type, reference_id, file_name, file_type, "
        "file_size, file_data, memo, uploaded_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (business_id, reference_type, reference_id,
         file_name, file_type, file_size, file_data,
         memo, user_id),
    )
    print(f"첨부파일 저장 완료: {file_name} ({original_size:,} → {file_size:,} bytes) → ID {attachment_id}")
    return attachment_id


def load_attachments(reference_type: str, reference_id: int) -> List[Dict]:
    """특정 거래의 첨부파일 목록을 조회합니다 (file_data 제외)."""
    return fetch_all(
        "SELECT id, business_id, reference_type, reference_id, "
        "file_name, file_type, file_size, memo, uploaded_by, created_at "
        "FROM stk_attachments "
        "WHERE reference_type = %s AND reference_id = %s "
        "ORDER BY created_at",
        (reference_type, reference_id),
    )


def load_attachment_data(attachment_id: int) -> Optional[Dict]:
    """첨부파일 데이터를 포함하여 조회합니다."""
    return fetch_one(
        "SELECT id, business_id, reference_type, reference_id, "
        "file_name, file_type, file_size, file_data, memo, created_at "
        "FROM stk_attachments WHERE id = %s",
        (attachment_id,),
    )


def delete_attachment(attachment_id: int) -> bool:
    """첨부파일을 삭제합니다."""
    affected = execute(
        "DELETE FROM stk_attachments WHERE id = %s",
        (attachment_id,),
    )
    return affected > 0


def has_attachments(reference_type: str, reference_id: int) -> bool:
    """특정 거래에 첨부파일이 있는지 확인합니다."""
    row = fetch_one(
        "SELECT COUNT(*) AS cnt FROM stk_attachments "
        "WHERE reference_type = %s AND reference_id = %s",
        (reference_type, reference_id),
    )
    return row["cnt"] > 0 if row else False


def load_attachment_ids_for_references(reference_type: str,
                                       reference_ids: List[int]) -> Dict[int, bool]:
    """여러 거래에 대해 첨부파일 존재 여부를 일괄 조회합니다."""
    if not reference_ids:
        return {}
    placeholders = ",".join(["%s"] * len(reference_ids))
    rows = fetch_all(
        f"SELECT reference_id, COUNT(*) AS cnt FROM stk_attachments "
        f"WHERE reference_type = %s AND reference_id IN ({placeholders}) "
        f"GROUP BY reference_id",
        (reference_type, *reference_ids),
    )
    return {row["reference_id"]: row["cnt"] > 0 for row in rows}


def load_attachments_by_period(business_id: int, start_date: str = "",
                               end_date: str = "",
                               reference_type: str = "") -> List[Dict]:
    """기간별 첨부파일 목록을 조회합니다 (세무 앱 연동용, file_data 제외)."""
    sql = (
        "SELECT a.id, a.reference_type, a.reference_id, a.file_name, "
        "a.file_type, a.file_size, a.memo, a.created_at "
        "FROM stk_attachments a "
        "WHERE a.business_id = %s"
    )
    params: list = [business_id]
    if reference_type:
        sql += " AND a.reference_type = %s"
        params.append(reference_type)
    if start_date:
        sql += " AND a.created_at >= %s"
        params.append(start_date)
    if end_date:
        sql += " AND a.created_at <= %s"
        params.append(end_date + " 23:59:59")
    sql += " ORDER BY a.created_at DESC"
    return fetch_all(sql, tuple(params))
