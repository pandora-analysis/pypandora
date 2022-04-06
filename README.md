# Python client and module for Pandora

## Installation

```bash
pip install pypandora
```

## Usage

### Command line

You can use the `pandora` command to submit a file:

```bash
$ pandora -h
usage: pandora [-h] [--url URL] (--redis_up | -f FILE)

Submit a file.

optional arguments:
  -h, --help            show this help message and exit
  --url URL             URL of the instance (defaults to https://pandora.circl.lu/).
  --redis_up            Check if redis is up.
  -f FILE, --file FILE  Path to the file to submit.

```

### Library

See [API Reference](https://pypandora.readthedocs.io/en/latest/api_reference.html)
