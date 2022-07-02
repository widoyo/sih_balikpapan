#!/home/widoyo/app/app.prinus.net/venv/bin/python3

import os, datetime, time
import sys
from dotenv import dotenv_values
import psycopg2 as pg2
from pathlib import Path
from app.db import SessionLocal
import pandas as pd
from app.models import Tenant, Device
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


config = dotenv_values()


def set_timezone(tz):
    '''@tz string'''
    os.environ['TZ'] = tz
    time.tzset()

def send_email():
    msg = MIMEMultipart()

    gmail_user = 'you@gmail.com'
    gmail_password = 'P@ssword!'

    sent_from = gmail_user
    to = ['me@gmail.com', 'bill@gmail.com']
    subject = 'OMG Super Important Message'
    body = 'Hey, what\'s up?\n\n- You'

    email_text = """\
    From: %s
    To: %s
    Subject: %s

    %s
    """ % (sent_from, ", ".join(to), subject, body)

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(gmail_user, gmail_password)
        server.sendmail(sent_from, to, email_text)
        server.close()

        print('Email sent!')
    except:
        print('Something went wrong...')

def send_data_to_tenant(tenant_id):
    '''
    foreach tenant as t:
        if not t.email:
            continue
        settimezone(t.tz)
        if localtime.hour != 7:
            continue
        bulan = datetime.date.today()
        foreach logger as l:

    '''
    db = SessionLocal()
    t = db.query(Tenant).filter(Tenant.id==tenant_id).one()
    set_timezone(t.tz)
    bulan = datetime.date.today().strftime('%m/%Y')
    for d in t.devices:
        r = get_data(d.sn, bulan)
        to_5(r['result'], d.sn, r['awal'], r['akhir'])

