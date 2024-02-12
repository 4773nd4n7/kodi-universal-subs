# -*- coding: utf-8 -*-

import re
from typing import Any, Dict

from xmltodict import parse

HTML_ENTITIES: Dict[str, str] = {
    "Aacute": "&#193;",
    "aacute": "&#225;",
    "Acirc": "&#194;",
    "acirc": "&#226;",
    "acute": "&#180;",
    "AElig": "&#198;",
    "aelig": "&#230;",
    "Agrave": "&#192;",
    "agrave": "&#224;",
    "alefsym": "&#8501;",
    "Alpha": "&#913;",
    "alpha": "&#945;",
    "amp": "&#38;",
    "and": "&#8743;",
    "ang": "&#8736;",
    "Aring": "&#197;",
    "aring": "&#229;",
    "asymp": "&#8776;",
    "Atilde": "&#195;",
    "atilde": "&#227;",
    "Auml": "&#196;",
    "auml": "&#228;",
    "Beta": "&#914;",
    "beta": "&#946;",
    "brvbar": "&#166;",
    "bull": "&#8226;",
    "cap": "&#8745;",
    "Ccedil": "&#199;",
    "ccedil": "&#231;",
    "cedil": "&#184;",
    "cent": "&#162;",
    "Chi": "&#935;",
    "chi": "&#967;",
    "clubs": "&#9827;",
    "cong": "&#8773;",
    "copy": "&#169;",
    "crarr": "&#8629;",
    "cup": "&#8746;",
    "curren": "&#164;",
    "darr": "&#8595;",
    "dArr": "&#8659;",
    "deg": "&#176;",
    "Delta": "&#916;",
    "delta": "&#948;",
    "diams": "&#9830;",
    "divide": "&#247;",
    "Eacute": "&#201;",
    "eacute": "&#233;",
    "Ecirc": "&#202;",
    "ecirc": "&#234;",
    "Egrave": "&#200;",
    "egrave": "&#232;",
    "empty": "&#8709;",
    "Epsilon": "&#917;",
    "epsilon": "&#949;",
    "equiv": "&#8801;",
    "Eta": "&#919;",
    "eta": "&#951;",
    "ETH": "&#208;",
    "eth": "&#240;",
    "Euml": "&#203;",
    "euml": "&#235;",
    "exist": "&#8707;",
    "fnof": "&#402;",
    "forall": "&#8704;",
    "frac12": "&#189;",
    "frac14": "&#188;",
    "frac34": "&#190;",
    "frasl": "&#8260;",
    "Gamma": "&#915;",
    "gamma": "&#947;",
    "ge": "&#8805;",
    "gt": "&#62;",
    "harr": "&#8596;",
    "hArr": "&#8660;",
    "hearts": "&#9829;",
    "hellip": "&#8230;",
    "Iacute": "&#205;",
    "iacute": "&#237;",
    "Icirc": "&#206;",
    "icirc": "&#238;",
    "iexcl": "&#161;",
    "Igrave": "&#204;",
    "igrave": "&#236;",
    "image": "&#8465;",
    "infin": "&#8734;",
    "int": "&#8747;",
    "Iota": "&#921;",
    "iota": "&#953;",
    "iquest": "&#191;",
    "isin": "&#8712;",
    "Iuml": "&#207;",
    "iuml": "&#239;",
    "Kappa": "&#922;",
    "kappa": "&#954;",
    "Lambda": "&#923;",
    "lambda": "&#955;",
    "lang": "&#9001;",
    "laquo": "&#171;",
    "larr": "&#8592;",
    "lArr": "&#8656;",
    "lceil": "&#8968;",
    "le": "&#8804;",
    "lfloor": "&#8970;",
    "lowast": "&#8727;",
    "loz": "&#9674;",
    "lt": "&#60;",
    "macr": "&#175;",
    "micro": "&#181;",
    "middot": "&#183;",
    "minus": "&#8722;",
    "Mu": "&#924;",
    "mu": "&#956;",
    "nabla": "&#8711;",
    "nbsp": "&#160;",
    "ne": "&#8800;",
    "ni": "&#8715;",
    "not": "&#172;",
    "notin": "&#8713;",
    "nsub": "&#8836;",
    "Ntilde": "&#209;",
    "ntilde": "&#241;",
    "Nu": "&#925;",
    "nu": "&#957;",
    "Oacute": "&#211;",
    "oacute": "&#243;",
    "Ocirc": "&#212;",
    "ocirc": "&#244;",
    "Ograve": "&#210;",
    "ograve": "&#242;",
    "oline": "&#8254;",
    "Omega": "&#937;",
    "omega": "&#969;",
    "Omicron": "&#927;",
    "omicron": "&#959;",
    "oplus": "&#8853;",
    "or": "&#8744;",
    "ordf": "&#170;",
    "ordm": "&#186;",
    "Oslash": "&#216;",
    "oslash": "&#248;",
    "Otilde": "&#213;",
    "otilde": "&#245;",
    "otimes": "&#8855;",
    "Ouml": "&#214;",
    "ouml": "&#246;",
    "para": "&#182;",
    "part": "&#8706;",
    "perp": "&#8869;",
    "Phi": "&#934;",
    "phi": "&#966;",
    "Pi": "&#928;",
    "pi": "&#960;",
    "piv": "&#982;",
    "plusmn": "&#177;",
    "pound": "&#163;",
    "prime": "&#8242;",
    "Prime": "&#8243;",
    "prod": "&#8719;",
    "prop": "&#8733;",
    "Psi": "&#936;",
    "psi": "&#968;",
    "radic": "&#8730;",
    "rang": "&#9002;",
    "raquo": "&#187;",
    "rarr": "&#8594;",
    "rArr": "&#8658;",
    "rceil": "&#8969;",
    "real": "&#8476;",
    "reg": "&#174;",
    "rfloor": "&#8971;",
    "Rho": "&#929;",
    "rho": "&#961;",
    "sdot": "&#8901;",
    "sect": "&#167;",
    "shy": "&#173;",
    "Sigma": "&#931;",
    "sigma": "&#963;",
    "sigmaf": "&#962;",
    "sim": "&#8764;",
    "spades": "&#9824;",
    "sub": "&#8834;",
    "sube": "&#8838;",
    "sum": "&#8721;",
    "sup": "&#8835;",
    "sup1": "&#185;",
    "sup2": "&#178;",
    "sup3": "&#179;",
    "supe": "&#8839;",
    "szlig": "&#223;",
    "Tau": "&#932;",
    "tau": "&#964;",
    "there4": "&#8756;",
    "Theta": "&#920;",
    "theta": "&#952;",
    "thetasym": "&#977;",
    "THORN": "&#222;",
    "thorn": "&#254;",
    "times": "&#215;",
    "trade": "&#8482;",
    "Uacute": "&#218;",
    "uacute": "&#250;",
    "uarr": "&#8593;",
    "uArr": "&#8657;",
    "Ucirc": "&#219;",
    "ucirc": "&#251;",
    "Ugrave": "&#217;",
    "ugrave": "&#249;",
    "uml": "&#168;",
    "upsih": "&#978;",
    "Upsilon": "&#933;",
    "upsilon": "&#965;",
    "Uuml": "&#220;",
    "uuml": "&#252;",
    "weierp": "&#8472;",
    "Xi": "&#926;",
    "xi": "&#958;",
    "Yacute": "&#221;",
    "yacute": "&#253;",
    "yen": "&#165;",
    "yuml": "&#255;",
    "Zeta": "&#918;",
    "zeta": "&#950;",
}


def build_doctype_definition(name: str, entities: Dict[str, str]) -> str:
    entities_definition = [
        '<!ENTITY %s "%s">' % (key, value)
        for key, value in entities.items()
    ]
    return '<!DOCTYPE ' + name + ' [' + "".join(entities_definition) + ']>\n'


HTML_ENTITIES_DOCTYPE = build_doctype_definition("html", HTML_ENTITIES)


def __normalize_node_values(node: Dict[str, Any]) -> None:
    for key, value_or_values in node.items():
        if not re.search("^[A-z]", key):
            continue
        if not isinstance(value_or_values, list):
            node[key] = [value_or_values]
        for index, value in enumerate(node[key]):
            if isinstance(value, dict):
                __normalize_node_values(value)
            elif isinstance(value, str):
                node[key][index] = {"#text": value}


def from_xml(xml_text: str, add_xml_header=True, doctype: str = HTML_ENTITIES_DOCTYPE) -> Dict[str, Any]:
    if doctype:
        xml_text = doctype + xml_text
    if add_xml_header:
        xml_text = '<?xml version="1.0"?>\n' + xml_text
    parsed_xml = parse(xml_text)
    __normalize_node_values(parsed_xml)
    return parsed_xml