"""ESC/POS 영수증 프린터 서비스 (IP Socket)"""
import socket
from typing import Dict, List, Optional, Tuple


# ── ESC/POS 명령어 상수 ──
ESC = b'\x1b'
GS = b'\x1d'
INIT = b'\x1b\x40'                  # 프린터 초기화
NORMAL = b'\x1b\x21\x00'            # 일반 글꼴
BOLD_ON = b'\x1b\x45\x01'           # 볼드 ON
BOLD_OFF = b'\x1b\x45\x00'          # 볼드 OFF
DOUBLE_HEIGHT = b'\x1b\x21\x10'     # 세로 2배
DOUBLE_WIDTH = b'\x1b\x21\x20'      # 가로 2배
DOUBLE_WH = b'\x1b\x21\x30'         # 가로+세로 2배
ALIGN_LEFT = b'\x1b\x61\x00'        # 왼쪽 정렬
ALIGN_CENTER = b'\x1b\x61\x01'      # 중앙 정렬
ALIGN_RIGHT = b'\x1b\x61\x02'       # 오른쪽 정렬
CUT_PAPER = b'\x1d\x56\x00'         # 용지 커팅
LF = b'\x0a'                        # 줄바꿈


class ReceiptPrinter:
    """ESC/POS IP 소켓 영수증 프린터"""

    def __init__(self, ip: str, port: int = 9100,
                 width: int = 40, encoding: str = "euc-kr"):
        self.ip = ip
        self.port = port
        self.width = width
        self.encoding = encoding
        self.buffer: bytearray = bytearray()

    # ── 버퍼 관리 ──

    def reset(self) -> "ReceiptPrinter":
        """버퍼를 초기화합니다."""
        self.buffer = bytearray(INIT)
        return self

    def _add(self, data: bytes) -> None:
        """바이트 데이터를 버퍼에 추가합니다."""
        self.buffer.extend(data)

    def _encode(self, text: str) -> bytes:
        """텍스트를 프린터 인코딩으로 변환합니다."""
        try:
            return text.encode(self.encoding)
        except UnicodeEncodeError:
            return text.encode("utf-8", errors="replace")

    # ── 텍스트 포맷 ──

    def text(self, content: str) -> "ReceiptPrinter":
        """일반 텍스트를 출력합니다."""
        self._add(self._encode(content))
        return self

    def line(self, content: str = "") -> "ReceiptPrinter":
        """한 줄을 출력합니다."""
        self._add(self._encode(content))
        self._add(LF)
        return self

    def newline(self, count: int = 1) -> "ReceiptPrinter":
        """빈 줄을 추가합니다."""
        for _ in range(count):
            self._add(LF)
        return self

    # ── 정렬 ──

    def left(self) -> "ReceiptPrinter":
        """왼쪽 정렬로 설정합니다."""
        self._add(ALIGN_LEFT)
        return self

    def center(self) -> "ReceiptPrinter":
        """중앙 정렬로 설정합니다."""
        self._add(ALIGN_CENTER)
        return self

    def right(self) -> "ReceiptPrinter":
        """오른쪽 정렬로 설정합니다."""
        self._add(ALIGN_RIGHT)
        return self

    # ── 스타일 ──

    def bold_on(self) -> "ReceiptPrinter":
        """볼드를 켭니다."""
        self._add(BOLD_ON)
        return self

    def bold_off(self) -> "ReceiptPrinter":
        """볼드를 끕니다."""
        self._add(BOLD_OFF)
        return self

    def normal(self) -> "ReceiptPrinter":
        """일반 글꼴로 설정합니다."""
        self._add(NORMAL)
        return self

    def double_size(self) -> "ReceiptPrinter":
        """가로+세로 2배 크기로 설정합니다."""
        self._add(DOUBLE_WH)
        return self

    def double_height(self) -> "ReceiptPrinter":
        """세로 2배 크기로 설정합니다."""
        self._add(DOUBLE_HEIGHT)
        return self

    # ── 라인 유틸리티 ──

    def separator(self, char: str = "-") -> "ReceiptPrinter":
        """구분선을 출력합니다."""
        self._add(self._encode(char * self.width))
        self._add(LF)
        return self

    def double_separator(self) -> "ReceiptPrinter":
        """이중 구분선을 출력합니다."""
        return self.separator("=")

    def pair_line(self, label: str, value: str) -> "ReceiptPrinter":
        """라벨:값 한 줄을 출력합니다 (왼쪽 라벨, 오른쪽 값)."""
        space = self.width - self._display_width(label) - self._display_width(value)
        if space < 1:
            space = 1
        self._add(ALIGN_LEFT)
        self._add(self._encode(label + " " * space + value))
        self._add(LF)
        return self

    def columns(self, cols: List[Tuple[str, int, str]]) -> "ReceiptPrinter":
        """다중 컬럼 한 줄을 출력합니다.
        cols: [(text, width, align)] align = 'L','R','C'
        """
        self._add(ALIGN_LEFT)
        line_str = ""
        for text, col_width, align in cols:
            disp_w = self._display_width(text)
            if disp_w > col_width:
                text = self._truncate(text, col_width)
                disp_w = self._display_width(text)
            padding = col_width - disp_w
            if padding < 0:
                padding = 0
            if align == "R":
                line_str += " " * padding + text
            elif align == "C":
                left_pad = padding // 2
                right_pad = padding - left_pad
                line_str += " " * left_pad + text + " " * right_pad
            else:
                line_str += text + " " * padding
        self._add(self._encode(line_str))
        self._add(LF)
        return self

    # ── 마무리 ──

    def cut(self) -> "ReceiptPrinter":
        """용지를 커팅합니다."""
        self.newline(4)
        self._add(CUT_PAPER)
        return self

    # ── 전송 ──

    def send(self) -> Tuple[bool, str]:
        """TCP 소켓으로 프린터에 전송합니다."""
        if not self.ip:
            return False, "Printer IP not configured"
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.ip, self.port))
            sock.sendall(bytes(self.buffer))
            sock.close()
            print(f"영수증 전송 완료: {self.ip}:{self.port} ({len(self.buffer)} bytes)")
            return True, "OK"
        except socket.timeout:
            return False, f"Connection timeout: {self.ip}:{self.port}"
        except ConnectionRefusedError:
            return False, f"Connection refused: {self.ip}:{self.port}"
        except Exception as e:
            return False, f"Print error: {str(e)}"

    def get_text_preview(self) -> str:
        """디버깅용 텍스트 미리보기를 반환합니다 (ESC 명령 제거)."""
        raw = bytes(self.buffer)
        text_parts = []
        i = 0
        while i < len(raw):
            b = raw[i]
            if b == 0x1b:
                if i + 1 < len(raw):
                    cmd = raw[i + 1]
                    if cmd == 0x40:
                        i += 2
                    elif cmd == 0x21:
                        i += 3
                    elif cmd == 0x45:
                        i += 3
                    elif cmd == 0x61:
                        i += 3
                    else:
                        i += 2
                else:
                    i += 1
            elif b == 0x1d:
                if i + 2 < len(raw):
                    i += 3
                else:
                    i += 1
            elif b == 0x0a:
                text_parts.append("\n")
                i += 1
            else:
                try:
                    chunk_end = i
                    while chunk_end < len(raw) and raw[chunk_end] not in (0x1b, 0x1d, 0x0a):
                        chunk_end += 1
                    chunk = raw[i:chunk_end]
                    try:
                        text_parts.append(chunk.decode(self.encoding))
                    except UnicodeDecodeError:
                        text_parts.append(chunk.decode("utf-8", errors="replace"))
                    i = chunk_end
                except Exception:
                    i += 1
        return "".join(text_parts)

    # ── 내부 유틸리티 ──

    def _display_width(self, text: str) -> int:
        """한글/전각 문자를 고려한 표시 폭을 계산합니다."""
        width = 0
        for ch in text:
            if ord(ch) > 0x7F:
                width += 2
            else:
                width += 1
        return width

    def _truncate(self, text: str, max_width: int) -> str:
        """표시 폭 기준으로 텍스트를 잘라냅니다."""
        width = 0
        result = []
        for ch in text:
            char_w = 2 if ord(ch) > 0x7F else 1
            if width + char_w > max_width:
                break
            result.append(ch)
            width += char_w
        return "".join(result)