def get_data(sn, bulan):
    if '-' not in sn:
        raise ValueError('SN tidak ditemukan') 
    if '/' in bulan:
        bl = datetime.datetime.strptime(bulan, '%m/%Y')
    elif '-' in bulan:
        bl = datetime.datetime.strptime(bulan, '%m-%Y')
    else:
        raise ValueError('"bulan" harus dalam format bl/tahu atau bl-tahu')
    now = datetime.datetime.now()
    if bl > now:
        raise ValueError('Waktu tidak bisa yang akan datang')
    bl = bl.replace(hour=7)
    if int(bl.strftime('%Y%m')) < int(now.strftime('%Y%m')):
        akhir = (bl.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
        akhir = akhir.replace(hour=7)
    else:
        akhir = now
    db = SessionLocal()
    sql = "SELECT content from raw \
        WHERE content->>'device' LIKE '{sn}' AND \
            (content->>'sampling')::BIGINT BETWEEN {awal} AND \
                {akhir} ORDER BY content->>'sampling'".format(sn='%'+sn+'/%', 
                awal=bl.timestamp(), akhir=akhir.timestamp())
    rst = db.execute(sql)
    #to_5([r[0] for r in rst.fetchall()], sn, bl, akhir)
    return {'result': [r[0] for r in rst.fetchall()], 'sn': sn, 'awal': bl, 'akhir': akhir} 


def to_5(data, sn, awal, akhir):
    '''output csv data 5 menitan
    @data: json dari 'raw.content' '''
    if not len(data):
        return
    db = SessionLocal()
    logger = db.query(Device).filter(Device.sn==sn).one()
    df = pd.DataFrame(data)
    dates = pd.date_range(awal, akhir, freq='5T')
    dft = pd.DataFrame(index=dates)
    df = df.drop(columns='device')
    if hasattr(df, 'tick'):
        if hasattr(df, 'tipping_factor'):
            df['rain'] = df['tick'] * df['tipping_factor']
        else:
            df['rain'] = df['tick'] * logger.tipp_fac
    if hasattr(df, 'distance'):
        if hasattr(df, 'sensor_height') and hasattr(df, 'sensor_resolution'):
            df['wlevel'] = (df['sensor_height'] - df['distance']) * df['sensor_resolution']
        else:
            df['wlevel'] = logger.ting_son - df['distance'] * logger.son_res
    df['sampling'] = pd.to_datetime(df['sampling'], unit='s')
    df['up_since'] = pd.to_datetime(df['up_since'], unit='s')
    df['time_set_at'] = pd.to_datetime(df['time_set_at'], unit='s')
    df = df.set_index('sampling')
    df = dft.join(df)
    df.to_csv('p_{sn}_{blth}.csv'.format(sn=sn, blth=awal.strftime('%b%Y')), index_label='sampling')
    to_jam(df, sn, awal, akhir)

    
def to_jam(dataframe, sn, awal, akhir):
    '''output csv data 60 menit (1 jam)'''
    if dataframe.empty:
        return
    db = SessionLocal()
    logger = db.query(Device).filter(Device.sn==sn).one()
    grouper = pd.Grouper(freq='1h')
    if hasattr(dataframe, 'rain'):
        grouped = dataframe.groupby(grouper)['rain']
        df = pd.DataFrame(grouped).sum()
    elif hasattr(dataframe, 'wlevel'):
        dmin = dataframe.groupby(grouper)['wlevel'].min()
        df = pd.DataFrame(dmin, 'min')
        dmax = dataframe.groupby(grouper)['wlevel'].max()
        dmean = dataframe.groupby(grouper)['wlevel'].mean()
        dcount = dataframe.groupby([dataframe.index.date, dataframe.index.hour]).distance.apply(lambda x:(12-x.isnull().sum())/12.0)*100

        # df.groupby([df.index.date, df.index.hour].distance.apply(lambda x: (12 - x.isnull().sum())/12.0 * 100))
        df = df.join(dmin, 'min')
        df = df.join(dmax, 'max')
        df = df.groupby([df.index.date, df.index.hour])
        df = df.join(dmean, 'rerata')
        df = df.join(dcount, 'banyak_data')
        
    df.to_csv('p_{sn}_{blth}_jam.csv'.format(sn=sn, blth=awal.strftime('%b%Y')))
    return df

def to_24(data):
    '''output csv data 24 jam '''
    pass

def create_data_file(sn, awal, akhir):
    outpath = '.'
    bl = datetime.datetime.fromtimestamp(awal)
    fname = 'primabot_'+sn+'_'+bl.strftime('%Y_%b')+'.csv'
    fdata = Path(outpath +'/'+fname)
    file_exists = fdata.is_file()
    
    try:
        conn = pg2.connect("dbname='{DB_DATABASE}' user='{DB_USERNAME}' host='localhost' password='{DB_PASSWORD}' port={DB_PORT}".format(**config))
    except:
        print("I am unable to connect to the database")
        exit()

    cur = conn.cursor()

    sql = "SELECT content from raw WHERE content->>'device' LIKE '{sn}' AND (content->>'sampling')::BIGINT BETWEEN {awal} AND {akhir} ORDER BY content->>'sampling'".format(sn='%'+sn+'/%', awal=awal, akhir=akhir)

    cur.execute(sql)
    coltma = 'sampling,up_since,distance,sensor_height,battery,rssi'
    colch = 'sampling,up_since,tick,tipping_factor,battery,rssi'
    colkli = 'sampling,up_since,tick,wind_speed,tipping_factor,battery,rssi'
    print('row count: ', cur.rowcount)
    r = cur.fetchone()
    r = r[0]
    out = []
    if 'distance' in r.keys():
        cols = coltma.split(',')
    elif 'wind_speed' in r.keys():
        cols = colkli.split(',')
    else:
        cols = colch.split(',')
    if not file_exists:
        out.append(','.join(cols) + '\n')
    row = []
    for col in cols:
        if col in ('sampling', 'up_since'):
            t = datetime.datetime.fromtimestamp(r[col])
            row.append(t.isoformat())
            continue
        row.append(str(r[col]))
    out.append(','.join(row) + "\n")
    for r in cur:
        del r[0]['device']
        row = []
        for col in cols:
            if col in ('sampling', 'up_since'):
                t = datetime.datetime.fromtimestamp(r[0][col])
                row.append(t.isoformat())
                continue
            row.append(str(r[0][col]))
        out.append(','.join(row) + '\n')
        #print(r[0].values())
    
    with open(fdata, 'w') as f:
        for o in out:
            f.write(o)
    cur.close()
    conn.close()
    return fname

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('\nUsage:\n'+' '+sys.argv[0]+' <sn> <mulai> <akhir>\n\
                mulai: timestamp\n\
                akhir: timestamp\n')
        print(config)
        exit()
    print('Hello')
