from paho.mqtt.client import Client
import datetime
import json
import psycopg2
from config import Config

from app.models import Hourly, Logger, Raw

def on_connect(client, userdata, flags, rc):
    print('on_connect')
    client.subscribe([('bbws-bsolo', 0), ('bws-sul2', 0), ('uns-ft', 0), ('pusair-bdg', 0), ('cimancis', 0), ('bwss2', 0), ('bwss4', 0), ('bws-kal3', 0), ('bws-sul1', 0), ('bws-kal1', 0), ('bws-pb', 0), ('bwss5', 0), ('upbbsolo', 0), ('bwsnt1', 0), ('banjarmasin', 0), ('btsungai', 0), ('bws-kal4', 0), ('float1', 0), ('dpublpp', 0), ('pdamgresik', 0), ('wikahutama', 0), ('bbwssul3', 0), ('purinilam', 0), ('palangkaraya', 0), ('pusdajatim', 0), ('dpuprklaten', 0), ('bwskal5', 0), ('bbwscitanduy', 0)])


def on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode('utf-8'))
    try:
        sn = data.get('device').split('/')[1]
    except IndexError:
        print('SN tidak ditemukan')
        return
    conn = psycopg2.connect(Config.DATABASE_URL)

    with conn:
        with conn.cursor() as curs:
            curs.execute('''UPDATE logger SET latest=%s, num_data=num_data+1 WHERE sn=%s''', (datetime.datetime.now(), sn))

    print('SN', sn)

def process_message(msg: str):
    msg = json.loads(msg)
    try:
        logger = Logger.get(sn=msg.get('device').split('/')[1])
    except Logger.DoesNotExist:
        print(msg.get('device').split('/')[1])
        return
    # update latest
    sampling = datetime.datetime.fromtimestamp(msg.get('sampling'))
    logger.latest_sampling = sampling
    logger.latest_battery = msg.get('battery')
    try:
        logger.latest_up = datetime.datetime.fromtimestamp(msg.get('up_since'))
    except TypeError:
        pass
    logger.save()
    # upsert hourly
    hour = sampling.replace(minute=0)
    hourly, created = Hourly.get_or_create(
        sn=logger.sn, sampling=hour,
        defaults={'location_id': logger.location, 'num_data': 1, 'batt_a': msg.get('battery')})
    if not created:
        hourly.num_data += 1
        try:
            hourly.tick += msg.get('tick')
        except:
            pass
        try:
            hourly.distance = msg.get('distance')
        except:
            pass
    hourly.save()
    print(hourly.id)
    # on TMA, check 
          
def run_listener():
    client = Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect('mqtt.prinus.net', port=14983)
    client.loop_forever()


if __name__ == '__main__':
    #run_listener()
    from app import create_app
    app = create_app()
    for m in Raw.select().order_by(Raw.received.asc()):
        process_message(m.content.strip('"').replace('\'', '"'))
        