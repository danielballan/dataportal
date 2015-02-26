from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import six
import uuid
import logging
import time as ttime
import logging
from collections import Iterable
from datetime import datetime
import numpy as np
import pandas as pd
from .. import sources
from ..sources import channelarchiver as ca
from ..sources import switch
from ..broker import DataBroker as db
from ..muxer import DataMuxer
from ..examples.sample_data import temperature_ramp

from nose.tools import make_decorator
from nose.tools import (assert_equal, assert_raises, assert_true,
                        assert_false, assert_less)


from metadatastore.odm_templates import (BeamlineConfig, EventDescriptor,
                                         Event, RunStart, RunStop)
from metadatastore.api import insert_run_start, insert_beamline_config
from filestore.api import db_connect, db_disconnect
logger = logging.getLogger(__name__)

db_name = str(uuid.uuid4())
conn = None
blc = None
insert_again = None


def setup():
    global conn
    global blc
    global insert_again
    db_disconnect()
    conn = db_connect(db_name, 'localhost', 27017)
    blc = insert_beamline_config({}, ttime.time())

    switch(channelarchiver=False)
    start, end = '2015-01-01 00:00:00', '2015-01-01 00:01:00'
    simulated_ca_data = generate_ca_data(['ch1', 'ch2'], start, end)
    ca.insert_data(simulated_ca_data)
    
    for i in range(5):
        insert_run_start(time=float(i), scan_id=i + 1,
                         owner='docbrown', beamline_id='example',
                         beamline_config=insert_beamline_config({}, time=0.))
    for i in range(5):
        rs = insert_run_start(time=float(i), scan_id=i + 1,
                              owner='nedbrainard', beamline_id='example',
                              beamline_config=insert_beamline_config(
                                  {}, time=0.))
        temperature_ramp.run(rs)
        # This is a hook for inserting more data into the last run.
        insert_again = lambda: temperature_ramp.run(rs)


def teardown():
    db_disconnect()
    if conn:
        conn.drop_database(db_name)



def test_basic_usage():
    header = db[-1]
    header = db.find_headers(owner='nedbrainard')
    header = db.find_headers(owner='this owner does not exist')
    events = db.fetch_events(header)

def test_update():
    header = db[-1]
    events = db.fetch_events(header)
    dm = DataMuxer.from_events(events)
    insert_again()
    # First just check that that insert worked.
    events_after = db.fetch_events(header)
    assert_less(len(events), len(events_after))

    # And now perform the test we are interested in.
    len_before = len(dm['Tsam'])
    db.update(dm)
    len_after = len(dm['Tsam'])
    assert_less(len_before, len_after)


def test_indexing():
    header = db[-1]
    is_list = isinstance(header, Iterable)
    assert_false(is_list)
    scan_id = header.scan_id
    assert_equal(scan_id, 5)

    header = db[-2]
    is_list = isinstance(header, Iterable)
    assert_false(is_list)
    scan_id = header.scan_id
    assert_equal(scan_id, 4)

    f = lambda: db[-100000]
    assert_raises(IndexError, f)

    headers = db[-5:]
    is_list = isinstance(headers, Iterable)
    assert_true(is_list)
    num = len(headers)
    assert_equal(num, 5)

    header = db[-6:]
    assert_true(is_list)
    num = len(headers)
    assert_equal(num, 5)

    headers = db[-1:]
    assert_true(is_list)
    num = len(headers)
    assert_equal(num, 1)
    header, = headers
    scan_id = header.scan_id
    assert_equal(scan_id, 5)

    headers = db[-2:-1]
    assert_true(is_list)
    num = len(headers)
    print(headers)
    assert_equal(num, 1)
    header, = headers
    scan_id = header.scan_id
    assert_equal(scan_id, 4)

    headers = db[-3:-1]
    scan_ids = [h.scan_id for h in headers]
    assert_equal(scan_ids, [4, 3])


def test_lookup():
    header = db[3]
    scan_id = header.scan_id
    owner = header.owner
    assert_equal(scan_id, 3)
    # This should be the most *recent* Scan 3. There is ambiguity.
    assert_equal(owner, 'nedbrainard')


def generate_ca_data(channels, start_time, end_time):
    timestamps = pd.date_range(start_time, end_time, freq='T').to_series()
    timestamps = list(timestamps.dt.to_pydatetime())  # list of datetime objects
    values = list(np.arange(len(timestamps)))
    return {channel: (timestamps, values) for channel in channels}
