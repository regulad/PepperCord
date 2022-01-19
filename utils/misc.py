def split_string_chunks(string: str, chunk_size: int = 2000) -> list[str]:
    return [string[i:i + chunk_size] for i in range(0, len(string), chunk_size)]
