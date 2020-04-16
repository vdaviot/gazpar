#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import datetime
import locale
from dateutil.relativedelta import relativedelta
import gazpar
import json

import argparse
import logging
import pprint

PFILE = "/.params"


# Sub to return format wanted by linky.py
def _dayToStr(date):
    return date.strftime("%d/%m/%Y")

# Open file with params for influxdb, enedis API and HC/HP time window
def _openParams(pfile):
    # Try to load .params then programs_dir/.params
    if os.path.isfile(os.getcwd() + pfile):
        p = os.getcwd() + pfile
    elif os.path.isfile(os.path.dirname(os.path.realpath(__file__)) + pfile):
        p = os.path.dirname(os.path.realpath(__file__)) + pfile
    else:
        if (os.getcwd() + pfile != os.path.dirname(os.path.realpath(__file__)) + pfile):
            logging.error('file %s or %s not exist', os.path.realpath(os.getcwd() + pfile) , os.path.dirname(os.path.realpath(__file__)) + pfile)
        else:
            logging.error('file %s not exist', os.getcwd() + pfile )
        sys.exit(1)
    try:
        f = open(p, 'r')
        try:
            array = json.load(f)
        except ValueError as e:
            logging.error('decoding JSON has failed', e)
            sys.exit(1)
    except IOError:
        logging.error('cannot open %s', p)
        sys.exit(1)
    else:
        f.close()
        return array


# Sub to get StartDate depending today - daysNumber
def _getStartDate(today, daysNumber):
    return _dayToStr(today - relativedelta(days=daysNumber))

# Get the midnight timestamp for startDate
def _getStartTS(daysNumber):
    date = (datetime.datetime.now().replace(hour=12,minute=0,second=0,microsecond=0) - relativedelta(days=daysNumber))
    return date.timestamp()

# Get the timestamp for calculating if we are in HP / HC
def _getDateTS(y,mo,d,h,m):
    date = (datetime.datetime(year=y,month=mo,day=d,hour=h,minute=m,second=0,microsecond=0))
    return date.timestamp()

# Let's start here !

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-d",  "--days",    type=int, help="Number of days from now to download", default=1)
    parser.add_argument("-l",  "--last",    action="store_true", help="Check from InfluxDb the number of missing days", default=False)
    parser.add_argument("-v",  "--verbose", action="store_true", help="More verbose", default=False)
    args = parser.parse_args()

    pp = pprint.PrettyPrinter(indent=4)
    logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)

    params = _openParams(PFILE)

    # Try to log in Enedis API
    try:
        logging.info("logging in GRDF URI %s...", gazpar.API_BASE_URI)
        token = gazpar.login(params['grdf']['username'], params['grdf']['password'])
        logging.info("logged in successfully!")
    except:
        logging.error("unable to login on %s : %s", gazpar.API_BASE_URI, exc)
        sys.exit(1)

    startDate = _getStartDate(datetime.date.today(), args.days)
    endDate = _dayToStr(datetime.date.today())
    firstTS =  _getStartTS(args.days)

    logging.info("will use %s as firstDate and %s as startDate", firstTS, startDate)

    # Try to get data from Enedis API
    resGrdf = gazpar.get_data_per_day(token, startDate, endDate)
    try:
        logging.info("get Data from GRDF from {0} to {1}".format(startDate, endDate))
        # Get result from Enedis by 30m
        resGrdf = gazpar.get_data_per_day(token, startDate, endDate)

        if (args.verbose):
            pp.pprint(resGrdf)

    except:
        logging.error("unable to get data from GRDF")
        sys.exit(1)

    # When we have all values let's start parse data and pushing it
    jsonInflux = []
    i = 0
    for d in resGrdf:
        # Use the formula to create timestamp, 1 ordre = 30min
        t = datetime.datetime.strptime(d['date'] + " 12:00", '%d-%m-%Y %H:%M')
        logging.info(("found value : {0:3} kWh / {1:7.2f} m3 at {2}").format(d['kwh'], d['mcube'], t.strftime('%Y-%m-%dT%H:%M:%SZ')))
        if t.timestamp() > firstTS:
            logging.info(("value added to jsonInflux as {0} > {1}").format(t.strftime('%Y-%m-%d %H:%M'), datetime.datetime.fromtimestamp(firstTS).strftime('%Y-%m-%d %H:%M')))
            jsonInflux.append({
                           "measurement": "conso_gaz",
                           "tags": {
                               "fetch_date" : endDate
                           },
                           "time": t.strftime('%Y-%m-%dT%H:%M:%SZ'),
                           "fields": {
                               "kwh": d['kwh'],
                               "mcube": d['mcube']
                           }
                         })
        else:
            logging.info(("value NOT added to jsonInflux as {0} > {1}").format(t.timestamp(), firstTS))
        i=+1
    pp.pprint(jsonInflux)
