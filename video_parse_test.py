from hachoir_parser import createParser
from hachoir_metadata import extractMetadata
from hachoir_core.cmd_line import unicodeFilename

import os

# Get the metadata from this filename
def getMetadata(filename):
	filename, realname = unicodeFilename(filename), filename
	
	parser = createParser(filename, realname)
	if not parser:
		print "Unable to parse file"
		exit(1)
	metadata = extractMetadata(parser)
	return metadata

dirpath = '/Users/elliots/Movies/dance_tutorials/spain_videos_miguel/'
filename = '9-3-2015.mp4'
		
file_data = getMetadata(dirpath + filename)
print file_data
print file_data.get('duration')
#print vars(file_data)
#print file_data.get('camera_model')

full_filelist = []

for file in os.listdir(dirpath):
	if os.path.isfile(dirpath + file):
		file_data = getMetadata(dirpath + file)
		len = file_data.get('duration')
		date = file_data.get('creation_date')
		print len
		print date
		full_filelist.append([date, len])
	elif os.path.isdir(dirpath + file):
		dirpath = dirpath + file + '/'
	 	for file in os.listdir(dirpath):
			file_data = getMetadata(dirpath + file)
			len = file_data.get('duration')
			date = file_data.get('creation_date')
			print len
			print date
			full_filelist.append([date, len])

# Make sure we have valid data (e.g. the dates aren't just zero)

#print full_filelist

for file in sorted(full_filelist, key=lambda vid: vid[0]):
	print file[0]
