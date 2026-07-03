# allows for arithmetic expressions in XML files, e.g. 2*796020.0

import xml.etree.ElementTree as ET
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from UtilityLib.moduleXML import loadVariablesConversion
from UtilityLib.xml_expression import eval_expr

def run_tests():
    tests = {
        "796020.0": 796020.0,
        "2*796020.0": 1592040.0,
        "796020.0/2": 398010.0,
        "2*(796020.0+1000)": 1594040.0,
        "1.59204e6": 1592040.0,
    }

    for expr, expected in tests.items():
        result = eval_expr(expr)
        assert result == expected, f"{expr}: expected {expected}, got {result}"
        print(f"ok {expr} = {result}")

    xml = "<root><betaLaplace>2*796020.0</betaLaplace></root>"
    text = ET.fromstring(xml).find("betaLaplace").text
    result = loadVariablesConversion("betaLaplace", text, None)
    assert result == 1592040.0, f"XML betaLaplace: expected 1592040.0, got {result}"
    print(f"ok XML betaLaplace = {result}")

    result = loadVariablesConversion("Ps", "2*100", "mmHg")
    expected = 2 * 100 * 133.32
    assert result == expected, f"XML Ps unit scaling: expected {expected}, got {result}"
    print(f"ok XML Ps unit scaling = {result}")

    for expr in ["abs(5)", '__import__("os")']:
        try:
            loadVariablesConversion("betaLaplace", expr, None)
        except TypeError:
            print(f"ok rejected XML betaLaplace expression: {expr}")
        else:
            raise AssertionError(f"XML betaLaplace expression should have been rejected: {expr}")

    print("\nAll tests passed.")

if __name__ == "__main__":
    run_tests()
