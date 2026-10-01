"""Strict numeric parsing shared by imports and business forms."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import numbers
import re


_GROUPED_INTEGER = re.compile(r"^[+-]?\d{1,3}([.,]\d{3})+$")
_PLAIN_INTEGER = re.compile(r"^[+-]?\d+$")
_DECIMAL = re.compile(r"^[+-]?(?:\d+(?:[.,]\d+)|[.,]\d+)$")


def _numeric_value(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (Decimal, numbers.Integral, numbers.Real)):
        try:
            numeric = Decimal(str(value))
            if not numeric.is_finite():
                raise ValueError(f"Giá trị số không hợp lệ: {value}")
            return numeric
        except (InvalidOperation, ValueError):
            raise ValueError(f"Giá trị số không hợp lệ: {value}")
    return None


def parse_number(value):
    """Parse an unambiguous number without guessing decimal separators."""
    numeric = _numeric_value(value)
    if numeric is not None:
        return numeric
    text = str(value or "").replace("\xa0", "").replace(" ", "").strip()
    if not text:
        raise ValueError("Giá trị số bị trống")
    if _PLAIN_INTEGER.fullmatch(text):
        return Decimal(text)
    if re.fullmatch(r"[+-]?0[.,]\d+", text):
        separator = "." if "." in text else ","
        return Decimal(text.replace(separator, "."))
    if _GROUPED_INTEGER.fullmatch(text) and text.count(".") + text.count(",") >= 2:
        separators = set(re.sub(r"^[+-]?\d{1,3}", "", text)[::4])
        if len(separators) == 1:
            return Decimal(text.replace(next(iter(separators)), ""))
    if _DECIMAL.fullmatch(text):
        separator = "." if "." in text else ","
        fraction = text.rsplit(separator, 1)[1]
        if text.count(".") + text.count(",") == 1 and len(fraction) != 3:
            return Decimal(text.replace(separator, "."))
    raise ValueError(f"Số không rõ định dạng: {value}")


def parse_decimal_strict(value):
    return parse_number(value)


def parse_money_vnd(value):
    """Parse VND where a three-digit separator denotes thousands."""
    numeric = _numeric_value(value)
    if numeric is not None:
        return numeric.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    text = str(value or "").replace("\xa0", "").replace(" ", "").strip()
    if not text:
        raise ValueError("Số tiền bị trống")
    if _PLAIN_INTEGER.fullmatch(text):
        return Decimal(text)
    if _GROUPED_INTEGER.fullmatch(text):
        separators = set(re.sub(r"^[+-]?\d{1,3}", "", text)[::4])
        if len(separators) == 1:
            return Decimal(text.replace(next(iter(separators)), ""))
    if _DECIMAL.fullmatch(text):
        separator = "." if "." in text else ","
        return Decimal(text.replace(separator, ".")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    raise ValueError(f"Số tiền không hợp lệ: {value}")


def parse_decimal(value, default=Decimal("0")):
    """Backward-compatible tolerant parser for legacy callers."""
    try:
        return parse_money_vnd(value)
    except (InvalidOperation, ValueError, TypeError):
        try:
            text = str(value or "").replace("\xa0", "").replace(" ", "")
            if "," in text and "." in text:
                if text.rfind(",") > text.rfind("."):
                    text = text.replace(".", "").replace(",", ".")
                else:
                    text = text.replace(",", "")
            numeric = Decimal(text)
            return numeric if numeric.is_finite() else default
        except (InvalidOperation, ValueError, TypeError):
            return default


def parse_get_int(value, *, min_value=1, max_value=2_147_483_647):
    """Đọc tham số GET nguyên dương một cách an toàn; giá trị xấu -> None.

    ``str.isdigit()`` chấp nhận cả chữ số Unicode như ``²`` (int() sẽ lỗi), còn
    ``nam=0``/``nam=99999`` làm ``date()`` hoặc truy vấn năm bị lỗi 500. Hàm này
    chỉ nhận chữ số ASCII và ép vào khoảng [min_value, max_value].
    """
    text = str(value if value is not None else "").strip()
    if not text or not (text.isascii() and text.isdigit()):
        return None
    # Bound the conversion before int(): Python rejects several thousand digits.
    significant = text.lstrip("0") or "0"
    if len(significant) > len(str(max_value)):
        return None
    number = int(significant)
    if number < min_value or number > max_value:
        return None
    return number
