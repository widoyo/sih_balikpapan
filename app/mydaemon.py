import logging
import sys

import daemonocle
import paho.mqtt.client as mqtt
from flask import json

from app import create_app
from app.models import Logger, Raw


def on_connect(client, userdata, flags, rc):
    client.subscribe([('bbws-bsolo', 0), ('bws-sul2', 0), ('uns-ft', 0), ('pusair-bdg', 0), ('cimancis', 0), ('bwss2', 0), ('bwss4', 0), ('bws-kal3', 0), ('bws-sul1', 0), ('bws-kal1', 0), ('bws-pb', 0), ('bwss5', 0), ('upbbsolo', 0), ('bwsnt1', 0), ('banjarmasin', 0), ('btsungai', 0), ('bws-kal4', 0), ('float1', 0), ('dpublpp', 0), ('pdamgresik', 0), ('wikahutama', 0), ('bbwssul3', 0), ('purinilam', 0), ('palangkaraya', 0), ('pusdajatim', 0), ('dpuprklaten', 0), ('bwskal5', 0), ('bbwscitanduy', 0), ('bbwspomje', 0), ('inpola', 0)])
    
def on_message(client, userdata, msg):
    '''
    '''
    data = json.loads(msg.payload)
    Raw._to_daily(data)
    
    
def cb_shutdown(message, code):
    logging.info('Daemon is stopping')
    logging.debug(message)

def main():
    logging.info('Daemon starting')
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("mqtt.prinus.net", 14983, 60)

    client.loop_forever()
    
def run_daemon():
    main()
    
if __name__ == '__main__':
    app = create_app()
    logging.basicConfig(filename='example.log', encoding='utf-8', level=logging.DEBUG)
    run_daemon()