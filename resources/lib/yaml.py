# -*- coding: utf-8 -*-

from datetime import timedelta
from pathlib import Path, PosixPath, WindowsPath
from typing import Any

import yaml

from resources.lib.language import Language
from resources.lib.providers.getresult import GetResult


def language_representer(dumper: yaml.SafeDumper, value: Language) -> yaml.nodes.MappingNode:
    return dumper.represent_str("%s [%s:%s]" % (value.name, value.two_letter_code, value.three_letter_code))


def timedelta_representer(dumper: yaml.SafeDumper, value: timedelta) -> yaml.nodes.MappingNode:
    return dumper.represent_str(str(value))


def path_representer(dumper: yaml.SafeDumper, value: Path) -> yaml.nodes.MappingNode:
    return dumper.represent_str(str(value.resolve()))


def get_result_representer(dumper: yaml.SafeDumper, value: GetResult) -> yaml.nodes.MappingNode:
    value_class = value.__class__
    return dumper.represent_mapping("!python/object:%s.%s" % (value_class.__module__, value_class.__name__), {
        "provider_name": value.provider_name,
        "file_name": value.file_name,
        "is_forced": value.is_forced,
        "is_hearing_impaired": value.is_hearing_impaired,
        "content_length": len(value.content) if value.content else -1,
    })


yaml.representer.Representer.add_representer(Language, language_representer)
yaml.representer.Representer.add_representer(Path, path_representer)
yaml.representer.Representer.add_representer(WindowsPath, path_representer)
yaml.representer.Representer.add_representer(PosixPath, path_representer)
yaml.representer.Representer.add_representer(timedelta, timedelta_representer)
yaml.representer.Representer.add_representer(GetResult, get_result_representer)


def to_yaml(data: Any) -> str:
    return yaml.dump(data, width=120)


def from_yaml(text: str):
    return yaml.load(text)
