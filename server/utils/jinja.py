import datetime

from fastapi.templating import Jinja2Templates


def strf(dt: datetime.datetime, f: str) -> str:
    try:
        return dt.strftime(f)
    except:
        return str(dt)


def time_diff(dt1: datetime.datetime, dt2: datetime.datetime) -> int:
    try:
        return int((dt1 - dt2).total_seconds())
    except:
        return 0


def intcomma(v: int) -> str:
    return "{:,}".format(v)


def register(templates: Jinja2Templates):
    templates.env.filters["strf"] = strf
    templates.env.filters["time_diff"] = time_diff
    templates.env.filters["intcomma"] = intcomma
