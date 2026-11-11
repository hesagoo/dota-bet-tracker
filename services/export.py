"""Экспорт истории ставок в CSV и Excel."""
import csv
from datetime import datetime

from core.calculator import bet_profit
from core.models import RESULT_LABELS, TYPE_LABELS, OP_LABELS

HEAD = ["Дата", "Тип", "Матч", "Турнир", "Сумма", "Коэффициент", "Результат", "Прибыль/убыток", "Комментарий"]


def _dec(v):
    return str(v).replace(".", ",")


def export_csv(path, bets, date_fmt="%d.%m.%Y"):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:       # utf-8-sig — чтобы Excel видел кириллицу
        w = csv.writer(f, delimiter=";")
        w.writerow(HEAD)
        for b in bets:
            w.writerow([b.placed_at.strftime(date_fmt + " %H:%M"), TYPE_LABELS.get(b.bet_type, b.bet_type), b.match,
                        b.tournament, _dec(b.stake), _dec(b.odds), RESULT_LABELS.get(b.result, b.result),
                        _dec(bet_profit(b)), b.comment])


def export_xlsx(path, bets, ops, date_fmt="%d.%m.%Y"):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    xl = date_fmt.replace("%d", "dd").replace("%m", "mm").replace("%Y", "yyyy") + " hh:mm"
    wb = Workbook()
    ws = wb.active
    ws.title = "Ставки"
    ws.append(HEAD)
    for b in bets:
        ws.append([b.placed_at, TYPE_LABELS.get(b.bet_type, b.bet_type), b.match, b.tournament, float(b.stake),
                   float(b.odds), RESULT_LABELS.get(b.result, b.result), float(bet_profit(b)), b.comment])
    for r in range(2, ws.max_row + 1):
        ws.cell(r, 1).number_format = xl
        for c in (5, 8):
            ws.cell(r, c).number_format = "#,##0.00"
        ws.cell(r, 6).number_format = "0.00"
    sheets = [(ws, [19, 12, 36, 24, 12, 13, 13, 16, 30])]
    if ops is not None:
        w2 = wb.create_sheet("Операции банка")
        w2.append(["Дата", "Операция", "Сумма", "Комментарий"])
        for o in sorted(ops, key=lambda o: o.ts):
            w2.append([o.ts, OP_LABELS.get(o.kind, o.kind), float(o.amount), o.comment])
        for r in range(2, w2.max_row + 1):
            w2.cell(r, 1).number_format = xl
            w2.cell(r, 3).number_format = "#,##0.00"
        sheets.append((w2, [19, 28, 14, 40]))
    for sh, widths in sheets:
        for i, wd in enumerate(widths, 1):
            sh.column_dimensions[get_column_letter(i)].width = wd
        for c in sh[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="3B4A8C")
            c.alignment = Alignment(horizontal="center")
        sh.freeze_panes = "A2"
    wb.save(path)
