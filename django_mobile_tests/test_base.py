# vim:fileencoding=utf-8
import pytest
import threading

from django.contrib.sessions.models import Session
from django.template import TemplateDoesNotExist
from django.test import Client, TestCase
from django.utils import six
from unittest.mock import MagicMock, Mock, patch
from .urls import index as index_view

from django.test import RequestFactory

from django_mobile import get_flavour, set_flavour
from django_mobile.conf import settings
from django_mobile.compat import get_engine
from django_mobile.middleware import MobileDetectionMiddleware, SetFlavourMiddleware


def _reset():
    """
    Reset the thread local.
    """
    import django_mobile
    del django_mobile._local
    django_mobile._local = threading.local()


def str_p3_response(string):
    """
    Since response.content is a binary string in python 3,
    we decode it to make it comparable to str objects
    ( python 2 compatibility )
    """
    if six.PY3:
        return string.decode('ASCII')
    return string


class BaseTestCase(TestCase):
    def setUp(self):
        _reset()

    def tearDown(self):
        _reset()


class BasicFunctionTests(BaseTestCase):
    def test_set_flavour(self):
        set_flavour('full')
        self.assertEqual(get_flavour(), 'full')
        set_flavour('mobile')
        self.assertEqual(get_flavour(), 'mobile')
        self.assertRaises(ValueError, set_flavour, 'spam')

    def test_set_flavour_with_cookie_backend(self):
        original_FLAVOURS_STORAGE_BACKEND = settings.FLAVOURS_STORAGE_BACKEND
        try:
            settings.FLAVOURS_STORAGE_BACKEND = 'cookie'
            response = self.client.get('/')
            self.assertFalse(settings.FLAVOURS_COOKIE_KEY in response.cookies)
            response = self.client.get('/', {
                settings.FLAVOURS_GET_PARAMETER: 'mobile',
            })
            self.assertTrue(settings.FLAVOURS_COOKIE_KEY in response.cookies)
            self.assertTrue(response.cookies[settings.FLAVOURS_COOKIE_KEY], u'mobile')
            print(response.content)
            self.assertContains(response, 'Mobile!')
        finally:
            settings.FLAVOURS_STORAGE_BACKEND = original_FLAVOURS_STORAGE_BACKEND

    def test_set_flavour_with_session_backend(self):
        original_FLAVOURS_STORAGE_BACKEND = settings.FLAVOURS_STORAGE_BACKEND
        try:
            settings.FLAVOURS_STORAGE_BACKEND = 'session'
            request = Mock()
            request.session = {}
            set_flavour('mobile', request=request)
            self.assertEqual(request.session, {})
            set_flavour('mobile', request=request, permanent=True)
            self.assertEqual(request.session, {
                settings.FLAVOURS_SESSION_KEY: u'mobile'
            })
            self.assertEqual(get_flavour(request), 'mobile')

            response = self.client.get('/')
            self.assertFalse('sessionid' in response.cookies)
            response = self.client.get('/', {
                settings.FLAVOURS_GET_PARAMETER: 'mobile',
            })
            self.assertTrue('sessionid' in response.cookies)
            sessionid = response.cookies['sessionid'].value
            session = Session.objects.get(session_key=sessionid)
            session_data = session.get_decoded()
            self.assertTrue(settings.FLAVOURS_SESSION_KEY in session_data)
            self.assertEqual(session_data[settings.FLAVOURS_SESSION_KEY], 'mobile')
        finally:
            settings.FLAVOURS_STORAGE_BACKEND = original_FLAVOURS_STORAGE_BACKEND


class TemplateLoaderTests(BaseTestCase):
    def test_get_template_on_filesystem(self):
        from django.template.loaders import app_directories, filesystem

        @patch.object(app_directories.Loader, 'get_template_sources')
        @patch.object(filesystem.Loader, 'get_template_sources')
        def testing(filesystem_loader, app_directories_loader):
            from django_mobile.loader import Loader
            loader = Loader(get_engine())

            set_flavour('mobile')
            with pytest.raises(TemplateDoesNotExist):
                loader.get_template('base.html')
            filesystem_loader.assert_called_with('mobile/base.html')
            app_directories_loader.assert_called_with('mobile/base.html')

            set_flavour('full')
            with pytest.raises(TemplateDoesNotExist):
                loader.get_template('base.html')
            filesystem_loader.assert_called_with('full/base.html')
            app_directories_loader.assert_called_with('full/base.html')

        testing()

    def test_get_template_sources_on_filesystem(self):
        from django.template.loaders import app_directories, filesystem

        @patch.object(app_directories.Loader, 'get_template_sources')
        @patch.object(filesystem.Loader, 'get_template_sources')
        def testing(filesystem_loader, app_directories_loader):
            filesystem_loader.return_value = iter(["fs/base.html"])
            app_directories_loader.return_value = iter(["apps/base.html"])

            from django_mobile.loader import Loader
            loader = Loader(get_engine())

            set_flavour('mobile')
            list(loader.get_template_sources('base.html'))
            filesystem_loader.assert_called_once_with('mobile/base.html')
            app_directories_loader.assert_called_once_with('mobile/base.html')

            filesystem_loader.reset_mock()
            app_directories_loader.reset_mock()

            set_flavour('full')
            list(loader.get_template_sources('base.html'))
            filesystem_loader.assert_called_once_with('full/base.html')
            app_directories_loader.assert_called_once_with('full/base.html')

        testing()

    def test_functional(self):
        from django.template.loader import render_to_string
        set_flavour('full')
        result = render_to_string('index.html')
        result = result.strip()
        self.assertEqual(result, 'Hello .')
        # simulate RequestContext
        response = self.client.get('/')
        result = response.content
        if six.PY3:
            result = result.decode('utf-8')
        result = result.strip()
        self.assertEqual(result, 'Hello full.')
        set_flavour('mobile')
        result = render_to_string('index.html')
        result = result.strip()
        self.assertEqual(result, 'Mobile!')

    def test_loading_unexisting_template(self):
        from django.template.loader import render_to_string
        try:
            render_to_string('not_existent.html')
        except TemplateDoesNotExist as e:
            self.assertEqual(e.args, ('not_existent.html',))
        else:
            self.fail('TemplateDoesNotExist was not raised.')


