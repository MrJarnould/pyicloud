import json

import requests
from rich import inspect, pretty
from rich import print as rprint
from rich import print_json
from rich.console import Console
from rich.traceback import install

install(show_locals=True)
pretty.install()

console = Console()


def insp(arg):
    """Inspect an object with rich"""
    return inspect(arg, all=True, help=True)


def print_d(input_dict):
    """Print a dictionary with rich"""
    return print_json(data=input_dict)


URL = "https://api.appledb.dev/device/main.json"

# get request to url
response = requests.get(URL, timeout=30)

rprint(response.json())

# save response to file
with open("appledb.json", "w", encoding="utf-8") as f:
    json.dump(response.json(), f)
