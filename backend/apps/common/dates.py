WEEKDAYS_ZH = ('星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日')


def weekday_zh(value):
    return WEEKDAYS_ZH[value.weekday()] if value else None
