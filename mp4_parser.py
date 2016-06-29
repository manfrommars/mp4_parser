import struct
import datetime
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
    if end_offset - start_offset < num_bytes:
        raise FileReadError(file.name, num_bytes, actual_bytes)

# Read and process all children in num_bytes
def processChildren(file, num_bytes):
    child_size = 0
    while child_size < num_bytes:
        child_size = child_size + readMp4Box(file)

# Print function for debugging
def dbg_print(*objects, sep=' ', end='\n', file=sys.stdout, flush=False):
    global DEBUG
    if DEBUG is 1:
        print(*objects, sep=sep, end=end, file=file, flush=flush)

######################################################################
## Box Types
######################################################################

# Supported box types: Box, FullBox
supported_boxes = {
    'ftyp':['Box',
             (4, 'u', 'major_brand'),
             (4, 'u', 'minor_version'),
             ('E', 'u', 'compatible_brands')]
    }

box_types = ['Box', 'FullBox']

# For each defined box, read its format from the dictionary
def processBox(file, box_len, info_list):
    box_info = {}
    # First item is always "Box" or "FullBox"
    if info_list[0] not in box_types:
        raise FileReadError

    bytes_read = 0

    for item in info_list[1:]:
        # item tuple contents:
        # size (in bits)
        # signed/unsigned + array
        # name
        if item[0] is not 'E':
            try:
                temp = readFromFile(file, item[0])
            except FileReadError as err:
                raise err
            bytes_read = bytes_read + item[0]
        else:
            try:
                temp = readFromFile(file, box_len-bytes_read)
            except FileReadError as err:
                raise err
        
# ISO/IEC 14496-12, Section 4.3, File Type Box
# Box Type:     'ftyp'
# Container:    File
# Mandatory:    Yes
# Quantity:     Exactly one
#
# Box Format:   [Offset,B]  [Field]             [Size, b]
#               0           major_brand         32
#               4           minor_version       32
#               8           compatible_brands   32 * n
# Last field is an array of 4x UTF-8 values and will fill the
# remainder of the box
def processFTYP(file, box_len):
    dbg_print(file.name)
    if box_len % 4 != 0:
        raise FormatError('ftyp')
    try:
        raw_major_brand = readFromFile(file, 4)
    except FileReadError as err:
        raise err
    major_brand = raw_major_brand.decode('utf-8')
    try:
        raw_minor_version = readFromFile(file, 4)
    except FileReadError as err:
        raise err
    minor_version = struct.unpack('>I', raw_minor_version)[0]
    try:
        raw_compatible_brands = readFromFile(file, box_len-8)
    except FileReadError as err:
        raise err
    compatible_brands = raw_compatible_brands.decode('utf-8')

    # Split up compatible brands 
    compatible_brands = \
        [compatible_brands[x:x+4] for x in range(0,box_len-8,4)]
        
    dbg_print("Major brand: " + major_brand)
    dbg_print("Minor version: " + str(minor_version))
    dbg_print("Compat. brands: ", end="")
    for brand in compatible_brands:
        dbg_print(brand + ", ", end="")
    dbg_print()
    return # TODO: return a container with all of these in them

# ISO/IEC 14496-12, Section 8.1, Movie Box
# Box Type:     'moov'
# Container:    File
# Mandatory:    Yes
# Quantity:     Exactly one
#
# Contains other boxes
def processMOOV(file, box_len):
    processChildren(file, box_len)

# ISO/IEC 14496-12, Section 8.2, Media Data Box
# Box Type:     'mdat'
# Container:    File
# Mandatory:    No
# Quantity:     Any number
#
# Box Format:   [Offset,B]  [Field]             [Size, b]
#               0           data                8 * n
# Last field is an array of the media bytes
def processMDAT(file, box_len):
    advanceNBytes(file, box_len)

