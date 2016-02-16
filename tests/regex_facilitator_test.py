import unittest
from threading import Thread

from hamcrest import assert_that, is_

from netman import regex


class RegexFacilitatorTest(unittest.TestCase):

    def test_basic_regex(self):
        regex.match('^(\w+)\s(\w+)$', 'hello world')
        assert_that(regex[0], is_('hello'))
        assert_that(regex[1], is_('world'))

    def test_should_be_threadsafe(self):
        regex.match('^(\w+)\s(\w+)$', 'hello world')

        def match_single_word():
            regex.match('^(\w+)$', 'bonjour')
            assert_that(regex[0], is_('bonjour'))

        t = Thread(target=match_single_word)
        t.start()
        t.join()

        assert_that(regex[1], is_('world'))
