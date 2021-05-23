def dict_difference(x: dict, y: dict):
    diff = dict(set(y.items()) - set(x.items()))
    return diff
