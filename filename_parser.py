import datetime

# Translate filenames encoded with date and timestamps into datetime objects

def datetimeFromFilename(filename):
    date = []
    time = []
    if filename.startswith('VID-'):
        # Type 1: VID-YYYYMMDD-WAXXXX
        # Creation time set to 00:00:00
        dates = filename.split('-')[1]
        date = [int(dates[:4]), int(dates[4:6]), int(dates[6:])]
    elif filename.startswith('VID_'):
        # Type 2: VID_YYYYMMDD_HHMMSS
        dates = filename.split('_')
        times = dates[2].strip('.mp4')
        print(times)
        dates = dates[1]
        date = [int(dates[:4]), int(dates[4:6]), int(dates[6:])]
        time = [int(times[:2]), int(times[2:4]), int(times[4:])]
    if not time:
        time = [0, 0, 0]
    if not date:
        date = [1900, 1, 1]
    print(str(date))
    print(str(time))
    try:
        dt = datetime.datetime(date[0],
                               date[1],
                               date[2],
                               time[0],
                               time[1],
                               time[2],
                               0)
    except ValueError as err:
        raise err
    print(str(dt))

    return dt
