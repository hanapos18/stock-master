"""엑셀 내보내기 서비스"""
from typing import List, Dict
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side


HEADER_FONT = Font(bold=True, size=11, color="FFFFFF")
HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center")
THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)


def generate_excel_report(title: str, headers: List[str], rows: List[List],
                          column_widths: List[int] = None) -> BytesIO:
    """엑셀 리포트를 생성하고 BytesIO 스트림으로 반환합니다."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title[:31]
    _write_title_row(sheet, title)
    _write_header_row(sheet, headers)
    _write_data_rows(sheet, rows, start_row=3)
    _set_column_widths(sheet, headers, column_widths)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def _write_title_row(sheet, title: str) -> None:
    """제목 행을 작성합니다."""
    sheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=1)
    cell = sheet.cell(row=1, column=1, value=title)
    cell.font = Font(bold=True, size=14)


def _write_header_row(sheet, headers: List[str]) -> None:
    """헤더 행을 작성합니다."""
    for col_idx, header in enumerate(headers, 1):
        cell = sheet.cell(row=2, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGNMENT
        cell.border = THIN_BORDER


def _write_data_rows(sheet, rows: List[List], start_row: int = 3) -> None:
    """데이터 행들을 작성합니다."""
    for row_idx, row_data in enumerate(rows, start_row):
        for col_idx, value in enumerate(row_data, 1):
            cell = sheet.cell(row=row_idx, column=col_idx, value=value)
            cell.border = THIN_BORDER
            if isinstance(value, (int, float)):
                cell.number_format = "#,##0.00"


def _set_column_widths(sheet, headers: List[str], widths: List[int] = None) -> None:
    """열 너비를 설정합니다."""
    for col_idx, header in enumerate(headers, 1):
        if widths and col_idx <= len(widths):
            width = widths[col_idx - 1]
        else:
            width = max(len(str(header)) + 4, 12)
        sheet.column_dimensions[chr(64 + col_idx) if col_idx <= 26 else "A"].width = width
