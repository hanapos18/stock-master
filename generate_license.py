#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StockMaster 라이센스 키 생성 도구 (딜러용)

사용법:
  python generate_license.py                        # 대화형 모드
  python generate_license.py <machine_id>           # 영구 키 (회차1)
  python generate_license.py <machine_id> 12        # 12개월 키 (회차1)
  python generate_license.py <machine_id> 12 2      # 12개월 키 (회차2 = 갱신)
  python generate_license.py --self                 # 현재 PC용 영구 키
  python generate_license.py --beta                 # 베타 12개월 (회차1)
  python generate_license.py --beta 12 2            # 베타 12개월 (회차2 = 갱신)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.license import (
    get_machine_id,
    generate_license_key,
    validate_license_key,
    PERIOD_MAP,
    PERIOD_LABELS,
    BETA_MACHINE_ID,
)


def main():
    print("=" * 55)
    print("  Hana StockMaster - License Key Generator (Dealer)")
    print("=" * 55)

    if len(sys.argv) >= 2 and sys.argv[1] == "--beta":
        period = int(sys.argv[2]) if len(sys.argv) >= 3 else 12
        seq = int(sys.argv[3]) if len(sys.argv) >= 4 else 1
        if period not in PERIOD_MAP:
            print(f"  지원하지 않는 기간: {period}  (지원: {list(PERIOD_MAP.keys())})")
            return
        key = generate_license_key(BETA_MACHINE_ID, period, seq)
        print(f"\n  [BETA] 유니버설 키 - 어느 PC에서든 사용 가능")
        print(f"  기간: {PERIOD_LABELS.get(period, 'Permanent')}")
        print(f"  회차: {seq}")
        print(f"\n  License Key: {key}\n")
        _verify(key, BETA_MACHINE_ID)
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "--self":
        machine_id = get_machine_id()
        period = int(sys.argv[2]) if len(sys.argv) >= 3 else 0
        seq = int(sys.argv[3]) if len(sys.argv) >= 4 else 1
        print(f"\n  현재 PC Machine ID: {machine_id}")
        key = generate_license_key(machine_id, period, seq)
        print(f"  기간: {PERIOD_LABELS.get(period, 'Permanent')}")
        print(f"  회차: {seq}")
        print(f"\n  License Key: {key}\n")
        _verify(key, machine_id)
        return

    if len(sys.argv) >= 2 and sys.argv[1] not in ("--self", "--beta"):
        machine_id = sys.argv[1].strip()
        period = int(sys.argv[2]) if len(sys.argv) >= 3 else 0
        seq = int(sys.argv[3]) if len(sys.argv) >= 4 else 1
    else:
        print(f"\n  현재 PC Machine ID (참고): {get_machine_id()}")
        machine_id = input("\n  고객 Machine ID 입력: ").strip()
        if not machine_id:
            print("  Machine ID가 필요합니다.")
            return
        print("\n  기간 선택:")
        for months, label in sorted(PERIOD_LABELS.items()):
            code = PERIOD_MAP[months]
            print(f"    {months:>2} = {label} ({code})")
        period_input = input("\n  기간 (개월, 0=영구) [0]: ").strip()
        period = int(period_input) if period_input else 0
        seq_input = input("  발급 회차 (1=최초, 2=갱신...) [1]: ").strip()
        seq = int(seq_input) if seq_input else 1

    if period not in PERIOD_MAP:
        print(f"  지원하지 않는 기간입니다: {period}")
        print(f"  지원 기간: {list(PERIOD_MAP.keys())}")
        return

    key = generate_license_key(machine_id, period, seq)
    print(f"\n  Machine ID : {machine_id}")
    print(f"  기간       : {PERIOD_LABELS.get(period, 'Unknown')}")
    print(f"  회차       : {seq}")
    print(f"  -------------------------------------------")
    print(f"  License Key: {key}")
    print(f"  -------------------------------------------\n")
    _verify(key, machine_id)


def _verify(key: str, machine_id: str):
    is_valid, period = validate_license_key(key, machine_id)
    if is_valid:
        print(f"  검증 결과: 유효 ({PERIOD_LABELS.get(period, 'Unknown')})")
    else:
        print(f"  검증 결과: 실패!")


if __name__ == "__main__":
    main()