# ISO/IEC 14496-12, Section 8.3, Movie Header Box
# Box Type:     'mvhd'
# Container:    Movie Box ('moov')
# Mandatory:    Yes
# Quantity:     Exactly one
#
# Box Format:   [Offset,B]  [Field]             [Size, b]
#               0           version             8
#               1           flags               24
######################### For version == 0 ###########################
#               4           creation_time       32
#               8           modification_time   32
#               12          timescale           32
#               16          duration            32
#               20          rate                32
#               24          volume              16
#               26          reserved            16
#               28          reserved            32*2
#               36          matrix              32*9
#               72          pre_defined         32*6
#               96          next_track_ID       32
#
# Last field is an array of 4x UTF-8 values and will fill the
# remainder of the box
def processMVHD(file, box_len):
    try:
        (version_info, flags) = readFullBoxHeader(file)
    except FileReadError as err:
        raise err
    if version_info == 0:
        try:
            raw_creation_time = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        creation_time = struct.unpack('>l', raw_creation_time)[0]
        dbg_print("Creation time: " + 
            datetime.datetime.fromtimestamp(
                creation_time
            ).strftime('%Y-%m-%d %H:%M:%S')
        )
        try:
            raw_modification_time = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        modification_time = struct.unpack('>l', raw_modification_time)[0]
        dbg_print("Modification time: " + 
            datetime.datetime.fromtimestamp(
                modification_time
            ).strftime('%Y-%m-%d %H:%M:%S')
        )
        try:
            raw_timescale = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        timescale = struct.unpack('>l', raw_timescale)[0]
        dbg_print("Timescale: " + str(timescale))
        try:
            raw_duration = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        duration = struct.unpack('>L', raw_duration)[0]
        dbg_print("Duration: " + str(duration))
    else:
        # TODO: implement 64-bit timestamps
        raise FormatError
    try:
        raw_rate = readFromFile(file, 4)
    except FileReadError as err:
        raise err
    rate = struct.unpack('>i', raw_rate)[0]
    dbg_print("Rate: " + str(rate))

    try:
        raw_volume = readFromFile(file, 2)
    except FileReadError as err:
        raise err
    volume = struct.unpack('>h', raw_volume)[0]
    dbg_print("Volume: " + str(volume))
    # Skip the next 10 bytes, they should all be 0
    advanceNBytes(file, 10)
    # Read matrix
    try:
        raw_matrix = readFromFile(file, 36)
    except FileReadError as err:
        raise err
    matrix = struct.unpack('>IIIIIIIII', raw_matrix)
    # Skip the next 24 bytes, they should all be 0
    advanceNBytes(file, 24)
    try:
        raw_next_track_ID = readFromFile(file, 4)
    except FileReadError as err:
        raise err
    next_track_ID = struct.unpack('>I', raw_next_track_ID)[0]
    dbg_print("Next track ID: " + str(next_track_ID))

# ISO/IEC 14496-12, Section 8.4, Track Box
# Box Type:     'trak'
# Container:    Movie Box ('moov')
# Mandatory:    Yes
# Quantity:     One or more
#
# Contains other boxes
def processTRAK(file, box_len):
    processChildren(file, box_len)

