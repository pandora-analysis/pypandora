# Python client and module for Pandora

## Installation

```bash
pip install pypandora
```

## Usage

### Command line

You can use the `pandora` command to submit a file:

```bash
$ poetry run pandora -h
usage: pandora [-h] [--url URL] [--redis_up | -f FILE] [--task_id TASK_ID]
               [--seed SEED] [--all_workers] [--worker_name WORKER_NAME]
               [--details]

Submit a file.

options:
  -h, --help            show this help message and exit
  --url URL             URL of the instance (defaults to
                        https://pandora.circl.lu/).
  --redis_up            Check if redis is up.
  -f FILE, --file FILE  Path to the file to submit.

getStatus:
  --task_id TASK_ID     The id of the task you'd like to get the status of
  --seed SEED           The seed of the task you'd like to get the status of
  --all_workers         True if you want the status of every workers
  --worker_name WORKER_NAME
                        The name of the worker you want to get the report of
  --details             True if you want the details of the workers
```

### Library

See [API Reference](https://pypandora.readthedocs.io/en/latest/api_reference.html)
