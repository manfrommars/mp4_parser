import mp4_parser
import filename_parser
import os
import sys
import io

stdout_redirect = 'file_output.txt'

with open(stdout_redirect, 'w') as f:
    sys.stdout = f

    dirpath = '~/Movies/dance_tutorials/'
    dirpath = os.path.expanduser(dirpath)
    mp4_parser.DEBUG=0
    print("Run parser:")

##    root = "~/Movies/dance_tutorials/spain_videos_miguel/"
##    for i in range(0,1):
##        for filename in ["9-3-2015.mp4"]:
    for root, directories, filenames in os.walk(dirpath):
        for filename in filenames:
            path = os.path.join(root,filename)
            print(path.encode('utf-8'))
            if path.endswith('.mp4'):
                print(path.encode('utf-8'))
                #print('='*60)
                #mp4_parser.readMp4File(os.path.join(root,filename))
                print('='*60)
                field = 'creation_time'
                val = mp4_parser.findMp4Field(os.path.join(root,filename), field)
                print("DEBUG: " + field + "="+ str(val))
                date = filename_parser.datetimeFromFilename(filename)
                print(str(date))