# ── 영수증 생성 헬퍼 ──

def create_printer() -> ReceiptPrinter:
    """config에서 프린터 인스턴스를 생성합니다."""
    import config
    return ReceiptPrinter(
        ip=config.PRINTER_IP,
        port=config.PRINTER_PORT,
        width=config.PRINTER_WIDTH,
        encoding=config.PRINTER_ENCODING,
    )


def format_number(value: float, decimals: int = 2) -> str:
    """숫자를 포맷합니다."""
    formatted = f"{value:,.{decimals}f}"
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


def build_sale_receipt(sale: Dict, store_name: str = "",
                       business_name: str = "") -> ReceiptPrinter:
    """판매 영수증 데이터를 빌드합니다."""
    printer = create_printer()
    w = printer.width
    is_narrow = w <= 20
    printer.reset()
    # 헤더
    printer.center().double_size()
    printer.line(business_name or "Hana StockMaster")
    printer.normal().center()
    if store_name:
        printer.line(store_name)
    printer.double_separator()
    # 판매 정보
    printer.left().normal()
    printer.pair_line("No:", sale["sale_number"])
    printer.pair_line("Date:", str(sale["sale_date"]))
    if sale.get("customer_name"):
        printer.pair_line("Customer:", sale["customer_name"])
    printer.separator()
    # 상품 목록
    if is_narrow:
        _build_items_narrow(printer, sale["line_items"])
    else:
        _build_items_wide(printer, sale["line_items"])
    printer.separator()
    # 합계
    printer.bold_on()
    printer.pair_line("TOTAL:", format_number(float(sale["total_amount"])))
    printer.bold_off()
    printer.separator()
    # 푸터
    printer.newline(1)
    printer.center().normal()
    printer.line("Thank you!")
    printer.newline(1)
    printer.left()
    printer.cut()
    return printer


