import struct
import datetime

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

    print("Box '"+box_type+"', Length: "+ str(box_size) + " bytes")

    return (box_size, box_type, read_offset)

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

######################################################################
## Box Types
######################################################################

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
    print(file.name)
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
        
    print("Major brand: " + major_brand)
    print("Minor version: " + str(minor_version))
    print("Compat. brands: ", end="")
    for brand in compatible_brands:
        print(brand + ", ", end="")
    print()
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
        raw_version_info = readFromFile(file, 1)
    except FileReadError as err:
        raise err
    version_info = struct.unpack('>B', raw_version_info)[0]
    print(version_info)
    try:
        raw_flags = readFromFile(file, 3)
    except FileReadError as err:
        raise err
    flags = struct.unpack('>BBB', raw_flags)
    print(flags)
    if version_info == 0:
        try:
            raw_creation_time = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        creation_time = struct.unpack('>L', raw_creation_time)[0]
        print("Creation time: " + 
            datetime.datetime.fromtimestamp(
                creation_time
            ).strftime('%Y-%m-%d %H:%M:%S')
        )
        try:
            raw_modification_time = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        modification_time = struct.unpack('>l', raw_modification_time)[0]
        print("Modification time: " + 
            datetime.datetime.fromtimestamp(
                modification_time
            ).strftime('%Y-%m-%d %H:%M:%S')
        )
        try:
            raw_timescale = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        timescale = struct.unpack('>l', raw_timescale)[0]
        print("Timescale: " + str(timescale))
        try:
            raw_duration = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        duration = struct.unpack('>L', raw_duration)[0]
        print("Duration: " + str(duration))
    else:
        # TODO: implement 64-bit timestamps
        raise FormatError
    try:
        raw_rate = readFromFile(file, 4)
    except FileReadError as err:
        raise err
    rate = struct.unpack('>i', raw_rate)[0]
    print("Rate: " + str(rate))

    try:
        raw_volume = readFromFile(file, 2)
    except FileReadError as err:
        raise err
    volume = struct.unpack('>h', raw_volume)[0]
    print("Volume: " + str(volume))
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
    print("Next track ID: " + str(next_track_ID))

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
        raw_version_info = readFromFile(file, 1)
    except FileReadError as err:
        raise err
    version_info = struct.unpack('>B', raw_version_info)[0]
    print(version_info)
    try:
        raw_flags = readFromFile(file, 3)
    except FileReadError as err:
        raise err
    flags = struct.unpack('>BBB', raw_flags)
    print(flags)
    if version_info == 0:
        try:
            raw_creation_time = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        creation_time = struct.unpack('>l', raw_creation_time)[0]
        print("Creation time: " + 
            datetime.datetime.fromtimestamp(
                creation_time
            ).strftime('%Y-%m-%d %H:%M:%S')
        )
        try:
            raw_modification_time = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        modification_time = struct.unpack('>l', raw_modification_time)[0]
        print("Modification time: " + 
            datetime.datetime.fromtimestamp(
                modification_time
            ).strftime('%Y-%m-%d %H:%M:%S')
        )
        try:
            raw_track_ID = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        track_ID = struct.unpack('>l', raw_track_ID)[0]
        print("Track ID: " + str(track_ID))
        advanceNBytes(file, 4)
        try:
            raw_duration = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        duration = struct.unpack('>l', raw_duration)[0]
    else:
        # TODO: implement 64-bit timestamps
        raise FormatError
    advanceNBytes(file, 8)

    try:
        raw_layer = readFromFile(file, 2)
    except FileReadError as err:
        raise err
    layer = struct.unpack('>h', raw_layer)[0]
    print("Layer: " + str(layer))

    try:
        raw_alternate_group = readFromFile(file, 2)
    except FileReadError as err:
        raise err
    alternate_group = struct.unpack('>h', raw_alternate_group)[0]
    print("Alternate group: " + str(alternate_group))

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
    print('Width: ' + str(width))

    try:
        raw_height = readFromFile(file, 4)
    except FileReadError as err:
        raise err
    height = struct.unpack('>l', raw_height)[0]
    print('Height: ' + str(height))

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
        raw_version_info = readFromFile(file, 1)
    except FileReadError as err:
        raise err
    version_info = struct.unpack('>B', raw_version_info)[0]
    print(version_info)
    try:
        raw_flags = readFromFile(file, 3)
    except FileReadError as err:
        raise err
    flags = struct.unpack('>BBB', raw_flags)
    print(flags)
    if version_info == 0:
        try:
            raw_creation_time = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        creation_time = struct.unpack('>L', raw_creation_time)[0]
        print("Creation time: " + 
            datetime.datetime.fromtimestamp(
                creation_time
            ).strftime('%Y-%m-%d %H:%M:%S')
        )
        try:
            raw_modification_time = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        modification_time = struct.unpack('>l', raw_modification_time)[0]
        print("Modification time: " + 
            datetime.datetime.fromtimestamp(
                modification_time
            ).strftime('%Y-%m-%d %H:%M:%S')
        )
        try:
            raw_timescale = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        timescale = struct.unpack('>l', raw_timescale)[0]
        print("Timescale: " + str(timescale))
        try:
            raw_duration = readFromFile(file, 4)
        except FileReadError as err:
            raise err
        duration = struct.unpack('>L', raw_duration)[0]
        print("Duration: " + str(duration))
    else:
        # TODO: implement 64-bit timestamps
        raise FormatError
    # Read the ISO-639-2/T language code and the padding bit
    try:
        raw_language = readFromFile(file, 2)
    except FileReadError as err:
        raise err
    language = struct.unpack('>H', raw_language)[0]
    print("Language code: " + str(language))

    advanceNBytes(file, 2)

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
    print("Process box...")
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
        if box_type == 'ftyp':
            processFTYP(file, box_size-read_offset)
        elif box_type == 'moov':
            processMOOV(file, box_size-read_offset)
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
        
