# vim:fileencoding=utf-8
from django.template.engine import Engine


def template_loader(loader_name):
    return Engine.get_default().find_template_loader(loader_name)


def template_from_string(template_code):
    return Engine().from_string(template_code)


def get_engine():
    return Engine.get_default()
