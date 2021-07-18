import re

import requests
from lxml import etree
from lxml.etree import _Element
from requests import Response

from app import db
from functions import get_semester, get_units, get_values, get_year
from models import Classes, Collection, Teachers, Timetable


# @scheduler.task('cron', id='sync_tables', hour='*/12')

def sync_tables():
    db.drop_all()
    db.create_all()

    year: int = get_year()
    semester: int = get_semester()

    _v = get_values(year, semester)
    for degree in _v["degree"]:
        if degree in ["%"]:
            continue

        for department in _v["department"]:
            # drop 進修推廣處
            if department in ["", "51", "%"]:
                continue

            for unit in get_units(department):
                unit = unit.popitem()
                unit = unit[1]

                # drop 進修推廣處
                if unit in ["", "2600", "%"]:
                    continue

                for cls_year in list(range(7)):
                    add_local(year, semester, degree, department, unit, cls_year)

    for _ in ["Bc", "BN", "BO", "BP", "BQ"]:
        add_local(year, semester, "%", "XS", "XS00", 0, _)


def add_local(year, semester, degree, department, unit, cls_year, hid_crk="%"):
    url: str = "http://shcourse.utaipei.edu.tw/utaipei/ag_pro/ag203_1.jsp"
    headers: dict[str, str] = {
        "Host": "shcourse.utaipei.edu.tw",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    params: dict[str, str] = {
        "yms_yms": f"{year}#{semester}",
        "dgr_id": f"{degree}",
        "dpt_id": f"{department}",
        "unt_id": f"{unit}",
        "clyear": f"{cls_year}",
        "class_type": "",
        "sub_name": "",
        "teacher": "",
        "ls_year": f"{year}",
        "ls_sms": f"{semester}",
        "hid_crk": f"{hid_crk}",  # hidden value
        "ls_years": "0",  # hidden value
        "ls_smss": "0",  # hidden value
    }

    r: Response = requests.post(url, data=params, headers=headers)
    if r.status_code != 200:
        # return abort error...
        print(r.status_code, department, unit, cls_year)

    root: _Element = etree.HTML(r.text)

    error: list[_Element] = root.xpath('//body//script[@language]')
    if error:
        reg = re.findall(r'(?<=alert\(\").*(?=\"\))', error[0].text)

        print(reg[0], department, unit, cls_year)
        return

        # start parsing data from school to local
    head: str = root.xpath('//html//body//table//font[@color]')[0].text
    reg = re.findall(r'(?<=\(共)\d+', head)
    total: int = int(reg[0])

    class_table: list[_Element] = root.xpath(
        "//body//table[@id='list_table']//tr[not(@align='center')]")

    if total > 0:
        for row in class_table:
            _ = Collection(iter(row))
            c = Classes(_, degree, department, unit, cls_year)

            if Classes.query.filter_by(id=c.id).first() is not None:
                continue

            db.session.add(c)
            db.session.commit()

            teachers = []
            for teacher in _.teachers:
                t = Teachers(c.id, teacher)
                teachers.append(t)

            times = []
            for _time in _.times:
                if not _time['time']:
                    t = Timetable(c.id, _time['day'], "")
                    times.append(t)
                else:
                    for _item in _time['time']:
                        t = Timetable(c.id, _time['day'], _item)
                        times.append(t)

            db.session.add_all(teachers)
            db.session.add_all(times)
            db.session.commit()
