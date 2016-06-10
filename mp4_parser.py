import struct

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
        raw_largesize = file.read(8)
        box_size = struct.unpack('>Q', raw_largesize)[0]
        read_offset = read_offset + 8

    # Check for uuid entry
    if box_type == 'uuid':
        raw_usertype = file.read(128)
        read_offset = read_offset + 128

    print("Box '"+box_type+"', Length: "+ str(box_size) + " bytes")

    return (box_size, box_type, read_offset)

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
    raw_major_brand = file.read(4)
    major_brand = raw_major_brand.decode('utf-8')
    raw_minor_version = file.read(4)
    minor_version = struct.unpack('>I', raw_minor_version)[0]
    raw_compatible_brands = file.read(box_len-8)
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
# Box Format:   [Offset,B]  [Field]             [Size, b]
#               0           major_brand         32
#               4           minor_version       32
#               8           compatible_brands   32 * n
# Last field is an array of 4x UTF-8 values and will fill the
# remainder of the box
def processMOOV(file, box_len):
    file.read(box_len)

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
    file.read(box_len)

# ISO/IEC 14496-12, Section 8.3, Movie Header Box
# Box Type:     'mvhd'
# Container:    Movie Box ('moov')
# Mandatory:    Yes
# Quantity:     Exactly one
#
### Box Format:   [Offset,B]  [Field]             [Size, b]
###               0           major_brand         32
###               4           minor_version       32
###               8           compatible_brands   32 * n
# Last field is an array of 4x UTF-8 values and will fill the
# remainder of the box
def processMVHD(file, box_len):
    file.read(box_len)

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
        print("Failed to read the file, bytes read: " + str(err.bytes_read))
        print("instead of: " + str(err.bytes_requested))
        return

    try:
        # Process each type
        if box_type == 'ftyp':
            processFTYP(file, box_size-read_offset)
        elif box_type == 'moov':
            processMOOV(file, box_size-read_offset)
        else:
            # TODO: should skip over the file contents rather than
            # reading them into memory
            data = file.read(box_size - read_offset)
    except FormatError as e:
        print("Formatting error in box type: ", e.box_type)

def readFile(filename):
    with open(filename, "rb") as f:
##        first_bytes = f.read(4)
####        print(first_bytes)
##        box_len = binaryLen(first_bytes)
##        print("Length: "+str(box_len))
##        datastr = f.read(box_len-4)
##        box_name = datastr[0:4].decode('utf-8')
##        print(box_name)
##        box_len = binaryLen(f.read(4))
##        print("Length: "+str(box_len))
##        datastr = f.read(box_len-4)
##        box_name = datastr[0:4].decode('utf-8')
##        print(box_name)
        readMp4Box(f)
        readMp4Box(f)
        readMp4Box(f)
        readMp4Box(f)

dirpath = '/Users/elliots/Movies/dance_tutorials/spain_videos_miguel/'
filename = '9-3-2015.mp4'
readFile(dirpath + filename)
