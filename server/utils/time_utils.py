import datetime
import time

import pytz

"""
time.time() : (Uni) utc timestamp
time.gmtime(): time.struct_time  # UTC
time.localtime(): time.struct_time  # 서버 시간
time.mktime()  # use timezone
time.ctime(secs) == time.asctime(time.localtime(secs)) # use timezone
"""

UTC = pytz.UTC
KOR = pytz.timezone('Etc/GMT-9')


def utc_to_kor(dt):
    # UTC 시간을 KOR 기준으로 바꿔준다. tzinfo 는 제거한다.
    return UTC.localize(dt).astimezone(KOR).replace(tzinfo=None)


def kst_dt_now():
    utc_dt = datetime.datetime.utcnow()
    kst_dt = utc_to_kor(utc_dt)
    return kst_dt


def kst_today():
    dt = kst_dt_now()
    return dt.date()


def utc_to_kor_ts(dt):
    dt = utc_to_kor(dt)
    return time.mktime(dt.timetuple())


def kor_ts_to_utc(ts):
    return datetime.datetime.fromtimestamp(ts) \
        .replace(tzinfo=KOR) \
        .astimezone(UTC) \
        .replace(tzinfo=None)


def n_days_later(dt=None, n=None):
    if dt:
        return dt + datetime.timedelta(days=n)
    else:
        return kst_dt_now() + datetime.timedelta(days=n)


def n_hours_later(dt=None, n=None):
    if dt:
        return dt + datetime.timedelta(hours=n)
    else:
        return kst_dt_now() + datetime.timedelta(hours=n)


def n_sec_later(dt=None, n=None):
    if dt:
        return dt + datetime.timedelta(seconds=n)
    else:
        return kst_dt_now() + datetime.timedelta(seconds=n)


def in_n_days(dt, n, crt=None):
    """ crt - n(days) < dt < crt """
    if not crt:
        crt = kst_dt_now()
    return dt >= n_days_later(crt, -1 * n)


def refine_dt(dt, hour=False, minute=True, second=True):
    """ True : 해당 값 지워버림 """
    if hour:
        dt = dt.replace(hour=0)
    if minute:
        dt = dt.replace(minute=0)
    if second:
        dt = dt.replace(second=0, microsecond=0)
    return dt
