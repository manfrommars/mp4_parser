import struct
import sys

DEBUG=0
######################################################################
## Errors
######################################################################

# Define a FormatError which we can raise when something goes wrong
# This may be extended to provide more fine-detailed exceptions
class FormatError(Exception):
    """Exception raised when the formatting of the file is incorrect

    Attributes:
        filename -- MP4 filename which generated the exception
    """

    def __init__(self, filename):
        self.filename = filename

# Subclass of FormatError when unable to read proper number of bytes
# from a file
class FileReadError(FormatError):
    """Exception raised when EOF is reached before all bytes are read

    Attributes:
        filename -- MP4 filename which generated the exception
        bytes_requested -- bytes requested to be read
        bytes_read -- bytes actually read
    """
    def __init__(self, filename, bytes_requested, bytes_read):
        FormatError.__init__(self, filename)
        self.bytes_requested = bytes_requested
        self.bytes_read      = bytes_read

######################################################################
## Helper Functions
######################################################################

# Read data from a file, checking for the correct number of bytes
def readFromFile(file, num_bytes):
    raw_data = file.read(num_bytes)
    actual_bytes = len(raw_data)
    dbg_print('Reading ' + str(num_bytes)+ 'B from file')
    if actual_bytes < num_bytes:
        raise FileReadError(file.name, num_bytes, actual_bytes)
    return raw_data

# Read 8 bytes and handle processing whichever portions are found
def readBoxHeader(file):
    try:
        raw_size = readFromFile(file, 4)
    except FileReadError as err:
        raise err

    read_offset = 4
    box_size = struct.unpack('>I',raw_size)[0]

    # Read box type
    try:
        raw_type = readFromFile(file, 4)
    except FileReadError as err:
        raise err

    read_offset = read_offset + 4
    box_type = raw_type.decode('utf-8')

    # Check to see if this uses a 64-bit size
    if box_size == 1:
        try:
            raw_largesize = readFromFile(file, 8)
        except FileReadError as err:
            raise err
        box_size = struct.unpack('>Q', raw_largesize)[0]
        read_offset = read_offset + 8

    # Check for uuid entry
    if box_type == 'uuid':
        try:
            raw_usertype = readFromFile(file, 128)
        except FileReadError as err:
            raise err
        read_offset = read_offset + 128

    dbg_print("Box '"+box_type+"', Length: "+ str(box_size) + " bytes")

    return (box_size, box_type, read_offset)

# Read version and flag info
def readFullBoxHeader(file):
    try:
        raw_version_info = readFromFile(file, 1)
    except FileReadError as err:
        raise err
    version_info = struct.unpack('>B', raw_version_info)[0]
    try:
        raw_flags = readFromFile(file, 3)
    except FileReadError as err:
        raise err
    flags = struct.unpack('>BBB', raw_flags)

    dbg_print("FullBox, v"+str(version_info)+" flags: "+str(flags))
    return (version_info, flags)

# Advance the file read pointer rather than reading data to memory
def advanceNBytes(file, num_bytes):
    start_offset = file.tell()
    file.seek(num_bytes, 1)
    end_offset = file.tell()
    dbg_print('Advancing ' + str(num_bytes)+ 'B in file')
    if end_offset - start_offset < num_bytes:
        raise FileReadError(file.name, num_bytes, actual_bytes)

# Read and process all children in num_bytes
def processChildren(file, num_bytes):
    child_size = 0
    local_dict = {}
    while child_size < num_bytes:
        box_size, box_info = readMp4Box(file)
        child_size = child_size + box_size
        local_dict.update(box_info)
    return local_dict

# Print function for debugging
def dbg_print(*objects, sep=' ', end='\n', file=sys.stdout, flush=False):
    global DEBUG
    if DEBUG is 1:
        print(*objects, sep=sep, end=end, file=file, flush=flush)

# Determine if the field is in the supported box types
def checkField(field):
    for key, value in supported_boxes.items():
        for tup in value[1:]:
            if len(tup) > 2:
                if tup[2] is field:
                    return True
    return False

######################################################################
## Box Types
######################################################################

# Supported box types: Box, FullBox
box_types = ['Box', 'FullBox']
versions  = [0,1]

