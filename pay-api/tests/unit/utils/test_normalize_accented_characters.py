# Copyright © 2025 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for normalize_accented_characters_json function."""

from pay_api.utils.util import normalize_accented_characters_json


def test_french_accented_characters_in_dict():
    """Test normalization of French accented characters in dictionary."""
    input_data = {
        "name": "GDGDGD",
        "chequeAdvice": "GDGDG2",
        "mailingAddress": {
            "city": "Montréal",
            "region": "QC",
            "street": "",
            "country": "CA",
            "postalCode": "H3B 4W8",
            "streetAdditional": (
                "à á â ã ä å è é ê ë ì í î ï ò ó ô õ ö ù ú û ü ý ÿ ç ñ ø æ œ "
                "À Á Â Ã Ä Å È É Ê Ë Ì Í Î Ï Ò Ó Ô Õ Ö Ù Ú Û Ü Ý Ç Ñ Ø Æ Œ"
            ),
            "deliveryInstructions": "",
        },
    }

    expected = {
        "name": "GDGDGD",
        "chequeAdvice": "GDGDG2",
        "mailingAddress": {
            "city": "Montreal",
            "region": "QC",
            "street": "",
            "country": "CA",
            "postalCode": "H3B 4W8",
            "streetAdditional": (
                "a a a a a a e e e e i i i i o o o o o u u u u y y c n o ae oe "
                "A A A A A A E E E E I I I I O O O O O U U U U Y C N O AE OE"
            ),
            "deliveryInstructions": "",
        },
    }

    result = normalize_accented_characters_json(input_data)
    assert result == expected


def test_weird_dashes():
    """Test normalization of em dash and en dash to regular hyphen."""
    input_data = {"title": "Business—Name", "description": "Company–Info", "address": "123—Main St–Suite 100"}

    expected = {"title": "Business-Name", "description": "Company-Info", "address": "123-Main St-Suite 100"}

    result = normalize_accented_characters_json(input_data)
    assert result == expected


def test_french_city_names():
    """Test normalization of French city names."""
    input_data = {"cities": ["Québec", "Trois-Rivières", "Saint-Jérôme", "Montréal"]}

    expected = {"cities": ["Quebec", "Trois-Rivieres", "Saint-Jerome", "Montreal"]}

    result = normalize_accented_characters_json(input_data)
    assert result == expected


def test_mixed_content():
    """Test normalization with mixed content types."""
    input_data = {
        "name": "François—Dupont",
        "addresses": [
            {"city": "Québec", "street": "Rue—Saint-Jean"},
            {"city": "Montréal", "street": "Avenue—du Parc"},
        ],
        "notes": "Client préfère—contact par téléphone",
    }

    expected = {
        "name": "Francois-Dupont",
        "addresses": [
            {"city": "Quebec", "street": "Rue-Saint-Jean"},
            {"city": "Montreal", "street": "Avenue-du Parc"},
        ],
        "notes": "Client prefere-contact par telephone",
    }

    result = normalize_accented_characters_json(input_data)
    assert result == expected


def test_string_input():
    """Test normalization of string input."""
    input_str = "Montréal—Québec"
    expected = "Montreal-Quebec"

    result = normalize_accented_characters_json(input_str)
    assert result == expected


def test_list_input():
    """Test normalization of list input."""
    input_list = ["Montréal", "Québec", "Trois-Rivières"]
    expected = ["Montreal", "Quebec", "Trois-Rivieres"]

    result = normalize_accented_characters_json(input_list)
    assert result == expected


def test_non_string_input():
    """Test that non-string inputs are returned unchanged."""
    input_data = {"number": 123, "boolean": True, "none_value": None, "float_value": 45.67}

    result = normalize_accented_characters_json(input_data)
    assert result == input_data


def test_empty_structures():
    """Test normalization of empty structures."""
    empty_dict = {}
    empty_list = []
    empty_string = ""

    assert normalize_accented_characters_json(empty_dict) == {}
    assert normalize_accented_characters_json(empty_list) == []
    assert normalize_accented_characters_json(empty_string) == ""


def test_nested_structures():
    """Test normalization of deeply nested structures."""
    input_data = {"level1": {"level2": {"level3": {"city": "Québec", "streets": ["Rue—Saint-Jean", "Avenue—du Parc"]}}}}

    expected = {"level1": {"level2": {"level3": {"city": "Quebec", "streets": ["Rue-Saint-Jean", "Avenue-du Parc"]}}}}

    result = normalize_accented_characters_json(input_data)
    assert result == expected


def test_normalize_simple_string_with_accents():
    """Test normalization of simple string with French accents."""
    input_string = "Montréal Québec Français"
    expected_string = "Montreal Quebec Francais"

    result = normalize_accented_characters_json(input_string)
    assert result == expected_string


def test_normalize_list_with_accents():
    """Test normalization of list containing strings with French accents."""
    input_list = ["Montréal", "Québec", "Français", "École"]
    expected_list = ["Montreal", "Quebec", "Francais", "Ecole"]

    result = normalize_accented_characters_json(input_list)
    assert result == expected_list


