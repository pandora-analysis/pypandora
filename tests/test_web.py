#!/usr/bin/env python3

import unittest

from pypandora import PyPandora


class TestBasic(unittest.TestCase):

    def setUp(self):
        self.client = PyPandora(root_url="http://127.0.0.1:6100")

    def test_up(self):
        self.assertTrue(self.client.is_up)
        self.assertTrue(self.client.redis_up())