supported_boxes = {
# ISO/IEC 14496-12, Section 4.3, File Type Box
# Box Type:     'ftyp'
# Container:    File
# Mandatory:    Yes
# Quantity:     Exactly one
#
    'ftyp':['Box',
            (4, 'u', 'major_brand'),
            (4, 'u', 'minor_version'),
            (0, 'c', 'compatible_brands', 4)],
# ISO/IEC 14496-12, Section 8.1, Movie Box
# Box Type:     'moov'
# Container:    File
# Mandatory:    Yes
# Quantity:     Exactly one
#
    'moov':['Box',
            (0, 'a', 'children')],
# ISO/IEC 14496-12, Section 8.2, Media Data Box
# Box Type:     'mdat'
# Container:    File
# Mandatory:    No
# Quantity:     Any number
#
    'mdat':['Box',
            (0, 'b', 'data_len')],
# ISO/IEC 14496-12, Section 8.3, Movie Header Box
# Box Type:     'mvhd'
# Container:    Movie Box ('moov')
# Mandatory:    Yes
# Quantity:     Exactly one
#
    'mvhd':['FullBox',
            ([4,8],   'u', 'creation_time'),
            ([4,8],   'u', 'modification_time'),
            ([4,4],   'u', 'timescale'),
            ([4,8],   'u', 'duration'),
            ([4,4],   'u', 'rate'),
            ([2,2],   'u', 'volume'),
            ([2,2],   'N'),
            ([8,8],   'N'),
            ([36,36], 'uuuuuuuuu', 'matrix'),
            ([24,24], 'N'),
            ([4,4],   'u', 'next_track_ID')],
# ISO/IEC 14496-12, Section 8.4, Track Box
# Box Type:     'trak'
# Container:    Movie Box ('moov')
# Mandatory:    Yes
# Quantity:     One or more
#
    'trak':['Box',
            (0, 'a', 'children')],
# ISO/IEC 14496-12, Section 8.5, Track Header Box
# Box Type:     'tkhd'
# Container:    Track Box ('trak')
# Mandatory:    Yes
# Quantity:     Exactly one
#
    'tkhd':['FullBox',
            ([4,8],   'u', 'creation_time'),
            ([4,8],   'u', 'modification_time'),
            ([4,4],   'u', 'track_ID'),
            ([4,4],   'N'),
            ([4,8],   'u', 'duration'),
            ([8,8],   'N'),
            ([2,2],   's', 'layer'),
            ([2,2],   's', 'alternate_group'),
            ([2,2],   's', 'volume'),
            ([2,2],   'N'),
            ([36,36], 'uuuuuuuuu', 'matrix'),
            ([4,4],   'u', 'width'),
            ([4,4],   'u', 'height')],
# ISO/IEC 14496-12, Section 8.7, Media Box
# Box Type:     'mdia'
# Container:    Track Box ('trak')
# Mandatory:    Yes
# Quantity:     Exactly one
#
    'mdia':['Box',
            (0, 'a', 'children')],
# ISO/IEC 14496-12, Section 8.8, Media Header Box
# Box Type:     'mdhd'
# Container:    Media Box ('mdia')
# Mandatory:    Yes
# Quantity:     Exactly one
#
    'mdhd':['FullBox',
            ([4,8],   'u', 'creation_time'),
            ([4,8],   'u', 'modification_time'),
            ([4,4],   'u', 'timescale'),
            ([4,8],   'u', 'duration'),
            ([2,2],   'i', 'language'),
            ([2,2],   'N')],
# ISO/IEC 14496-12, Section 8.9, Handler Reference Box
# Box Type:     'hdlr'
# Container:    Media Box ('mdia') or Meta Box ('meta')
# Mandatory:    Yes
# Quantity:     Exactly one
#
    'hdlr':['FullBox',
            ([4,4],   'N'),
            ([4,4],   'c', 'handler_type', 4),
            ([12,12], 'N'),
            ([0,0],   'str', 'name')],
# ISO/IEC 14496-12, Section 8.10, Media Information Box
# Box Type:     'minf'
# Container:    Media Box ('mdia')
# Mandatory:    Yes
# Quantity:     Exactly one
#
    'minf':['Box',
            (0, 'a', 'children')],
# ISO/IEC 14496-12, Section 8.11.2, Video Media Header Box
# Box Type:     'vmhd'
# Container:    Media Information Box ('minf')
# Mandatory:    Yes
# Quantity:     Exactly one specific media header shall be present
#
    'vmhd':['FullBox',
            ([2,2], 'u', 'graphicsmode'),
            ([6,6], 'uuu', 'opcolor')],
# ISO/IEC 14496-12, Section 8.11.3, Sound Media Header Box
# Box Type:     'smhd'
# Container:    Media Information Box ('minf')
# Mandatory:    Yes
# Quantity:     Exactly one specific media header shall be present
#
    'smhd':['FullBox',
            ([2,2], 'u', 'balance'),
            ([2,2], 'N')],
# ISO/IEC 14496-12, Section 8.12, Data Information Box
# Box Type:     'dinf'
# Container:    Media Information Box ('mdia') OR
#               Meta Box ('meta')
# Mandatory:    Yes (within 'minf'), No (within 'meta')
# Quantity:     Exactly one
#
    'dinf':['Box',
            (0, 'a', 'children')],
# ISO/IEC 14496-12, Section 8.14, Sample Table Box
# Box Type:     'stbl'
# Container:    Media Information Box ('minf')
# Mandatory:    Yes
# Quantity:     Exactly one
#
    'stbl':['Box',
            (0, 'a', 'children')],
# ISO/IEC 14496-12, Section 8.13, Data Reference Box
# Box Type:     'dref'
# Container:    Data Information Box ('dinf')
# Mandatory:    Yes
# Quantity:     Exactly one 
#
    'dref':['FullBox',
            ([4,4], 'u', 'entry_count'),
            ([0,0], 'aa', 'data_entry')],
# ISO/IEC 14496-12, Section 8.13, Data Reference Box
# Box Type:     'url '
# Container:    Data Information Box ('dinf')
# Mandatory:    Yes
# Quantity:     Exactly one 
#
    'url ':['FullBox',
            ([0,0], 'str', 'location')],
# ISO/IEC 14496-12, Section 8.15.2, Decoding Time to Sample Box
# Box Type:     'stts'
# Container:    Sample Table Box ('stbl')
# Mandatory:    Yes
# Quantity:     Exactly one 
#
    'stts':['FullBox',
            ([4,4], 'u', 'entry_count'),
            ([0,0], 'aaa', ['sample_count', 'sample_delta'])],
# ISO/IEC 14496-12, Section 8.15.3, Composition Time to Sample Box
# Box Type:     'ctts'
# Container:    Sample Table Box ('stbl')
# Mandatory:    No
# Quantity:     Zero or one 
#
    'ctts':['FullBox',
            ([4,4], 'u', 'entry_count'),
            ([0,0], 'aaa', ['sample_count', 'sample_offset'])],
# ISO/IEC 14496-12, Section 8.20, Sync Sample Box
# Box Type:     'stss'
# Container:    Sample Table Box ('stbl')
# Mandatory:    No
# Quantity:     Zero or one 
#
    'stss':['FullBox',
            ([4,4], 'u', 'entry_count'),
            ([0,0], 'aaa', ['sample_number'])],
# ISO/IEC 14496-12, Section 8.17, Sample Size Box
# Box Type:     'stsz'
# Container:    Sample Table Box ('stbl')
# Mandatory:    Yes
# Quantity:     Exactly one variant
#
    'stsz':['FullBox',
            ([4,4], 'u', 'sample_size'),
            ([4,4], 'u', 'sample_count'),
            ([0,0], 'A', 'entry_size')],
# ISO/IEC 14496-12, Section 8.18, Sample To Chunk Box
# Box Type:     'stts'
# Container:    Sample Table Box ('stbl')
# Mandatory:    Yes
# Quantity:     Exactly one 
#
    'stsc':['FullBox',
            ([4,4], 'u', 'entry_count'),
            ([0,0], 'aaa', ['first_chunk', 'samples_per_chunk',
                            'sample_description_index'])],
# ISO/IEC 14496-12, Section 8.19, Chunk Offset Box
# Box Type:     'stco'
# Container:    Sample Table Box ('stbl')
# Mandatory:    Yes
# Quantity:     Exactly one variant
#
    'stco':['FullBox',
            ([4,4], 'u', 'entry_count'),
            ([0,0], 'aaa', ['chunk_offset'])],
# ISO/IEC 14496-12, Section 8.40.2, Independent and Disposable Samples Box
# Box Type:     'sdtp'
# Container:    Sample Table Box ('stbl') or Track Fragment Box ('traf')
# Mandatory:    No
# Quantity:     Zero or one 
#
    'sdtp':['FullBox',
            ([0,0], 'b', 'samples')],
# ISO/IEC 14496-12, Section 8.16, Sample Description Box
# Box Type:     'stsd'
# Container:    Sample Table Box ('stbl')
# Mandatory:    Yes
# Quantity:     Exactly one 
#
    'stsd':['FullBox',
            ([4,4], 'u', 'entry_count'),
            ([0,0], 'b', 'sample_entry')],
# ISO/IEC 14496-12, Section 8.24, Free Space Box
# Box Type:     'free'
# Container:    File or other box
# Mandatory:    No
# Quantity:     Any number
#
    'free':['Box',
            (0, 'b', 'data')],
# ISO/IEC 14496-12, Section 8.25, Edit Box
# Box Type:     'edts'
# Container:    Track Box ('trak')
# Mandatory:    No
# Quantity:     Zero or one
#
    'edts':['Box',
            (0, 'a', 'children')],
# ISO/IEC 14496-12, Section 8.27, User Data Box
# Box Type:     'udta'
# Container:    Movie Box ('moov') OR
#               Track Box ('trak')
# Mandatory:    No
# Quantity:     Zero or one
#
    'udta':['Box',
            (0, 'a', 'children')],
# ISO/IEC 14496-12, Section 8.44.1, Meta Box
# Box Type:     'meta'
# Container:    File, Movie Box (moov), or Track Box ('trak')
# Mandatory:    No
# Quantity:     Zero or one
#
    'meta':['Box',
            (0, 'b', 'data')],
# ISO/IEC 14496-12, Section 8.26, Edit List Box
# Box Type:     'elst'
# Container:    Edit Box (edts)
# Mandatory:    No
# Quantity:     Zero or one
#
    'elst':['Box',
            (0, 'b', 'data')], # not translated
# Other Box Types
    'wide':['Box',
            (0, 'b', 'data')], # not translated
    'iods':['Box',
            (0, 'b', 'data')], # not translated
    'SDLN':['Box',
            (0, 'b', 'data')], # not translated
    }


