import re

def get_pages(filename):
	with open(filename) as f:
		data = f.read()
	return data.split('\x0c')

header_pattern = re.compile(r'^RFC \d+\s+.*\s+(\w+ \d{4})$', re.M)
footer_pattern = re.compile(r'^\w+\s+\w+\s+\[Page \d+\]$', re.M)

def remove_header(page):
	page = header_pattern.sub('', page)
	return page.lstrip('\n')

def remove_footer(page):
	page = footer_pattern.sub('', page)
	return page.rstrip() + '\n\n'

def clean_pages():
	return map(remove_header, map(remove_footer, get_pages('rfc2812.txt')))

def save_clean():
	with open('rfc2812-clean.txt', 'w') as f:
		map(f.write, clean_pages())

if __name__ == '__main__':
	save_clean()
