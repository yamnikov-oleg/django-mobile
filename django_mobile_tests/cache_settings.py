# vim:fileencoding=utf-8
from .settings import *


MIDDLEWARE = (
    'django.middleware.cache.UpdateCacheMiddleware',
) + MIDDLEWARE + (
    'django_mobile.cache.middleware.CacheFlavourMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',
)
