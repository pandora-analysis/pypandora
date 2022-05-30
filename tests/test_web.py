#!/usr/bin/env python3

import time
import unittest

from pypandora import PyPandora


class TestBasic(unittest.TestCase):

    def setUp(self):
        self.client = PyPandora(root_url="http://127.0.0.1:6100")

    def test_up(self):
        self.assertTrue(self.client.is_up)
        self.assertTrue(self.client.redis_up())

    def test_submit(self):
        response = self.client.submit_from_disk(__file__)
        self.assertTrue(response['success'], response)

    def test_status(self):
        response = self.client.submit_from_disk(__file__, seed_expire=3600)
        self.assertTrue(response['success'], response)
        i = 0
        while i < 30:
            status = self.client.task_status(response['taskId'], response['seed'])
            if status['status'] == 'CLEAN':
                break
            else:
                i += 1
                time.sleep(1)
        else:
            raise Exception(f'The task never finished: {status}.')
