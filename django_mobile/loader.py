from django.template.loaders.cached import Loader as DjangoCachedLoader
from django_mobile import get_flavour
from django_mobile.conf import settings
from django_mobile.compat import template_loader
from django.template.loaders.base import Loader as BaseLoader


def prepare_template_name(template_name):
    template_name = u'%s/%s' % (get_flavour(), template_name)
    if settings.FLAVOURS_TEMPLATE_PREFIX:
        template_name = settings.FLAVOURS_TEMPLATE_PREFIX + template_name
    return template_name


class Loader(BaseLoader):
    is_usable = True
    _template_source_loaders = None

    def get_contents(self, origin):
        return origin.loader.get_contents(origin)

    def get_template_sources(self, template_name):
        template_name = prepare_template_name(template_name)
        for loader in self.other_template_source_loaders:
            if hasattr(loader, 'get_template_sources'):
                try:
                    for result in loader.get_template_sources(template_name):
                        yield result
                except UnicodeDecodeError:
                    # The template dir name was a bytestring that wasn't valid UTF-8.
                    raise
                except ValueError:
                    # The joined path was located outside of this particular
                    # template_dir (it might be inside another one, so this isn't
                    # fatal).
                    pass

    @property
    def other_template_source_loaders(self):
        if not self._template_source_loaders:
            loaders = []
            for loader_name in settings.FLAVOURS_TEMPLATE_LOADERS:
                loader = template_loader(loader_name)
                if loader is not None:
                    loaders.append(loader)
            self._template_source_loaders = tuple(loaders)
        return self._template_source_loaders


class CachedLoader(DjangoCachedLoader):
    is_usable = True

    def cache_key(self, template_name, *args):
        key = super(CachedLoader, self).cache_key(template_name, *args)
        return '{0}:{1}'.format(get_flavour(), key)
