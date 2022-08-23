#!/usr/bin/env python3

import pkg_resources

from datetime import datetime, timedelta, date
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Any, Union
from urllib.parse import urljoin, urlparse

import requests


class PyPandoraError(Exception):
    pass


class AuthError(PyPandoraError):
    pass


class PyPandora():

    def __init__(self, root_url: str="https://pandora.circl.lu/", useragent: Optional[str]=None):
        '''Query a specific instance.

        :param root_url: URL of the instance to query.
        '''
        self.root_url = root_url

        if not urlparse(self.root_url).scheme:
            self.root_url = 'http://' + self.root_url
        if not self.root_url.endswith('/'):
            self.root_url += '/'
        self.session = requests.session()
        self.session.headers['user-agent'] = useragent if useragent else f'PyPandora / {pkg_resources.get_distribution("pypandora").version}'
        self.apikey: Optional[str] = None

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
               seed_expire: Optional[Union[datetime, timedelta, int]]=None,
               password: Optional[str]=None) -> Dict[str, Any]:
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
        params: Dict[str, Optional[Union[int, str]]] = {'validity': self._expire_in_sec(seed_expire)}
        if password:
            params['password'] = password
        r = self.session.post(url, files=files, params=params)
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

    def get_apikey(self, username: str, password: str) -> Dict[str, str]:
        '''Get the API key for the given user.'''
        to_post = {'username': username, 'password': password}
        r = self.session.get(urljoin(self.root_url, str(Path('api', 'get_token'))), params=to_post)
        return r.json()

    def init_apikey(self, username: Optional[str]=None, password: Optional[str]=None, apikey: Optional[str]=None):
        '''Init the API key for the current session. All the requests against pandora after this call will be authenticated.'''
        if apikey:
            self.apikey = apikey
        elif username and password:
            t = self.get_apikey(username, password)
            if 'authkey' in t:
                self.apikey = t['authkey']
        else:
            raise AuthError('Username and password required')
        if self.apikey:
            self.session.headers['Authorization'] = self.apikey
        else:
            raise AuthError('Unable to initialize API key')

    def _make_stats_path(self, url_path: Path, interval: str,
                         year: Optional[int]=None, month: Optional[int]=None,
                         week: Optional[int]=None, day: Optional[int]=None,
                         full_date: Optional[Union[date, datetime]]=None) -> Path:
        if interval not in ['year', 'month', 'week', 'day']:
            raise PyPandoraError('Invalid interval')
        if full_date:
            year = full_date.year
            month = full_date.month
            day = full_date.day
            # FIXME Starting in python 3.9, we can do full_date.isocalendar().week
            week = full_date.isocalendar()[1]
        url_path /= interval
        if interval == 'year' and year:
            url_path /= str(year)
        elif interval == 'month' and month:
            url_path /= str(month)
            if year:
                url_path /= str(year)
        elif interval == 'week' and week:
            url_path /= str(week)
            if year:
                url_path /= str(year)
        elif interval == 'day' and day:
            url_path /= str(day)
            if month:
                url_path /= str(month)
                if year:
                    url_path /= str(year)
        return url_path

    def get_stats(self, interval: str='year', year: Optional[int]=None,
                  month: Optional[int]=None, week: Optional[int]=None,
                  day: Optional[int]=None, full_date: Optional[Union[date, datetime]]=None):
        '''[Admin only] Gets an overview of what was submitted on the platform'''
        url_path = self._make_stats_path(Path('api', 'stats'), interval,
                                         year, month, week, day, full_date)
        url = urljoin(self.root_url, str(url_path))
        r = self.session.get(url)
        return r.json()

    def get_submit_stats(self, interval: str='year', year: Optional[int]=None,
                         month: Optional[int]=None, week: Optional[int]=None,
                         day: Optional[int]=None, full_date: Optional[Union[date, datetime]]=None):
        '''[Admin only] Get the number of submissions on a specific interval'''
        url_path = self._make_stats_path(Path('api', 'stats', 'submit'), interval,
                                         year, month, week, day, full_date)
        url = urljoin(self.root_url, str(url_path))
        r = self.session.get(url)
        return r.json()

    def search(self, query: str, limit_days: int=3):
        '''[Admin only] Search a hash or a filename in the tasks'''
        url_path = Path('api', 'search', query)
        if limit_days:
            url_path /= str(limit_days)
        url = urljoin(self.root_url, str(url_path))
        r = self.session.get(url)
        return r.json()
