import argparse
import json
import sys

from pathlib import Path

from .api import PyPandora


def main():
    parser = argparse.ArgumentParser(description='Submit a file.')
    parser.add_argument('--url', type=str, help='URL of the instance (defaults to https://pandora.circl.lu/).')
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--redis_up', action='store_true', help='Check if redis is up.')
    group.add_argument('-f', '--file', type=Path, help='Path to the file to submit.')
    group2 = parser.add_argument_group('getStatus')
    group2.add_argument('--task_id', help="The id of the task you'd like to get the status of")
    group2.add_argument('--seed', help="The seed of the task you'd like to get the status of")
    group2.add_argument('--all_workers', action='store_true', default=False, help="True if you want the status of every workers")
    group2.add_argument('--worker_name', help="The name of the worker you want to get the report of")
    group2.add_argument('--details', action='store_true', default=False, help="True if you want the details of the workers")
    args = parser.parse_args()

    if args.url:
        client = PyPandora(args.url)
    else:
        client = PyPandora()

    if not client.is_up:
        print(f'Unable to reach {client.root_url}. Is the server up?')
        sys.exit(1)
    if args.redis_up:
        response = client.redis_up()
    if args.all_workers or args.worker_name:
        response = client.worker_status(args.task_id, args.all_workers, args.details, args.seed, args.worker_name)
    elif args.task_id and args.seed:
        response = client.task_status(args.task_id, args.seed)
    elif args.file:
        response = client.submit_from_disk(args.file, seed_expire=3600)
    print(json.dumps(response, indent=2))