def test_normalize_nested_dict_with_accents():
    """Test normalization of nested dictionary with French accents."""
    input_data = {
        "addresses": [
            {"city": "Montréal", "province": "Québec", "description": "École primaire"},
            {"city": "Toronto", "province": "Ontario", "description": "Regular text"},
        ]
    }

    expected_data = {
        "addresses": [
            {"city": "Montreal", "province": "Quebec", "description": "Ecole primaire"},
            {"city": "Toronto", "province": "Ontario", "description": "Regular text"},
        ]
    }

    result = normalize_accented_characters_json(input_data)
    assert result == expected_data


def test_normalize_dict_keys_with_accents():
    """Test normalization of dictionary keys with French accents."""
    input_data = {"adresse": "123 Main St", "ville": "Montréal", "pays": "Canada"}

    expected_data = {"adresse": "123 Main St", "ville": "Montreal", "pays": "Canada"}

    result = normalize_accented_characters_json(input_data)
    assert result == expected_data


def test_normalize_mixed_data_types():
    """Test normalization with mixed data types including non-string values."""
    input_data = {
        "name": "François",
        "age": 30,
        "active": True,
        "score": 95.5,
        "address": None,
        "cities": ["Montréal", "Québec", "Ottawa"],
    }

    expected_data = {
        "name": "Francois",
        "age": 30,
        "active": True,
        "score": 95.5,
        "address": None,
        "cities": ["Montreal", "Quebec", "Ottawa"],
    }

    result = normalize_accented_characters_json(input_data)
    assert result == expected_data


def test_normalize_complex_nested_structure():
    """Test normalization of complex nested structure with French accents."""
    input_data = {
        "organisation": {
            "nom": "Édole de Montréal",
            "adresse": {
                "rue": "123 Rue de la Paix",
                "ville": "Montréal",
                "province": "Québec",
                "code_postal": "H1A 1A1",
            },
            "contacts": [
                {"nom": "Rean-François", "email": "rean-francois@fake.ca", "téléphone": "515-222-3555"},
                {"nom": "Larie-Claire", "email": "larie-claire@fake.ca", "téléphone": "516-222-3333"},
            ],
        }
    }

    expected_data = {
        "organisation": {
            "nom": "Edole de Montreal",
            "adresse": {
                "rue": "123 Rue de la Paix",
                "ville": "Montreal",
                "province": "Quebec",
                "code_postal": "H1A 1A1",
            },
            "contacts": [
                {"nom": "Rean-Francois", "email": "rean-francois@fake.ca", "telephone": "515-222-3555"},
                {"nom": "Larie-Claire", "email": "larie-claire@fake.ca", "telephone": "516-222-3333"},
            ],
        }
    }

    result = normalize_accented_characters_json(input_data)
    assert result == expected_data


def test_normalize_specific_french_characters():
    """Test normalization of specific French accented characters."""
    input_data = {
        "lowercase_accents": "àáâãäåèéêëìíîïòóôõöùúûüýÿçñ",
        "uppercase_accents": "ÀÁÂÃÄÅÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÝÇÑ",
        "mixed_case": "Érole Français Québec Montréal",
    }

    expected_data = {
        "lowercase_accents": "aaaaaaeeeeiiiiooooouuuuyycn",
        "uppercase_accents": "AAAAAAEEEEIIIIOOOOOUUUUYCN",
        "mixed_case": "Erole Francais Quebec Montreal",
    }

    result = normalize_accented_characters_json(input_data)
    assert result == expected_data


def test_special_characters_oe_ae():
    """Test normalization of special characters ø, æ, œ and their uppercase versions."""
    input_data = {
        "lowercase_special": "øæœ",
        "uppercase_special": "ØÆŒ",
        "mixed_special": "Café Søren Æsop Œuvre",
        "with_dashes": "Café—Søren–Æsop—Œuvre",
    }

    expected_data = {
        "lowercase_special": "oaeoe",
        "uppercase_special": "OAEOE",
        "mixed_special": "Cafe Soren AEsop OEuvre",
        "with_dashes": "Cafe-Soren-AEsop-OEuvre",
    }

    result = normalize_accented_characters_json(input_data)
    assert result == expected_data


def test_unicode_quotation_marks():
    """Test normalization of Unicode quotation marks and apostrophes."""
    input_data = {
        "name": "O\u2019Co",
        "quote": "He said \u201cHello\u201d",
        "apostrophe": "It\u2019s a test",
        "mixed": "O\u2019Connor said \u201cYes\u201d",
    }

    expected_data = {
        "name": "O'Co",
        "quote": 'He said "Hello"',
        "apostrophe": "It's a test",
        "mixed": 'O\'Connor said "Yes"',
    }

    result = normalize_accented_characters_json(input_data)
    assert result == expected_data


def test_remove_all_non_ascii():
    """Test that all non-ASCII characters are removed."""
    input_data = {
        "chinese": "你好世界",
        "emoji": "Hello 😀 World 🌍",
        "symbols": "Price: €100 ¥50 £30",
        "mixed": "Café résumé naïve",
    }

    expected_data = {
        "chinese": "",
        "emoji": "Hello  World ",
        "symbols": "Price: 100 50 30",
        "mixed": "Cafe resume naive",
    }

    result = normalize_accented_characters_json(input_data)
    assert result == expected_data