class MobileDetectionMiddlewareTests(BaseTestCase):
    @patch('django_mobile.middleware.set_flavour')
    def test_mobile_browser_agent(self, set_flavour):
        request = Mock()
        request.META = {
            'HTTP_USER_AGENT': 'My Mobile Browser',
        }
        middleware = MobileDetectionMiddleware()
        middleware.process_request(request)
        self.assertEqual(set_flavour.call_args, (('mobile', request), {}))

    @patch('django_mobile.middleware.set_flavour')
    def test_desktop_browser_agent(self, set_flavour):
        request = Mock()
        request.META = {
            'HTTP_USER_AGENT': 'My Desktop Browser',
        }
        middleware = MobileDetectionMiddleware()
        middleware.process_request(request)
        self.assertEqual(set_flavour.call_args, (('full', request), {}))


class SetFlavourMiddlewareTests(BaseTestCase):
    def test_set_default_flavour(self):
        request = Mock()
        request.META = MagicMock()
        request.GET = {}
        middleware = SetFlavourMiddleware()
        middleware.process_request(request)
        # default flavour is set
        self.assertEqual(get_flavour(), 'full')

    @patch('django_mobile.middleware.set_flavour')
    def test_set_flavour_through_get_parameter(self, set_flavour):
        request = Mock()
        request.META = MagicMock()
        request.GET = {'flavour': 'mobile'}
        middleware = SetFlavourMiddleware()
        middleware.process_request(request)
        self.assertEqual(set_flavour.call_args,
                         (('mobile', request), {'permanent': True}))


class RealAgentNameTests(BaseTestCase):
    def assertFullFlavour(self, agent):
        client = Client(HTTP_USER_AGENT=agent)
        response = client.get('/')
        if str_p3_response(response.content.strip()) != 'Hello full.':
            self.fail(u'Agent is matched as mobile: %s' % agent)

    def assertMobileFlavour(self, agent):
        client = Client(HTTP_USER_AGENT=agent)
        response = client.get('/')
        if str_p3_response(response.content.strip()) != 'Mobile!':
            self.fail(u'Agent is not matched as mobile: %s' % agent)

    def test_ipad(self):
        self.assertFullFlavour(
            u'Mozilla/5.0 (iPad; U; CPU OS 3_2 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko)'
            u' Version/4.0.4 Mobile/7B334b Safari/531.21.10')

    def test_iphone(self):
        self.assertMobileFlavour(
            u'Mozilla/5.0 (iPhone; U; CPU like Mac OS X; en) AppleWebKit/420+ (KHTML, like Gecko)'
            u' Version/3.0 Mobile/1A543a Safari/419.3')

    def test_motorola_xoom(self):
        self.assertFullFlavour(
            u'Mozilla/5.0 (Linux; U; Android 3.0; en-us; Xoom Build/HRI39) AppleWebKit/534.13 (KHTML, like Gecko)'
            u' Version/4.0 Safari/534.13')

    def test_opera_mobile_on_android(self):
        """
        Regression test of issue #9
        """
        self.assertMobileFlavour(
            u'Opera/9.80 (Android 2.3.3; Linux; Opera Mobi/ADR-1111101157; U; en) Presto/2.9.201 Version/11.50')


class RegressionTests(BaseTestCase):
    def setUp(self):
        self.desktop = self.client
        # wap triggers mobile behaviour
        self.mobile = Client(HTTP_USER_AGENT='wap')
        self.request_factory = RequestFactory()

    def get_desktop(self, path):
        request = self.request_factory.get(path)
        return index_view(request)

    def test_multiple_browser_access(self):
        """
        Regression test of issue #2
        """
        response = self.get_desktop('/')
        self.assertEqual(str_p3_response(response.content.strip()), 'Hello full.')

        response = self.mobile.get('/')
        self.assertEqual(str_p3_response(response.content.strip()), 'Mobile!')

        response = self.desktop.get('/')
        self.assertEqual(str_p3_response(response.content.strip()), 'Hello full.')

        response = self.mobile.get('/')
        self.assertEqual(str_p3_response(response.content.strip()), 'Mobile!')

    def test_cache_page_decorator(self):
        response = self.mobile.get('/cached/')
        self.assertEqual(str_p3_response(response.content.strip()), 'Mobile!')

        response = self.desktop.get('/cached/')
        self.assertEqual(str_p3_response(response.content.strip()), 'Hello full.')

        response = self.mobile.get('/cached/')
        self.assertEqual(str_p3_response(response.content.strip()), 'Mobile!')

        response = self.desktop.get('/cached/')
        self.assertEqual(str_p3_response(response.content.strip()), 'Hello full.')