# For each defined box, read its format from the dictionary
def processBox(file, read_offset, box_info):
    info_list = supported_boxes[box_info['type']]
    # First item is always "Box" or "FullBox"
    if info_list[0] not in box_types:
        raise FileReadError

    dbg_print('type: ' +     box_info['type']       )
    dbg_print('size: ' + str(box_info['size']) + 'B')

    if info_list[0] is 'FullBox':
        try:
            (box_info['version'],
             box_info['flags']) = readFullBoxHeader(file)
        except FileReadError as err:
            raise err
        dbg_print('version: ' + str(box_info['version']))
        dbg_print('flags: ' + str(box_info['flags']))
        read_offset = read_offset + 4

    for item in info_list[1:]:
        # item tuple contents:
        # size (in bits)
        # signed/unsigned/chars/children/binary data
        # name
        # split size for arrays (if necessary)
        if 'version' in box_info:
            size = item[0][box_info['version']]
        else:
            size = item[0]
        #print('Read offset: ' + str(read_offset))
        #print('Read size: ' + str(box_len-read_offset))
        if item[1] == 'N':
            read_offset = read_offset + size
            advanceNBytes(file, size)
        elif size != 0:
            try:
                temp = readFromFile(file, size)
            except FileReadError as err:
                raise err
            read_offset = read_offset + size
        else:
            if item[1] == 'a':
                # flatten the inputs by appending the child dictionary
                dbg_print("Process children")
                info = processChildren(file, box_info['size']-read_offset)
                box_info.update(info)
            elif item[1] == 'aa':
                for i in range(0, box_info['entry_count']):
                    processChildren(file, box_info['size']-read_offset)
            elif item[1] == 'aaa':
                for i in range(0, box_info['entry_count']):
                    for j in range(0, len(item[2])):
                        try:
                            temp = readFromFile(file, 4)
                        except FileReadError as err:
                            raise err
                        read_offset = read_offset + 4
                        # Put together a list of entries
                        if item[2][j] in box_info:
                            box_info[item[2][j]].append(struct.unpack('>L', temp)[0])
                        else:
                            box_info[item[2][j]]=[struct.unpack('>L', temp)[0]]
            elif item[1] == 'A':
                if box_info['sample_size'] == 0:
                    for i in range(0, box_info['sample_count']):
                        try:
                            temp = readFromFile(file, 4)
                        except FileReadError as err:
                            raise err
                        read_offset = read_offset + 4
                        if item[2] in box_info:
                            box_info[item[2]].append(struct.unpack('>L', temp)[0])
                        else:
                            box_info[item[2]]=[struct.unpack('>L', temp)[0]]
            elif item[1] != 'b':
                try:
                    temp = readFromFile(file, box_info['size']-read_offset)
                except FileReadError as err:
                    raise err
        # After reading in the data, process the type
        if item[1] == 'c':
            # UTF-8 string
            temp = temp.decode('utf-8')
            if len(item) == 4:
                temp = [temp[x:x+4] for x in range(0,len(temp),4)]
            else:
                print("Unhandled string case: " + str(len(item)))
            box_info[item[2]]=temp
            dbg_print(item[2] + ": " + str(box_info[item[2]]))
        elif item[1] == 'u':
            # Unsigned value
            if size == 2:
                temp = struct.unpack('>H', temp)[0]
            elif size == 4:
                temp = struct.unpack('>L', temp)[0]
            else:
                print("Unhandled size: " + str(size))
            box_info[item[2]]=temp
            dbg_print(item[2] + ": " + str(box_info[item[2]]))
        elif item[1] == 'uuu':
            # Unsigned values
            if size == 6:
                box_info[item[2]] = struct.unpack('>HHH', temp)
            else:
                print("ERROR: unhandled size")
            dbg_print(item[2] + ": " + str(box_info[item[2]]))
        elif item[1] == 'uuuuuuuuu':
            box_info[item[2]] = struct.unpack('>LLLLLLLLL', temp)
            dbg_print(item[2] + ": " + str(box_info[item[2]]))
        elif item[1] == 'b':
            # Binary data
            box_info[item[2]] = box_info['size'] - read_offset
            advanceNBytes(file, box_info['size'] - read_offset)
        elif item[1] == 'i':
            # ISO-639-2/T language code
            # 5 bits each, an offset from 0x60
            offset0 = bytes([temp[1] & b'\x1f'[0]])
            offset0 = bytes([offset0[0] + b'\x60'[0]]).decode('unicode_escape')
            offset1 = bytes([(temp[1] >> 5) | (temp[0] << 1) & b'\x1f'[0]])
            offset1 = bytes([offset1[0] + b'\x60'[0]]).decode('unicode_escape')
            offset2 = bytes([(temp[0] >> 1) & b'\x1f'[0]])
            offset2 = bytes([offset2[0] + b'\x60'[0]]).decode('unicode_escape')
            box_info[item[2]] = offset2+offset1+offset0
            dbg_print(item[2] + ": " + str(box_info[item[2]]))
        elif item[1] == 'str':
            box_info[item[2]] = temp.decode('utf-8')
            if box_info[item[2]] != '\0':
                dbg_print(item[2] + ": " + str(box_info[item[2]]))
            else:
                dbg_print(item[2] + ": <NULL>")

