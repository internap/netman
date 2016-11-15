import unittest

from flexmock import flexmock, flexmock_teardown
from hamcrest import assert_that, is_

from netman.adapters.switches.util import PageReader


class PageReaderTest(unittest.TestCase):

    def setUp(self):
        self.reader = PageReader(
            read_while="--More-- or (q)uit",
            and_press="m",
            unless_prompt="#")

        self.shell_mock = flexmock()

    def tearDown(self):
        flexmock_teardown()

    def test_reads_without_pagination(self):
        self.shell_mock.should_receive("do").with_args("command", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).once().ordered().and_return([
            "line1",
            "line2",
            "prompt#"
        ])

        result = self.reader.do(self.shell_mock, "command")

        assert_that(result, is_([
            "line1",
            "line2"
        ]))

    def test_reads_2_pages_and_removes_page_indicators_and_prompt(self):
        self.shell_mock.should_receive("do").with_args("command", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).once().ordered().and_return([
            "line1",
            "line2",
            "--More-- or (q)uit"
        ])

        self.shell_mock.should_receive("send_key").with_args("m", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).once().ordered().and_return([
            "line3",
            "line4",
            "--More-- or (q)uit"
        ])

        self.shell_mock.should_receive("send_key").with_args("m", wait_for=("--More-- or (q)uit", "#"), include_last_line=True).once().ordered().and_return([
            "line5",
            "line6",
            "prompt#"
        ])

        result = self.reader.do(self.shell_mock, "command")

        assert_that(result, is_([
            "line1",
            "line2",
            "line3",
            "line4",
            "line5",
            "line6"
        ]))
