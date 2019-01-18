import unittest

from netman.core.objects.exceptions import BadMplsIpState
from netman.core.validator import is_valid_mpls_state


class ValidatorsTest(unittest.TestCase):
    def test_is_valid_mpls_state(self):
        self.assertEqual(dict(state=True), is_valid_mpls_state('true'))
        self.assertEqual(dict(state=False), is_valid_mpls_state('false'))
        self.assertEqual(dict(state=True), is_valid_mpls_state(True))
        self.assertEqual(dict(state=False), is_valid_mpls_state(False))

    def test_is_valid_mpls_state_with_invalid_input(self):
        with self.assertRaises(BadMplsIpState) as expect:
            is_valid_mpls_state('30')

        self.assertIn('MPLS IP state is invalid', str(expect.exception))
