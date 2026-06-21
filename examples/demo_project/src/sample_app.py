def greeting(name: str) -> str:
    clean_name = name.strip() or 'there'
    return f'Hello, {clean_name}!'
