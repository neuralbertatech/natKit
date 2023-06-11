#!/usr/bin/env python

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))
sys.path.append(PROJECT_ROOT)

import unittest

test_modules = [
        "api",
#        "client",
        "common",
#       "server",
        ]

def decorate_module_test_path(module):
    return "natKit/{}/test/python/natKit".format(module)

def prepend_project_path(path):
    return "{}/{}".format(PROJECT_ROOT, path)

def get_paths_for_modules(modules):
    return [prepend_project_path(decorate_module_test_path(module)) for module in modules]

def get_suites():
    suites = []
    for module_path in get_paths_for_modules(test_modules):
        suite = unittest.TestSuite()
        loader = unittest.TestLoader()
        for test_suites in loader.discover(module_path, pattern="*_test.py"):
            for test_suite in test_suites:
                suite.addTest(test_suite)
        suites.append({"path": module_path, "suite": suite})
    return suites


if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    suites = get_suites()
    for suite in suites:
        print(suite["path"])
        runner.run(suite["suite"])
