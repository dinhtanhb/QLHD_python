from decimal import Decimal

from django import template

register = template.Library()


@register.filter

def vn_number(value):
    """Định dạng số theo kiểu Việt Nam: 65000000 -> 65.000.000."""
    if value is None or value == "":
        return "0"
    try:
        number = Decimal(str(value))
    except Exception:
        return value

    if number == number.to_integral_value():
        return f"{int(number):,}".replace(",", ".")

    text = format(number, "f").rstrip("0").rstrip(".")
    integer, _, fraction = text.partition(".")
    integer = f"{int(integer):,}".replace(",", ".")
    return f"{integer},{fraction}"


@register.filter(name="intcomma")
def vn_intcomma(value):
    """Alias tương thích cho template cũ nhưng dùng dấu chấm Việt Nam."""
    return vn_number(value)
