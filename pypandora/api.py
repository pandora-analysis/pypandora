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
        files = {'file': (filename, file_in_memory)}
        url = urljoin(self.root_url, 'submit')
        r = self.session.post(url, files=files, params={'validity': self._expire_in_sec(seed_expire)})
        to_return = r.json()
        to_return['link'] = urljoin(self.root_url, to_return['link'])
        return to_return
