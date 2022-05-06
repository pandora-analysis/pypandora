#!/usr/bin/env python3

from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Any, Union
from urllib.parse import urljoin, urlparse

import requests


class PyPandora():

    def __init__(self, root_url: str="https://pandora.circl.lu/"):
        '''Query a specific instance.

        :param root_url: URL of the instance to query.
        '''
        self.root_url = root_url

        if not urlparse(self.root_url).scheme:
            self.root_url = 'http://' + self.root_url
        if not self.root_url.endswith('/'):
            self.root_url += '/'
        self.session = requests.session()

    @property
    def is_up(self) -> bool:
        '''Test if the given instance is accessible'''
        r = self.session.head(self.root_url)
        return r.status_code == 200

    def redis_up(self) -> Dict:
        '''Check if redis is up and running'''
        r = self.session.get(urljoin(self.root_url, 'redis_up'))
        return r.json()

    def submit_from_disk(self, file_on_disk: Union[str, Path], /,
                         seed_expire: Optional[Union[datetime, timedelta, int]]=None) -> Dict[str, Any]:
        '''Submit a file from the disk.

        :param file_on_disk: The path to the file to upload.
        :param seed_expire: If not None, the response will contain a seed allowing to view the result of the analysis.
                            If the type is a `datetime`, the seed will expire at that time.
                            If the type is a `timedelta`, the seed will expire then the given time interval expires.
                            If the type is a `int`, the seed will expire after the value (in seconds) expires. 0 means the seed never expires.
        '''
        if not isinstance(file_on_disk, Path):
            file_on_disk = Path(file_on_disk)
        if not file_on_disk.exists():
            raise OSError(f'File {file_on_disk} not found.')
        filename = file_on_disk.name
        with file_on_disk.open('rb') as f:
            file_in_memory = BytesIO(f.read())
        return self.submit(file_in_memory, filename, seed_expire)

    def _expire_in_sec(self, seed_expire: Optional[Union[datetime, timedelta, int]]=None) -> Optional[int]:
        if isinstance(seed_expire, int) or seed_expire is None:
            return seed_expire
        if isinstance(seed_expire, timedelta):
            interval = seed_expire
        else:
            interval = seed_expire - datetime.now()
        if interval.total_seconds() <= 0:
            raise ValueError(f'Expiration date ({seed_expire}) is in the past. Now: {datetime.now()}')
        return int(interval.total_seconds())

    def submit(self, file_in_memory: BytesIO, filename: str, /,
               seed_expire: Optional[Union[datetime, timedelta, int]]=None) -> Dict[str, Any]:
        '''Submit a file from the disk.

        :param file_in_memory: Memory object of the file to submit.
        :param filename: The name of the file.
        :param seed_expire: If not None, the response will contain a seed allowing to view the result of the analysis.
                            If the type is a `datetime`, the seed will expire at that time.
                            If the type is a `timedelta`, the seed will expire then the given time interval expires.
                            If the type is a `int`, the seed will expire after the value (in seconds) expires. 0 means the seed never expires.
        '''
        files = {'file': (filename, file_in_memory)}
        url = urljoin(self.root_url, 'submit')
        r = self.session.post(url, files=files, params={'validity': self._expire_in_sec(seed_expire)})
        to_return = r.json()
        to_return['link'] = urljoin(self.root_url, to_return['link'])
        return to_return

    def task_status(self, task_id: str, seed: Optional[str]=None) -> Dict[str, Any]:
        '''Get the status of a task.

        :param task_id: The UUID of the task
        :param seed: The seed. The seed must be still valid at the time the query is made. It is optional if the session is authenticated.
        '''
        url = urljoin(self.root_url, 'task_status')
        r = self.session.get(url, params={'task_id': task_id, 'seed': seed})
        return r.json()

    def worker_status(self, task_id: str, all_workers: bool=False, details: bool=False, seed: Optional[str]=None, worker_name: Optional[str]=None) -> Dict[str, Any]:
        '''Get the status of a task.

        :param task_id: The UUID of the task
        :param seed: The seed. The seed must be still valid at the time the query is made. It is optional if the session is authenticated.
        :param all_workers: Show the status of every workers and the details at the same time
        :param worker_name: The name of the worker you want the status of. It is optional if you want every workers details
        :param details: The details from the wanted worker
        '''
        url = urljoin(self.root_url, 'worker_status')
        r = self.session.get(url, params={'task_id': task_id, 'seed': seed, 'all_workers': 1 if all_workers else 0, 'worker_name': worker_name, 'details': 1 if details else 0})
        return r.json()
