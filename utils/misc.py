import os
from typing import Mapping


def split_string_chunks(string: str, chunk_size: int = 2000) -> list[str]:
    return [string[i:i + chunk_size] for i in range(0, len(string), chunk_size)]


def get_list_of_files_in_base(basedir: str) -> list[str]:
    list_of_files: list[str] = os.listdir(basedir)
    all_files: list[str] = []
    # Iterate over all the entries
    for entry in list_of_files:
        # Create full path
        full_path = os.path.join(basedir, entry)
        # If entry is a directory then get the list of files in this directory
        if os.path.isdir(full_path):
            all_files += get_list_of_files_in_base(full_path)
        all_files.append(full_path)

    return all_files


def is_module(file_or_directory: str) -> bool:
    if os.path.isdir(file_or_directory):
        return "__init__.py" in os.listdir(file_or_directory)
    else:
        return (
                file_or_directory.endswith(".py")
                and not ("__init__.py" in os.listdir(os.path.join(file_or_directory, os.pardir)))
        )


def get_python_modules(basedir: str) -> list[str]:
    return [
        os.path.splitext(module)[0].replace("/", ".").replace("\\", ".")
        for module in get_list_of_files_in_base(basedir)
        if is_module(module)
    ]


class FrozenDict(Mapping):
    def __init__(self, *args, **kwargs):
        self._d = dict(*args, **kwargs)
        self._hash = None

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def __getitem__(self, key):
        return self._d[key]

    def __hash__(self):
        # It would have been simpler and maybe more obvious to
        # use hash(tuple(sorted(self._d.iteritems()))) from this discussion
        # so far, but this solution is O(n). I don't know what kind of
        # n we are going to run into, but sometimes it's hard to resist the
        # urge to optimize when it will gain improved algorithmic performance.
        if self._hash is None:
            hash_ = 0
            for pair in self.items():
                hash_ ^= hash(pair)
            self._hash = hash_
        return self._hash


__all__: list[str] = [
    "split_string_chunks",
    "FrozenDict",
    "is_module",
    "get_list_of_files_in_base",
    "get_python_modules",
]