def _build_items_narrow(printer: ReceiptPrinter, line_items: List[Dict]) -> None:
    """20자 폭 좁은 영수증 상품 목록을 포맷합니다."""
    for item in line_items:
        name = item.get("product_name", item.get("product_code", ""))
        qty = format_number(float(item["quantity"]))
        price = format_number(float(item["unit_price"]))
        amount = format_number(float(item["amount"]))
        printer.line(printer._truncate(name, printer.width))
        printer.pair_line(f" {qty} x {price}", amount)


def _build_items_wide(printer: ReceiptPrinter, line_items: List[Dict]) -> None:
    """40자 폭 넓은 영수증 상품 목록을 포맷합니다."""
    w = printer.width
    col_qty = 6
    col_price = 10
    col_amt = 10
    col_name = w - col_qty - col_price - col_amt
    if col_name < 8:
        col_name = 8
    # 헤더
    printer.bold_on()
    printer.columns([
        ("Item", col_name, "L"),
        ("Qty", col_qty, "R"),
        ("Price", col_price, "R"),
        ("Amt", col_amt, "R"),
    ])
    printer.bold_off()
    # 아이템
    for item in line_items:
        name = item.get("product_name", item.get("product_code", ""))
        qty = format_number(float(item["quantity"]))
        price = format_number(float(item["unit_price"]))
        amount = format_number(float(item["amount"]))
        printer.columns([
            (name, col_name, "L"),
            (qty, col_qty, "R"),
            (price, col_price, "R"),
            (amount, col_amt, "R"),
        ])


def test_connection(ip: str = "", port: int = 9100) -> Tuple[bool, str]:
    """프린터 연결 테스트를 수행합니다."""
    import config
    target_ip = ip or config.PRINTER_IP
    target_port = port or config.PRINTER_PORT
    if not target_ip:
        return False, "Printer IP not configured"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((target_ip, target_port))
        sock.close()
        return True, f"Connected to {target_ip}:{target_port}"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"


def print_test_page() -> Tuple[bool, str]:
    """테스트 페이지를 인쇄합니다."""
    printer = create_printer()
    printer.reset()
    printer.center().double_size()
    printer.line("PRINTER TEST")
    printer.normal().center()
    printer.double_separator()
    printer.left()
    printer.line("Connection: OK")
    printer.pair_line("Width:", f"{printer.width} chars")
    printer.pair_line("Encoding:", printer.encoding)
    printer.separator()
    printer.center()
    printer.line("1234567890" * (printer.width // 10))
    if printer.width == 40:
        printer.line("----+----1----+----2----+----3----+----4")
    else:
        printer.line("----+----1----+----2")
    printer.separator()
    printer.line("Test OK!")
    printer.cut()
    return printer.send()