# ISO/IEC 14496-12, Section 8.5, Track Header Box
# Box Type:     'tkhd'
# Container:    Track Box ('trak')
# Mandatory:    Yes
# Quantity:     Exactly one
#
# Box Format:   [Offset,B]  [Field]             [Size, b]
#               0           version             8
#               1           flags               24
######################### For version == 0 ###########################
#               4           creation_time       32
#               8           modification_time   32
#               12          track_ID            32
#               16          reserved            32
#               20          duration            32
#               24          reserved            64
#               32          layer               16
#               34          alternate_group     16
#               36          volume              16
#               38          reserved            16
#               40          matrix              32*9
#               76          width               32
#               80          height              32
def processTKHD(file, box_len):
    try:
        (version_info, flags) = readFullBoxHeader(file)
    except FileReadError as err:
        raise err
    if version_info == 0:
        try:
            raw_creation_time = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        creation_time = struct.unpack('>l', raw_creation_time)[0]
        dbg_print("Creation time: " + 
            datetime.datetime.fromtimestamp(
                creation_time
            ).strftime('%Y-%m-%d %H:%M:%S')
        )
        try:
            raw_modification_time = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        modification_time = struct.unpack('>l', raw_modification_time)[0]
        dbg_print("Modification time: " + 
            datetime.datetime.fromtimestamp(
                modification_time
            ).strftime('%Y-%m-%d %H:%M:%S')
        )
        try:
            raw_track_ID = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        track_ID = struct.unpack('>l', raw_track_ID)[0]
        dbg_print("Track ID: " + str(track_ID))
        advanceNBytes(file, 4)
        try:
            raw_duration = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        duration = struct.unpack('>L', raw_duration)[0]
    else:
        # TODO: implement 64-bit timestamps
        raise FormatError
    advanceNBytes(file, 8)

    try:
        raw_layer = readFromFile(file, 2)
    except FileReadError as err:
        raise err
    layer = struct.unpack('>h', raw_layer)[0]
    dbg_print("Layer: " + str(layer))

    try:
        raw_alternate_group = readFromFile(file, 2)
    except FileReadError as err:
        raise err
    alternate_group = struct.unpack('>h', raw_alternate_group)[0]
    dbg_print("Alternate group: " + str(alternate_group))

    try:
        raw_volume = readFromFile(file, 2)
    except FileReadError as err:
        raise err
    volume = struct.unpack('>h', raw_volume)
    advanceNBytes(file, 2)
    # Read matrix
    try:
        raw_matrix = readFromFile(file, 36)
    except FileReadError as err:
        raise err
    matrix = struct.unpack('>IIIIIIIII', raw_matrix)

    try:
        raw_width = readFromFile(file, 4)
    except FileReadError as err:
        raise err
    width = struct.unpack('>l', raw_width)[0]
    dbg_print('Width: ' + str(width))

    try:
        raw_height = readFromFile(file, 4)
    except FileReadError as err:
        raise err
    height = struct.unpack('>l', raw_height)[0]
    dbg_print('Height: ' + str(height))

# ISO/IEC 14496-12, Section 8.7, Media Box
# Box Type:     'mdia'
# Container:    Track Box ('trak')
# Mandatory:    Yes
# Quantity:     Exactly one
#
# Contains other boxes
def processMDIA(file, box_len):
    processChildren(file, box_len)

# ISO/IEC 14496-12, Section 8.8, Media Header Box
# Box Type:     'mdhd'
# Container:    Media Box ('mdia')
# Mandatory:    Yes
# Quantity:     Exactly one
#
# Box Format:   [Offset,B]  [Field]             [Size, b]
#               0           version             8
#               1           flags               24
######################### For version == 0 ###########################
#               4           creation_time       32
#               8           modification_time   32
#               12          timescale           32
#               16          duration            32
def processMDHD(file, box_len):
    try:
        (version_info, flags) = readFullBoxHeader(file)
    except FileReadError as err:
        raise err
    if version_info == 0:
        try:
            raw_creation_time = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        creation_time = struct.unpack('>l', raw_creation_time)[0]
        dbg_print("Creation time: " + 
            datetime.datetime.fromtimestamp(
                creation_time
            ).strftime('%Y-%m-%d %H:%M:%S')
        )
        try:
            raw_modification_time = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        modification_time = struct.unpack('>l', raw_modification_time)[0]
        dbg_print("Modification time: " + 
            datetime.datetime.fromtimestamp(
                modification_time
            ).strftime('%Y-%m-%d %H:%M:%S')
        )
        try:
            raw_timescale = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        timescale = struct.unpack('>l', raw_timescale)[0]
        dbg_print("Timescale: " + str(timescale))
        try:
            raw_duration = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        duration = struct.unpack('>L', raw_duration)[0]
        dbg_print("Duration: " + str(duration))
    else:
        # TODO: implement 64-bit timestamps
        raise FormatError
    # Read the ISO-639-2/T language code and the padding bit
    try:
        raw_language = readFromFile(file, 2)
    except FileReadError as err:
        raise err
    language = struct.unpack('>H', raw_language)[0]
    dbg_print("Language code: " + str(language))

    # Skip bytes defined to 0
    advanceNBytes(file, 2)