# Function reads ISO/IEC 14496-12 MP4 file boxes and returns the
# object tree
# Box Format:   [Offset,B]  [Field]             [Size, b]
#               0           Size                32
#               4           Type                32
#              *8           (largesize)         64
#              *8           (usertype)          128
# Last two fields optional, largesize only included if Size == 1,
# usertype only included if Type == 'uuid'.  
def readMp4Box(file):
    dbg_print("Process box...")
    try:
        (box_size, box_type, read_offset) = readBoxHeader(file)
    except FileReadError as err:
        # Ignore this case for now, it signals EOF
        if err.bytes_read != 0:
            print("Failed to read the file, bytes read: " + str(err.bytes_read))
            print("instead of: " + str(err.bytes_requested))
        return (err.bytes_read, {})

    box_info = {'size': box_size,
                'type': box_type }

    try:
        # Process each type
        if box_type in supported_boxes:
            processBox(file, read_offset, box_info)
        else:
            print("Not handling: " + box_type)
            advanceNBytes(file, box_size - read_offset)
    except FormatError as e:
        print("Formatting error in box type: ", e.box_type)
    return (box_size, box_info)

# Function reads an MP4 file and parses all of the box types it
# recognizes
def readMp4File(filename):
    with open(filename, "rb") as f:
        # readMp4Box returns the number of bytes read and box info,
        # EOF when it reads 0 (and box info)
        while readMp4Box(f)[0] > 0:
            pass            

# Function reads an MP4 file and returns a specific field from the box type specified
def findMp4Field(filename, box_field):
    dbg_print("Search for: " + box_field)
    if checkField(box_field):
        with open(filename, "rb") as f:
            # readMp4Box returns the number of bytes read, EOF when it
            # reads 0 (and box info)
            metadata = [1,0]
            while metadata[0] > 0:
                metadata = readMp4Box(f)
                for key, value in metadata[1].items():
                    if box_field in key:
                        return metadata[1][box_field] # value of field
