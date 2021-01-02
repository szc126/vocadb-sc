#!/usr/bin/env python3

import pickle

def disk_cache_decorator(filename):
	def decorator(function):
		def inner(*args, **kwargs):
			key = locals()
			key['function'] = function.__name__ # non-constant memory address is not helpful
			key = str(key)
			value = None
			pickle_all = {}

			try:
				with open(filename, 'rb') as file:
					try:
						pickle_all = pickle.load(file) # load data
					except EOFError: # empty file
						pass
			except FileNotFoundError: # no file
				pass

			if key in pickle_all:
				return pickle_all[key] # return data
			else:
				value = function(*args, **kwargs) # perform the original function call and save the result
				pickle_all[key] = value # add data
				with open(filename, 'wb') as file:
					pickle.dump(pickle_all, file) # write data
				return value # return data
		return inner
	return decorator
	