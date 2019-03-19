import toml
import os


def load_conf(path=os.path.dirname(os.path.abspath(__file__))+"/config/default.toml"):
    with open(path) as f:
        conf_file = toml.load(f)
    return conf_file
