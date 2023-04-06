#!/usr/bin/env python

import os
import importlib.util

# 99% authored by ChatGPT

def load_lang():
	lang = {}

	base_dir = os.path.dirname(os.path.abspath(__file__))
	current_filename = os.path.basename(os.path.abspath(__file__))
	module_files = [filename for filename in os.listdir(base_dir) if filename.endswith('.py')]
	module_files.remove(current_filename)
	module_files.remove('__init__.py')

	for filename in module_files:
		module_name = os.path.splitext(filename)[0]
		module_path = os.path.join(base_dir, filename)
		module_spec = importlib.util.spec_from_file_location(module_name, module_path)
		module = importlib.util.module_from_spec(module_spec)
		module_spec.loader.exec_module(module)
		lang[module_name] = module

	return lang