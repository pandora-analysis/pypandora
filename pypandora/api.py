#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timedelta, date
from importlib.metadata import version
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from urllib3.util import Retry
from requests.adapters import HTTPAdapter


class PyPandoraError(Exception):
    pass


class AuthError(PyPandoraError):
    pass


class PyPandora():

    def __init__(self, root_url: str="https://pandora.circl.lu/", useragent: str | None=None,
                 *, proxies: dict[str, str] | None=None):
        '''Query a specific instance.

        :param root_url: URL of the instance to query.
        :param useragent: The User Agent used by requests to run the HTTP requests against Pandora.
        :param proxies: The proxies to use to connect to Pandora - More details: https://requests.readthedocs.io/en/latest/user/advanced/#proxies
        '''
        self.root_url = root_url
        self.apikey: str | None = None

        if not urlparse(self.root_url).scheme:
            self.root_url = 'http://' + self.root_url
        if not self.root_url.endswith('/'):
            self.root_url += '/'
        self.session = requests.session()
        self.session.headers['user-agent'] = useragent if useragent else f'PyPandora / {version("pypandora")}'
        if proxies:
            self.session.proxies.update(proxies)
        retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('http://', HTTPAdapter(max_retries=retries))

    @property
    def is_up(self) -> bool:
        '''Test if the given instance is accessible'''
        try:
            r = self.session.head(self.root_url)
        except requests.exceptions.ConnectionError:
            return False
        return r.status_code == 200

    def redis_up(self) -> bool:
        '''Check if redis is up and running'''
        r = self.session.get(urljoin(self.root_url, 'redis_up'))
        return r.json()

    def submit_from_disk(self, file_on_disk: str | Path, /,
                         seed_expire: datetime | timedelta | int | None=None) -> dict[str, Any]:
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

    def _expire_in_sec(self, seed_expire: datetime | timedelta | int | None=None) -> int | None:
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
               seed_expire: datetime | timedelta | int | None=None,
               password: str | None=None) -> dict[str, Any]:
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
        params: dict[str, int | str | None] = {'validity': self._expire_in_sec(seed_expire)}
        if password:
            params['password'] = password
        r = self.session.post(url, files=files, params=params)
        to_return = r.json()
        if 'link' in to_return:
            # Otherwise, we have an error.
            to_return['link'] = urljoin(self.root_url, to_return['link'])
        return to_return

    def task_status(self, task_id: str, seed: str | None=None) -> dict[str, Any]:
        '''Get the status of a task.

        :param task_id: The UUID of the task
        :param seed: The seed. The seed must be still valid at the time the query is made. It is optional if the session is authenticated.
        '''
        url = urljoin(self.root_url, 'task_status')
        r = self.session.get(url, params={'task_id': task_id, 'seed': seed})
        return r.json()

    def worker_status(self, task_id: str, all_workers: bool=False, details: bool=False, seed: str | None=None, worker_name: str | None=None) -> dict[str, Any]:
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

    def get_apikey(self, username: str, password: str) -> dict[str, str]:
        '''Get the API key for the given user.'''
        to_post = {'username': username, 'password': password}
        r = self.session.get(urljoin(self.root_url, str(PurePosixPath('api', 'get_token'))), params=to_post)
        return r.json()

    def init_apikey(self, username: str | None=None, password: str | None=None, apikey: str | None=None) -> None:
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

    def _make_stats_path(self, url_path: PurePosixPath, interval: str,
                         year: int | None=None, month: int | None=None,
                         week: int | None=None, day: int | None=None,
                         full_date: date | datetime | None=None) -> PurePosixPath:
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

    def get_stats(self, interval: str='year', year: int | None=None,
                  month: int | None=None, week: int | None=None,
                  day: int | None=None, full_date: date | datetime | None=None) -> dict[str, Any]:
        '''[Admin only] Gets an overview of what was submitted on the platform'''
        url_path = self._make_stats_path(PurePosixPath('api', 'stats'), interval,
                                         year, month, week, day, full_date)
        url = urljoin(self.root_url, str(url_path))
        r = self.session.get(url)
        return r.json()

    def get_submit_stats(self, interval: str='year', year: int | None=None,
                         month: int | None=None, week: int | None=None,
                         day: int | None=None, full_date: date | datetime | None=None) -> dict[str, Any]:
        '''[Admin only] Get the number of submissions on a specific interval'''
        url_path = self._make_stats_path(PurePosixPath('api', 'stats', 'submit'), interval,
                                         year, month, week, day, full_date)
        url = urljoin(self.root_url, str(url_path))
        r = self.session.get(url)
        return r.json()

    def search(self, query: str, limit_days: int=3) -> dict[str, Any]:
        '''[Admin only] Search a hash or a filename in the tasks'''
        url_path = PurePosixPath('api', 'search', query)
        if limit_days:
            url_path /= str(limit_days)
        url = urljoin(self.root_url, str(url_path))
        r = self.session.get(url)
        return r.json()

    def workers_stats_day(self, year: int | str | None=None, month: int | str | None=None, day: int | str | None=None) -> dict[str, Any]:
        '''[Admin only] Get the workers stats for a specific day - defaults to today'''
        url_path = PurePosixPath('api', 'workers_stats', 'day')
        if day is not None:
            url_path /= str(day)
            if month is not None:
                url_path /= str(month)
                if year is not None:
                    url_path /= str(year)

        url = urljoin(self.root_url, str(url_path))
        r = self.session.get(url)
        return r.json()

    def workers_stats_week(self, year: int | str | None=None, week: int | str | None=None) -> dict[str, Any]:
        '''[Admin only] Get the workers stats for a specific week - defaults to this week'''
        url_path = PurePosixPath('api', 'workers_stats', 'week')
        if week is not None:
            url_path /= str(week)
            if year is not None:
                url_path /= str(year)

        url = urljoin(self.root_url, str(url_path))
        r = self.session.get(url)
        return r.json()

    def workers_stats_month(self, year: int | str | None=None, month: int | str | None=None) -> dict[str, Any]:
        '''[Admin only] Get the workers stats for a specific month - defaults to this month'''
        url_path = PurePosixPath('api', 'workers_stats', 'month')
        if month is not None:
            url_path /= str(month)
            if year is not None:
                url_path /= str(year)

        url = urljoin(self.root_url, str(url_path))
        r = self.session.get(url)
        return r.json()

    def workers_stats_year(self, year: int | str | None=None) -> dict[str, Any]:
        '''[Admin only] Get the workers stats for a specific year - defaults to this year'''
        url_path = PurePosixPath('api', 'workers_stats', 'year')
        if year is not None:
            url_path /= str(year)

        url = urljoin(self.root_url, str(url_path))
        r = self.session.get(url)
        return r.json()

    def get_enabled_workers(self) -> list[str]:
        '''Get all the enabled workers'''
        url_path = PurePosixPath('api', 'enabled_workers')
        url = urljoin(self.root_url, str(url_path))
        r = self.session.get(url)
        return r.json()
