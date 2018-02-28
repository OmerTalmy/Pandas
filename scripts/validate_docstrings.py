#!/usr/bin/env python
"""
Analyze docstrings to detect errors.

If no argument is provided, it does a quick check of docstrings and returns
a csv with all API functions and results of basic checks.

If a function or method is provided in the form "pandas.function",
"pandas.module.class.method", etc. a list of all errors in the docstring for
the specified function or method.

Usage::
    $ ./validate_docstrings.py
    $ ./validate_docstrings.py pandas.DataFrame.head
"""
import os
import sys
import csv
import re
import functools
import argparse
import inspect
import importlib
import doctest
import numpy

BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(BASE_PATH))
import pandas

sys.path.insert(1, os.path.join(BASE_PATH, 'doc', 'sphinxext'))
from numpydoc.docscrape import NumpyDocString


def _to_original_callable(obj):
    while True:
        if inspect.isfunction(obj) or inspect.isclass(obj):
            f = inspect.getfile(obj)
            if f.startswith('<') and f.endswith('>'):
                return None
            return obj
        if inspect.ismethod(obj):
            obj = obj.__func__
        elif isinstance(obj, functools.partial):
            obj = obj.func
        elif isinstance(obj, property):
            obj = obj.fget
        else:
            return None


class Docstring:
    def __init__(self, method_name, method_obj):
        self.method_name = method_name
        self.method_obj = method_obj
        self.raw_doc = method_obj.__doc__ or ''
        self.doc = NumpyDocString(self.raw_doc)

    def __len__(self):
        return len(self.raw_doc)

    @property
    def source_file_name(self):
        fname = inspect.getsourcefile(self.method_obj)
        if fname:
            fname = os.path.relpath(fname, BASE_PATH)
            return fname

    @property
    def source_file_def_line(self):
        try:
            return inspect.getsourcelines(self.method_obj)[-1]
        except OSError:
            pass

    @property
    def github_url(self):
        url = 'https://github.com/pandas-dev/pandas/blob/master/'
        url += '{}#L{}'.format(self.source_file_name,
                               self.source_file_def_line)
        return url

    @property
    def first_line_blank(self):
        if self.raw_doc:
            return not bool(self.raw_doc.split('\n')[0].strip())

    @property
    def summary(self):
        return ' '.join(self.doc['Summary'])

    @property
    def extended_summary(self):
        return ' '.join(self.doc['Extended Summary'])

    @property
    def needs_summary(self):
        return not (bool(self.summary) and bool(self.extended_summary))

    @property
    def doc_parameters(self):
        return self.doc['Parameters']

    @property
    def signature_parameters(self):
        if not inspect.isfunction(self.method_obj):
            return tuple()
        params = tuple(inspect.signature(self.method_obj).parameters.keys())
        if params and params[0] in ('self', 'cls'):
            return params[1:]
        return params

    @property
    def correct_parameters(self):
        if self.doc_parameters:
            doc_param_names = list(zip(*self.doc_parameters))[0]
            return doc_param_names == self.signature_parameters

        return not bool(self.signature_parameters)

    @property
    def see_also(self):
        return self.doc['See Also']

    @property
    def examples(self):
        return self.doc['Examples']

    @property
    def first_line_ends_in_dot(self):
        if self.doc:
            return self.doc.split('\n')[0][-1] == '.'

    @property
    def deprecated(self):
        pattern = re.compile('.. deprecated:: ')
        return (self.method_name.startswith('pandas.Panel') or
                bool(pattern.search(self.summary)) or
                bool(pattern.search(self.extended_summary)))

    @property
    def examples_pass_tests(self):
        finder = doctest.DocTestFinder()
        runner = doctest.DocTestRunner()
        context = {'np': numpy, 'pd': pandas}
        for test in finder.find(self.raw_doc, self.method_name, globs=context):
            print(runner.run(test))


def get_api_items():
    api_fname = os.path.join(BASE_PATH, 'doc', 'source', 'api.rst')

    position = None
    with open(api_fname) as f:
        for line in f:
            if line.startswith('.. currentmodule::'):
                current_module = line.replace('.. currentmodule::', '').strip()
                continue

            if line == '.. autosummary::\n':
                position = 'autosummary'
                continue

            if position == 'autosummary':
                if line == '\n':
                    position = 'items'
                    continue

            if position == 'items':
                if line == '\n':
                    position = None
                    continue
                item = line.strip()
                func = importlib.import_module(current_module)
                for part in item.split('.'):
                    func = getattr(func, part)

                yield '.'.join([current_module, item]), func


def validate_all():
    writer = csv.writer(sys.stdout)
    writer.writerow(['Function or method',
                     'Type',
                     'File',
                     'Code line',
                     'GitHub link',
                     'Is deprecated',
                     'Has summary',
                     'Has extended summary',
                     'Parameters ok',
                     'Has examples',
                     'Shared code with'])
    seen = {}
    for func_name, func in get_api_items():
        obj_type = type(func).__name__
        original_callable = _to_original_callable(func)
        if original_callable is None:
            writer.writerow([func_name, obj_type] + [''] * 9)
        else:
            doc = Docstring(func_name, original_callable)
            key = doc.source_file_name, doc.source_file_def_line
            shared_code = seen.get(key, '')
            seen[key] = func_name
            writer.writerow([func_name,
                             obj_type,
                             doc.source_file_name,
                             doc.source_file_def_line,
                             doc.github_url,
                             int(doc.deprecated),
                             int(bool(doc.summary)),
                             int(bool(doc.extended_summary)),
                             int(doc.correct_parameters),
                             int(bool(doc.examples)),
                             shared_code])

    return 0


def validate_one(func_name):
    for maxsplit in range(1, func_name.count('.') + 1):
        # TODO when py3 only replace by: module, *func_parts = ...
        func_name_split = func_name.rsplit('.', maxsplit=maxsplit)
        module = func_name_split[0]
        func_parts = func_name_split[1:]
        try:
            func_obj = importlib.import_module(module)
        except ImportError:
            pass
        else:
            continue

    if 'module' not in locals():
        raise ImportError('No module can be imported '
                          'from "{}"'.format(func_name))

    for part in func_parts:
        func_obj = getattr(func_obj, part)

    doc = Docstring(func_name, func_obj)

    errs = []
    if not doc.summary:
        errs.append('No summary found')
    else:
        if not doc.summary[0].isupper():
            errs.append('Summary does not start with capital')
        if doc.summary[-1] != '.':
            errs.append('Summary does not end with dot')
        if doc.summary.split(' ')[0][-1] == 's':
            errs.append('Summary must start with infinitive verb, '
                        'not third person (e.g. use "Generate" instead of '
                        '"Generates")')
    if not doc.extended_summary:
        errs.append('No extended summary found')
    if not doc.correct_parameters:
        errs.append('Documented parameters do not match the signature')
    if not doc.examples:
        errs.append('No examples')

    if errs:
        sys.stderr.write('Errors for "{}" docstring:\n'.format(func_name))
        for err in errs:
            sys.stderr.write('\t* {}\n'.format(err))
    else:
        sys.stderr.write('Docstring for "{}" correct. :)\n'.format(func_name))

    return len(errs)


def main(function):
    if function is None:
        return validate_all()
    else:
        return validate_one(function)


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(
        description='validate pandas docstrings')
    argparser.add_argument('function',
                           nargs='?',
                           default=None,
                           help=('function or method to validate '
                                 '(e.g. pandas.DataFrame.head) '
                                 'if not provided, all docstrings '
                                 'are validated'))
    args = argparser.parse_args()
    sys.exit(main(args.function))