# ISO/IEC 14496-12, Section 8.9, Handler Reference Box
# Box Type:     'hdlr'
# Container:    Media Box ('mdia') or Meta Box ('meta')
# Mandatory:    Yes
# Quantity:     Exactly one
#
# Box Format:   [Offset,B]  [Field]             [Size, b]
#               0           version             8
#               1           flags               24
#               4           pre_defined         32
#               8           handler_type        32
#               12          reserved            32*3
#               24          name                8*n
# Last field contains a string which goes to the end of the file
def processHDLR(file, box_len):
    try:
        (version_info, flags) = readFullBoxHeader(file)
    except FileReadError as err:
        raise err
    # Only version info == 0 is defined
    if version_info is not 0:
        raise FormatError

    # Skip defined 0s
    advanceNBytes(file, 4)

    try:
        raw_handler_type = readFromFile(file, 4)
    except FileReadError as err:
        raise err
    handler_type = raw_handler_type.decode('utf-8')
    dbg_print("Handler type: " + handler_type)

    # Skip defined 0s
    advanceNBytes(file, 12)

    # Read the remainder of the file as a UTF-8
    try:
        raw_name = readFromFile(file, box_len - 24)
    except FileReadError as err:
        raise err

    name = raw_name.decode('utf-8')
    dbg_print("Name: ", end="")
    if name is '\0':
        dbg_print("(None)")
    else:
        dbg_print(name)

# ISO/IEC 14496-12, Section 8.10, Media Information Box
# Box Type:     'minf'
# Container:    Media Box ('mdia')
# Mandatory:    Yes
# Quantity:     Exactly one
#
# Contains other boxes
def processMINF(file, box_len):
    processChildren(file, box_len)

# ISO/IEC 14496-12, Section 8.11.2, Video Media Header Box
# Box Type:     'vmhd'
# Container:    Media Information Box ('minf')
# Mandatory:    Yes
# Quantity:     Exactly one specific media header shall be present
#
# Box Format:   [Offset,B]  [Field]             [Size, b]
#               0           version             8
#               1           flags               24
#               4           graphicsmode        16
#               6           opcolor             16*3
def processVMHD(file, box_len):
    readFullBoxHeader(file)
    try:
        raw_graphicsmode = readFromFile(file, 2)
    except FileReadError as err:
        raise err
    graphicsmode = struct.unpack('>H', raw_graphicsmode)[0]
    dbg_print(graphicsmode)

    try:
        raw_opcolor = readFromFile(file, 6)
    except FileReadError as err:
        raise err
    opcolor = struct.unpack('>HHH', raw_opcolor)
    dbg_print(opcolor)

# ISO/IEC 14496-12, Section 8.11.3, Sound Media Header Box
# Box Type:     'smhd'
# Container:    Media Information Box ('minf')
# Mandatory:    Yes
# Quantity:     Exactly one specific media header shall be present
#
# Box Format:   [Offset,B]  [Field]             [Size, b]
#               0           version             8
#               1           flags               24
#               4           balance             16
#               6           reserved            16
def processSMHD(file, box_len):
    try:
        (version_info, flags) = readFullBoxHeader(file)
    except FileReadError as err:
        raise err

    try:
        raw_balance = readFromFile(file, 2)
    except FileReadError as err:
        raise err
    balance = struct.unpack('>H', raw_balance)[0]
    dbg_print(balance)

    advanceNBytes(file, 2)

# ISO/IEC 14496-12, Section 8.12, Data Information Box
# Box Type:     'dinf'
# Container:    Media Information Box ('mdia') OR
#               Meta Box ('meta')
# Mandatory:    Yes (within 'minf'), No (within 'meta')
# Quantity:     Exactly one
#
# Contains other boxes
def processDINF(file, box_len):
    processChildren(file, box_len)

