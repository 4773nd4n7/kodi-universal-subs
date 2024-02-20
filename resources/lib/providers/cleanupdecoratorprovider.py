# -*- coding: utf-8 -*-

import copy
import os
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List

from resources.lib.common.settings import Settings
from resources.lib.formats.subtitleformat import Subtitle, SubtitleLine
from resources.lib.formats.subtitleformatsregistry import \
    SubtitleFormatsRegistry
from resources.lib.providers.decoratorprovider import DecoratorProvider
from resources.lib.providers.getrequest import GetRequest
from resources.lib.providers.getresult import GetResult
from resources.lib.providers.provider import Provider
from resources.lib.utils.httpclient import HttpClient, HttpRequest


class CleanupDecoratorProvider(DecoratorProvider):

    def __init__(self, source: Provider, settings: Settings):
        super().__init__(source)
        self._settings = settings
        self._formats_registry = SubtitleFormatsRegistry()
        self._clean_up_rules: Dict[str, List[str]] = None

    @property
    def name(self) -> str:
        return "Cleanup"

    def __ensure_clean_up_rules_file_exists(self) -> Path:
        sections_rules_path = self._settings.addon_user_path.joinpath("clean_up_rules.ini")
        if not sections_rules_path.exists() or \
            (self._settings.clean_up_rules_update_interval and self._settings.clean_up_rules_update_url
             and self._settings.clean_up_rules_update_interval.total_seconds() < (time.time() - os.path.getmtime(sections_rules_path))):
            try:
                http_response = HttpClient().exchange(HttpRequest(self._settings.clean_up_rules_update_url))
                http_response.write_into(sections_rules_path)
            except:
                self._logger.error("Error updating cleanup rules from \"%s\"" % self.update_url, exc_info=True)
        if not sections_rules_path.exists():
            try:
                reference_sections_rules_path = self._settings.addon_path.joinpath("resources", "clean_up_rules.ini")
                shutil.copyfile(reference_sections_rules_path, sections_rules_path)
            except:
                self._logger.error("Error copying cleanup rules from \"%s\"" % self.update_url, exc_info=True)
                return None
        return sections_rules_path

    def __ensure_clean_up_rules_loaded(self) -> None:
        if self._clean_up_rules:
            return  # cleanup rules already loaded
        self._clean_up_rules: Dict[str, List[str]] = {}
        clean_up_rules_path = self.__ensure_clean_up_rules_file_exists()
        if not clean_up_rules_path:
            return  # was unable to download nor copy the cleanup rules
        section_rules: List[str] = None
        with open(clean_up_rules_path, "rt", encoding='utf-8') as file:
            for file_line in file:
                file_line = re.sub("#.*", "", file_line).strip()  # strip comments
                if not file_line:
                    continue
                section_name_match = re.match(r"\[([^\]]+)\]", file_line)
                if section_name_match:
                    section_name = section_name_match[1].lower()
                    section_rules = self._clean_up_rules.get(section_name, None)
                    if section_rules is None:
                        self._clean_up_rules[section_name] = section_rules = []
                elif section_rules is not None:
                    section_rules.append(file_line)

    def apply_clean_up_rules(self, text: str, clean_up_rules: List[str]) -> str:
        for clean_up_rule in clean_up_rules:
            try:
                text = re.sub(clean_up_rule, '', text, flags=re.IGNORECASE | re.DOTALL)
            except Exception as e:
                self._logger.debug("Error processing cleanup rule %s: '", clean_up_rule, str(e))
        return text

    def clean_up_subtitle(self, subtitle: Subtitle, ads_rules: List[str], hi_marks_rules: List[str]) -> GetResult:
        for _line in reversed(subtitle.lines):
            line: SubtitleLine = _line
            line_text: str = line.text or ""
            line_text = re.sub(' {2,}', ' ', line_text).strip()
            if ads_rules:
                line_text = self.apply_clean_up_rules(line_text, ads_rules)
            if hi_marks_rules:
                line_text = self.apply_clean_up_rules(line_text, hi_marks_rules)
            line_text = re.sub(' {2,}', ' ', line_text).strip()
            if not line_text:
                subtitle.lines.remove(line)
            else:
                line.text = line_text

    def _transform_get_results(self, request: GetRequest, source_request: GetRequest, source_results: List[GetResult]) -> List[GetResult]:
        self.__ensure_clean_up_rules_loaded()
        ads_rules: List[str] = self._clean_up_rules.get("ads", []) + self._clean_up_rules.get("ads_" + request.language.three_letter_code, []) \
            if self._settings.clean_up_ads else None
        hi_marks_rules: List[str] = self._clean_up_rules.get(
            "ccmarks", []) if self._settings.clean_up_hi_markers else None
        cleanedup_results: List[GetResult] = []
        for source_result in source_results:
            try:
                format, subtitle = self._formats_registry.parse(source_result.file_name, source_result.content)
                self.clean_up_subtitle(subtitle, ads_rules, hi_marks_rules)
                cleanedup_result = copy.deepcopy(source_result)
                cleanedup_result.provider_name = self.name + "|" + source_result.provider_name
                cleanedup_result.content = format.render(subtitle)
                cleanedup_results.append(cleanedup_result)
            except:
                self._logger.error("Error cleaning up result \"%s\"" % source_result.file_name, exc_info=True)
                cleanedup_results.append(source_result)
        return cleanedup_results