# ISO/IEC 14496-12, Section 8.14, Sample Table Box
# Box Type:     'stbl'
# Container:    Media Information Box ('minf')
# Mandatory:    Yes
# Quantity:     Exactly one
#
# Contains other boxes
def processSTBL(file, box_len):
    processChildren(file, box_len)

# ISO/IEC 14496-12, Section 8.13, Data Reference Box
# Box Type:     'dref'
# Container:    Data Information Box ('dinf')
# Mandatory:    Yes
# Quantity:     Exactly one 
#
# Box Format:   [Offset,B]  [Field]             [Size, b]
#               0           version             8
#               1           flags               24
#               4           entry_count         32
#               8           DataEntryBox        n*entry_count
def processDREF(file, box_len):
    try:
        (version_info, flags) = readFullBoxHeader(file)
    except FileReadError as err:
        raise err

    try:
        raw_entry_count = readFromFile(file, 4)
    except FileReadError as err:
        raise err
    entry_count = struct.unpack('>L', raw_entry_count)[0]

    for i in range(0, entry_count):
        processChildren(file, box_len-8)

# ISO/IEC 14496-12, Section 8.13, Data Reference Box
# Box Type:     'url'
# Container:    Data Information Box ('dinf')
# Mandatory:    Yes
# Quantity:     Exactly one 
#
# Box Format:   [Offset,B]  [Field]             [Size, b]
#               0           version             8
#               1           flags               24
#               4           location            n
def processURL(file, box_len):
    try:
        (version_info, flags) = readFullBoxHeader(file)
    except FileReadError as err:
        raise err

    # Read the remainder of the box as a UTF-8
    try:
        raw_url = readFromFile(file, box_len - 4)
    except FileReadError as err:
        raise err

    url = raw_url.decode('utf-8')
    dbg_print("URL: ", end="")
    if url is '\0':
        dbg_print("(None)")
    else:
        dbg_print(url)


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
        return err.bytes_read

    try:
        # Process each type
        if box_type in supported_boxes:
            processBox(file, box_size-read_offset, supported_boxes[box_type])
        elif box_type == 'ftyp':
            processFTYP(file, box_size-read_offset)
        elif box_type == 'moov':
            processMOOV(file, box_size-read_offset)
        elif box_type == 'mdat':
            processMDAT(file, box_size-read_offset)
        elif box_type == 'mvhd':
            processMVHD(file, box_size-read_offset)
        elif box_type == 'trak':
            processTRAK(file, box_size-read_offset)
        elif box_type == 'tkhd':
            processTKHD(file, box_size-read_offset)
        elif box_type == 'mdia':
            processMDIA(file, box_size-read_offset)
        elif box_type == 'mdhd':
            processMDHD(file, box_size-read_offset)
        elif box_type == 'hdlr':
            processHDLR(file, box_size-read_offset)
        elif box_type == 'minf':
            processMINF(file, box_size-read_offset)
        elif box_type == 'vmhd':
            processVMHD(file, box_size-read_offset)
        elif box_type == 'smhd':
            processSMHD(file, box_size-read_offset)
        elif box_type == 'dinf':
            processDINF(file, box_size-read_offset)
        elif box_type == 'stbl':
            processSTBL(file, box_size-read_offset)
        elif box_type == 'dref':
            processDREF(file, box_size-read_offset)
        elif box_type == 'url ':
            processURL(file, box_size-read_offset)
        else:
            # TODO: add handling for more box types
            print("Not handling: " + box_type)
            advanceNBytes(file, box_size - read_offset)
    except FormatError as e:
        print("Formatting error in box type: ", e.box_type)

    return box_size

# Function reads an MP4 file and parses all of the box types it
# recognizes
def readMp4File(filename):
    with open(filename, "rb") as f:
        # readMp4Box returns the number of bytes read, EOF when it
        # reads 0
        while readMp4Box(f) > 0:
            pass
        
